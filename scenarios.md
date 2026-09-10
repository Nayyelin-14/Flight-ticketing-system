# Flight Booking System - End-to-End Scenarios

> This document synthesizes the **Database Design** (database-design.md) and **Scalability & Performance Architecture** (scalability-performance.md) into complete service scenarios. It covers the happy path, every failure point, and the retry/recovery mechanisms.

---

## System Context

```mermaid
graph TB
    CLIENT[Client App] -->|HTTPS - SSL terminated at LB| LB[Load Balancer<br/>NGINX<br/>Health checks, least-connections]
    LB --> K8S[Kubernetes Cluster<br/>3-10 API pods]
    K8S --> REDIS[(Redis Cluster)]
    K8S --> DB[(PostgreSQL<br/>Sharded)]
    K8S --> KAFKA[Apache Kafka<br/>3 brokers]
    KAFKA --> NOTIFY[Notification Service]
    KAFKA --> LOG[Log Processor]
    KAFKA --> ANA[Analytics Service]
    NOTIFY --> EMAIL[Email]
    NOTIFY --> SMS[SMS]
    NOTIFY --> PUSH[Push]
```

---

## SCENARIO 1: HAPPY PATH - Complete Booking Journey

### User Story
> Alice searches for flights from DEL to BOM on 15 Jan, picks a flight, books seat 12A, pays ₹4,500 via UPI, receives confirmation.

### Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Alice
    participant LB as Load Balancer
    participant API as API Service (Pod)
    participant Redis as Redis Cache
    participant DB as PostgreSQL (Sharded)
    participant Kafka as Kafka Broker
    participant PAY as Payment Gateway
    participant NOTIF as Notification Service

    Note over Alice,NOTIF: STEP 1 - SEARCH FLIGHTS
    Alice->>LB: GET /flights?origin=DEL&dest=BOM&date=15-01
    LB->>API: route to healthy pod
    API->>Redis: check key search:DEL:BOM:15-01
    Redis-->>API: MISS (cache miss)
    API->>DB: SELECT * FROM flights WHERE origin='DEL' AND destination='BOM' AND dep_time > NOW() AND status='scheduled'
    DB-->>API: Flight: F101 (origin=DEL, dest=BOM)
    API->>Redis: SETEX search:DEL:BOM:15-01 (TTL 2min)
    API-->>Alice: 200 OK [Flight F101]

    Note over Alice,NOTIF: STEP 2 - CHECK SEAT AVAILABILITY
    Alice->>API: GET /flights/F101/seats
    API->>Redis: check key seats:F101
    Redis-->>API: HASH with seats (available=45)
    API-->>Alice: 200 OK [seat 12A available]

    Note over Alice,NOTIF: STEP 3 - CREATE BOOKING (transactional)
    Alice->>API: POST /bookings {flight_id: F101, seat: 12A}
    API->>DB: BEGIN TRANSACTION
    API->>DB: UPDATE seats SET status='reserved' WHERE flight_id='F101' AND seat_number='12A' AND status='available'
    DB-->>API: 1 row updated (only if still available)
    API->>DB: INSERT INTO bookings (user_id, flight_id, seat_number, status='pending', price=4500)
    API->>DB: COMMIT
    API->>DB: UPDATE bookings SET payment_id = ? WHERE id = ?
    Note right of API: payment_id = NULL at this point,<br/>linked after payment
    API->>Kafka: PUBLISH booking.events {BOOKING_CREATED, booking_id}
    API-->>Alice: 201 Created [booking_id=B900]

    Note over Alice,NOTIF: STEP 4 - INITIATE PAYMENT
    Alice->>API: POST /bookings/B900/payment {method: UPI}
    API->>DB: INSERT INTO payments (booking_id, status='pending', method='UPI')
    API-->>Alice: 202 Accepted [payment_id=P300, redirect to UPI]

    Note over Alice,NOTIF: STEP 5 - PAYMENT GATEWAY CALLBACK
    PAY-->>API: Webhook: PAYMENT_SUCCESS {payment_id=P300}
    API->>DB: UPDATE payments SET status='completed', paid_at=NOW() WHERE id='P300'
    API->>DB: UPDATE bookings SET status='confirmed', payment_id='P300' WHERE id='B900'
    API->>DB: UPDATE seats SET status='booked' WHERE flight_id='F101' AND seat_number='12A'
    API->>Redis: DEL seats:F101  (invalidate cache)
    API->>Redis: DEL user:{alice}:bookings (invalidate)
    API->>Kafka: PUBLISH payment.events {PAYMENT_COMPLETED, payment_id}
    API-->>PAY: 200 OK (acknowledge webhook)

    Note over Alice,NOTIF: STEP 6 - ASYNC NOTIFICATION (event-driven)
    Kafka->>NOTIF: Consume payment.events PAYMENT_COMPLETED
    NOTIF->>NOTIF: Route to Email Worker + SMS Worker + Push Worker
    NOTIF->>Alice: ✉️ Email: Booking Confirmed (B900, 12A, ₹4,500)
    NOTIF->>Alice: 💬 SMS: Ticket confirmed for F101 DEL→BOM
    NOTIF->>Alice: 🔔 Push: Ready to fly!

    Note over Alice,NOTIF: STEP 7 - VERIFY BOOKING
    Alice->>API: GET /bookings/B900
    API->>Redis: check key booking:B900
    Redis-->>API: MISS (or HIT)
    API->>DB: SELECT booking JOIN payments JOIN flights WHERE booking_id='B900'
    DB-->>API: Confirmed, P300, F101 details
    API-->>Alice: 200 OK [full booking detail]
