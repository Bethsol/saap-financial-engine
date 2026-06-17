#!/bin/bash
echo "================================"
echo " SaaP Backend — Starting..."
echo "================================"
cd "$(dirname "$0")"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
echo "Installing dependencies..."
pip install -q fastapi "uvicorn[standard]" pandas numpy pydantic python-multipart rapidfuzz openai python-dotenv requests

echo ""
echo "Backend running at http://localhost:8000"
echo "Press Ctrl+C to stop."
echo ""
uvicorn main:app --reload --port 8000
