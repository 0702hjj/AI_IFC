"""design_builder.py — design JSON → **规范化几何数据**(features.json 类似物, 供下游构建脚本引用).

定位(框定器, 非生成器):
  LLM 产出 design JSON(参数化几何意图: path轴网 / arc弧形 / along沿轴, 不碰坐标)
    → 本脚本**规范化 + 展开**成纯几何数据(axis折线/轮廓/位置) → 输出 features.json
  具体建设(几何→IFC)由**下游构建脚本**(每建筑单独)走传统 Pipeline(骨架→元素→开洞→数据→导出),
  用 flows 单步操作(skeleton/wall/slab_profile/opening_door/type_material/pset_qto)组装。

  类比 reverse: design JSON ≈ 原始意图, 本脚本输出 ≈ features.json, 下游构建脚本 ≈ rebuild_mall.py。

用法:
  python design_builder.py design.json -o features.json
"""
import json, math, sys, argparse
from pathlib import Path

MM = 0.001


class SchemaError(Exception):
    """规范化失败 → 抛给上层做 Self-Refine(LLM 重出 design JSON)"""


def _snap(v, mod):
    return round(round(v / mod) * mod, 6)


def _snap_pts(pts, mod):
    return [(_snap(p[0], mod), _snap(p[1], mod)) for p in pts]


