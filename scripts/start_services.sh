#!/usr/bin/env bash
#
# Start the AgentIA stack: MLflow tracking, the FastAPI backend, and the Vite frontend.
#
#   ./scripts/start_services.sh              start everything
#   ./scripts/start_services.sh status       show what is up
#   ./scripts/start_services.sh stop         stop what THIS script started
#   ./scripts/start_services.sh logs backend follow a log
#
# Options: --no-mlflow  --no-backend  --no-frontend
#
# Design notes, because a start script that lies is worse than none:
#
#  * It never kills a process it did not start. If a port is already taken, that
#    service is reported and skipped -- a colleague's server, or a manually started
#    one, is not this script's to take down. `stop` likewise only touches PIDs it
#    recorded itself.
#  * It waits for each service to actually answer before printing a URL, so "started"
#    means "responding", not "spawned".
#  * Logs go to .run/logs/ rather than the terminal, so a crash is diagnosable after
#    the fact instead of scrolling away.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/.run"
LOG_DIR="$RUN_DIR/logs"
PID_DIR="$RUN_DIR/pids"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
MLFLOW_PORT="${MLFLOW_PORT:-5000}"

VENV_PY="$ROOT/.venv/bin/python"
VENV_MLFLOW="$ROOT/.venv/bin/mlflow"

START_MLFLOW=1
START_BACKEND=1
START_FRONTEND=1

# --- output ----------------------------------------------------------------
if [ -t 1 ]; then
  C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
  C_OK=""; C_WARN=""; C_ERR=""; C_DIM=""; C_OFF=""
fi
ok()   { printf '%s  ok  %s %s\n' "$C_OK" "$C_OFF" "$*"; }
warn() { printf '%s warn %s %s\n' "$C_WARN" "$C_OFF" "$*"; }
err()  { printf '%s fail %s %s\n' "$C_ERR" "$C_OFF" "$*" >&2; }
info() { printf '%s      %s %s\n' "$C_DIM" "$C_OFF" "$*"; }

# --- helpers ---------------------------------------------------------------
port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && exec 3>&- && return 0
  return 1
}

pid_of_port() {
  # Best-effort, for reporting only. Never used to kill.
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | awk -v p=":$1" '$4 ~ p {print $NF}' | head -1
  fi
}

wait_for_http() {
  local url="$1" name="$2" tries="${3:-40}"
  for _ in $(seq 1 "$tries"); do
    if curl -fsS -o /dev/null --max-time 2 "$url" 2>/dev/null; then return 0; fi
    sleep 0.5
  done
  return 1
}

wait_for_port() {
  local port="$1" tries="${2:-40}"
  for _ in $(seq 1 "$tries"); do
    port_in_use "$port" && return 0
    sleep 0.5
  done
  return 1
}

record_pid() { printf '%s' "$2" > "$PID_DIR/$1.pid"; }

spawn() {
  # spawn <name> <workdir> <command...>
  #
  # Detachment matters, and a first version of this script got it wrong: `nohup ... &`
  # still shares the parent's process group, so all three services died the moment the
  # invoking shell was torn down -- verified by killing the parent and watching every
  # port close. `setsid` gives each service its own session, and `</dev/null` plus full
  # redirection stops a detached child holding the caller's stdout open, which is what
  # made `... | tail` hang.
  #
  # The PID is written by the process itself, not from `$!`: `setsid` forks when it is
  # already a group leader, so `$!` would name a short-lived parent and the pidfile
  # would point at a process that no longer exists.
  local name="$1" dir="$2"; shift 2
  local log="$LOG_DIR/$name.log" pidfile="$PID_DIR/$name.pid"

  if command -v setsid >/dev/null 2>&1; then
    ( cd "$dir" && setsid bash -c 'echo $$ >"$1"; shift; exec "$@"' _ "$pidfile" "$@" \
        >"$log" 2>&1 </dev/null & )
  else
    ( cd "$dir" && nohup bash -c 'echo $$ >"$1"; shift; exec "$@"' _ "$pidfile" "$@" \
        >"$log" 2>&1 </dev/null & )
  fi
}

