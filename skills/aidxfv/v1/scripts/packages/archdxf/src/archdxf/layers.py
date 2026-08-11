"""AIA-style layer tables per drawing domain.

Each table maps layer name -> {color, lineweight, linetype?}. Callers pick
the table(s) their sheet needs and ensure them on the document.
"""

from __future__ import annotations

FLOOR_LAYERS = {
    "A-WALL": {"color": 7, "lineweight": 50},
    "A-WALL-INTR": {"color": 7, "lineweight": 35},
    "A-DOOR": {"color": 4, "lineweight": 25},
    "A-GLAZ": {"color": 4, "lineweight": 25},
    "A-FIRE": {"color": 1, "lineweight": 25},
    "A-FIXT": {"color": 8, "lineweight": 18},
    "A-STRS": {"color": 8, "lineweight": 25},
    "A-COLS": {"color": 7, "lineweight": 35},
    "A-ANNO-SECT": {"color": 6, "lineweight": 25, "linetype": "DASHED"},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "A-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

SITE_LAYERS = {
    "C-PROP": {"color": 7, "lineweight": 50},
    "C-PROP-SBCK": {"color": 8, "lineweight": 18, "linetype": "DASHED"},
    "C-BLDG-EXST": {"color": 8, "lineweight": 25},
    "C-BLDG-PROP": {"color": 7, "lineweight": 50},
    "C-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "C-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

SECTION_LAYERS = {
    "A-WALL": {"color": 7, "lineweight": 50},
    "A-WALL-INTR": {"color": 7, "lineweight": 35},
    "A-ROOF": {"color": 7, "lineweight": 50},
    "A-ELEV": {"color": 7, "lineweight": 35},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "A-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

ELEVATION_LAYERS = {
    "A-ELEV": {"color": 7, "lineweight": 35},
    "A-ROOF": {"color": 7, "lineweight": 50},
    "A-DOOR": {"color": 4, "lineweight": 25},
    "A-GLAZ": {"color": 4, "lineweight": 25},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "A-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

ROOF_PLAN_LAYERS = {
    "A-ROOF": {"color": 7, "lineweight": 50},
    "A-WALL-BLW": {"color": 8, "lineweight": 18, "linetype": "DASHED"},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
}

SCHEDULE_LAYERS = {
    "A-ANNO-TABL": {"color": 7, "lineweight": 25},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
}

FOUNDATION_LAYERS = {
    "S-FNDN": {"color": 7, "lineweight": 35},
    "S-FNDN-FTNG": {"color": 8, "lineweight": 25, "linetype": "DASHED"},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "A-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

FRAMING_LAYERS = {
    "S-FRAM": {"color": 7, "lineweight": 35},
    "S-FRAM-RAFT": {"color": 8, "lineweight": 18},
    "S-FRAM-RIDG": {"color": 7, "lineweight": 50},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "A-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

LAYER_TABLES = {
    "floor": FLOOR_LAYERS,
    "site": SITE_LAYERS,
    "section": SECTION_LAYERS,
    "elevation": ELEVATION_LAYERS,
    "roof_plan": ROOF_PLAN_LAYERS,
    "schedule": SCHEDULE_LAYERS,
    "foundation": FOUNDATION_LAYERS,
    "framing": FRAMING_LAYERS,
}


def ensure_layers(doc, table: str | dict) -> None:
    """Add every layer of a named table (or explicit dict) to the document."""

    if isinstance(table, str):
        if table not in LAYER_TABLES:
            raise ValueError(f"unknown layer table {table!r}; have {sorted(LAYER_TABLES)}")
        table = LAYER_TABLES[table]
    for name, attribs in table.items():
        if name not in doc.layers:
            doc.layers.add(name, **attribs)
