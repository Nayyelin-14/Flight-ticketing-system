# <span style="color:#ff6b6b">System Design & Architecture</span>

## <span style="color:#4ecdc4">Flight Booking Backend with FastAPI</span>

## <span style="color:#ffe66d">Functional Requirements</span>

| <span style="color:#ff6b6b">#</span> | <span style="color:#ff6b6b">Feature</span> | <span style="color:#ff6b6b">Description</span> |
| --- | ------------------- | ----------------------------------------------------------------------------- |
| <span style="color:#4ecdc4">1</span> | <span style="color:#ffffff">Search Flight</span> | <span style="color:#ffffff">Users can search for available flights by route, date, and passenger count.</span> |
| <span style="color:#4ecdc4">2</span> | <span style="color:#ffffff">View Flight Details</span> | <span style="color:#ffffff">Users can view full details of a specific flight including pricing and stops.</span> |
| <span style="color:#4ecdc4">3</span> | <span style="color:#ffffff">User Authentication</span> | <span style="color:#ffffff">Users can register, log in, and access protected endpoints via JWT tokens.</span> |
| <span style="color:#4ecdc4">4</span> | <span style="color:#ffffff">Ticket Issuance</span> | <span style="color:#ffffff">System generates and assigns a unique ticket upon successful booking.</span> |
| <span style="color:#4ecdc4">5</span> | <span style="color:#ffffff">Seat Selection</span> | <span style="color:#ffffff">Users can choose or change their preferred seat before checkout.</span> |
| <span style="color:#4ecdc4">6</span> | <span style="color:#ffffff">Booking History</span> | <span style="color:#ffffff">Users can view all past and upcoming bookings linked to their account.</span> |
| <span style="color:#4ecdc4">7</span> | <span style="color:#ffffff">Payment</span> | <span style="color:#ffffff">Users can complete payments securely via integrated payment providers.</span> |
| <span style="color:#4ecdc4">8</span> | <span style="color:#ffffff">Cancel Flight</span> | <span style="color:#ffffff">Users can cancel a booking and receive applicable refunds.</span> |

---

## <span style="color:#ffe66d">Non-Functional Requirements</span>

| <span style="color:#ff6b6b">#</span> | <span style="color:#ff6b6b">Requirement</span> | <span style="color:#ff6b6b">Description</span> |
| --- | ----------------- | ------------------------------------------------------------------------------ |
| <span style="color:#4ecdc4">1</span> | <span style="color:#ffffff">High Availability</span> | <span style="color:#ffffff">System stays operational with minimal downtime using redundant infrastructure.</span> |
| <span style="color:#4ecdc4">2</span> | <span style="color:#ffffff">Scalability</span> | <span style="color:#ffffff">Architecture handles millions of concurrent users through horizontal scaling.</span> |
| <span style="color:#4ecdc4">3</span> | <span style="color:#ffffff">Low Latency</span> | <span style="color:#ffffff">API responses remain fast (<200ms) via caching and optimized queries.</span> |
| <span style="color:#4ecdc4">4</span> | <span style="color:#ffffff">Consistency</span> | <span style="color:#ffffff">Booking data stays accurate and synchronized across all services.</span> |
| <span style="color:#4ecdc4">5</span> | <span style="color:#ffffff">Resilience</span> | <span style="color:#ffffff">System recovers gracefully from failures using retries and circuit breakers.</span> |
| <span style="color:#4ecdc4">6</span> | <span style="color:#ffffff">Data Integrity</span> | <span style="color:#ffffff">All transactions follow ACID guarantees to prevent duplicate or lost bookings.</span> |

---

## <span style="color:#4ecdc4">High-Level Architecture</span>