stop_one() {
  # stop_one <name> <port>
  local name="$1" port="${2:-}"
  local pidfile="$PID_DIR/$name.pid"

  if [ ! -f "$pidfile" ]; then
    info "$name: not started by this script"
    return 0
  fi

  local pid; pid="$(cat "$pidfile" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.25; done
    kill -9 "$pid" 2>/dev/null || true
    ok "$name stopped (pid $pid)"
  else
    # A pidfile is only meaningful within the PID namespace that wrote it. Run from a
    # different namespace -- a container, or a different harness session -- and the
    # recorded PID is invisible even though the service is very much alive. Saying
    # "not running" there would be a false statement about the user's machine, so the
    # port is what decides the report.
    if [ -n "$port" ] && port_in_use "$port"; then
      warn "$name: pid $pid is not visible from here, but port $port is still open"
      info "  the service was started in another session or namespace; stop it there"
    else
      info "$name: not running"
    fi
  fi
  rm -f "$pidfile"
}

# --- preflight -------------------------------------------------------------
preflight() {
  local failed=0

  if [ ! -x "$VENV_PY" ]; then
    err "no virtualenv at .venv (expected $VENV_PY)"
    info "create it with: python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt"
    failed=1
  fi

  if [ "$START_MLFLOW" = 1 ] && [ ! -x "$VENV_MLFLOW" ]; then
    warn "mlflow is not installed in .venv -- skipping it"
    info "install with: UV_CACHE_DIR=\"\$PWD/.uvcache\" uv pip install --python .venv/bin/python mlflow"
    START_MLFLOW=0
  fi

  if [ "$START_FRONTEND" = 1 ]; then
    if [ ! -d "$ROOT/frontend/node_modules" ]; then
      err "frontend/node_modules is missing"
      info "run: cd frontend && npm install"
      failed=1
    fi
  fi

  mkdir -p "$LOG_DIR" "$PID_DIR"
  return "$failed"
}

# --- services --------------------------------------------------------------
start_mlflow() {
  if port_in_use "$MLFLOW_PORT"; then
    warn "MLflow port $MLFLOW_PORT already in use -- leaving it alone"
    info "if that is an older MLflow, this run mirrors into it"
    return 0
  fi

  info "starting MLflow on :$MLFLOW_PORT ..."
  spawn mlflow "$ROOT" "$VENV_MLFLOW" server \
      --backend-store-uri "sqlite:///$ROOT/mlflow.db" \
      --default-artifact-root "$ROOT/mlruns" \
      --host 127.0.0.1 --port "$MLFLOW_PORT"

  if wait_for_http "http://127.0.0.1:$MLFLOW_PORT/health" "mlflow"; then
    ok "MLflow      http://127.0.0.1:$MLFLOW_PORT   (store: mlflow.db)"
  else
    err "MLflow did not answer on :$MLFLOW_PORT -- see .run/logs/mlflow.log"
    tail -n 5 "$LOG_DIR/mlflow.log" 2>/dev/null | sed 's/^/        /'
    return 1
  fi
}

start_backend() {
  if port_in_use "$BACKEND_PORT"; then
    warn "backend port $BACKEND_PORT already in use -- leaving it alone"
    if wait_for_http "http://127.0.0.1:$BACKEND_PORT/healthz" backend 3; then
      ok "backend     http://127.0.0.1:$BACKEND_PORT   (already running)"
    fi
    return 0
  fi

  info "starting FastAPI on :$BACKEND_PORT ..."
  spawn backend "$ROOT" "$VENV_PY" -m uvicorn app.main:app \
      --app-dir backend --host 0.0.0.0 --port "$BACKEND_PORT" --reload

  if wait_for_http "http://127.0.0.1:$BACKEND_PORT/healthz" backend 60; then
    ok "backend     http://127.0.0.1:$BACKEND_PORT   (docs: /docs)"
  else
    err "backend did not answer on :$BACKEND_PORT -- see .run/logs/backend.log"
    tail -n 5 "$LOG_DIR/backend.log" 2>/dev/null | sed 's/^/        /'
    return 1
  fi
}

