# Architecture

## Overview

Local AI Chat is a self-hosted conversational AI app. Everything runs on your machine — no cloud, no API keys. The architecture is intentionally simple: three layers communicating over local HTTP and WebSocket connections.

```
┌─────────────────────────────────────────────────────────┐
│                      Your Device                        │
│                                                         │
│  ┌──────────┐    WebSocket     ┌──────────────────┐     │
│  │          │◄────────────────►│                  │     │
│  │ Frontend │    HTTP/REST     │  FastAPI Server   │     │
│  │ (Browser)│◄────────────────►│  (server.py)     │     │
│  │          │                  │                  │     │
│  └──────────┘                  └────────┬─────────┘     │
│       ▲                             │        │          │
│       │                        HTTP │   SQLite│          │
│       │                        Stream    R/W  │          │
│       │                             │        │          │
│       │                        ┌────▼──┐ ┌───▼────┐     │
│       │                        │Ollama │ │chats.db│     │
│       │                        │Server │ └────────┘     │
│       │                        └───┬───┘                │
│       │                            │                    │
│       │                       ┌────▼─────┐              │
│       │                       │ LLM Model│              │
│       │                       │(llama.cpp)│              │
│       │                       └──────────┘              │
│       │                                                 │
│  ┌────┴─────┐  (optional)                               │
│  │  ngrok   │──── public URL ───► Phone browser         │
│  └──────────┘                                           │
└─────────────────────────────────────────────────────────┘
```

## Components

### 1. Frontend (`frontend/index.html`)

A single-file SPA served by FastAPI. No build step, no framework, no dependencies.

- **Rendering**: Vanilla JS with a lightweight markdown parser
- **Communication**: WebSocket for chat streaming, REST for chat management
- **State**: In-memory JS objects, synced with the backend on every action
- **Theming**: CSS custom properties with dark/light toggle (persisted in `localStorage`)
- **Mobile**: Responsive layout with collapsible sidebar, safe-area handling for iOS

**Key interactions:**
| Action | Protocol | Endpoint |
|--------|----------|----------|
| List chats | GET | `/api/chats` |
| Create chat | POST | `/api/chats` |
| Delete chat | DELETE | `/api/chats/{id}` |
| Load messages | GET | `/api/chats/{id}/messages` |
| Send message & stream response | WebSocket | `/ws/chat/{id}` |
| List models | GET | `/api/models` |

### 2. Backend (`server.py`)

FastAPI async server — handles REST endpoints, WebSocket connections, and proxies to Ollama.

**Request flow for a chat message:**

```
User types message
       │
       ▼
Frontend sends JSON via WebSocket
       │
       ▼
Backend saves user message to SQLite
       │
       ▼
Backend loads full conversation history from SQLite
       │
       ▼
Backend sends POST to Ollama /api/chat (stream=true)
       │
       ▼
Ollama streams tokens back via chunked HTTP response
       │
       ▼
Backend forwards each token to frontend via WebSocket
       │
       ▼
Frontend renders tokens incrementally (markdown parsed live)
       │
       ▼
On stream complete, backend saves full response to SQLite
```

**Why WebSocket instead of SSE?**
- Bidirectional — the same connection handles sending messages and receiving tokens
- No need to reconnect between messages in the same chat
- Simpler client code for handling multiple message types (token, done, error, title)

### 3. Ollama

Ollama wraps `llama.cpp` with a REST API. It handles:
- Model downloading and management
- Quantization (models are pre-quantized for efficiency)
- GPU acceleration via Metal (Apple Silicon) or CUDA (NVIDIA)
- Context window management and KV cache

The backend communicates with Ollama over `http://localhost:11434`. This is a standard HTTP API — Ollama could be swapped for any OpenAI-compatible API with minimal changes.

### 4. SQLite (`chats.db`)

Simple two-table schema:

```sql
chats
├── id TEXT PRIMARY KEY        -- 12-char hex UUID
├── title TEXT                 -- auto-set from first message
├── created_at REAL            -- unix timestamp
└── updated_at REAL            -- unix timestamp

messages
├── id INTEGER PRIMARY KEY     -- autoincrement
├── chat_id TEXT FK→chats.id   -- cascade delete
├── role TEXT                  -- "user" or "assistant"
├── content TEXT               -- raw message text
└── created_at REAL            -- unix timestamp
```

- Foreign keys with cascade delete — deleting a chat removes all its messages
- Max 10 chats enforced at the application level (oldest auto-deleted)
- No ORM — raw async SQL via `aiosqlite`

### 5. ngrok tunnel (optional)

