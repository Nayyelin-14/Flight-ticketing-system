# <span style="color:#ff6b6b">Component Design</span>

### <span style="color:#4ecdc4">1. Search Service</span>

**<span style="color:#ffe66d">Responsibility:</span>** <span style="color:#ffffff">Handle flight search queries and return available flights.</span>

| <span style="color:#ff6b6b">Component</span> | <span style="color:#ff6b6b">Description</span> |
| --------------- | --------------------------------------------------------- |
| <span style="color:#4ecdc4">Debounce Layer</span> | <span style="color:#ffffff">Prevents excessive API calls from rapid user inputs</span> |
| <span style="color:#4ecdc4">Cache (Redis)</span> | <span style="color:#ffffff">Caches frequent search results to reduce Amadeus calls</span> |
| <span style="color:#4ecdc4">Elasticsearch</span> | <span style="color:#ffffff">Full-text search for flights, airports, and routes</span> |
| <span style="color:#4ecdc4">Amadeus Adapter</span> | <span style="color:#ffffff">Fetches live flight data from Amadeus Self-Service APIs</span> |
| <span style="color:#4ecdc4">DB (Indexed)</span> | <span style="color:#ffffff">PostgreSQL with indexed columns for fast search queries</span> |

#### <span style="color:#4ecdc4">Data Flow</span>

```mermaid
graph LR
    A[Client] --> B[Search Service]
    B --> C{Redis Cache}
    C -->|HIT| D[Return Cached]
    C -->|MISS| E[Elasticsearch]
    E --> F[Amadeus API]
    F --> G[(Database - Indexed)]

    style A fill:#2d3436,stroke:#00b894,color:#000
    style B fill:#0984e3,stroke:#00b894,color:#000
    style C fill:#e17055,stroke:#00b894,color:#000
    style D fill:#00b894,stroke:#0984e3,color:#000
    style E fill:#6c5ce7,stroke:#00b894,color:#000
    style F fill:#fdcb6e,stroke:#e17055,color:#000
    style G fill:#e84393,stroke:#00b894,color:#000
```

---

### <span style="color:#4ecdc4">2. Seat Management Service</span>

**<span style="color:#ffe66d">Responsibility:</span>** <span style="color:#ffffff">Manage seat selection, availability, and concurrency control.</span>

| <span style="color:#ff6b6b">Component</span> | <span style="color:#ff6b6b">Description</span> |
| ---------------- | ------------------------------------------------- |
| <span style="color:#4ecdc4">WebSocket</span> | <span style="color:#ffffff">Real-time seat updates to all connected clients</span> |
| <span style="color:#4ecdc4">Redis Locks</span> | <span style="color:#ffffff">Distributed locks to prevent double-booking</span> |
| <span style="color:#4ecdc4">Concurrency Ctrl</span> | <span style="color:#ffffff">Ensures only one user can select a seat at a time</span> |
| <span style="color:#4ecdc4">DB (Indexed)</span> | <span style="color:#ffffff">PostgreSQL with indexed seat/flight columns</span> |

#### <span style="color:#4ecdc4">Concurrency Flow</span>

```mermaid
sequenceDiagram
    participant C1 as Client 1
    participant C2 as Client 2
    participant WS as WebSocket
    participant Redis as Redis Lock
    participant DB as Database

    C1->>WS: Select Seat 12A
    WS->>Redis: Acquire Lock (seat:12A)
    Redis-->>WS: Lock Acquired
    C2->>WS: Select Seat 12A
    WS->>Redis: Acquire Lock (seat:12A)
    Redis-->>WS: Lock Denied (already locked)
    WS-->>C2: Seat Unavailable
    C1->>WS: Confirm Seat
    WS->>DB: Save Seat
    WS->>Redis: Release Lock
    WS-->>C1: Seat Confirmed
    WS-->>C2: Seat Taken (broadcast)

    rect rgba(9, 132, 227, 0.3)
        Note over C1,C2: Client Requests
    end
    rect rgba(225, 112, 85, 0.3)
        Note over WS,DB: Service Processing
    end
```

---

### <span style="color:#4ecdc4">3. Booking Service</span>

**<span style="color:#ffe66d">Responsibility:</span>** <span style="color:#ffffff">Manage the full booking flow from seat selection to payment to confirmation.</span>

