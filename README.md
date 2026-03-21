# Local ChatGPT-like Chatbot

A simple Python script that downloads a HuggingFace language model and lets you chat with it locally — no API keys, no cloud, everything runs on your machine.

## How It Works

- Downloads [TinyLlama-1.1B-Chat](https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0), a lightweight instruction-tuned chat model (1.1B parameters, ~2GB download)
- Uses HuggingFace's `transformers` pipeline with the standard chat message format
- Automatically uses Apple Silicon GPU (MPS) if available, otherwise falls back to CPU
- Maintains conversation history so the model remembers context within a session

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python chat.py
```

Type your messages at the `You:` prompt. Type `quit` or `exit` to stop.

```
You: What is Python?
Assistant: Python is a high-level programming language known for its simple syntax...

You: What are some common uses?
Assistant: Python is commonly used for web development, data science...
```

## Using a Different Model

Change `MODEL_NAME` in `chat.py` to swap models:

| Model | Size | RAM Needed | Quality |
|-------|------|------------|---------|
| `TinyLlama/TinyLlama-1.1B-Chat-v1.0` (default) | 1.1B | ~4GB | Basic |
| `microsoft/Phi-3-mini-4k-instruct` | 3.8B | ~8GB | Good |
| `mistralai/Mistral-7B-Instruct-v0.3` | 7B | ~14GB | Great |

## Requirements

- Python 3.9+
- ~2GB disk space for the default model (cached in `~/.cache/huggingface`)
- macOS with Apple Silicon recommended (uses GPU via MPS)