Creates a public HTTPS URL that tunnels to `localhost:8000`. This allows phone access without LAN IP configuration. The tunnel is ephemeral — a new URL is generated each time.

```
Phone browser ──HTTPS──► ngrok edge server ──tunnel──► localhost:8000
```

## Data Flow Summary

```
                    ┌─────────────┐
                    │   Browser   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │ REST       │ WebSocket  │
              │            │            │
         ┌────▼────┐  ┌────▼────┐       │
         │ Chat    │  │ Message │       │
         │ CRUD    │  │ Stream  │       │
         └────┬────┘  └────┬────┘       │
              │            │            │
              └─────┬──────┘            │
                    │                   │
              ┌─────▼─────┐     ┌───────▼──────┐
              │  SQLite   │     │    Ollama     │
              │ (persist) │     │  (inference)  │
              └───────────┘     └──────────────┘
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Single HTML file | Zero build tooling, easy to modify, fast to serve |
| No frontend framework | Keeps it simple, no node_modules, works offline |
| WebSocket over SSE | Bidirectional, cleaner multi-message handling |
| SQLite over JSON files | ACID transactions, cascade deletes, indexed queries |
| Ollama over raw HuggingFace | 5-10x faster inference on Apple Silicon via llama.cpp |
| FastAPI over Flask | Native async, WebSocket support, auto-docs at `/docs` |
| 10 chat limit | Prevents unbounded storage growth on a local machine |
| No auth | Single-user local app — auth would add complexity with no benefit |

---

## Scaling Roadmap

### Phase 1: Current — Single User (1-5 users)

What we have today. Everything on one machine.

```
┌──────────────────────────────────┐
│           Single Machine         │
│                                  │
│  Browser ──► FastAPI ──► Ollama  │
│                 │                │
│              SQLite              │
└──────────────────────────────────┘
```

**Bottleneck**: GPU can only run one inference at a time.

---

### Phase 2: Multi-User — 100 Users

Add a request queue, swap SQLite for Postgres, add auth, and run multiple inference workers behind a load balancer.

```
                    ┌──────────┐
                    │  Users   │
                    │ (phones, │
                    │ browsers)│
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ Nginx /  │
                    │ Caddy    │ ◄── TLS termination, rate limiting
                    │ (reverse │
                    │  proxy)  │
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼──┐  ┌────▼──┐  ┌────▼──┐
         │FastAPI│  │FastAPI│  │FastAPI│  ◄── 2-3 app server replicas
         │  #1   │  │  #2   │  │  #3   │      (stateless, behind LB)
         └───┬───┘  └───┬───┘  └───┬───┘
             │          │          │
             └──────────┼──────────┘
                   │         │
            ┌──────▼──┐ ┌────▼──────┐
            │  Redis  │ │ Postgres  │
            │ (queue +│ │ (users,   │
            │  cache) │ │  chats,   │
            └────┬────┘ │  messages)│
                 │      └───────────┘
        ┌────────┼────────┐
        │        │        │
   ┌────▼──┐ ┌──▼────┐ ┌─▼─────┐
   │Ollama │ │Ollama │ │Ollama │  ◄── GPU workers (1 per GPU)
   │ GPU 1 │ │ GPU 2 │ │ GPU 3 │
   └───────┘ └───────┘ └───────┘
