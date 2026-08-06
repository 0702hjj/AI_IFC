# Model Library & Upload

The model library page is the platform entry point: upload, list, status tracking, retry, download and delete.

## Upload

- Drag in or select an `.ifc` file (≤200MB); non-`.ifc` extensions and oversized files are blocked by the frontend and validated again by the backend.
- After upload the model enters `converting`; the server queues the converter to generate XKT and metadata, and the page polls every 2 seconds until all models leave `converting`.
- Status values: `converting` (being converted), `ready` (usable), `failed` (conversion failed, retryable).

## List operations

- **Retry**: re-queue conversion for a `failed` model.
- **Download**: download the original IFC file (the unmodified upload).
- **Delete**: cascades to the IFC, XKT, metadata and state files, plus the model's issues / changes / overrides.

## Related API

The endpoint contracts for upload, list, retry, download and delete are in [Viewer REST API](/en/reference/rest-api).