```

### State Transitions Across the Journey

```mermaid
stateDiagram-v2
    [*] --> SEARCH: User searches route
    SEARCH --> SEAT_SELECT: Pick flight F101
    SEAT_SELECT --> PENDING: Create booking, seat reserved
    PENDING --> PAYMENT_INITIATED: User clicks pay (UPI)
    PAYMENT_INITIATED --> CONFIRMED: Webhook PAYMENT_SUCCESS
    CONFIRMED --> COMPLETED: Flight departs
    PENDING --> CANCELLED: Timeout (no payment)
    PAYMENT_INITIATED --> CANCELLED: User aborts / payment fails
    CONFIRMED --> REFUNDED: User cancels booking
    CANCELLED --> [*]
    REFUNDED --> [*]
    COMPLETED --> [*]
```

---

## SCENARIO 2: FAILURE & RETRY SCENARIOS

### 2.1 Seat Contention - "Double Booking Race"

**Scenario:** Two users try to book the last seat (12A) simultaneously.

```mermaid
sequenceDiagram
    autonumber
    actor U1 as User 1 (Alice)
    actor U2 as User 2 (Bob)
    participant API1 as API Pod 1
    participant API2 as API Pod 2
    participant DB as PostgreSQL (Sharded)

    U1->>API1: POST /bookings {flight: F101, seat: 12A}
    U2->>API2: POST /bookings {flight: F101, seat: 12A}

    Note over API1,DB: BOTH hit DB concurrently
    API1->>DB: BEGIN
    API1->>DB: UPDATE seats SET status='reserved' WHERE seat='12A' AND status='available'
    DB-->>API1: 1 row updated ✅ (Alice wins - row lock acquired)

    API2->>DB: BEGIN
    API2->>DB: UPDATE seats SET status='reserved' WHERE seat='12A' AND status='available'
    DB-->>API2: 0 rows updated ❌ (Bob blocked by lock, condition fails)

    API1->>DB: INSERT booking B900 (Alice)
    API1->>DB: COMMIT
    API1-->>U1: 201 Created ✅

    API2->>DB: ROLLBACK (or orphan pending booking auto-cancelled)
    API2-->>U2: 409 Conflict "Seat 12A no longer available"
    API2->>Redis: DEL seats:F101 (force cache refresh)
```

**Why it works:** The conditional `UPDATE ... WHERE status='available'` is atomic. PostgreSQL row-level locking ensures only one transaction updates the row. Bob's update affects 0 rows, so the API rejects.

**Retry path for Bob:** The API returns 409. The client UI shows alternatives:

```mermaid
graph LR
    A[409 Seat Taken] --> B{Show alternatives?}
    B -->|Yes| C[Query seats:F101 from cache]
    B -->|No| D[Suggest waitlist or adjacent flight]
    C --> E[Bob picks 13A]
    E --> F[Retry booking 13A]
