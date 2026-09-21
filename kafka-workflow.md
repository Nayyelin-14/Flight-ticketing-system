# Kafka + Welcome Email — Full Workflow

> One diagram, every function labeled. Reading path: every box shows
> `file.py::function()` so you can jump to the code. Two delivery routes
> share the **same handler**: the polling worker (`KAFKA_ENABLED=false`)
> and the Kafka publisher/consumer (`KAFKA_ENABLED=true`).

```mermaid
flowchart TD
    %% ============================ CLASSES ============================
    classDef api fill:#1f6feb,color:#fff,stroke:#0d3b8f,stroke-width:2px
    classDef poller fill:#8957e5,color:#fff,stroke:#4c2a99,stroke-width:2px
    classDef kafka fill:#238636,color:#fff,stroke:#165c3a,stroke-width:2px
    classDef handler fill:#d29922,color:#fff,stroke:#8a5a0d,stroke-width:2px
    classDef storage fill:#3d444d,color:#fff,stroke:#1f242c,stroke-width:2px
    classDef err fill:#f85149,color:#fff,stroke:#921f17,stroke-width:2px

    %% ============================ 1. API + OUTBOX ============================
    subgraph S1["1 — HTTP + Transactional Outbox (FastAPI)"]
        direction TB
        A1["routers/users.py<br/>register()<br/>POST /users/register/"]
        A2["dependencies.py<br/>get_db()<br/>opens Session"]
        A3["crud/users.py<br/>get_user_by_email(db, email)<br/>409 EMAIL_ALREADY_REGISTERED if exists"]
        A4["crud/users.py<br/>create_user(db, user_in)<br/>hash_password() + db.add(user) + db.flush()"]
        A5["crud/outbox.py<br/>create_outbox_job(db, 'WELCOME_EMAIL',<br/>payload = recipient + user_id)"]
        A6["db.commit()<br/>(ONE transaction: user row + outbox row)"]
        A7["returns 201 UserResponse"]

        A1 --> A2 --> A3 --> A4 --> A5 --> A6 --> A7
    end

    DB_OUTBOX["postgres: outbox table<br/>(OutboxJob: status=PENDING, attempts=0)<br/>job_type = JobType.WELCOME_EMAIL (models/outbox.py)"]
    A6 --> DB_OUTBOX

    %% ============================ 2. ROUTE CHOICE ============================
    D0["worker.py<br/>main()"]
    DB_OUTBOX --> D0
    D0 -->|"KAFKA_ENABLED = false"| POLLER
    D0 -->|"KAFKA_ENABLED = true"| KAFKA

    %% ============================ 2a. FALLBACK POLLER ============================
    subgraph S2["2a — Fallback Poller (KAFKA_ENABLED = false)"]
        direction TB
        P1["jobs/worker.py<br/>run_worker(settings, SessionLocal)<br/>infinite loop"]
        P2["crud/outbox.py<br/>recover_stale_jobs()<br/>PROCESSING stuck > timeout -> PENDING"]
        P3["crud/outbox.py<br/>claim_eligible_jobs()<br/>PENDING & due  (Postgres: FOR UPDATE SKIP LOCKED)<br/>marks PROCESSING"]
        P4["jobs/worker.py<br/>_process_job(settings, job)"]
        P5["jobs/registry.py<br/>get_handler(job.job_type)"]
        P6["KeyError -> crud/outbox.py<br/>mark_failed('Unknown job type')"]
        P7["WelcomeEmailHandler().handle(job)"]
        P8["jobs/worker.py<br/>_handle_retry()<br/>delays via events/backoff.py<br/>backoff_seconds()"]
        P9["crud/outbox.py<br/>schedule_retry(job, delay, error)<br/>attempts+1, next_attempt_at"]
        P10["crud/outbox.py<br/>mark_completed(job_id)"]
        P11["jobs/worker.py<br/>sleep(email_poll_interval=5s)"]

        P1 --> P2 --> P3 --> P4 --> P5
        P5 -->|"no handler"| P6
        P5 -->|"handler found"| P7
        P7 -->|"JobPermanentError"| P8
        P7 -->|"JobRetryError / generic"| P8
        P7 -->|"success"| P10
        P8 -->|"attempts < email_max_attempts"| P9
        P8 -->|"attempts >= max"| P6
        P9 --> P1
        P10 --> P1
        P11 --> P1
        P7 -.-> HANDLER_SUB
        P11 -.-> P2
    end
    class P4,P5,P7,P8,P2,P3,P6,P9,P10 poller

    %% ============================ 2b. KAFKA ============================
    subgraph S3["2b — Kafka Path (KAFKA_ENABLED = true)"]
        direction TB
        K0["worker.py<br/>_run_kafka(settings)"]
        K1["events/kafka.py<br/>ensure_topics(settings)<br/>only if kafka_provision_topics<br/>(idempotent, once at startup)"]
        K1A["events/kafka.py<br/>build_admin_client() + list_topics()<br/>create only missing:<br/>users.events<br/>users.events-retry<br/>users.events-dlq<br/>tolerate TopicAlreadyExistsError"]
        K2["events/kafka.py<br/>build_producer(settings)<br/>aiokafka producer (SASL_SSL)"]
        K3["asyncio.gather(publisher.run(),<br/>main_consumer.run(), retry_consumer.run())"]

        K0 --> K1 --> K1A
        K0 --> K2 --> K3

        %% --- publisher ---
        K4["events/publisher.py<br/>OutboxPublisher.run()<br/>loop"]
        K5["events/publisher.py<br/>publish_once()<br/>recover_stale_jobs() + claim_eligible_jobs() (SKIP LOCKED)"]
        K6["events/publisher.py<br/>_publish_job(job)"]
        K7["events/envelope.py<br/>EventEnvelope(event_id=job.id,<br/>event_type=job.job_type, attempts,<br/>source, payload)"]
        K8["events/domains.py<br/>event_topic(job.job_type)<br/>event_domain -> EVENT_DOMAINS<br/>domain_topic() -> 'users.events'"]
        K9A["KeyError: 'No domain registered'<br/>-> crud/outbox.py<br/>schedule_retry(job)"]
        K9["producer.send_and_wait(topic='users.events',<br/>key=str(job.id)  <-- event_id,<br/>value=serialize_event(envelope))"]
        K10["success -> crud/outbox.py<br/>mark_completed(job_id)"]
        K11["retry -> crud/outbox.py<br/>schedule_retry(job, error, backoff)"]
        K12["worker.py<br/>sleep(same kafka_poll_interval)"]

        K3 --> K4 --> K5 --> K6 --> K7 --> K8
        K8 -->|"unknown event"| K9A
        K8 -->|"topic resolved"| K9
        K9 -->|"send ok"| K10
        K9 -->|"send failed"| K11
        K10 --> K12 --> K4
        K11 --> K12

        K9 -->|"event"| EVT_TOPIC

        %% --- main consumer ---
        K13["events/consumer.py<br/>EventConsumer.run()<br/>main, topics=all_domain_topics()<br/>group = kafka_consumer_group"]
        K14["events/envelope.py<br/>deserialize_event(message.value)"]
        K15["BAD: events/consumer.py<br/>_handle_malformed()<br/>envelope.event_type='UNKNOWN'<br/>DLQ fallback = dlq_topic(message.topic)"]
        K16["events/idempotency.py<br/>was_processed(group, event_id)?"]
        K17["events/consumer.py<br/>_commit(message)<br/>OffsetAndMetadata(offset+1)<br/>enable_auto_commit=False"]
        K18["jobs/registry.py<br/>get_handler(event_type)"]
        K19["no handler -> events/consumer.py<br/>_send_to_dlq()<br/>domain delta = users.events-dlq"]
        K20["WelcomeEmailHandler().handle(job)"]
        K21["events/idempotency.py<br/>mark_processed(group, event_id)<br/>ON CONFLICT DO NOTHING"]
        K22["JobPermanentError -> _send_to_dlq()<br/>users.events-dlq"]
        K23["transient -> events/consumer.py<br/>_handle_transient()<br/>attempts+1"]
        K24["attempts >= kafka_max_attempts<br/>-> _send_to_dlq() users.events-dlq"]
        K25["else -> publish to<br/>retry_topic(canonical_topic)<br/>'users.events' -retry ONLY (no -retry-retry)"]

        EVT_TOPIC["Kafka topic: users.events"]
        EVT_TOPIC --> K13 --> K14
        K14 -->|"not JSON / missing fields"| K15
        K15 --> K17
        K14 -->|"decoded"| K16
        K16 -->|"already processed"| K17
        K16 -->|"new"| K18
        K18 -->|"no handler"| K19
        K19 --> K17
        K18 -->|"handler found"| K20
        K20 -->|"success"| K21 --> K17
        K20 -->|"JobPermanentError"| K22 --> K17
        K20 -->|"JobRetryError / generic"| K23
        K23 -->|"exhausted"| K24 --> K17
        K23 -->|"retry"| K25
        RETRY_TOPIC["Kafka topic: users.events-retry"]
        K25 --> RETRY_TOPIC

        %% --- retry consumer ---
        K26["events/consumer.py<br/>EventConsumer.run()<br/>is_retry=True, topics=[users.events-retry]<br/>SAME group id"]
        RETRY_TOPIC --> K26
        K26 --> K26A["sleep backoff_seconds(envelope.attempts)<br/>before reprocessing"]
        K26A --> K26B["same _process_message() flow:<br/>deserialize -> dedup -> get_handler -> handle"]
        K26B -->|"fails again"| K25
        K26B -->|"permanent/exhausted"| K24

        K14 --> DB_PE
        K21 --> DB_PE
    end
    class K1,K1A,K2,K4,K5,K6,K7,K8,K9,K13,K14,K15,K16,K17,K18,K19,K20,K21,K22,K23,K24,K25,K26,K26A,K26B kafka

    %% ============================ 3. HANDLER + EMAIL ============================
    subgraph S4["3 — Handler + Email Send (shared by both paths)"]
        direction TB
        H1["jobs/handlers/welcome_email.py<br/>WelcomeEmailHandler.__init__()<br/>sender = external_services/email_sender.py<br/>get_email_sender(settings)"]
        H2["jobs/handlers/welcome_email.py<br/>WelcomeEmailHandler.handle(job)<br/>reads payload['recipient'], payload['user_id']"]
        H3["external_services/email.py<br/>send_welcome_email(recipient,<br/>user_id, sender, settings)"]
        H4["external_services/email.py<br/>render_welcome_email(recipient, app_url)<br/>Jinja2 template: templates/emails/welcome.html"]
        H5["external_services/email_sender.py<br/>EmailSender.send(recipient,<br/>subject=WELCOME_SUBJECT='Welcome to SKYFLARE', html)"]
        H6["ExternalError -> mapped in welcome_email.py<br/>PermanentEmailError -> JobPermanentError<br/>EmailSendError     -> JobRetryError"]
        H7["SMTP backend | NOOP backend<br/>(email_backend setting, smtp_* settings)"]

        H1 --> H2 --> H3 --> H4 --> H5 --> H7
        H5 -->|"error"| H6
    end
    class H1,H2,H3,H4,H5,H6 handler

    %% ============================ STORAGE ============================
    DB_PE["postgres: processed_events table (models/events.py)<br/>PK = consumer_group + event_id<br/>durable idempotency / at-least-once"]

    subgraph S5["Infra config"]
        CFG1["core/settings.py<br/>kafka_* and email_* settings<br/>KAFKA_ENABLED, KAFKA_PROVISION_TOPICS,<br/>kafka_consumer_group='notification-workers'"]
    end
    class DB_OUTBOX,DB_PE storage
    class CFG1 api

    P7 --> HANDLER_SUB["WelcomeEmailHandler.handle(job)"]
    K20 --> HANDLER_SUB
    HANDLER_SUB -.-> H2
    A1 -.-> CFG1
```

