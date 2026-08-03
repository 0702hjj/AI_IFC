# Spatial Quality Rules — Design Constraints (read BEFORE generating, checked AFTER)

> **Two roles**:
> 1. **Design constraints read BEFORE the design JSON** — when framing the footprint / stair layout / door positions, the LLM internalizes these rules so the design JSON is born compliant (articulated footprint, continuous stair, clear door swing). **Read this file before emitting any design JSON.**
> 2. **Hard checks run AFTER generation** via `design_review.py` — catches any violation for the Self-Refine loop.
>
> Purpose: prevent "technically valid but functionally broken / aesthetically lazy" models — a door that can't open, a stair you can't walk, a 6-storey building that is just a plain rectangle.
> Each rule: ID, description, measurement, pass threshold, severity.
>
> **Core check targets** (what actually matters — everything else is secondary guidance):
> - **External connectivity**: the envelope closes, and doors/openings connect inside↔outside and room↔room — no sealed-off space, no wall dead-ending a required connection.
> - **Walkability**: a person can physically move through the building — stairs are continuous and climbable, door swings are clear, stair/corridor exits are not dead ends.
>
> **Diversity is protected**: these rules check *function*, never *form*. A spiral stair in a circular bookshop, a cantilevered/suspended stair, an open atrium ramp, a railing-free stair — none fails just for not matching the "straight flight + railing + slab hole" stereotype. When a rule assumes a standard form, the special case is an **exemption, not an error**.

---

## 0. Geometric Integrity Rules (GI) — Highest Priority

**These are ERRORS, not warnings. A building with perfect proportions but broken topology is useless.**

### GI-01: Exterior Wall Closure

| Field | Value |
|---|---|
| Description | Exterior walls must form a closed polygon on the building perimeter (no gaps) |
| Measurement | Extract all exterior wall 2D endpoints per storey; check if they connect head-to-tail into a loop |
| Pass threshold | Closed loop OR documented intentional opening (entrance recess, courtyard) |
| Severity | **Error** |
| Rationale | A gap in the envelope means the building is not watertight |

### GI-02: Window-Wall Attachment

| Field | Value |
|---|---|
| Description | Every window must be geometrically ON a wall (not floating in space) |
| Measurement | Window center point vs. all wall XY bounding boxes + Z-range overlap |
| Pass threshold | Every window center is within some wall's XY extent AND Z overlap |
| Severity | **Error** |
| Rationale | A floating window is a modeling error, not a design choice |

### GI-03: Stair-Floor Opening (penetrating straight flights only)

| Field | Value |
|---|---|
| Description | A stair flight that passes THROUGH a floor slab must have a corresponding opening in that slab. **Exemptions**: spiral/helical stairs, cantilevered/suspended stairs, and stairs whose path does not pierce a slab (open-atrium ramps, exterior stairs) — these need no hole |
| Measurement | For each straight `IfcStairFlight`, check the slab directly above for an inner void or `IfcOpeningElement` covering its XY extent |
| Pass threshold | Covered — OR the stair is a non-straight / non-penetrating form (spiral, cantilever, exterior) |
| Severity | **Error** for straight penetrating flights; skip non-penetrating forms |
| Rationale | A straight flight through solid floor is impossible — but a spiral stair in a circular bookshop or a cantilever stair must NOT be forced into the "straight flight + slab hole" template. Check intent, not stereotype |

### GI-04: Opening Containment

| Field | Value |
|---|---|
| Description | Every opening (IfcOpeningElement) must be fully contained within its host wall |
| Measurement | Opening bounding box vs. host wall bounding box (XY and Z) |
| Pass threshold | Opening box is fully inside host wall box |
| Severity | **Error** |
| Rationale | An opening extending beyond the wall edge cuts into adjacent space incorrectly |

### GI-05: Wall-Slab Alignment