def normalize(design):
    """design JSON → features(规范化几何数据). 规范化: 模数吸附 + footprint 闭合 + 轴网对齐;
    展开: path轴网→axis折线, arc弧形→axis多段逼近, openings 保留 along(参数化定位)."""
    meta = design.get("meta", {})
    mod = float(meta.get("modulus", 0.1))

    # ── frame 规范化 ──
    frame = design.get("frame", {})
    fp = _snap_pts(frame.get("footprint", []), mod)
    if len(fp) > 1 and fp[0] == fp[-1]:
        fp = fp[:-1]
    if len(fp) < 3:
        raise SchemaError("footprint 需 ≥3 点(闭合多边形)")
    storeys = frame.get("storeys")
    if not storeys:
        raise SchemaError("frame.storeys 必填(层名→标高)")
    storeys = dict(sorted({k: _snap(v, mod) for k, v in storeys.items()}.items(), key=lambda kv: kv[1]))
    ag = {d: [_snap(v, mod) for v in frame.get("axis_grid", {}).get(d, [])] for d in ("x", "y")}

    # ── 标准层展开: floors 的 typical 键(如 "STD")复制到 frame.typical 列的各层 ──
    typical = frame.get("typical", {})           # {"STD": ["2F","3F","4F","5F","6F"]}
    floor_defs = design.get("floors", {})
    expanded = {}                                 # 层名 → floor 内容
    for key, fd in floor_defs.items():
        if key in typical:                        # 标准层键 → 复制到 typical[key] 的各层
            for sname in typical[key]:
                expanded[sname] = fd
        else:
            expanded[key] = fd

    # ── floors 展开(纯几何), 按 storeys 顺序 ──
    walls, openings, slabs, stairs, balconies = [], [], [], [], []
    roof = None
    for sname in storeys:
        fd = expanded.get(sname)
        if not fd:
            continue
        base = len(walls)   # 本层墙的起始全局索引(openings.wall 是本层索引 → 全局)
        for w in fd.get("walls", []):
            t = _snap(w.get("t", 0.2), mod)
            kind = w.get("kind", "int")
            if "path" in w:                      # 轴网路径 → axis 折线
                try:
                    pts = [(ag["x"][p["x"]], ag["y"][p["y"]]) for p in w["path"]]
                except (KeyError, IndexError):
                    raise SchemaError(f"path 轴网索引越界: {w['path']}")
                for i in range(len(pts) - 1):    # 共轴校验
                    if abs(pts[i][0]-pts[i+1][0]) > 1e-6 and abs(pts[i][1]-pts[i+1][1]) > 1e-6:
                        raise SchemaError(f"path 段{i} 不沿轴网(斜线), 改用 axis 折线")
                walls.append({"storey": sname, "axis": pts, "t": t, "kind": kind})
            elif "arc" in w:                     # 弧形 → axis 多段逼近
                a = w["arc"]
                cx, cy = _snap(a["center"][0], mod), _snap(a["center"][1], mod)
                r = _snap(a["r"], mod)
                a0, a1 = math.radians(a.get("a0", 0.0)), math.radians(a.get("a1", 360.0))
                n = max(4, int(abs(a1 - a0) / math.radians(12)))
                pts = [(cx + r*math.cos(a0+(a1-a0)*i/n), cy + r*math.sin(a0+(a1-a0)*i/n)) for i in range(n + 1)]
                walls.append({"storey": sname, "axis": pts, "t": t, "kind": kind})
            else:                                # axis 直墙/多段斜折线
                pts = _snap_pts(w["axis"], mod)
                walls.append({"storey": sname, "axis": pts, "t": t, "kind": kind})
        for op in fd.get("openings", []):
            openings.append({
                "storey": sname, "wall": base + op["wall"],
                "along": _snap(op["along"], mod), "w": _snap(op["w"], mod), "h": _snap(op["h"], mod),
                "sill": _snap(op.get("sill", 0.0), mod), "type": op.get("type", "window")})
        for s in fd.get("slabs", [{"t": 0.15}]):
            prof = s.get("profile") or fp
            slabs.append({"storey": sname, "profile": _snap_pts(prof, mod),
                          "t": s.get("t", 0.15), "predef": s.get("predef", "FLOOR")})
        for st in fd.get("stairs", []):          # 楼梯：shaft 绑墙(疏散) 或 at+size 独立(开敞)，两种位置标记
            out = {"storey": sname, "type": st.get("type"), "width": st.get("width")}
            shaft = st.get("shaft")
            if isinstance(shaft, dict) and isinstance(shaft.get("x"), list) and isinstance(shaft.get("y"), list):
                # shaft 轴线索引 → 井道矩形坐标（疏散梯，边界=墙轴线）
                try:
                    xi, xj = shaft["x"]; yk, yl = shaft["y"]
                    out["shaft"] = {"x0": ag["x"][xi], "x1": ag["x"][xj],
                                    "y0": ag["y"][yk], "y1": ag["y"][yl]}
                except (KeyError, IndexError, ValueError):
                    raise SchemaError(f"stairs shaft 轴网索引越界/格式错: {shaft}")
            elif "at" in st:                       # at + size 独立位置（开敞/螺旋/悬挑/扶梯，不绑墙）
                at = st["at"]; size = st.get("size", [2, 3])
                out["at"] = [_snap(at[0], mod), _snap(at[1], mod)]
                out["size"] = [_snap(size[0], mod), _snap(size[1], mod)]
            else:                                   # 兼容其他/旧格式
                out.update({k: v for k, v in st.items() if k not in ("type", "width", "storey")})
            stairs.append(out)
        for b in fd.get("balcony", []):           # 阳台只标位置/悬挑(建造交下游 balcony_cantilever)
            nb = dict(b)
            if "wall" in nb:
                nb["wall"] = base + nb["wall"]    # 本层墙索引 → 全局(同 openings)
            balconies.append({"storey": sname, **nb})
        if "roof" in fd:                          # 屋顶标大类(建造交下游 roof_pitched)
            roof = fd["roof"]

    allx = [p[0] for p in fp]
    ally = [p[1] for p in fp]
    return {
        "meta": meta,
        "bounds": {"x": [min(allx), max(allx)], "y": [min(ally), max(ally)]},
        "storeys": storeys, "axis_grid": ag, "footprint": fp,
        "walls": walls, "openings": openings, "slabs": slabs,
        "stairs": stairs, "balconies": balconies, "roof": roof,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design", help="design JSON 路径")
    ap.add_argument("-o", "--out", default="features.json")
    a = ap.parse_args()
    design = json.loads(Path(a.design).read_text())
    try:
        feat = normalize(design)
    except SchemaError as e:
        print(f"[SchemaError] {e}  → LLM 需重出 design JSON(Self-Refine)")
        sys.exit(2)
    Path(a.out).write_text(json.dumps(feat, ensure_ascii=False, indent=1))
    print(f"规范化: walls={len(feat['walls'])} openings={len(feat['openings'])} "
          f"slabs={len(feat['slabs'])} stairs={len(feat['stairs'])} balconies={len(feat['balconies'])} → {a.out}")
    print("下游: 构建脚本读此 features.json + flows 单步操作走 Pipeline → IFC")


if __name__ == "__main__":
    main()