## Legend

| Color | Phase | Files |
|---|---|---|
| Blue | HTTP entry + transactional outbox | `routers/users.py`, `crud/*`, `schemas/*`, `dependencies.py` |
| Purple | Fallback polling worker | `jobs/worker.py`, `crud/outbox.py` |
| Green | Kafka publisher / consumer path | `events/*`, `worker.py` |
| Orange | Handler + email send | `jobs/handlers/*`, `external_services/*`, `templates/*` |
| Grey | Persistence | `models/*`, `alembic/*` |

## Why the invariants hold

- **One DB transaction**: the outbox row is written in the same commit as the user row, so the email job never exists without the user (`crud/users.py::create_user`).
- **At-least-once, not exactly-once**: the outbox row id is both the Kafka key *and* the `event_id`; if the process crashes after the broker acks but before `mark_completed`, staleness recovery republishes the *same* event id and the consumer dedups it via `processed_events`.
- **Durable dedup**: `processed_events` is keyed by `(consumer_group, event_id)`, `ON CONFLICT DO NOTHING` on Postgres. Dedup is per consumer group — a future second group gets its own ledger.
- **No `-retry-retry`**: retry/DLQ targets are computed from `event_type → EVENT_DOMAINS → canonical domain topic` (`events/consumer.py::_canonical_topic`), never from the message's actual topic, so a message replayed from `users.events-retry` still resolves back to `users.events-retry` (or `users.events-dlq` when exhausted).
- **Offset commit after success**: `enable_auto_commit=False`; the offset is committed only after the handler succeeded *or* the message was safely re-routed (retry/DLQ). A crash mid-handle replays the same event → dedup absorbs it.
- **Malformed messages never kill the loop**: undecodable bytes go to the DLQ via the `message.topic` fallback.
- **Single source of truth**: `events/domains.py` maps `JobType → Domain → topic`. Publisher routing, consumer subscriptions, and startup provisioning (`ensure_topics`) all derive from it — adding a domain requires only `Domain` + `EVENT_DOMAINS` + a handler, then redeploy. No per-event topic config anywhere.
- **Two delivery routes, one handler**: `WelcomeEmailHandler` accepts any `JobLike` (an `OutboxJob` from the poller or an `EventJob` from the Kafka consumer), so the two paths can never diverge in behavior.

