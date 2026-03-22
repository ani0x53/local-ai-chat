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
