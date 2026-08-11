# Upload Your First IFC

The repository bundles an official buildingSMART sample IFC:

`converter/test/fixtures/wall-with-opening-and-window.ifc`

## Workflow

1. **Upload**: drag an `.ifc` file (≤200MB; non-`.ifc` is rejected) onto the model library page. The model enters `converting`; the page polls every 2 seconds until it becomes `ready`. Failures show an error and can be retried.
2. **Open the model**: click the model to enter the 3D viewer. The model tree on the left expands one level by default and supports search, IFC-type filtering and per-node visibility; clicking an element highlights it and shows its property sets (psets) in the right panel.
3. **Review**: use the visibility toolbar (hide / isolate / X-Ray / reset), section sliders and distance measurement. Select an element to create an Issue (camera state and screenshot are captured automatically) and a 3D pin appears on the element.
4. **Edit**: the property panel is read-only (historical overrides shown with markers). On script-backed models, select an element and click "Locate script" to jump to its call line in the Design panel's script editor; change PARAMS or the script, then sandbox-validate and save a big version. See [IFC Script Editing](/en/viewer/editing) for details.
5. **Compare versions**: open **Diff** in the toolbar, choose base and target (a version or `current`) and run a semantic comparison; see [Versions & Diff Viewer](/en/viewer/versions-diff).

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Stuck in converting | Check the converter stderr in server logs; run `node converter/convert.js <ifc> <outDir>` manually; verify `nodeBin` / `converterScript` |
| Conversion failed | Retry with `POST /api/v1/models/{id}/retry` |
| Editing returns 404 model not found | `VIEWER_DATA_DIR` and the Go `dataDir` point to different directories |
| Script edit returns 422 | Script contract validation or sandbox build failed — the request had no side effects, fix per the detail and resend |
| Script changes not reflected in the UI | Only Go-proxied run/save/rollback trigger reconversion; direct edit-service calls need a manual refresh or a proxied replay |

The full troubleshooting table: [Testing & Debugging](/development/testing) (Chinese).
