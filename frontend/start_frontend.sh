#!/bin/bash
echo "================================"
echo " SaaP Frontend — Starting..."
echo "================================"
cd "$(dirname "$0")"

# Check node
if ! command -v node &> /dev/null; then
  echo "ERROR: Node.js not found."
  echo "Download from https://nodejs.org (LTS version)"
  exit 1
fi

echo "Installing npm packages..."
npm install

echo ""
echo "Frontend running at http://localhost:3000"
echo "Press Ctrl+C to stop."
echo ""
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
