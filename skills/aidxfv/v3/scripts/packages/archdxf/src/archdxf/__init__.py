"""archdxf: architectural DXF drafting primitives (self-written, ezdxf-based).

Drawing-construction layer for aidxfv1 gen_dxf() sources: wall frames,
opening subtraction, door/window symbols, fixtures, annotation chains.
Design decisions (where walls are, what openings exist) stay with the
caller; this library only expands declarations into standard drafting.
"""

from __future__ import annotations

from . import annotate, canon, fixtures, frames, intervals, layers, openings, stairs

__all__ = [
    "annotate", "canon", "fixtures", "frames", "intervals", "layers", "openings", "stairs",
]
__version__ = "0.1.0"
