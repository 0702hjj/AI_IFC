# OpenAPI Files

## edit-service (machine-consumable)

The full OpenAPI schema: [ai-tools.openapi.json](/ai-tools.openapi.json), exported directly from the implementation (`create_app().openapi()`), identical to the live `GET /openapi.json`.

Regenerate after editing the editing API:

```bash
cd viewer/edit-service
uv run python scripts/export_openapi.py
```

The script writes `docs/site/public/ai-tools.openapi.json` (published with the site's public directory).

The page [Editing API Reference (generated)](/reference/edit-api-reference) is generated from that schema by `docs/scripts/gen-edit-api-reference.mjs`; run `npm run gen:api` after any schema change and commit the result. `npm run check:api` fails when committed output drifts.

## Go server

The Go server's REST contract is documented by hand at [Viewer REST API](/en/reference/rest-api). A machine-readable endpoint inventory is generated from the Go mux registrations: [go-rest-api.routes.json](/go-rest-api.routes.json) (method, path, handler, source file). Full request/response schema generation for Go remains a follow-up.

> Automated page generation from schemas and CI drift detection are partially delivered (see above); code-vs-schema drift detection for edit-service is now unblocked (dependencies are self-contained via PyPI), see the [Roadmap](/project/roadmap) (Chinese).
