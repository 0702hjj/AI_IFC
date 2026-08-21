"""record.py 测试（P0-1：draw 调用序列记录 + build() 脚本固化）。

链路：LLM 逐次调 dxfkit.draw（record 包装记录）→ 固化 build() 脚本 →
重放 build() 产 DXF → 与原 DXF 字节级一致（确定性）。
"""

import subprocess
import sys

import pytest

from dxfkit import draw, record


@pytest.fixture(autouse=True)
def _wrap_and_record():
    """每个测试：开始记录 + 包装 draw 模块（draw_api 调用面不变）。"""
    record.start()
    record.wrap_draw_module(draw)
    yield
    record.start()  # 清理


def _draw_sample_floor():
    """模拟 LLM 画一层：底座 + 一堵墙 + 一个门洞 + 一扇门（draw_api 调用形态）。"""
    draw.reset_keys()
    doc = draw.new_doc()
    msp = doc.modelspace()
    wkey = draw.wall_run(msp, (0, 0), (8000, 0), 200, cuts=[])
    okey = draw.opening(msp, wkey, 1000, 900)
    draw.door(msp, wkey, okey, 1000, 900, "in-left")
    return doc


class TestRecordCalls:
    def test_records_draw_calls_in_order(self):
        _draw_sample_floor()
        fns = [c["fn"] for c in record.calls()]
        assert fns == ["wall_run", "opening", "door"]

    def test_excludes_msp_from_args(self):
        _draw_sample_floor()
        for c in record.calls():
            # msp（modelspace 运行时对象）不可序列化，被排除
            for a in c["args"]:
                assert not hasattr(a, "add_line"), f"msp 泄漏进记录: {c}"

    def test_records_returned_keys(self):
        _draw_sample_floor()
        rets = [c["ret"] for c in record.calls()]
        # key 共享 _key_counter 顺序计数：wall_0001 → open_0002 → door_0003（确定性）
        assert rets[0] == "wall_0001"
        assert rets[1] == "open_0002"
        assert rets[2] == "door_0003"

    def test_key_refs_are_literals(self):
        """door 引用的 wall_key/open_key 是字面值（确定性，重放自然对齐）。"""
        _draw_sample_floor()
        door_call = record.calls()[2]
        assert door_call["fn"] == "door"
        assert "wall_0001" in door_call["args"]
        assert "open_0002" in door_call["args"]


class TestToBuildScript:
    def test_script_has_contract_shape(self):
        _draw_sample_floor()
        script = record.to_build_script(record.calls(), params={"zone": "test"})
        assert "PARAMS = " in script
        assert "def build(params, out_path):" in script
        assert 'if __name__ == "__main__":' in script
        assert "draw.wall_run(msp," in script

    def test_script_passes_contract_validation(self):
        """固化脚本过 services/cad validate_script_contract（ast 静态门）。"""
        _draw_sample_floor()
        script = record.to_build_script(record.calls(), params={"zone": "test"})
        import tempfile
        from pathlib import Path
        flows = Path(__file__).resolve().parents[3] / "services" / "cad" / "flows"
        sys.path.insert(0, str(flows))
        from cad_script_lib import validate_script_contract
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(script)
            path = f.name
        assert validate_script_contract(path) == []

    def test_replay_produces_dxf(self, tmp_path):
        """固化脚本在沙箱 PYTHONPATH（archdxf+dxfkit）里重放 → 产 DXF。"""
        _draw_sample_floor()
        script = record.to_build_script(record.calls(), params={"zone": "test"})
        script_path = tmp_path / "zone.py"
        script_path.write_text(script, encoding="utf-8")
        out = tmp_path / "floor.dxf"
        # 用当前解释器跑 build（dxfkit 已在 PYTHONPATH——本测试环境 editable install）
        subprocess.run(
            [sys.executable, str(script_path), str(out)],
            check=True, capture_output=True, timeout=30,
        )
        assert out.is_file() and out.stat().st_size > 0
        import ezdxf
        doc = ezdxf.readfile(str(out))
        assert len(list(doc.modelspace())) > 0

    def test_replay_deterministic(self, tmp_path):
        """同一固化脚本跑两次 → 字节级一致（确定性）。"""
        _draw_sample_floor()
        script = record.to_build_script(record.calls(), params={"zone": "test"})
        script_path = tmp_path / "zone.py"
        script_path.write_text(script, encoding="utf-8")
        outs = []
        for i in range(2):
            out = tmp_path / f"floor_{i}.dxf"
            subprocess.run(
                [sys.executable, str(script_path), str(out)],
                check=True, capture_output=True, timeout=30,
            )
            outs.append(out.read_bytes())
        assert outs[0] == outs[1], "重放应字节级确定（同脚本同 DXF）"