```

---

### 2.2 Redis Cache Failure (Cache Miss / Redis Down)

```mermaid
sequenceDiagram
    autonumber
    actor Alice
    participant API as API Service
    participant Redis as Redis (Down)
    participant DB as PostgreSQL

    Alice->>API: GET /flights?origin=DEL&dest=BOM
    API->>Redis: GET search:DEL:BOM:date
    Note over API: Connection refused / timeout
    API->>API: CATCH error → circuit breaker opens (Redis)
    API->>DB: Direct query (fallback bypasses cache)
    DB-->>API: Flight list
    API-->>Alice: 200 OK (served, slight latency increase)

    Note over API: Circuit breaker: `OPEN` after N failures
    Note over API: Half-open probe every 10s → close on success
```

**Protections:**
- **Read fallback:** API never fails just because Redis is down; it queries DB directly.
- **Circuit breaker:** Prevents hammering a dead Redis → recovers gracefully.
- **Cache stampede / hot-key protection:** For popular routes (DEL→BOM), Redis is populated on first miss; TTL 5 min prevents all reads hitting DB.
- **Write-through invalidation:** On booking confirmation, `seats:F101` key is deleted so next read repopulates fresh data.
- If Redis is down at **write time**, cache invalidation silently fails → acceptable because TTL eventually expires.

---

### 2.3 Payment Gateway Failure - Timeout & Retry

```mermaid
sequenceDiagram
    autonumber
    actor Alice
    participant API as API Service
    participant PAY as Payment Gateway
    participant Kafka as Kafka
    participant Sched as Scheduler
    participant DB as PostgreSQL

    Note over Alice,DB: ATTEMPT 1 - Timeout
    Alice->>API: POST /bookings/B900/payment
    API->>PAY: Charge 4500 UPI
    PAY--XAPI: TIMEOUT (no response in 30s)
    API->>DB: UPDATE bookings.schedule_retry = NOW()+1min, attempts=1
    API-->>Alice: 202 "Payment processing, check status"

    Note over Alice,DB: ATTEMPT 2 (after backoff)
    Sched->>API: Trigger retry (attempt 2)
    API->>PAY: Charge 4500 UPI (idempotency key: B900)
    PAY--XAPI: TIMEOUT again → retry at NOW()+5min

    Note over Alice,DB: ATTEMPT 3 (final)
    Sched->>API: Trigger retry (attempt 3)
    API->>DB: payments.status='failed' WHERE booking_id='B900'
    API->>DB: bookings.status='cancelled' (seat 12A released)
    API->>DB: UPDATE seats SET status='available'
    API->>Redis: DEL seats:F101
    API->>Kafka: PUBLISH payment.events {PAYMENT_FAILED}
    Kafka->>NOTIF: Notification Service
    NOTIF-->>Alice: "Payment failed, booking cancelled"

    Note over API,DB: Recovery is safe because idempotency key prevents<br/>double charge, status machine prevents double-cancel
```

**Retry policy:**
| Attempts | Delay | Result |
|----------|-------|--------|
| 1 | immediate | 30s timeout |
| 2 | +1 min | 30s timeout |
| 3 | +5 min (exponential) | failed → booking cancelled, seat released |
| DLQ | — | Marked for manual review, alert to ops team |

**Idempotency protection:** Payment gateway call carries `Idempotency-Key: B900`. Even if retries overlap, the gateway returns the same transaction for the same key → no double charge.

---

### 2.4 Kafka Failure - Event Buffering & Delivery Guarantee

```mermaid
sequenceDiagram
    autonumber
    participant API as API Service
    participant Kafka as Kafka (Broker down)
    participant NOTIF as Notification Service
    participant Redis as Redis
    participant DB as PostgreSQL

    API->>Kafka: PUBLISH booking.events
    Note over API,Kafka: Broker unavailable → producer exception

    Note over API: KAFKA PATTERN A - Sync (block & retry)
    API->>Kafka: retry x3 (exponential backoff)
    Kafka--XAPI: still down
    API->>DB: INSERT INTO outbox_events (payload, status='PENDING')
    API-->>Alice: 201 Created (booking still succeeds, event waits)

    Note over API: KAFKA PATTERN B - Async (fire & tolerate)
    API->>Kafka: publish (async, no await)
    API-->>Alice: 201 Created immediately
    Note over NOTIF: If event lost → notification eventually consistent<br/>via scheduled compensation job that scans outbox_events

    Note over Redis,Kafka: RECOVERY
    Kafka-->>API: Broker back online
    API->>DB: SELECT * FROM outbox_events WHERE status='PENDING'
    API->>Kafka: REPLAY pending events to kafka
    API->>DB: UPDATE outbox_events SET status='SENT'