<!-- 

Read it in one pass — 5 phases, top to bottom:
1. Entry (blue) — box A1 (register) → A2 (get_db) → A3 (get_user_by_email) → A4 (create_user) → A5 (create_outbox_job) → A6 (db.commit) → A7 (201) → lands in DB_OUTBOX.
2. Fork (green/grey) — D0 (main) → DB row → either down to poller (purple) or right into Kafka (green).
3. Kafka provisioning — K0 → K1 → K1A (creates users.events, -retry, -dlq) → K2 → K3.
4. Kafka runtime — three loops in parallel:
- Publisher: K4 → K5 → K6 → K7 (envelope) → K8 (topic) → K9 (send) → K10/K11 → K12 (sleep) → back to K4.
- Main consumer: EVT_TOPIC → K13 → K14 → dedup K16 → K18 (handler) → K20 (work) → K21 (dedup write) → K17 (commit). Failure branches: K15 (malformed→DLQ), K19 (no handler→DLQ), K22 (permanent→DLQ), K23→K24/K25 (retry/DLQ).
- Retry consumer: K26 → K26A (backoff) → K26B (same flow) → re-loop K25 or K24.
5. Email (orange) — poller P7 or Kafka K20 both → H2 (handle) → H3 → H4 (render) → H5 (send) → H7 (SMTP/NOOP), with H6 mapping errors back into JobPermanentError/JobRetryError → the retry/DLQ branches.
Start at A1, follow the arrow to D0, then choose the poller column or the Kafka column, and end at H5. That's the complete lifecycle: register → outbox → (poller | Kafka) → handler → email. -->