| Field | Value |
|---|---|
| Description | Wall base elevation must align with slab top elevation (no floating or sunken walls) |
| Measurement | Wall bottom z vs. slab top z (slab elevation + slab depth) |
| Pass threshold | \|wall_bottom_z - slab_top_z\| < 50mm |
| Severity | **Error** |
| Rationale | A wall floating above or sunk into the slab indicates placement error |

### GI-06: Column-Slab Alignment

| Field | Value |
|---|---|
| Description | Column base elevation must align with slab top elevation |
| Measurement | Column bottom z vs. slab top z |
| Pass threshold | \|column_bottom_z - slab_top_z\| < 50mm |
| Severity | **Error** |
| Rationale | A floating column indicates placement error |

### GI-07: Filling Within Wall Thickness

| Field | Value |
|---|---|
| Description | Every door/window filling an opening must sit within its host wall's thickness (no glass floating inside the room or protruding outside) |
| Measurement | Distance from filling placement origin to host wall centerline (2D) vs. wall thickness (from body profile) |
| Pass threshold | dist ≤ wall_thickness/2 + 25mm |
| Severity | **Error** |
| Rationale | `add_filling` does NOT reparent the filling — its placement is entirely manual; offsetting by the opening's thickness offset instead of the filling's own body center puts glass outside the wall |

### GI-08: Door Swing Clearance

| Field | Value |
|---|---|
| Description | The opening path of every door must be clear of obstructing walls/columns directly behind it — a wall right behind a door blocks it from opening |
| Measurement | For each door, check the half-space directly behind its plane (within door width × ~door depth) for any wall/column body intersecting the door's open position |
| Pass threshold | No wall/column body within the door's swing zone (door width × door depth behind the door plane) |
| Severity | **Error** |
| Rationale | A door with a wall immediately behind it cannot open — a functional failure. Common cause: a partition wall placed blindly across from an entry door. **Design-time check**: when placing a partition opposite an entry door, leave ≥ door-depth clearance |

### GI-09: Stair Continuity & Walkability

| Field | Value |
|---|---|
| Description | A stair must be walkable end-to-end AND connect every floor: each flight's top connects flush to the next landing/flight bottom (no vertical gaps/overlaps), treads are human-scale, and the whole stair actually reaches the next storey |
| Measurement | Per storey: R1 last-tread top z == landing top z == R2 first-tread bottom z (±25mm); riser 150–180mm, tread 250–300mm; landing present between opposing runs; AND **the highest tread top of the storey's stair == next-storey elevation (±100mm)** — i.e. `2 × rise_run == storey_height` |
| Pass threshold | All flight-landing-flight z connections flush within 25mm; riser ∈ [150,180]mm; tread ∈ [250,300]mm; highest stair tread reaches next floor within 100mm |
| Severity | **Error** |
| Rationale | A disconnected stair (landing floating above R1 top, or R2 starting past the landing edge) is impossible to walk. The common silent killer: `rise_run` set to a round number (e.g. 1.5m) while `storey_height` is 3.3/3.6m → the stair tops out short of the next floor, so you **cannot travel between storeys**. **Design-time rule**: `rise_run = storey_height / 2` always; R2 must start at the landing's near edge, landing top flush with R1 top |

### GI-10: Floor Slab Coverage (fall hazard)

| Field | Value |
|---|---|
| Description | Every occupied storey must have a floor slab whose footprint actually covers the wall envelope — occupants must be able to stand on a floor, not fall through |
| Measurement | Per storey: sum the **net** floor-slab area (slab profile outer area − profile inner voids − `IfcOpeningElement` shaft openings) and compare to the wall-envelope polygon area (chained from exterior-wall axes, concavity-aware); also confirm ≥1 FLOOR slab exists |
| Pass threshold | ≥1 floor slab AND net floor area ≥ 75% of wall-envelope area |
| Severity | **Error** |
| Rationale | A storey with walls but no/partial floor is a **fall hazard** (occupants "fall through"). The root cause is the *brute-force anti-pattern*: cutting oversized/stair-shaft voids, or omitting slabs, to dodge the GI-03 stair-through-slab check — leaving the floor missing or a swiss-cheese of holes. A legitimate outdoor courtyard is excluded from the envelope polygon (concavity-aware area), so it does not false-trigger. **Design-time rule**: net floor area must remain ≥75% of the enclosed envelope after every opening |