| <span style="color:#ff6b6b">Component</span> | <span style="color:#ff6b6b">Description</span> |
| ----------------- | ------------------------------------------------------------- |
| <span style="color:#4ecdc4">Idempotent API</span> | <span style="color:#ffffff">Prevents duplicate bookings from retry attempts</span> |
| <span style="color:#4ecdc4">Retry Logic</span> | <span style="color:#ffffff">Automatically retries failed requests with exponential backoff</span> |
| <span style="color:#4ecdc4">Payment Processor</span> | <span style="color:#ffffff">Handles payment verification before confirming booking</span> |
| <span style="color:#4ecdc4">DB (Transactional)</span> | <span style="color:#ffffff">Ensures atomicity across booking, seat, and payment records</span> |

#### <span style="color:#4ecdc4">Booking Flow</span>

```mermaid
sequenceDiagram
    participant C as Client
    participant B as Booking Service
    participant S as Seat Service
    participant P as Payment Service
    participant DB as Database

    C->>B: Select Seat + Book
    B->>S: Reserve Seat
    S-->>B: Seat Reserved
    B->>P: Process Payment
    alt Payment Success
        P-->>B: Payment Confirmed
        B->>DB: Save Booking (idempotent key)
        B-->>C: Booking Confirmed
    else Payment Failed
        P-->>B: Payment Failed
        B->>S: Release Seat
        B-->>C: Booking Failed
    end

    rect rgba(108, 92, 231, 0.3)
        Note over C,DB: Booking Flow
    end
    rect rgba(253, 203, 110, 0.3)
        Note over P: Payment Processing
    end
```

#### <span style="color:#4ecdc4">Idempotency Flow</span>

```mermaid
graph LR
    A[Client Request] --> B{Idempotent Key?}
    B -->|New Key| C[Process Request]
    B -->|Duplicate Key| D[Return Previous Result]
    C --> E[Save to DB]
    E --> F[Return Response]

    style A fill:#2d3436,stroke:#00b894,color:#000
    style B fill:#0984e3,stroke:#00b894,color:#000
    style C fill:#6c5ce7,stroke:#00b894,color:#000
    style D fill:#e17055,stroke:#00b894,color:#000
    style E fill:#00b894,stroke:#0984e3,color:#000
    style F fill:#2d3436,stroke:#00b894,color:#000
```

---

### <span style="color:#4ecdc4">4. Payment Service</span>

**<span style="color:#ffe66d">Responsibility:</span>** <span style="color:#ffffff">Process payments via Chimoney API and handle success/failure.</span>

| <span style="color:#ff6b6b">Component</span> | <span style="color:#ff6b6b">Description</span> |
| ------------------- | ------------------------------------------------------- |
| <span style="color:#4ecdc4">Chimoney Adapter</span> | <span style="color:#ffffff">Integrates with Chimoney API for payment processing</span> |
| <span style="color:#4ecdc4">Success Handler</span> | <span style="color:#ffffff">Confirms payment and triggers booking confirmation</span> |
| <span style="color:#4ecdc4">Failure Handler</span> | <span style="color:#ffffff">Logs error, notifies user, and triggers seat release</span> |
| <span style="color:#4ecdc4">Retry Logic</span> | <span style="color:#ffffff">Retries failed API calls with exponential backoff</span> |

#### <span style="color:#4ecdc4">Payment Flow</span>

```mermaid
sequenceDiagram
    participant C as Client
    participant P as Payment Service
    participant CH as Chimoney API
    participant B as Booking Service
    participant N as Notification Service

    C->>P: Initiate Payment
    P->>CH: Charge User
    alt Payment Success
        CH-->>P: Payment Confirmed
        P->>B: Confirm Booking
        P->>N: Send Receipt
        P-->>C: Payment Successful
    else Payment Failed
        CH-->>P: Payment Failed
        P->>B: Release Seat
        P->>N: Send Failure Alert
        P-->>C: Payment Failed
    end

    rect rgba(9, 132, 227, 0.3)
        Note over C,N: Payment Flow
    end
    rect rgba(225, 112, 85, 0.3)
        Note over CH: Chimoney API
    end
```

#### <span style="color:#4ecdc4">Success/Failure Handling</span>

