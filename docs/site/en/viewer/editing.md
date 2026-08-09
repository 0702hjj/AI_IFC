# IFC Script Editing

All web edits are unified as **edits to the build script** (script-as-source): the IFC is always a derived artifact of the script, and every persisted change is accompanied by a script change. The former L1 direct-edit chain (pending → commit, mutating the IFC) is retired — its endpoints return 410 Gone (recoverable from git history, anchor `fb55a8a`).

## Two model shapes

- **script-backed** (has a build script): full editing — select-and-locate, PARAMS form, script editor, staging and big versions.
- **plain** (external upload, no script): view and review only (Issues/Diff); no editing entry in the UI. With AI involved, the uploaded IFC can be reproduced as a script (bootstrap, below), turning the model script-backed.

## Select an element → locate the script

The property panel is read-only. Select an element and click **"Locate script"**:

1. The frontend calls `GET /api/v1/models/{id}/script/locate?guid=`: guid → `Pset_AIIFC.designKey` → current ScriptMap (`v{n}.map.json`, staging first).
2. Hit: the Design panel switches to the script editor with the cursor on the call line, highlighted.
3. Miss: locate returns 200 `{"found": false}` and the panel stays read-only (a missing designKey is a contract violation — please report it as a bug).

## Rewriting (two sub-paths)

The locate result carries an `origin` tag that decides the rewrite strategy:

- **`origin=params`**: the value comes from the top-level `PARAMS` block — edit the key in the Design panel's PARAMS form; submitting stages one step (`PUT /script`).
- **`origin=literal`**: an inline scalar literal — edit the argument in the script editor. The API also offers `POST /models/{id}/script/edit-call` (edit-service direct only): a lossless libcst rewrite of one scalar argument (str/int/float/bool, formatting and comments preserved) → sandbox re-run → on success equivalent to a staged `PUT /script`; `origin=traced`, non-scalars, illegal argument names and non-finite floats all get 422 with zero side effects.
- **`origin=traced`** (key computed at runtime): the factory call line is still located, but automatic rewriting is refused — edit the script manually.

## Sandbox validation and staging

Form submits and editor saves pass static contract validation first (422 with zero side effects on failure) and enter the staging buffer; edit-call additionally sandbox-runs before staging (**build failure = 422, zero side effects**). The staging buffer is a 10-step ring, persisted atomically and restored after a restart, with undo/redo:

- **Discard** → drop the staging chain: zero diff, zero version.
- **Run** → sandbox-execute the staged script for a preview, without creating a version.
- **Save version** → run the script to produce the IFC and promote to big version v{n+1} (script + map snapshotted as a pair; only the latest IFC is materialized — see [Versions & Diff Viewer](/en/viewer/versions-diff)).

## Bootstrap: uploaded IFC → script (AI route)

With AI involved, an uploaded IFC is meant as a **reference for reproduction**:

1. The user uploads an IFC (plain state, view-only).
2. The AI reads the model via the MCP server and writes a reproduction script with the aiifc skill.
3. On the first `PUT /script` the platform preserves the original upload as `bootstrap.ifc`; after sandbox validation, `script/save` stores big version v1 and the model becomes script-backed.
4. The first save response carries an `alignment` count (`added/removed/changed` — a semantic-diff summary of bootstrap.ifc vs the generated IFC), serving as the acceptance signal for reproduction fidelity.

For the endpoint contract see [Script editing & version diff](/en/reference/design-edit) and the [IFC Editing API](/en/reference/edit-api).
