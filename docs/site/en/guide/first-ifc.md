# Upload Your First IFC

The repository bundles an official buildingSMART sample IFC:

`viewer/converter/test/fixtures/wall-with-opening-and-window.ifc`

## Workflow

1. **Upload**: drag an `.ifc` file (≤200MB; non-`.ifc` is rejected) onto the model library page. The model enters `converting`; the page polls every 2 seconds until it becomes `ready`. Failures show an error and can be retried.
2. **Open the model**: click the model to enter the 3D viewer. The model tree on the left expands one level by default and supports search, IFC-type filtering and per-node visibility; clicking an element highlights it and shows its property sets (psets) in the right panel.
3. **Review**: use the visibility toolbar (hide / isolate / X-Ray / reset), section sliders and distance measurement. Select an element to create an Issue (camera state and screenshot are captured automatically) and a 3D pin appears on the element.
4. **Edit**: in the property panel, the whitelisted fields (Name / Description / Classification / FireRating / Comments) can be edited inline and saved as overrides; see [IFC Property Editing](/viewer/editing) (Chinese) for details.
5. **Compare versions**: open **Diff** in the toolbar, choose base and target (a version or `current`) and run a semantic comparison; see [Versions & Diff Viewer](/viewer/versions-diff) (Chinese).

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Stuck in converting | Check the converter stderr in server logs; run `node viewer/converter/convert.js <ifc> <outDir>` manually; verify `nodeBin` / `converterScript` |
| Conversion failed | Retry with `POST /api/v1/models/{id}/retry` |
| Editing returns 404 model not found | `VIEWER_DATA_DIR` and the Go `dataDir` point to different directories |
| Editing returns 422 | Attribute name or value type is wrong — the request had no side effects, fix and resend |
| Commit returns 409 | No pending changes (pending lives in memory and is lost when edit-service restarts) |
| Attribute changes not reflected in the UI | Only Go-proxied commits trigger reconversion; direct edit-service calls need a manual refresh or a proxied replay |

The full troubleshooting table: [Testing & Debugging](/development/testing) (Chinese).