```

**Key guarantees (from scalability-performance.md):**
- Replication factor 3, min in-sync replicas 2
- Acks=all for critical events (`payment.events`, `booking.events`)
- **Outbox pattern** ensures no event is lost when Kafka is down: events are written to DB first, then a relay publishes them.
- Consumer lag is monitored via Prometheus → alert when consumers fall behind.

---

### 2.5 Database / Shard Failure

```mermaid
graph TD
    A[API writes to shard 2] --> B{Is shard 2 healthy?}
    B -->|Yes| C[Write succeeds]
    B -->|No| D{Is a replica promoted?}
    D -->|Yes| E[Replica becomes new primary<br/>API retries write]
    D -->|No| F[API returns 503<br/>Kubernetes restarts pod<br/>Circuit breaker on shard 2]
    F --> G{scheduler retries?}
    G -->|Yes| H[Resume once shard recovers]
    G -->|No| I[Event stored in outbox<br/>DB replay when healthy]
```

```mermaid
sequenceDiagram
    autonumber
    participant API as API Service
    participant DB as Shard 2 Primary
    participant Replica as Shard 2 Replica
    participant LB as Load Balancer
    participant K8S as Kubernetes

    API->>DB: INSERT INTO bookings ...
    DB--XAPI: Connection lost (primary crashed)
    Note over API: DB connection pool marks node dead
    API->>LB: (health check to pod passes - app layer recovers)
    K8S->>K8S: Detect primary down via probes
    Replica->>Replica: Promoted to PRIMARY (automatic failover)
    API->>Replica: RETRY INSERT (with idempotent booking_id UUID)
    Replica-->>API: Success (commit)
    API-->>Alice: 201 Created (slightly delayed, user retries)
```

**Protections:**
- Write requests use UUID as PRIMARY KEY → idempotent, safe to retry.
- PostgreSQL fails over to replica automatically (RTO 15 min, RPO 5 min target).
- Shard routing is at the app layer → does not depend on DB topology changes.
- If a shard is down, that region's traffic still works (flights distributed by region).

---

### 2.6 Notification Delivery Failure

```mermaid
sequenceDiagram
    autonumber
    participant Kafka as Kafka (notification.email)
    participant W as Email Worker
    participant P as Email Provider (SendGrid/SES)
    participant DLQ as Dead Letter Queue

    Kafka->>W: Consume notification.email (booking confirmation)
    W->>P: Send email
    P--XW: 500 / timeout
    W->>W: RETRY 1 (backoff 1s)
    W->>P: Send email
    P--XW: 500 again
    W->>W: RETRY 2 (backoff 5s)
    W->>P: Send email
    P--XW: still failing
    W->>W: RETRY 3 (backoff 25s, max exceeded)
    W->>DLQ: Push dead-letter (message preserved)
    DLQ-->>Ops: Alert - manual intervention or trigger alternate channel (SMS fallback)
```

**Multi-channel fallback:**
| Channel | On Success | On Failure |
|---------|------------|------------|
| Email | Confirm sent | Retry x3 → if fail, try SMS |
| SMS | Confirm sent | Retry x3 → if fail, alert + DLQ |
| Push | Confirm sent | Best-effort (no retry, push is disposable) |

**User notification guarantee:** Even if all channels fail at delivery, the user can always check `GET /bookings/{id}` in-app, which reads from DB (source of truth). Notifications are nice-to-have; booking state is guaranteed.

---

### 2.7 Kubernetes / Load Balancer Failure

```mermaid
graph LR
    A[LB health check fails on Pod 2] --> B[LB stops routing to Pod 2]
    B --> C[K8s restarts Pod 2<br/>livenessProbe fails → container restart]
    C --> D[Pod 2 ready again → LB resumes routing]

    style A fill:#ffcccc
    style B fill:#ffe6cc
    style C fill:#e6ffe6
    style D fill:#ccffcc
