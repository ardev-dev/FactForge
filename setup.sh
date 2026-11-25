#!/bin/bash
# YouTube Automation System — One-Command Setup
# Usage: bash setup.sh

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  YouTube Automation System — Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Check Python 3 ──────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "Installing Python 3..."
  brew install python
fi

# ─── Create virtual environment ─────────────────
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate

# ─── Install Python packages ────────────────────
echo "Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ─── Try Kokoro TTS ─────────────────────────────
echo "Installing Kokoro TTS (optional — may take a moment)..."
pip install kokoro-onnx -q 2>/dev/null && echo "Kokoro TTS: installed" || echo "Kokoro TTS: skipped (will use Edge TTS fallback)"

# ─── Install Remotion ───────────────────────────
if [ ! -d "video/remotion-project/node_modules" ]; then
  echo "Installing Remotion dependencies..."
  cd video/remotion-project && npm install -q && cd ../..
fi

# ─── Create .env from example ───────────────────
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  Created .env file. You MUST fill in your API keys:"
  echo "   nano .env"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Fill in .env with your API keys"
echo "  2. Run: source venv/bin/activate"
echo "  3. Run: python main.py"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
