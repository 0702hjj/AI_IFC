# Contributing

## Development environment

See [Environment & Local Deployment](/en/guide/quickstart). Development follows TDD: write a failing test first, then implement; tests live next to the source.

## Local verification

```bash
# backend
cd viewer/server && go test ./... && go vet ./...
# edit service
cd viewer/edit-service && uv run pytest
# frontend
cd viewer/web && npm test && npm run build
# converter
cd viewer/converter && npm test
# documentation (public site + API reference drift)
cd docs && npm ci && npm run docs:build && npm run check:api
```

## Documentation contributions

- The public site source lives in `docs/site/`, the single source of truth; after changes you must run `cd docs && npm run docs:build` (dead links fail the build).
- `docs/internal/` is never part of the site — internal records only (the former `docs/archive/` was removed in the 2026-08-05 cleanup; see git history).
- Pages that describe undelivered capabilities must be marked as Roadmap items and must not provide non-executable steps.
- After moving or archiving documents, update all Markdown relative links in the repository.
- Generated files (`docs/site/reference/edit-api-reference.md`, `docs/site/public/go-rest-api.routes.json`) must not be edited by hand; regenerate with `npm run gen:api` and commit the result. `npm run check:api` detects drift.
- To add an English page, create the real translated content under `docs/site/en/`; empty navigation or placeholder pages are not allowed.

## Commits and PRs

- Commit messages follow the repository convention: `feat:` / `fix:` / `docs:` / `ci:` / `chore:` prefix plus a short Chinese or English description.
- PRs to `main` run the viewer CI and the docs build; both must pass.
- Never commit personal machine paths, secrets or runtime data (`viewer/data/`).

## License

This repository is AGPL-3.0-only. Contributing means you agree to release your contribution under that license; third-party attributions: [License & third-party components](/project/license) (Chinese).