### GI-11: Stair Fall Protection (guard the open well)

| Field | Value |
|---|---|
| Description | A stair must not leave an unguarded opening someone can fall into: the open well between double-run flights, and the inner (non-wall) edge of every run, must be enclosed by a guardrail/handrail; the stair-well slab opening must be walled off on every floor |
| Measurement | Per storey with stair flights: (a) check an `IfcRailing` exists within the stair's XY extent (proxy for well/run guardrails); (b) design-time: the double-run well (gap between the two parallel lanes) must have a guardrail on each run's inner edge, and the shaft slab opening must be enclosed by shaft walls + a door — never an open hole in occupied floor |
| Pass threshold | ≥1 `IfcRailing` within the stair extent per stair storey; runs flush against the shaft side-walls (no side gap) |
| Severity | **Error** |
| Rationale | A double-run stair has an open well between the two flights — without guardrails a student can step off a run into the shaft ("跳楼"). Equally, a stair-well hole cut in an occupied floor with no enclosure is a fall hazard. **Design-time rule**: each run hugs a side wall on its outer edge and carries a guardrail on its inner (well) edge; the shaft opening is walled + doored, not left open |

### GI-12: Stair Shaft Hygiene (no cavity walls, circulation preserved, GF egress)

| Field | Value |
|---|---|
| Description | The stair shaft must be **sized to fit** between the building's existing walls, must **not block** horizontal circulation, and the stair must have a **ground-floor external entrance** |
| Measurement | (a) **Auto**: no two parallel *interior* walls within 1.2m forming a sealed cavity — the "small wall inside a wall" anti-pattern; (b) **design-time**: a solid-floor circulation strip is reserved beside the shaft so corridor ↔ 连廊 passage is unblocked; (c) **design-time**: a GF door on a gable/exterior wall enters the stair directly from outside (in addition to per-floor corridor doors) |
| Pass threshold | No parallel interior cavity walls <1.2m apart; circulation strip + GF external door present |
| Severity | **Error** |
| Rationale | A thin shaft wall erected ~1m from an existing wall ("墙里面建小墙") wastes space and signals the stair wasn't sized to fit — **size the stair runs to abut existing walls instead** (shaft width = 2·lane + well ≈ 3m, side walls = existing partition/gable or one wall at the full stair-width distance). A shaft filling the whole end-bay blocks corridor/连廊 circulation (reserve a strip). A stair with no GF external door is not a real egress stair |

---

## 1. Proportion Rules

### PR-01: Window-to-Wall Ratio

| Field | Value |
|---|---|
| Description | Ratio of total window area to total exterior wall area per storey |
| Measurement | `sum(window.OverallHeight × window.OverallWidth) / sum(wall.length × wall.height)` per storey |
| Pass range | 25%–50% (school), 30%–70% (public/office), 15%–40% (residential), 40%–80% (retail) |
| Severity | **Error** |
| Rationale | Too low = dark, prison-like, educationally harmful (no daylight in classrooms); too high = structural/thermal issues, glass box monotony. Daylight is a *functional* requirement for schools/offices, not a stylistic preference, so an out-of-range WWR is a hard failure, not a warning |

### PR-02: Column Spacing

| Field | Value |
|---|---|
| Description | Distance between adjacent columns in grid |
| Measurement | `np.diff(sorted(column_x_positions))` and `np.diff(sorted(column_y_positions))` |
| Pass range | 6.0m–12.0m |
| Severity | Error |
| Rationale | <6m = cramped, inefficient; >12m = requires deep beams, uneconomical |