```

**Detailed sequence:**
1. Pod 2 becomes unhealthy (memory leak, hung request).
2. Liveness probe (`/health/live`) fails 3 times → container killed & restarted by kubelet.
3. Readiness probe (`/health/ready`) fails → pod removed from Service endpoints → LB stops sending traffic.
4. Container restarts; on restart, `readinessProbe` passes → pod re-added to LB rotation.
5. **HPA** sees elevated CPU across cluster → scales 3 → 10 pods for surge load.

**Session affinity note:** If a user was mid-payment on Pod 2 and it dies, the user's request fails at LB layer → client retries → lands on Pod 3 → because booking/payment state is in DB, **retry succeeds** without loss.

---

## SCENARIO 3: Retry & Recovery Matrix (Complete Reference)

| # | Component Failure | User Impact | Retry Mechanism | Recovery | Guarantee |
|---|-------------------|-------------|-----------------|----------|-----------|
| 1 | Seat taken (concurrent booking) | 409 error | User re-selects seat | Atomic conditional UPDATE, row locks | No double-booking |
| 2 | Redis down | Slight latency | API falls back to DB | Circuit breaker + TTL cache | Read availability |
| 3 | Payment timeout | Transaction pending | Scheduler retries (1m, 5m) × 3 → cancel | Idempotency key prevents double charge | Eventually consistent |
| 4 | Kafka down | Notification delayed | Outbox pattern in DB | Relay replays pending events | No event loss |
| 5 | DB shard down | 503 on region | K8s restart + replica failover | Auto-promotion, idempotent UUID retry | RTO 15m / RPO 5m |
| 6 | Email/SMS provider down | User misses notification | Exponential backoff ×3 → DLQ | SMS fallback, in-app booking status | Best-effort notify, DB is truth |
| 7 | Pod killed | Temporary timeout | Client retries via LB | Liveness/readiness probes, HPA scale-out | Stateless API, state in DB |
| 8 | Load balancer down | All traffic lost | DNS failover to secondary LB | Health checks + multi-AZ | High availability |

---

## SCENARIO 4: Full Lifecycle State Change (Liked by Design)

```
User Search      →  Flight Selected   →  Booking PENDING   →  Payment PENDING
     │                    │                    │                   │
     v                    v                    v                   v
 ┌────────┐        ┌────────────┐      ┌────────────┐      ┌───────────────┐
 │ Flight │        │ Seat       │      │ Booking    │      │ Payment       │
 │ list   │        │ RESERVED   │      │ (pending)  │      │ (pending)     │
 └────────┘        └────────────┘      └────────────┘      └───────────────┘
        ───────────────────────────────────────────────────────────┘
                                   │
                        Webhook PAYMENT_SUCCESS
                                   │
                                   v
                    ┌─────────────────────────────┐
                    │  Booking CONFIRMED          │
                    │  Seat BOOKED                │
                    │  Payment COMPLETED          │
                    │  Cache Invalidated          │
                    │  Kafka → Notification       │
                    └─────────────────────────────┘
                                   │
                   ┌───────────────┴───────────────┐
                   │                               │
                   v                               v
        ┌──────────────────┐           ┌──────────────────┐
        │ Flight departs   │           │ User cancels     │
        │ Booking COMPLETED│           │ Booking CANCELLED│
        │                  │           │ Seat AVAILABLE   │
        │                  │           │ Payment REFUNDED │
        └──────────────────┘           └──────────────────┘
