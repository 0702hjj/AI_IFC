"""dxfkit/svg.py —— DXF → SVG 导出（T21）。

纯导出脚本，主 agent 可跑，不依赖 MCP。ezdxf add-ons.drawing SVG 后端。
确定性：同输入同输出（固定布局参数）。
"""

from __future__ import annotations

import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.config import Configuration
from ezdxf.addons.drawing.svg import SVGBackend


def export(dxf_path, out_path) -> None:
    """DXF → SVG 文件。

    :param dxf_path: 输入 DXF 路径
    :param out_path: 输出 SVG 路径（.svg）
    """
    from ezdxf.addons.drawing import layout
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    backend = SVGBackend()
    ctx = RenderContext(doc)
    config = Configuration.defaults()
    frontend = Frontend(ctx, backend, config=config)
    frontend.draw_layout(msp)
    svg_str = backend.get_string(layout.Page(0, 0))
    from pathlib import Path
    Path(out_path).write_text(svg_str, encoding="utf-8")
