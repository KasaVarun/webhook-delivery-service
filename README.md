# Webhook Delivery Service

## Overview

FastAPI service that stores webhook destinations, accepts client-identified events, creates one persisted delivery per destination, and posts the JSON payload with bounded retries. It uses PostgreSQL through async SQLAlchemy and `asyncpg`.

The current `BackgroundTasks` delivery loop is a timed-exercise implementation, **not crash safe**. A restart can abandon pending, delivering, or sleeping work.

## Architecture

```text
Current
Client --> FastAPI routes --> async SQLAlchemy --> PostgreSQL
                 |                 |              events/webhooks/deliveries
                 v                 v
         BackgroundTasks --> DeliveryService --> httpx POST --> receiver

10x
Client --> API replicas --> PgBouncer --> PostgreSQL
                    \-> durable queue --> worker replicas --> receivers
                                      \-> Redis: rate limits/coordination

100x
Client --> load balancer --> API replicas --> managed PostgreSQL
                                     \-> partitioned durable queue --> workers
observability: logs, metrics, traces, alerts
```

## Project Structure

```text
app/main.py              app lifespan, logging, DB-error handler
app/config.py            environment-backed settings
app/database.py          async engine, session factory, health query
app/models.py            PostgreSQL models, constraints, indexes
app/services.py          in-process delivery/retry loop
app/repositories/        persistence operations
app/routes/              API endpoints
app/schemas/             validation and responses
tests/                   10 PostgreSQL integration tests
scripts/                 existing deploy helper and systemd unit
```

## Technology Choices

- PostgreSQL: `JSONB`, relational constraints, and indexed durable state.
- SQLAlchemy 2 async plus `asyncpg`: non-blocking database access in FastAPI.
- Ubuntu LTS Droplet plus `systemd`: deployment artifacts exist; no Droplet deployment or public verification is claimed.

## Data Model

`webhooks` has UUID, name, HTTP(S) URL, and timestamps. `events` has UUID, client `event_id`, event type, JSONB payload, and timestamps. `deliveries` links event/webhook and stores state (`pending`, `delivering`, `succeeded`, `failed`), attempt count, latest HTTP status/error, and timestamps.

Constraints: `uq_events_event_id` is unique; `deliveries.event_id` cascades on event delete; `deliveries.webhook_id` restricts webhook delete; modeled core fields are non-null. Existing indexes: `ix_events_event_type_created_at(event_type, created_at)`, `ix_deliveries_event_id(event_id)`, `ix_deliveries_webhook_id_status(webhook_id, status)`, and `ix_deliveries_status_created_at(status, created_at)`.

## API and OpenAPI

OpenAPI is at `/openapi.json`, Swagger UI at `/docs`, and ReDoc at `/redoc`.

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/health` | Runs `SELECT 1`; readiness or `503`. |
| `POST` | `/webhooks` | Creates an HTTP(S) destination. |
| `GET` | `/webhooks` | Lists destinations newest first. |
| `POST` | `/events` | Persists event and current webhook fan-out, then schedules delivery. |
| `GET` | `/deliveries/{delivery_id}` | Returns a persisted delivery. |
| `GET` | `/events/{event_id}/deliveries` | Returns event and its deliveries. |
| `GET` | `/metrics` | Counts and average persisted attempt count. |

```json
POST /webhooks
{"name":"orders","url":"https://receiver.example/hooks"}

POST /events
{"event_id":"order-1842-paid","event_type":"order.paid","payload":{"order_id":"1842","total":42.5}}
```

Creates return `201`. Validation failures, including non-HTTP(S) URLs and blank identifiers, return `422`. Duplicate `event_id` returns `409 {"detail":"event_id already exists"}`. Missing delivery/event history returns `404`; database failures and failed readiness return `503 {"detail":"database unavailable"}`. Any `2xx` delivery succeeds; non-`2xx` and `httpx.HTTPError` outcomes persist and retry up to `MAX_DELIVERY_ATTEMPTS` (default four), waiting 1, 2, then 4 seconds.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/webhooks` | Application PostgreSQL URL. |
| `PORT` | `8000` | Uvicorn port. |
| `LOG_LEVEL` | `INFO` | Python logging level. |
| `WEBHOOK_TIMEOUT_SECONDS` | `10.0` | Positive outbound timeout. |
| `MAX_DELIVERY_ATTEMPTS` | `4` | Positive total attempts. |
| `TEST_DATABASE_URL` | unset | Test database URL; overrides `DATABASE_URL` in tests. |

