#!/bin/bash
set -e

PROJECT="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo " SaaP Financial Intelligence Engine"
echo "========================================"

# ── Backend (API only, port 8000) ─────────────────────────────────────────
echo ""
echo "[1/3] Starting backend (API) on port 8000..."
cd "$PROJECT/backend"
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
venv/bin/pip install -q -r requirements.txt
nohup venv/bin/uvicorn main:app --port 8000 > /tmp/saap-backend.log 2>&1 &
BACKEND_PID=$!

# ── Production instance (API + frontend, port 8001) ───────────────────────
echo "[2/3] Starting production instance (UI + API) on port 8001..."
SERVE_FRONTEND=1 nohup venv/bin/uvicorn main:app --port 8001 > /tmp/saap-prod.log 2>&1 &
PROD_PID=$!

# ── Frontend dev server (port 3000) ───────────────────────────────────────
echo "[3/3] Starting frontend dev server on port 3000..."
cd "$PROJECT/frontend"
npm install --silent
NEXT_PUBLIC_API_BASE=http://localhost:8000 nohup npm run dev > /tmp/saap-frontend.log 2>&1 &
FRONTEND_PID=$!

# ── Wait for backend to be ready ──────────────────────────────────────────
echo ""
echo "Waiting for services..."
for i in $(seq 1 20); do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then break; fi
  sleep 1
done

# ── Cloudflare tunnel (public link) ───────────────────────────────────────
echo "Starting public tunnel..."
nohup cloudflared tunnel --url http://localhost:8001 --no-autoupdate > /tmp/saap-tunnel.log 2>&1 &
TUNNEL_PID=$!

# Wait for tunnel URL
for i in $(seq 1 20); do
  TUNNEL_URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' /tmp/saap-tunnel.log 2>/dev/null | tail -1)
  if [ -n "$TUNNEL_URL" ]; then break; fi
  sleep 1
done

# ── Done ──────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " All services running"
echo "========================================"
echo ""
echo "  Dev frontend   →  http://localhost:3000"
echo "  API            →  http://localhost:8000"
echo "  Public link    →  ${TUNNEL_URL:-'(tunnel starting, check /tmp/saap-tunnel.log)'}"
echo ""
echo "Logs:"
echo "  Backend  /tmp/saap-backend.log"
echo "  Frontend /tmp/saap-frontend.log"
echo "  Tunnel   /tmp/saap-tunnel.log"
echo ""
echo "Press Ctrl+C to stop everything."
echo "========================================"

# ── Trap Ctrl+C to kill all child processes ───────────────────────────────
trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $PROD_PID $FRONTEND_PID $TUNNEL_PID 2>/dev/null; exit 0" INT TERM

wait
