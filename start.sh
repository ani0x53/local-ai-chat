#!/bin/bash
set -e

echo "============================================"
echo "  Local AI Chat — Starting up"
echo "============================================"
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "Ollama is not installed."
    echo "Install it from: https://ollama.com/download"
    echo ""
    echo "Or run:  brew install ollama"
    exit 1
fi

# Check if ngrok is available
if ! command -v ngrok &> /dev/null; then
    echo "ngrok not found. Install it for phone access:"
    echo "  brew install ngrok"
    echo ""
    echo "Continuing without tunnel (local access only)..."
    NO_TUNNEL=1
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama..."
    ollama serve &
    sleep 2
fi

# Pull model if needed
MODEL="llama3.1:8b"
if ! ollama list | grep -q "$MODEL"; then
    echo "Pulling $MODEL (this may take a few minutes on first run)..."
    ollama pull "$MODEL"
fi

# Install Python deps if needed
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

pip install -q -r requirements.txt

# Start the server in background
python server.py &
SERVER_PID=$!

# Wait for server to be ready
echo "Starting server..."
for i in $(seq 1 15); do
    if curl -s http://localhost:8000 > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo ""
echo "============================================"
echo "  Chat is ready!"
echo ""
echo "  Local:  http://localhost:8000"

# Start ngrok
if [ -z "$NO_TUNNEL" ]; then
    echo ""
    echo "  Starting ngrok tunnel for phone access..."
    ngrok http 8000 --log=stdout > /tmp/ngrok.log &
    TUNNEL_PID=$!
    sleep 2
    # Extract the public URL
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || echo "")
    if [ -n "$NGROK_URL" ]; then
        echo "  Phone:  $NGROK_URL"
    else
        echo "  Phone:  check http://localhost:4040 for your ngrok URL"
    fi
fi

echo "============================================"
echo ""
echo "Press Ctrl+C to stop everything."
echo ""

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $SERVER_PID 2>/dev/null
    [ -n "$TUNNEL_PID" ] && kill $TUNNEL_PID 2>/dev/null
    wait 2>/dev/null
    echo "Done."
}
trap cleanup EXIT INT TERM

# Wait for server process
wait $SERVER_PID