## Local PostgreSQL, Run, and Test

Create separate `webhooks` and `webhooks_test` PostgreSQL databases. Tests read `TEST_DATABASE_URL`, normalize conventional PostgreSQL URLs to `asyncpg`, and drop/recreate schema per client fixture; never point them at a valuable database.

Local verification used `TEST_DATABASE_URL=postgresql+asyncpg://varunkasa@localhost:5432/webhooks_test` and passed all 10 integration tests. Install `.[dev]`, set `DATABASE_URL`, run Uvicorn against `app.main:app`, and set `TEST_DATABASE_URL` before pytest. Startup invokes `create_all`; it is not a versioned migration system.

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on push and pull request, installs `.[dev]`, starts PostgreSQL 15 with database `webhooks_test` and user/password `postgres`, then runs pytest with `TEST_DATABASE_URL`. The workflow configuration has not run in GitHub Actions.

## Manual Droplet Steps

These are target-environment steps, not completed deployment evidence.

1. Provision Ubuntu LTS, create non-root `webhook`, and place a `webhook`-owned checkout at `/opt/webhook-delivery-service`.
2. Install Python 3.11 and PostgreSQL; create a dedicated role/database and bind PostgreSQL to loopback when co-hosted.
3. Create restricted `/etc/webhook-delivery-service.env` with `DATABASE_URL`, `PORT=8000`, logging, timeout, and attempt-limit values.
4. Configure UFW for `22/tcp` and `8000/tcp` as intended; put TLS/reverse proxy controls in front of public traffic.
5. Run the existing `scripts/deploy.sh`; it creates the venv, installs the package/unit, reloads systemd, and enables the service.
6. Check `systemctl status webhook-delivery.service`, use `systemctl restart webhook-delivery.service`, and inspect `journalctl -u webhook-delivery.service -f`. Verify `/health` locally and from an allowed outside URL after networking/TLS are set up.

No Droplet, systemd target run, outside URL, or public verification has been performed.

## Security

HTTP(S)-only validation exists, but it does not stop SSRF to private, loopback, link-local, metadata, or redirected addresses. Production must resolve/block forbidden targets before connecting, re-check redirects, and apply egress controls. There is no API auth, authorization, tenant isolation, registration policy, or rate limiting. Use protected environment files or a secret manager, never source/logs, terminate TLS at a configured proxy/load balancer, and add per-destination credentials and signed outbound payloads.[SAS](https://docs.google.com/document/d/1az78y3dfsUsq5Of3Dcs4d0qMholqy1clSfEcUeb9g7Y/edit?tab=t.y6vm3e4mgo6u)
 

## Limitations and Production Path

Crashes can lose in-process work; concurrent instances can duplicate delivery; `2xx` then DB-commit failure can duplicate later; DB state can commit before an HTTP attempt; and `delivering` rows are never reclaimed. The schema stores only aggregate attempt data.

Use a durable queue/outbox and worker pool. Claim rows with `FOR UPDATE SKIP LOCKED` or visibility timeouts, use leases/heartbeats and reclaim expired locks, and retain immutable attempt records. Enforce `(event, webhook)` idempotency and send an idempotency key receivers deduplicate. Bound SQLAlchemy pools; put PgBouncer before PostgreSQL under connection pressure; use Redis for rate limits, coordination, and cache, not authoritative delivery state. For managed PostgreSQL use private networking/TLS, backups/PITR, monitoring, least-privilege roles, and Alembic expand/backfill/contract migrations instead of startup `create_all`.
