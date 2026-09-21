# Review Guide

## 60-Second Walkthrough

Start at `app/main.py`: startup creates SQLAlchemy metadata, logs request latency, and converts SQLAlchemy errors to `503`. Routes validate input and call repositories. `POST /events` invokes `EventRepository.create_with_deliveries`, inserting the event plus all current webhook deliveries in one transaction, then schedules `DeliveryService.deliver` background tasks. The service posts JSON with `httpx`, persists attempts/results, and retries failures up to four times. PostgreSQL access is async SQLAlchemy/asyncpg. Tests use real PostgreSQL via `webhooks_test`.

```text
Request: Client -> POST /events -> validation -> event + delivery transaction -> 201
                                                        |
                                                        v
                                               BackgroundTasks -> DeliveryService

Delivery: load -> mark delivering/increment -> HTTP POST -> commit success/failure
                                          |                 |
                                          +-- sleep/retry <--+ (until budget)
```

## Key Points

- Transaction: event plus current webhook fan-out is one `session.begin()` transaction; unique `event_id` maps to `409`.
- Retry: `2xx` succeeds; non-`2xx` and `httpx.HTTPError` failures persist status/error. Defaults are four attempts and 1/2/4 second waits.
- PostgreSQL/async: JSONB, async sessions, pool pre-ping, and `SELECT 1` readiness are implemented. `create_all` is local convenience, not migrations.
- Droplet/systemd: artifacts target `/opt/webhook-delivery-service`, user `webhook`, an environment file, and restart-on-failure. None is target-verified.
- Failures: crashes abandon background work; a remote success plus local commit failure can duplicate; uncertain remote writes can duplicate; `delivering` rows are not reclaimed.
- Concurrency/idempotency: unique `events.event_id` deduplicates intake only. There is no unique delivery pair, worker lease/lock, or receiver-facing idempotency key.
- SSRF/security: HTTP(S) validation exists; private/reserved address controls, redirect/DNS checks, auth, authorization, rate limits, signing, secrets management, and TLS termination are not implemented.
- Tests/CI: ten PostgreSQL integration tests passed locally. CI configuration exists but has no GitHub run evidence.
- Observability: request latency and delivery outcomes are logged; `/metrics` returns persisted counts/average attempts. No Prometheus, tracing, dashboard, alert, or DLQ exists.
- Scaling/migrations: durable queue/outbox, workers with `SKIP LOCKED` or leases, immutable attempts, PgBouncer, Redis coordination/rate limits, managed PostgreSQL, and Alembic are the production path.

## More Time

**30 more minutes:** add migrations, API authentication, SSRF address/redirect defenses, signed payload contract, correlation IDs, and deployment rehearsal.

**2 hours:** add outbox/worker claims with leases and `SKIP LOCKED`, attempt records, delivery/idempotency uniqueness, concurrent/crash tests, and basic metrics/tracing.

**Production version:** private managed PostgreSQL with PITR and monitored migrations; queue-backed workers; pool management/PgBouncer; Redis for coordination/rate limiting; TLS proxy; secret manager; auth/quotas; signed webhooks; dashboards, alerts, DLQ/replay, and incident runbooks.

## 30 Likely Questions

1. Why PostgreSQL? JSONB, constraints, indexes, durable state.
2. Why async SQLAlchemy? Non-blocking database I/O with FastAPI.
3. Why asyncpg? Native async PostgreSQL driver.
4. What is intake idempotency? `uq_events_event_id` plus `409`.
5. Is delivery idempotent? No.
6. When are deliveries created? In the event transaction.
7. What if no webhooks exist? Event persists with no deliveries.
8. What is success? Any HTTP `2xx`.
9. What retries? Non-`2xx` and `httpx.HTTPError`.
10. How many attempts? Four total by default.
11. What delays? 1, 2, and 4 seconds.
12. Is retry durable? No, it is `BackgroundTasks`.
13. Where is state? Aggregate fields on `deliveries`.
14. What does health check? Database `SELECT 1`.
15. What does metrics expose? Counts/states/mean attempts.
16. Why PostgreSQL tests? UUID/JSONB schema behavior.
17. How do tests isolate state? Drop/create metadata per fixture.
18. Which indexes exist? One event index and three delivery indexes from README.
19. Why `create_all`? Exercise convenience; replace with migrations.
20. What does pool pre-ping do? Checks stale pooled connections.
21. Is auth present? No.
22. Is rate limiting present? No.
23. Is SSRF solved? No.
24. Where are secrets? Restricted environment file/secret manager.
25. How does TLS work? Reverse proxy/load balancer.
26. What does systemd do? Runs Uvicorn as `webhook`, restarts on failure.
27. Why PgBouncer? Limits direct PostgreSQL connection pressure.
28. Why Redis? Coordination/rate limits, not durable delivery truth.
29. Why managed PostgreSQL? Backups, PITR, private networking, operations.
30. What is verified? Local behavior and 10 PG tests, not GitHub/Droplet/public behavior.

## 15 Difficult Follow-Ups

1. Prevent duplicate remote effects across response/commit failure?
2. Claim and recover work safely across replicas?
3. Required locks/isolation for fan-out and transitions?
4. Defend against DNS rebinding and redirect SSRF?
5. Sign payloads and rotate keys?
6. Preserve per-customer ordering?
7. Rate-limit hostile/slow destinations fairly?
8. Audit/replay immutable attempts?
9. Perform zero-downtime large-table migrations?
10. Choose worker concurrency from timeout/pool limits?
11. Separate receiver, application, and queue-lag failures in metrics?
12. Backfill an outbox with idempotency?
13. Protect payloads in logs, backups, and retries?
14. Recover after managed PostgreSQL failover?
15. Test crash points around state writes and HTTP?

## Files and Functions to Know Cold

- `app/main.py`: `lifespan`, `log_request_latency`, `handle_database_error`.
- `app/config.py`: `Settings`, `get_settings`.
- `app/database.py`: engine/session setup and `database_is_healthy`.
- `app/models.py`: states, constraints, indexes, foreign keys.
- `app/routes/events.py`: `create_event` background scheduling.
- `app/routes/webhooks.py`: registration/listing.
- `app/routes/deliveries.py`: lookup/history semantics.
- `app/routes/health.py` and `app/routes/metrics.py`: readiness and counts.
- `app/repositories/event.py`: `create_with_deliveries` transaction.
- `app/repositories/delivery.py`: state transitions, `get_for_delivery`, `metrics`.
- `app/services.py`: `DeliveryService.deliver`.
- `tests/conftest.py` and `tests/test_webhook_delivery.py`: test DB and 10 verified scenarios.
- `scripts/deploy.sh` and `scripts/webhook-delivery.service`: deployment assumptions.