### PR-03: Floor Height

| Field | Value |
|---|---|
| Description | Storey height (floor to floor) |
| Measurement | `storey.Elevation[i+1] - storey.Elevation[i]` |
| Pass range | 3.3m–4.5m |
| Severity | Error |
| Rationale | <3.3m = oppressive; >4.5m = wasteful for typical programs |

### PR-04: Slab Thickness

| Field | Value |
|---|---|
| Description | Floor slab thickness |
| Measurement | `slab.Depth` or profile extrusion depth |
| Pass range | 0.10m–0.25m |
| Severity | Error |
| Rationale | <100mm = structural concern; >250mm = excessive self-weight |

### PR-05: Cantilever Depth

| Field | Value |
|---|---|
| Description | Balcony, canopy, or overhang projection beyond support |
| Measurement | Distance from support line to outer edge |
| Pass range | ≤ 4.0m |
| Severity | Warning |
| Rationale | >4m requires complex structure, visual instability |

---

## 2. Rhythm Rules (RH) — regularity of facade & grid

| ID | What | Pass threshold | Severity |
|---|---|---|---|
| RH-01 | Facade bay spacing consistency (window/panel widths) | CV < 0.15 | Warning |
| RH-02 | Column grid regularity (X & Y spacing) | CV < 0.10 | Error |
| RH-03 | Vertical repetition (facade pattern across floors) | ≥80% storeys share pattern | Info |
| RH-04 | Setback rhythm (if setbacks present) | Monotonic increase / constant | Warning |

**Rationale**: irregular bays / grid look accidental; per-floor randomness looks chaotic. Deliberate asymmetry needs design logic, not noise.

---

## 3. Material Contrast (MC)

| ID | What | Pass threshold | Severity |
|---|---|---|---|
| MC-01 | Base-body contrast (L1 vs L2+) | Different material OR RGB dist > 0.2 | Warning |
| MC-02 | Structure-envelope contrast (columns/beams vs walls/glass) | Different material assigned | Info |
| MC-03 | Distinct material count | ≥ 3 | Warning |
| MC-04 | Glass-to-opaque balance on facade | 20%–80% glass | Info |

**Rationale**: uniform treatment lacks hierarchy; <3 materials = monotonous; all-glass or all-opaque lacks interest. Typical good buildings use 3–6 materials.

---

## 4. Composition Rules

### CP-01: Three-Part Hierarchy

| Field | Value |
|---|---|
| Description | Clear distinction between base, body, and top |
| Measurement | Compare floor treatment: L1 (base), middle (body), top floor/roof (top) |
| Pass threshold | At least 2 of 3 zones have distinct treatment (height, material, or setback) |
| Severity | Warning |
| Rationale | Uniform extrusion lacks compositional sophistication |

### CP-02: Entrance Emphasis

| Field | Value |
|---|---|
| Description | Visual prominence of main entrance |
| Measurement | Check for: canopy, recess, height change, material change, or frame emphasis at entrance |
| Pass threshold | At least 1 emphasis feature present |
| Severity | Warning |
| Rationale | Unmarked entrance is hard to find, unwelcoming |

### CP-03: Roof Termination

| Field | Value |
|---|---|
| Description | Visual termination of building top |
| Measurement | Check for: parapet, cornice, setback, penthouse, or roof structure expression |
| Pass threshold | At least 1 termination feature present |
| Severity | Info |
| Rationale | Abrupt flat top looks unfinished |

### CP-04: Corner Treatment

| Field | Value |
|---|---|
| Description | Differentiation or emphasis at building corners |
| Measurement | Check for: corner window, material change, fin, or chamfer at corners |
| Pass threshold | At least 1 corner feature OR intentional simplicity (all corners same) |
| Severity | Info |
| Rationale | Corners are visual anchors; treatment should be deliberate |

