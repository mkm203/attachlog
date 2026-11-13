# Copilot instructions for AttachLog

## Repository overview

AttachLog is a three-service Python FastAPI application:

- `placement-service/` owns placements and the SQLite `placement.db`; it verifies HS256 JWTs and enforces role checks on writes.
- `logbook-service/` owns weekly entries and reviews in `logbook.db`; it verifies the same JWTs and calls the placement service over HTTP while forwarding the caller's bearer token.
- `bff/` is a Strawberry GraphQL facade that composes both REST APIs. It has no database and exposes `placement`, `myEntries`, and `reviewLogEntry`.

The overall runtime is:

- client / GraphiQL -> BFF on port 8003
- BFF -> placement service on port 8001
- BFF -> logbook service on port 8002
- logbook service -> placement service for placement checks, forwarding the original JWT

`client/` is a demo script, `integration-tests/` starts the real services end-to-end, and `k8s/` contains deployment manifests for containerized runs.

## Build, test, and validation commands

Use the repo's Python virtual environment at `.venv/` and run commands from the service directory unless stated otherwise.

### Core pytest commands

```powershell
cd placement-service; ..\.venv\Scripts\python.exe -m pytest
cd logbook-service;   ..\.venv\Scripts\python.exe -m pytest
cd bff;               ..\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest integration-tests
```

### Single-test runs

```powershell
cd logbook-service; ..\.venv\Scripts\python.exe -m pytest tests/test_reviews.py::test_progress_for_the_academic_supervisor
```

Always run `python -m pytest` rather than bare `pytest`. Each service imports `app.*`, so test execution must happen from the service root. The only exception is `integration-tests/`, which is meant to run from the repo root and starts its own temporary service processes.

### Local run commands

```powershell
cd placement-service; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001
cd logbook-service;   ..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8002
cd bff;               ..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8003
```

### Docker / Compose

```powershell
docker compose up --build -d
docker compose ps
docker compose down -v
```

### OpenAPI snapshot regeneration

Regenerate `openapi.json` in a service after route or auth changes:

```powershell
cd placement-service; ..\.venv\Scripts\python.exe -c "import json; from app.main import app; open('openapi.json','w',encoding='utf-8').write(json.dumps(app.openapi(), indent=2)+'\n')"
```

There is no configured linter, formatter, type checker, migration tool, or CI pipeline in this repo. Pytest is the primary validation path.

## Architecture and data flow

### Service boundaries

- `placement-service` owns placement records and business rules like term validation, placement state, and JWT issuance for the dev token endpoint.
- `logbook-service` owns weekly entries, reviews, and progress summaries. It depends on the placement service for placement lookup/validation and forwards the caller token.
- `bff` provides the public GraphQL API and hides the two REST services behind one schema.

### Auth and authorization model

All services share the same dev JWT secret and the same JWT claims shape (`sub`, `role`).

- Roles: `student`, `company_supervisor`, `academic_supervisor`, `coordinator`
- Missing or invalid tokens return HTTP 401
- Wrong-role access returns HTTP 403
- BFF converts auth failures to GraphQL errors with `extensions.code` set to `not_authenticated` or `forbidden`

The dev token endpoint is intentionally simple and not backed by a user store: it signs whatever `sub` and `role` you send for local demo usage.

### Database and schema conventions

- Tables are created by `Base.metadata.create_all(engine)` in each service's `app/main.py`.
- There are no migrations. If a SQLAlchemy model changes, delete the local `.db` file to recreate the schema.
- SQLite paths are relative to the working directory, so each service must be started from its own folder.

### API conventions

- All REST routes live under `/v1`.
- Every service also exposes `/health`.
- Business errors use the shared shape:

```json
{"error": {"code": "entry_exists", "message": "An entry already exists for week 1", "details": null}}
```

- Raise `ApiError(status, code, message)` from `app/errors.py` and keep the codes stable; tests assert exact error codes.
- Keep route logic in `app/routes.py`, auth in `app/auth.py`, Pydantic models in `app/schemas.py`, and SQLAlchemy models in `app/models.py`.

### GraphQL conventions

The BFF is a thin facade over the REST services. It should not add database logic or duplicate domain rules; it should adapt REST responses into GraphQL objects and map auth/business failures appropriately.

## Key repository conventions

- `client/client.py` seeds a placement and entry through REST if `--placement-id` / `--entry-id` are not supplied.
- `logbook-service/tests/test_enteries.py` is intentionally misspelled and should be treated as part of the repo history, not fixed unless the task specifically calls for it.
- Tests rely on per-service `tests/conftest.py` patterns involving in-memory SQLite and `app.dependency_overrides`.
- Logbook tests often fake the placement client instead of spinning up a second server.
- BFF tests use `TestClient` and monkeypatch async client methods (`schema_module.placements` and `schema_module.logbook`) with `AsyncMock`.
- Query params are snake_case except for the logbook list endpoint's `placementId` alias.
- When changing routes or auth, also refresh the generated OpenAPI JSON snapshots.

## Environment variables and runtime defaults

| Variable | Service | Default |
| --- | --- | --- |
| `JWT_SECRET` | all | `dev-secret-change-me-use-32-chars-min` |
| `JWT_TTL_MINUTES` | placement | `480` |
| `DATABASE_URL` | placement / logbook | `sqlite:///./placement.db` / `sqlite:///./logbook.db` |
| `TERM_START`, `TERM_END` | placement | `2026-09-01`, `2027-02-28` |
| `PLACEMENT_SERVICE_URL` | logbook / bff | `http://localhost:8001` |
| `LOGBOOK_SERVICE_URL` | bff | `http://localhost:8002` |

## Useful repo-specific rules

- Do not run a full multi-service stack from the repo root unless specifically testing the end-to-end flow.
- For validation, prefer service-local pytest runs and narrow single-test invocations.
- Keep authentication and authorization behavior consistent across all three services.
- Preserve existing error codes and response shapes; tests assert them exactly.
- Treat the repository as a set of lightweight service integrations rather than a general monolith; changes often require adjusting both the service and the BFF contract.
