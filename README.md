# Local AI Chat

A private ChatGPT-like app that runs entirely on your computer. No API keys, no subscriptions, no data leaving your machine.

![dark themed chat UI](https://img.shields.io/badge/UI-ChatGPT--style-blue) ![runs locally](https://img.shields.io/badge/runs-100%25%20local-green) ![mobile friendly](https://img.shields.io/badge/mobile-friendly-orange)

## Features

- **Fully private** — your conversations never leave your computer
- **ChatGPT-like UI** — dark theme, streaming responses, markdown rendering
- **Mobile friendly** — open on your phone with ngrok (optional)
- **Chat history** — up to 10 conversations, persisted across restarts
- **Model switcher** — use any model available through Ollama
- **Streaming** — responses appear token-by-token in real time
- **Zero cost** — no API keys or subscriptions needed

## Quick Start

### 1. Install Ollama

Ollama runs AI models locally, optimized for your hardware.

**Mac:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Or download from [ollama.com/download](https://ollama.com/download)

### 2. Clone and run

```bash
git clone https://github.com/ani0x53/local-ai-chat.git
cd local-ai-chat
./start.sh
```

That's it. Open **http://localhost:8000** in your browser.

The start script handles everything automatically:
- Starts Ollama if it's not running
- Downloads the default model (`llama3.1:8b`) on first run
- Creates a Python virtual environment
- Installs dependencies
- Launches the chat server

### 3. Access from your phone (optional)

Install [ngrok](https://ngrok.com/) and set up a free account:

```bash
# 1. Install ngrok
brew install ngrok    # Mac
# or: snap install ngrok   # Linux

# 2. Create a free account at https://dashboard.ngrok.com/signup

# 3. Copy your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken

# 4. Add your authtoken (one-time setup)
ngrok config add-authtoken YOUR_TOKEN_HERE
```

After that, the start script will automatically create a tunnel and print a public URL. Open it on your phone and start chatting.

## Recommended Models

The default model is `llama3.1:8b` — a great balance of speed and quality. You can switch models from the sidebar dropdown, or pull new ones:

| Model | Size | RAM Needed | Best For |
|-------|------|-----------|----------|
| `llama3.1:8b` | 4.7 GB | 8 GB | **Default** — fast and smart |
| `qwen2.5:14b` | 9 GB | 16 GB | Higher quality conversations |
| `mistral-small` | 14 GB | 24 GB | Strong reasoning |
| `qwen2.5:32b` | 20 GB | 32 GB | Excellent quality |
| `llama3.3:70b` | 43 GB | 64 GB | Best quality (slower) |

To pull a new model:
```bash
ollama pull qwen2.5:14b
```

It will appear in the model dropdown automatically.

## Requirements

- **Python 3.10+**
- **Ollama** ([install](https://ollama.com/download))
- **8 GB+ RAM** (16 GB+ recommended)
- **Node.js** (only if you want ngrok phone access)

## Project Structure

```
├── start.sh          # One-command launcher
├── server.py         # FastAPI backend + WebSocket streaming
├── frontend/
│   └── index.html    # Chat UI (single file)
├── requirements.txt  # Python dependencies
└── chats.db          # SQLite database (created on first run)
```

## Manual Setup

If you prefer to run things manually:

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start the chat
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

## License

MIT