### CP-05: Footprint Articulation (no lazy rectangles)

| Field | Value |
|---|---|
| Description | The building footprint must not be a single plain rectangle when the program allows richer massing — use L/U/T/E shapes, corner cuts, inset courts, or stepped edges to reflect internal organization (unit mix, lighting, site) |
| Measurement | Footprint polygon: vertex count + convexity. A plain rectangle = 4 corners, all 90°, fully convex. Articulated = ≥6 corners OR ≥1 concave (re-entrant) angle OR an inset court |
| Pass threshold | ≥6 vertices OR ≥1 concave corner OR documented justification (tiny guardhouse, single-room extension, narrow site-constrained) |
| Severity | Warning |
| Rationale | A pure rectangle for a multi-storey residential/mixed building is a lazy default, not a design. Real buildings respond to site, light, and unit mix with setbacks, notches, and courts. **Do NOT default to `[[0,0],[L,0],[L,W],[0,W]]` — earn the shape from the program.** A designer asks: where does the sun come from? Where is the entrance? Which units get the corner? — the answers carve the footprint |

---

## 5. Facade Depth (FD)

| ID | What | Pass threshold | Severity |
|---|---|---|---|
| FD-01 | Window recess (frame depth behind wall surface) | 0.05m–0.30m | Warning |
| FD-02 | Facade articulation (fins/sunshades/balconies/recesses/reveals) | ≥1 element per 10m facade | Info |
| FD-03 | Shadow lines (string courses/reveals/sills/cornices) | ≥1 per 3 storeys | Info |

**Rationale**: flat facades are boring; depth creates shadow, scale, richness. Flush windows look cheap; deep recesses add shadow.

---

## 6. Spatial Quality (SQ)

| ID | What | Pass threshold | Severity |
|---|---|---|---|
| SQ-01 | Atrium / light well (buildings >3 storey & >2000m²) | Present OR justified (narrow plate) | Info |
| SQ-02 | Natural light access (% floor within 8m of window/atrium) | ≥80% | Warning |
| SQ-03 | Circulation clarity (stair/elevator legibility) | ≥1 visible stair or marked elevator per floor | Info |

**Rationale**: deep plates need interior light; dark interiors are uninhabitable; hidden circulation confuses occupants.

---

## 7. Severity & Workflow

| Level | Meaning | Action |
|---|---|---|
| Error | Violates functional/design logic (GI-xx incl. GI-09 stair reach / GI-10 floor coverage / GI-11 stair fall-protection / GI-12 stair shaft hygiene, PR-01 daylight, PR-02/03/04, RH-02) | Must fix before delivery |
| Warning | Deviates from good practice | Review and justify or fix |
| Info | Enhancement suggestion | Optional |

**Workflow** (authoritative pipeline in `SKILL.md` #15-16): generate → `ifcopenshell.validate` (schema) → `design_review.py` (these rules) → 0 errors ⇒ deliver; else Self-Refine. The report format is what `design_review.py` prints (ERRORS / WARNINGS / INFO + summary); this file defines the *rules*, not the output template.

---

## 8. Rule Tuning by Building Type

| Rule | Residential | Office | School | Retail |
|---|---|---|---|---|
| PR-01 (WWR) | 15–40% | 30–70% | 25–50% | 40–80% |
| PR-02 (col spacing) | 3–9m | 8–12m | 8–10m | 8–12m |
| PR-03 (floor height) | 2.8–4.5m | 3.3–4.5m | 3.3–4.5m | 3.3–5.5m |
| CP-05 (footprint articulation) | Recommended | Required | Recommended | Required |
| MC-01 (base contrast) | Optional | Required | Recommended | Required |
| CP-01 (3-part) | Optional | Required | Recommended | Required |
| SQ-01 (atrium) | N/A | Recommended | Recommended | Required |

`design_review.py` already applies the Residential column for PR-02/PR-03. Adjust thresholds by building type before running.