start_frontend() {
  if port_in_use "$FRONTEND_PORT"; then
    warn "frontend port $FRONTEND_PORT already in use -- leaving it alone"
    ok "frontend    http://127.0.0.1:$FRONTEND_PORT   (already running)"
    return 0
  fi

  info "starting Vite on :$FRONTEND_PORT ..."
  spawn frontend "$ROOT/frontend" npm run dev

  if wait_for_port "$FRONTEND_PORT" 60; then
    ok "frontend    http://127.0.0.1:$FRONTEND_PORT"
  else
    err "frontend did not open :$FRONTEND_PORT -- see .run/logs/frontend.log"
    tail -n 5 "$LOG_DIR/frontend.log" 2>/dev/null | sed 's/^/        /'
    return 1
  fi
}

# --- commands --------------------------------------------------------------
cmd_status() {
  printf 'AgentIA services\n'
  for entry in "MLflow:$MLFLOW_PORT:/health:http://127.0.0.1:$MLFLOW_PORT" \
               "backend:$BACKEND_PORT:/healthz:http://127.0.0.1:$BACKEND_PORT" \
               "frontend:$FRONTEND_PORT::http://127.0.0.1:$FRONTEND_PORT"; do
    local name="${entry%%:*}" rest="${entry#*:}"
    local port="${rest%%:*}" rest2="${rest#*:}"
    local path="${rest2%%:*}" base="${rest2#*:}"
    if [ -n "$path" ] && wait_for_http "$base$path" "$name" 1; then
      ok "$(printf '%-9s' "$name") up    http://127.0.0.1:$port"
    elif [ -z "$path" ] && port_in_use "$port"; then
      ok "$(printf '%-9s' "$name") up    http://127.0.0.1:$port"
    elif port_in_use "$port"; then
      warn "$(printf '%-9s' "$name") port $port is open but not answering $path"
    else
      info "$(printf '%-9s' "$name") down"
    fi
  done
}

cmd_stop() {
  stop_one frontend "$FRONTEND_PORT"
  stop_one backend  "$BACKEND_PORT"
  stop_one mlflow   "$MLFLOW_PORT"
  info "note: a service whose port was already in use when you started was NOT touched"
}

cmd_logs() {
  local name="${1:-backend}" file="$LOG_DIR/$name.log"
  [ -f "$file" ] || { err "no log at $file"; exit 1; }
  info "tailing $file (Ctrl-C to stop)"
  tail -f "$file"
}

usage() {
  sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# --- main ------------------------------------------------------------------
CMD="start"
for arg in "$@"; do
  case "$arg" in
    start|status|stop|logs) CMD="$arg" ;;
    --no-mlflow)   START_MLFLOW=0 ;;
    --no-backend)  START_BACKEND=0 ;;
    --no-frontend) START_FRONTEND=0 ;;
    -h|--help)     usage; exit 0 ;;
    *) err "unknown argument: $arg"; usage; exit 2 ;;
  esac
done

case "$CMD" in
  status) cmd_status; exit 0 ;;
  stop)   cmd_stop;   exit 0 ;;
  logs)   shift || true; cmd_logs "$@" ;;
esac

preflight || exit 1

printf 'AgentIA stack  %s%s%s\n' "$C_DIM" "$ROOT" "$C_OFF"
failed=0
[ "$START_MLFLOW"   = 1 ] && { start_mlflow   || failed=1; }
[ "$START_BACKEND"  = 1 ] && { start_backend  || failed=1; }
[ "$START_FRONTEND" = 1 ] && { start_frontend || failed=1; }

if [ "$failed" = 0 ]; then
  printf '\n'
  ok "ready -- open http://127.0.0.1:$FRONTEND_PORT"
  info "logs:  .run/logs/{mlflow,backend,frontend}.log   (./scripts/start_services.sh logs backend)"
  info "stop:  ./scripts/start_services.sh stop"
  if [ "$START_MLFLOW" = 1 ]; then
    info "MLflow UI at http://127.0.0.1:$MLFLOW_PORT -- cost runs mirror there, the local"
    info "  cost_tracking.db stays the system of record"
  fi
  printf '\n'
  info "reminder: the UI defaults to the MOCK provider. For model generation open"
  info "  Settings, select DeepSeek, paste the key, verify, then start a NEW session."
else
  err "some services failed to start -- see above"
  exit 1
fi
