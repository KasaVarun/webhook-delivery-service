# Requirements Ledger

## Required

- [VERIFIED] Async FastAPI REST API backed by PostgreSQL via `DATABASE_URL`.
- [VERIFIED] `GET /health` verifies database connectivity and reports readiness.
- [VERIFIED] Register and list webhook destinations with HTTP(S) URL validation.
- [VERIFIED] Persist events with database-enforced unique `event_id` handling.
- [VERIFIED] Create a delivery for every registered webhook per accepted event.
- [VERIFIED] Attempt deliveries with timeout; retry failed work up to four total attempts.
- [VERIFIED] Persist delivery state, attempts, latest HTTP status/error, and timestamps.
- [VERIFIED] Delivery lookup and event delivery history with documented 404 responses.
- [VERIFIED] Metrics including the mean persisted attempt count, returning `0.0` when empty.
- [VERIFIED] OpenAPI, validation, structured request/delivery logging, and database error handling.
- [VERIFIED] 10 PostgreSQL integration tests passed locally against `webhooks_test`: health/database failure; webhook validation/listing; event creation/duplicate; successful delivery; network failure; non-2xx failure; retry exhaustion; delivery/history lookup; metrics; and database uniqueness.
- [VERIFIED] Implementation-specific README and REVIEW guide.
- [VERIFIED] GitHub Actions CI configuration passed in GitHub run `35660800623`.
- [VERIFIED] DigitalOcean Droplet deployment: enabled, active systemd service; local PostgreSQL readiness; public health/docs; and public delivery workflow.
- [VERIFIED] Local PostgreSQL verification completed with `TEST_DATABASE_URL=postgresql+asyncpg://varunkasa@localhost:5432/webhooks_test`; all 10 integration tests passed.

## Optional

- [NOT IMPLEMENTED] Nginx reverse proxy.
- [IMPLEMENTED BUT NOT VERIFIED] Safe deployment helper script.
- [NOT IMPLEMENTED] API key authentication.

## Assumed

- Delivery attempt data is stored as aggregate fields on `Delivery`, as the requested minimum schema does not require a separate delivery-attempt table.
- FastAPI background tasks perform the timed-exercise retry loop. This is not crash-safe.
- Webhook registrations are append-only in this MVP; there is no requested webhook lookup route.

## Out Of Scope

- [VERIFIED] GitHub repository, GitHub Actions CI, and DigitalOcean Droplet were verified in this exercise.
- [NOT IMPLEMENTED] Crash-safe distributed delivery processing. The production design is documented as durable queue workers with locking and idempotency.

## Final Requirement Evidence

| Requirement | Implementation | File/function | Automated test | Manual test | Cloud verification | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Readiness | PostgreSQL `SELECT 1` | `app/database.py:database_is_healthy` | health success/failure | `GET /health` 200 | Public 200 | VERIFIED |
| Webhooks | Validated persistent registration/listing | `app/routes/webhooks.py` | registration, invalid URL, list | POST/GET locally | Public registration completed | VERIFIED |
| Events | Atomic event/delivery creation and DB duplicate handling | `app/repositories/event.py:create_with_deliveries` | creation, duplicate, unique constraint | POST and duplicate 409 | Public event accepted | VERIFIED |
| Delivery | HTTP post and persisted terminal state | `app/services.py:DeliveryService.deliver` | success, network, non-2xx | controlled receiver returned 200 | HTTP 204 delivery persisted | VERIFIED |
| Retry | Four-attempt bounded backoff | `app/services.py:DeliveryService.deliver` | exact retry exhaustion | Not manually failed over HTTP | Unreachable target exhausted after 4 attempts | VERIFIED |
| Lookup/history | Delivery and event delivery reads with 404s | `app/routes/deliveries.py` | lookup/history tests | both reads returned 200 | Public event history read | VERIFIED |
| Metrics | Aggregate persisted state and attempt mean | `app/repositories/delivery.py:metrics` | metrics test | `GET /metrics` 200 | Not repeated publicly | VERIFIED |
| OpenAPI/logging | Route metadata and request/delivery logs | `app/routes`, `app/main.py` | Route paths exercised | `/docs` 200, logs observed | Public docs 200; journal inspected | VERIFIED |
| CI | PostgreSQL GitHub Actions workflow | `.github/workflows/ci.yml` | GitHub run `35660800623` | Not applicable | Passed | VERIFIED |
| Droplet/systemd | Unit and deployment instructions | `scripts/webhook-delivery.service`, `scripts/deploy.sh` | Not applicable | Active/enabled service; loopback PostgreSQL; UFW checked | Public service verified | VERIFIED |
| Public workflow | External health, docs, delivery flow | Droplet `:8000` | Not applicable | Public HTTP workflow completed | Health/docs/delivery verified | VERIFIED |