"""svg.py 测试（T21）：DXF → SVG 导出。"""

import pytest

from dxfkit.svg import export


@pytest.fixture(scope="module")
def golden_dxf(tmp_path_factory):
    import importlib.util
    from pathlib import Path
    src = Path(__file__).resolve().parent.parent / "tests" / "golden" / "dxf" / "residence_1br.py"
    spec = importlib.util.spec_from_file_location("residence_1br", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc = mod.gen_dxf()
    path = tmp_path_factory.mktemp("svg") / "residence_1br.dxf"
    doc.saveas(path)
    return path


class TestSvgExport:
    def test_export_nonempty(self, golden_dxf, tmp_path):
        out = tmp_path / "out.svg"
        export(golden_dxf, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert len(content) > 500  # 非空

    def test_export_has_svg_root(self, golden_dxf, tmp_path):
        out = tmp_path / "out.svg"
        export(golden_dxf, out)
        content = out.read_text(encoding="utf-8")
        assert "<svg" in content

    def test_export_deterministic(self, golden_dxf, tmp_path):
        a = tmp_path / "a.svg"
        b = tmp_path / "b.svg"
        export(golden_dxf, a)
        export(golden_dxf, b)
        assert a.read_bytes() == b.read_bytes()