```mermaid
graph TD
    subgraph CLIENTS["CLIENTS"]
        direction LR
        WEB["Web App"]
        MOB["Mobile App"]
    end

    subgraph GATEWAY["API GATEWAY"]
        direction LR
        RL["Rate Limiting"]
        AUTH_GW["Auth"]
        LB["Load Balancing"]
        SSL["SSL/TLS Termination"]
    end

    subgraph SERVICES["BACKEND SERVICES"]
        direction LR
        SEARCH["Search Service"]
        BOOKING["Booking Service"]
        PAYMENT_SVC["Payment Service"]
        NOTIFY["Notifications Service"]
        USER["User/Auth Service"]
        SEAT["Seat Service"]
    end

    subgraph DATA["DATABASES & EXTERNAL SYSTEMS"]
        direction LR
        PG["PostgreSQL\nPrimary DB"]
        REDIS["Redis\nCache"]
        PAY_GW["Payment Gateway"]
        AMADEUS["Amadeus APIs\n3rd Party"]
    end

    WEB --> GATEWAY
    MOB --> GATEWAY

    GATEWAY --> SEARCH
    GATEWAY --> BOOKING
    GATEWAY --> PAYMENT_SVC
    GATEWAY --> NOTIFY
    GATEWAY --> USER
    GATEWAY --> SEAT

    SEARCH --> DATA
    BOOKING --> DATA
    PAYMENT_SVC --> DATA
    NOTIFY --> DATA
    USER --> DATA
    SEAT --> DATA

    style CLIENTS fill:#2d3436,stroke:#00b894,color:#000
    style GATEWAY fill:#0984e3,stroke:#00b894,color:#000
    style SERVICES fill:#6c5ce7,stroke:#00b894,color:#000
    style DATA fill:#e17055,stroke:#00b894,color:#000

    style WEB fill:#00b894,stroke:#0984e3,color:#000
    style MOB fill:#00b894,stroke:#0984e3,color:#000
    style RL fill:#fdcb6e,stroke:#e17055,color:#000
    style AUTH_GW fill:#fdcb6e,stroke:#e17055,color:#000
    style LB fill:#fdcb6e,stroke:#e17055,color:#000
    style SSL fill:#fdcb6e,stroke:#e17055,color:#000
    style SEARCH fill:#e84393,stroke:#00b894,color:#000
    style BOOKING fill:#e84393,stroke:#00b894,color:#000
    style PAYMENT_SVC fill:#e84393,stroke:#00b894,color:#000
    style NOTIFY fill:#e84393,stroke:#00b894,color:#000
    style USER fill:#e84393,stroke:#00b894,color:#000
    style SEAT fill:#e84393,stroke:#00b894,color:#000
    style PG fill:#fdcb6e,stroke:#e17055,color:#000
    style REDIS fill:#fdcb6e,stroke:#e17055,color:#000
    style PAY_GW fill:#fdcb6e,stroke:#e17055,color:#000
    style AMADEUS fill:#fdcb6e,stroke:#e17055,color:#000
```

### <span style="color:#4ecdc4">Architecture Layers</span>

| <span style="color:#ff6b6b">Layer</span> | <span style="color:#ff6b6b">Components</span> | <span style="color:#ff6b6b">Purpose</span> |
| ------------------------ | -------------------------------------------------------- | --------------------------------------------- |
| <span style="color:#4ecdc4">**Client**</span> | <span style="color:#ffffff">Web App, Mobile App</span> | <span style="color:#ffffff">User interface for end users</span> |
| <span style="color:#4ecdc4">**API Gateway**</span> | <span style="color:#ffffff">Rate limiting, Auth, Load balancing, SSL/TLS</span> | <span style="color:#ffffff">Single entry point, security, traffic mgmt</span> |
| <span style="color:#4ecdc4">**Backend Services**</span> | <span style="color:#ffffff">Search, Booking, Payment, Notifications, User/Auth, Seat</span> | <span style="color:#ffffff">Core business logic (microservices)</span> |
| <span style="color:#4ecdc4">**Databases / External**</span> | <span style="color:#ffffff">PostgreSQL, Redis, Payment Gateway, Amadeus APIs</span> | <span style="color:#ffffff">Data storage, caching, 3rd party integrations</span> |

---

> <span style="color:#ff6b6b">**Status:**</span> <span style="color:#ffffff">This document outlines the initial brief. Architecture details (tech stack, API design, data models) to be expanded.</span>