```

**Key changes from Phase 1:**

| Component | Phase 1 | Phase 2 |
|-----------|---------|---------|
| Reverse proxy | None | Nginx/Caddy with TLS |
| App servers | 1 process | 2-3 stateless replicas |
| Database | SQLite | PostgreSQL |
| Queue | None | Redis (inference job queue) |
| Inference | 1 Ollama | 2-3 Ollama workers (1 per GPU) |
| Auth | None | JWT tokens + user accounts |
| Deployment | `./start.sh` | Docker Compose |

**Why Redis?** Inference is slow (seconds). You need a queue to:
- Accept messages instantly, process them FIFO
- Prevent GPU overload when 10 users send messages at once
- Enable retry on failure

**Estimated hardware**: 1 server with 2-3 GPUs (e.g., 3x RTX 4090), or 3 separate GPU machines. ~$500-1500/mo on cloud.

---

### Phase 3: Production Scale — 10 Million Users

At this scale, you're building infrastructure, not an app. The architecture shifts to microservices, managed cloud, and purpose-built inference engines.

```
                         ┌──────────────┐
                         │   10M Users  │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │  CloudFlare  │ ◄── Global CDN, DDoS protection,
                         │  / AWS CF    │     static asset caching
                         └──────┬───────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
              ┌─────▼──┐ ┌─────▼──┐ ┌─────▼──┐
              │  API    │ │  API   │ │  API   │ ◄── Regional API clusters
              │ Gateway │ │ Gateway│ │ Gateway│     (US, EU, Asia)
              │ (Kong)  │ │        │ │        │
              └────┬────┘ └────┬───┘ └────┬───┘
                   │           │          │
         ┌─────────────────────────────────────┐
         │          Kubernetes Cluster          │
         │                                      │
         │  ┌───────────┐    ┌───────────────┐  │
         │  │ Chat      │    │ Auth Service  │  │
         │  │ Service   │    │ (OAuth, JWT)  │  │
         │  │ (FastAPI) │    └───────────────┘  │
         │  │ 20+ pods  │                       │
         │  └─────┬─────┘    ┌───────────────┐  │
         │        │          │ User Service  │  │
         │        │          │ (profiles,    │  │
         │        │          │  billing)     │  │
         │        │          └───────────────┘  │
         └────────┼─────────────────────────────┘
                  │
       ┌──────────┼──────────────┐
       │          │              │
  ┌────▼───┐ ┌───▼─────┐  ┌─────▼──────┐
  │ Kafka  │ │Postgres │  │   Redis     │
  │ (event │ │ Cluster │  │  Cluster    │
  │ stream)│ │ (RDS)   │  │(ElastiCache)│
  └───┬────┘ └─────────┘  └────────────┘
      │
      │  ┌─────────────────────────────────────────┐
      │  │       GPU Inference Fleet                │
      │  │                                          │
      │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
      └──►  │  vLLM   │ │  vLLM   │ │  vLLM   │   │
         │  │  Node 1  │ │  Node 2 │ │  Node N │   │ ◄── Auto-scaling GPU pool
         │  │ (8xA100) │ │ (8xA100)│ │(8xA100) │   │     Continuous batching
         │  └─────────┘ └─────────┘ └─────────┘   │     PagedAttention
         │                                          │
         │  ┌─────────────────────────────────┐     │
         │  │  Model Registry (S3 + cache)    │     │
         │  │  Multiple model versions/sizes  │     │
         │  └─────────────────────────────────┘     │
         └──────────────────────────────────────────┘
```

**Key changes from Phase 2:**

| Concern | Phase 2 | Phase 3 |
|---------|---------|---------|
| Inference engine | Ollama (llama.cpp) | vLLM with continuous batching & PagedAttention |
| Scaling | Manual | Kubernetes auto-scaling (pods + GPU nodes) |
| Queue | Redis | Kafka (event streaming, replay, audit) |
| Database | Single Postgres | Postgres cluster (read replicas, sharding) |
| CDN | None | CloudFlare / CloudFront for static + edge caching |
| Auth | JWT | OAuth2 + SSO + billing integration |
| Regions | Single | Multi-region (latency-sensitive) |
| GPU fleet | 2-3 GPUs | 50-200+ GPUs, auto-scaling by queue depth |
| Monitoring | Logs | Prometheus, Grafana, distributed tracing |
| Cost | ~$1K/mo | ~$200K-$1M+/mo (GPU-dominated) |

**Why vLLM over Ollama at scale?**
- **Continuous batching**: processes multiple user requests in a single GPU pass (10-50x throughput vs sequential)
- **PagedAttention**: efficient memory management, fits more concurrent contexts per GPU
- **Tensor parallelism**: splits large models across multiple GPUs on one node

**The real bottleneck at 10M users is cost.** Each inference takes ~1-5 seconds on a GPU. At 10M users doing ~10 messages/day, that's ~100M inferences/day. You need hundreds of GPUs running 24/7, which is why every company at this scale either:
1. Uses heavily quantized / smaller models to maximize throughput
2. Implements aggressive caching (common questions, system prompts)
3. Charges $20/mo per user (sound familiar?)

---

### Migration Path Summary

```
Phase 1 (Now)          Phase 2 (100 users)       Phase 3 (10M users)
─────────────          ───────────────────        ───────────────────
./start.sh        ──►  docker compose up    ──►   helm install
SQLite            ──►  PostgreSQL           ──►   Postgres cluster + sharding
Ollama            ──►  Ollama x3 + Redis    ──►   vLLM fleet + Kafka
No auth           ──►  JWT + user accounts  ──►   OAuth2 + SSO + billing
Single file HTML  ──►  React/Next.js SPA    ──►   React + CDN edge cache
localhost         ──►  Nginx + TLS          ──►   CloudFlare + API Gateway
1 machine         ──►  1 server + 3 GPUs    ──►   Kubernetes multi-region
$0/mo             ──►  $500-1500/mo         ──►   $200K-1M+/mo
```
