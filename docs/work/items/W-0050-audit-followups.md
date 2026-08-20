# W-0050: aiplan/aidxfv 静态审计收尾修复

- **状态：** done
- **关闭于：** PR #53
- **优先级：** P2
- **Milestone：** v0.12（见 PLAN-v0.1.0.md）
- **来源：** 2026-08-20 aiplan/aidxfv 静态审计报告（用户裁决全修）
- **执行者/分支：** kimi-code / `fix/w0050-audit-followups`

## 背景

W-0049 拆分收口后对 aiplan / aidxfv v3 两个 MIT 自包含 skill 做了一次静态审计，
发现真实数据 bug、假测试、依赖卫生与一处路径穿越面。用户裁决全部修复。

## 涉及位置与方案

1. **golden meta.json 乱码键（真实数据 bug）**：
   `skills/aiplan/references/golden/residence/res_2s4u_std/meta.json` 与
   `office/office_std_01/meta.json` 的键 `" এক句话"`（孟加拉文混入）改回 `"一句话"`，
   占位值 `"..."` 补为真实描述（风格对齐同目录其他案例）；
   新增 `tests/test_golden_meta.py` 遍历全部 golden meta.json 做数据卫生校验
   （必需键/键名字符集/一句话非占位）。
2. **假测试清理**：
   - `aidxfv/v3/tests/test_goldlib_ingest.py`：两个「ingest 非 ingested 就 skip」
     改真断言（fixture 调整为 replay 可过的真实案例副本）；
     `test_goldlib.py` 两个 `pass` 占位用例删除
     （P3 覆盖归 test_goldlib_reverse.py::test_ingest_quarantine_fail，
     P4 覆盖归同文件 test_reindex_idempotent）。
   - `aidxfv/v3/tests/test_ingest_flow.py` `assert True` → 真断言（readback 无 error 字段）。
   - `aiplan/tests/test_pack_drift.py` `== 0 or True` → 按 `_main` 真实契约断言 `== 0`。
   - `aidxfv/v3/tests/test_readback.py` test_proxy_rejected 名不符实 →
     改名 `test_plain_entities_not_rejected` 并写明 ezdxf 无法构造代理实体的限制。
3. **依赖卫生**：
   - `aiplan/requirements.txt`：pytest 移入新 `requirements-dev.txt`；
     注释写明 ezdxf 为可选（仅 translate_golden 坐标诊断）。
   - `aiplan/SKILL.md` frontmatter `compatibility` 「仅依赖 jsonschema」改为实话
     （jsonschema + shapely，ezdxf 可选）。
   - `aidxfv/v3/requirements.txt` 删除零 import 的 Pillow（全目录 grep 确认）。
   - `aiplan/` 补 MIT LICENSE（复制自 aidxfv/v3/LICENSE，版权行风格一致）。
4. **flowops/pack.py node 名校验**：node（CLI 参数直传，作 `missions/` 目录名）
   加白名单校验 `^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)*$`（`<zone>.<stage>` 段式，
   拒绝路径分隔符与 `..`），pack_mission/register_mission 双入口生效，配参数化失败测试。
5. **删 aiplan 侧重复 golden DXF**：`skills/aiplan/references/golden/*/*/source.dxf`
   9 个文件 git rm（与 aidxfv 侧 md5 全同，约 23MB）；
   `translate_golden.py` 的 source_dxf_bbox 诊断本就有缺失降级（返回 None），
   补「source.dxf 缺失仍出报告、source_bbox=None」测试锁定。

## 验收标准

- 上述 5 项全部落地；两 skill 归属注释（MIT）不变。
- `aidxfv/v3` 与 `aiplan` 测试套件绿；假测试清理的用例数增减在提交信息中说明。
- `tests/skill` 142+2s 绿（skill venv 移走后跑，防 build-noise 误判）；
  `bash scripts/check_file_size.sh` 绿。

## 测试要求

- 行为修复（1/4）TDD：先失败测试后实现；5 先补降级测试再删文件。
- 假测试清理不得把「会失败的真问题」改成 skip——ingest 失败必须 fail。