```

---

## SCENARIO 5: High Concurrency - Flash Sale (e.g., 1000 users, 1 flight)

**Problem:** Flight F200 has 80 economy seats. 1,000 users hammer book simultaneously.

```mermaid
sequenceDiagram
    autonumber
    participant LB as Load Balancer
    participant K8S as Kubernetes (scales 3→10 pods)
    participant Redis as Redis (rate limit + cache)
    participant API as API Pods
    participant DB as PostgreSQL (flights shard)

    Note over LB: 1000 concurrent requests hit LB
    LB->>K8S: Distribute across 10 API pods
    K8S->>K8S: HPA triggered (CPU > 70%) auto-scale

    loop Each booking request
        API->>Redis: INCR rate:{ip}:window (rate limit check)
        Redis-->>API: within limit → proceed, else 429
        API->>DB: Atomic claim - UPDATE seats WHERE available LIMIT 1
        DB-->>API: success for first 80, 0 rows for rest
    end

    Note over DB: 80 succeed, 920 receive 409 "sold out"
    API->>Redis: DEL seats:F200 (invalidate cache once sold out)
    API->>Kafka: PUBLISH flight.events {FLIGHT_SOLD_OUT}
    Kafka->>NOTIF: Notification service
    NOTIF-->>Users: "Sold out" / waitlist available
```

> **Note:** SQL is kept outside the diagram. Mermaid message text renders plain-flow only. The actual seat-claim statement:
>
> ```sql
> BEGIN;
> UPDATE seats SET status='reserved'
> WHERE status='available'   -- 0 rows = seat gone, 1 row = claimed
> LIMIT 1;
> COMMIT;
> ```

**Scaling protections implemented:**
- **Rate limiting** in Redis (`rate:{ip}`) prevents single-user flooding.
- **Opt-out of caching** for seat check during flash sale (or 1s TTL) to avoid cache stampede.
- **Conditional UPDATE** as seat-slot claim is atomic; PostgreSQL queues row locks naturally.
- **HPA** scales API pods 3→10; DB sharding spreads load across region shards.

---

## SCENARIO 6: Cross-Shard Query Challenge

**Scenario:** An admin/reporting query `SELECT region, COUNT(*) FROM bookings GROUP BY region` spans all shards.

```mermaid
graph TD
    A[Analytics Query] --> R1[Run per-shard sub-query<br/>Shard 1: APAC counts]
    A --> R2[Run per-shard sub-query<br/>Shard 2: EU counts]
    A --> R3[Run per-shard sub-query<br/>Shard 3: US counts]
    R1 --> M[Merge results in app layer]
    R2 --> M
    R3 --> M
    M --> Out[Return combined report]
```

**Preferred approach (documented in scalability-performance.md):**
- **Denormalize** booking rows with `user_region` column copied at write-time → single-shard reads for user-scoped queries.
- **Materialized views** refreshed from Kafka `audit.logs` for analytics (read-only replica attached to analytics consumer group).
- **Reference tables** (airlines) replicated across all shards to avoid cross-shard joins.
- Use Kafka events (`booking.events`) → data warehouse for complex reporting instead of querying live shards.

---

## Operational Alerting (Alerts that trigger ops intervention)

| Alert | Metric | Action |
|-------|--------|--------|
| Booking success rate < 99% | Prometheus counter | Pager, investigate DB lock contention |
| Payment success rate < 90% | Prometheus counter | Pager, check payment gateway webhooks |
| Kafka consumer lag > 1000 | consumer_lag metric | Check Notification/Logger workers |
| Cache hit ratio < 70% | redis cache hit ratio | Review TTL and key design |
| p99 latency > 2s | request duration histogram | Scale pods, check DB slow queries |
| Shard down > 5 min | shard health probe | Restore from replica / backup recovery |
| DLQ depth > 100 | dead letter count | Manual replay or notification audit |

---

## Key Design Principles (Summary)

1. **DB is the source of truth** — always consistent; Redis/Kafka are accelerators, never authoritative for critical data.
2. **Events are never lost** — Kafka acks=all + outbox pattern in DB for critical events.
3. **Seat booking race is solved at the DB level** — atomic conditional UPDATE, not app-level locks.
4. **Stateless API + stateful DB/queue** — any pod can die; retries land anywhere and still succeed.
5. **Idempotency everywhere** — UUID PKs, idempotency keys on payments, outbox event replays safe.
6. **Notifications are best-effort; booking state is guaranteed** — user can always query in-app.
7. **Failures are staggered, not cascading** — circuit breakers, backoff, DLQs, fallback channels.