```mermaid
graph LR
    A[Chimoney Response] --> B{Status?}
    B -->|Success| C[Confirm Booking]
    C --> D[Send Receipt]
    D --> E[Return Success]
    B -->|Failure| F[Log Error]
    F --> G[Release Seat]
    G --> H[Notify User]
    H --> I[Return Failure]

    style A fill:#2d3436,stroke:#00b894,color:#000
    style B fill:#0984e3,stroke:#00b894,color:#000
    style C fill:#00b894,stroke:#0984e3,color:#000
    style D fill:#00b894,stroke:#0984e3,color:#000
    style E fill:#00b894,stroke:#0984e3,color:#000
    style F fill:#e17055,stroke:#00b894,color:#000
    style G fill:#e17055,stroke:#00b894,color:#000
    style H fill:#e17055,stroke:#00b894,color:#000
    style I fill:#e17055,stroke:#00b894,color:#000
```

---

### <span style="color:#4ecdc4">5. Ticketing Service</span>

**<span style="color:#ffe66d">Responsibility:</span>** <span style="color:#ffffff">Generate, store tickets with PNR and send email/SMS notifications.</span>

| <span style="color:#ff6b6b">Component</span> | <span style="color:#ff6b6b">Description</span> |
| ----------------- | ------------------------------------------------------- |
| <span style="color:#4ecdc4">Ticket Generator</span> | <span style="color:#ffffff">Creates unique ticket with PNR linked to flight booking</span> |
| <span style="color:#4ecdc4">PNR Manager</span> | <span style="color:#ffffff">Manages Passenger Name Record for flight check-in</span> |
| <span style="color:#4ecdc4">Email Service</span> | <span style="color:#ffffff">Sends ticket and booking confirmation via email</span> |
| <span style="color:#4ecdc4">SMS Service</span> | <span style="color:#ffffff">Sends ticket and booking confirmation via SMS</span> |

#### <span style="color:#4ecdc4">Ticket Flow</span>

```mermaid
sequenceDiagram
    participant B as Booking Service
    participant T as Ticketing Service
    participant DB as Database
    participant E as Email Service
    participant S as SMS Service
    participant C as Client

    B->>T: Payment Confirmed
    T->>T: Generate PNR
    T->>T: Generate Ticket
    T->>DB: Store Ticket + PNR
    T->>E: Send Ticket Email
    T->>S: Send Ticket SMS
    E-->>C: Email Delivered
    S-->>C: SMS Delivered
    T-->>B: Ticket Issued

    rect rgba(108, 92, 231, 0.3)
        Note over B,T: Ticket Generation
    end
    rect rgba(0, 184, 148, 0.3)
        Note over E,S: Notification Delivery
    end
```

#### <span style="color:#4ecdc4">PNR Structure</span>

| <span style="color:#ff6b6b">Field</span> | <span style="color:#ff6b6b">Description</span> |
| ----------- | ----------------------------------------- |
| <span style="color:#4ecdc4">PNR Code</span> | <span style="color:#ffffff">6-character unique booking reference</span> |
| <span style="color:#4ecdc4">Flight Info</span> | <span style="color:#ffffff">Flight number, route, date, time</span> |
| <span style="color:#4ecdc4">Passenger Info</span> | <span style="color:#ffffff">Name, contact, passport details</span> |
| <span style="color:#4ecdc4">Seat Number</span> | <span style="color:#ffffff">Assigned seat (e.g. 12A)</span> |
| <span style="color:#4ecdc4">Booking Status</span> | <span style="color:#ffffff">Confirmed / Pending / Cancelled</span> |

#### <span style="color:#4ecdc4">Success/Failure Handling</span>

```mermaid
graph TD
    A[Generate Ticket] --> B{PNR Created?}
    B -->|Yes| C[Store in DB] --> D[Send Email + SMS] --> E[Return Success]
    B -->|No| F[Log Error] --> G{Retries Left?}
    G -->|Yes| A
    G -->|No| H[Alert Admin] --> I[Return Failure]

    style A fill:#6c5ce7,stroke:#00b894,color:#000
    style B fill:#0984e3,stroke:#00b894,color:#000
    style C fill:#00b894,stroke:#0984e3,color:#000
    style D fill:#00b894,stroke:#0984e3,color:#000
    style E fill:#00b894,stroke:#0984e3,color:#000
    style F fill:#e17055,stroke:#00b894,color:#000
    style G fill:#0984e3,stroke:#00b894,color:#000
    style H fill:#e17055,stroke:#00b894,color:#000
    style I fill:#e17055,stroke:#00b894,color:#000
```

---

> <span style="color:#ff6b6b">**Status:**</span> <span style="color:#ffffff">Search, Seat Management, Booking, Payment, and Ticketing services detailed. Other services to be added.</span>
