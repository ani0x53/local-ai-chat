"""
Local AI Chat — FastAPI backend.
Streams responses from Ollama, persists chat history in SQLite.
"""

import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import aiohttp
import aiosqlite
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"
MAX_CHATS = 10
DB_PATH = Path(__file__).parent / "chats.db"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id)")
        await db.execute("PRAGMA foreign_keys = ON")
        await db.commit()


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

# Serve static frontend
FRONTEND_DIR = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/chats")
async def list_chats():
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT id, title, created_at, updated_at FROM chats ORDER BY updated_at DESC"
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


@app.post("/api/chats")
async def create_chat():
    db = await get_db()
    try:
        # Enforce max chats
        count_row = await db.execute_fetchall("SELECT COUNT(*) as c FROM chats")
        if count_row[0]["c"] >= MAX_CHATS:
            # Delete the oldest chat
            oldest = await db.execute_fetchall(
                "SELECT id FROM chats ORDER BY updated_at ASC LIMIT 1"
            )
            if oldest:
                await db.execute("DELETE FROM messages WHERE chat_id = ?", (oldest[0]["id"],))
                await db.execute("DELETE FROM chats WHERE id = ?", (oldest[0]["id"],))

        chat_id = uuid.uuid4().hex[:12]
        now = time.time()
        await db.execute(
            "INSERT INTO chats (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (chat_id, "New chat", now, now),
        )
        await db.commit()
        return {"id": chat_id, "title": "New chat", "created_at": now, "updated_at": now}
    finally:
        await db.close()


@app.get("/api/chats/{chat_id}/messages")
async def get_messages(chat_id: str):
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT role, content, created_at FROM messages WHERE chat_id = ? ORDER BY created_at",
            (chat_id,),
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: str):
    db = await get_db()
    try:
        await db.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        await db.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@app.put("/api/chats/{chat_id}/title")
async def update_title(chat_id: str, body: dict):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
            (body["title"], time.time(), chat_id),
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@app.get("/api/models")
async def list_models():
    """Proxy to Ollama's model list."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OLLAMA_BASE}/api/tags") as resp:
                data = await resp.json()
                return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# WebSocket — streaming chat
# ---------------------------------------------------------------------------

@app.websocket("/ws/chat/{chat_id}")
async def chat_ws(websocket: WebSocket, chat_id: str):
    await websocket.accept()

    try:
        while True:
            data = json.loads(await websocket.receive_text())
            user_msg = data.get("message", "").strip()
            model = data.get("model", DEFAULT_MODEL)
            if not user_msg:
                continue

            now = time.time()
            db = await get_db()

            # Save user message
            await db.execute(
                "INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (chat_id, "user", user_msg, now),
            )
            await db.execute(
                "UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id)
            )
            await db.commit()

            # Build context from history
            rows = await db.execute_fetchall(
                "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY created_at",
                (chat_id,),
            )
            messages = [{"role": "system", "content": "You are a helpful, friendly assistant. Give clear and concise answers. Use markdown formatting when appropriate."}]
            messages += [{"role": r["role"], "content": r["content"]} for r in rows]

            await db.close()

            # Auto-title on first user message
            if len(messages) == 2:  # system + first user
                title = user_msg[:50] + ("…" if len(user_msg) > 50 else "")
                db2 = await get_db()
                await db2.execute(
                    "UPDATE chats SET title = ? WHERE id = ?", (title, chat_id)
                )
                await db2.commit()
                await db2.close()
                await websocket.send_text(json.dumps({"type": "title", "title": title}))

            # Stream from Ollama
            full_response = ""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{OLLAMA_BASE}/api/chat",
                        json={"model": model, "messages": messages, "stream": True},
                    ) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "content": f"Ollama error: {error_text}"
                            }))
                            continue

                        async for line in resp.content:
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                full_response += token
                                await websocket.send_text(json.dumps({
                                    "type": "token",
                                    "content": token,
                                }))

                            if chunk.get("done"):
                                await websocket.send_text(json.dumps({"type": "done"}))
                                break

            except aiohttp.ClientError as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "content": f"Cannot reach Ollama at {OLLAMA_BASE}. Is it running?\n\nError: {e}"
                }))
                continue

            # Save assistant response
            if full_response:
                db3 = await get_db()
                await db3.execute(
                    "INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    (chat_id, "assistant", full_response, time.time()),
                )
                await db3.commit()
                await db3.close()

    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
