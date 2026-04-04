#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-phi4-mini}"

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

echo "🔧 Local KB macOS setup"

auto_install_ollama() {
  if have_cmd ollama; then
    return 0
  fi

  # Try Homebrew if available (or in standard location)
  if have_cmd brew; then
    brew install ollama
  elif [ -x /opt/homebrew/bin/brew ]; then
    eval "$('/opt/homebrew/bin/brew' shellenv)"
    brew install ollama
  else
    echo "❌ Ollama not found and Homebrew is not available in PATH."
    echo "Install one of these, then rerun:"
    echo "  - Homebrew: https://brew.sh"
    echo "  - Ollama app: https://ollama.com/download/mac"
    exit 1
  fi
}

auto_install_ollama

# Start Ollama service if brew manages it; otherwise user may have app/daemon running.
if have_cmd brew; then
  brew services start ollama || true
fi

if [ -f "requirements.txt" ]; then
  python3 -m pip install --user -r requirements.txt
fi

echo "📦 Pulling model: $MODEL"
ollama pull "$MODEL"

echo ""
echo "✅ Setup complete"
echo "Try this next:"
echo "  python3 scripts/kb.py compile --model $MODEL"
echo "  python3 scripts/kb.py ask \"What is this project for?\" --model $MODEL"
