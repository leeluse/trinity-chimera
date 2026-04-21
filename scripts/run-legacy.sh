#!/bin/bash

# Trinity Project Runner
# - One command to run backend + tunnel reliably
# - Auto bootstrap for Python runtime (venv + dependencies)
# - Works across slightly different local environments

# -------------------------------------------------------------------
# Core paths and runtime knobs
# -------------------------------------------------------------------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ -f "$SCRIPT_DIR/../requirements.txt" ] && [ -d "$SCRIPT_DIR/../server" ] && [ -d "$SCRIPT_DIR/../client" ]; then
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  PROJECT_ROOT="$SCRIPT_DIR"
fi
# Add common bin paths for background execution
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
COMMAND=$1
BACKEND_PORT="${BACKEND_PORT:-8000}"
TUNNEL_SUBDOMAIN="${TUNNEL_SUBDOMAIN:-}"
LT_LOCAL_HOST="${LT_LOCAL_HOST:-127.0.0.1}"
LT_HOST="${LT_HOST:-https://loca.lt}"
PY_MANAGER="${PY_MANAGER:-auto}"
JS_MANAGER="${JS_MANAGER:-auto}"
AUTO_BOOTSTRAP="${AUTO_BOOTSTRAP:-1}"
AUTO_TUNNEL_ON_SERVER="${AUTO_TUNNEL_ON_SERVER:-0}"
INSTALL_ROOT_REQUIREMENTS="${INSTALL_ROOT_REQUIREMENTS:-0}"
AUTO_BOOTSTRAP_FRONTEND="${AUTO_BOOTSTRAP_FRONTEND:-1}"
TRINITY_LOG_LEVEL="${TRINITY_LOG_LEVEL:-WARNING}"
UVICORN_LOG_LEVEL="${UVICORN_LOG_LEVEL:-warning}"
UVICORN_ACCESS_LOG="${UVICORN_ACCESS_LOG:-0}"
UVICORN_RELOAD="${UVICORN_RELOAD:-0}"
export TRINITY_LOG_LEVEL UVICORN_LOG_LEVEL UVICORN_ACCESS_LOG UVICORN_RELOAD
RUN_DIR="$PROJECT_ROOT/tmp/always_on"
API_PID_FILE="$RUN_DIR/api.pid"
PROXY_PID_FILE="$RUN_DIR/proxy.pid"
PROXY_LOG="$RUN_DIR/proxy-8082.log"
TUNNEL_PID_FILE="$RUN_DIR/localtunnel.pid"
PY_BOOTSTRAP_STATE="$RUN_DIR/python_bootstrap.state"
FRONTEND_BOOTSTRAP_STATE="$RUN_DIR/frontend_bootstrap.state"
AUTO_TUNNEL_LOG="$RUN_DIR/auto_tunnel.log"
API_LOG="$RUN_DIR/api-${BACKEND_PORT}.log"
TUNNEL_LOG="$RUN_DIR/localtunnel-${BACKEND_PORT}.log"
URL_FILE="$RUN_DIR/backend_tunnel_url.txt"
VERCEL_AUTO_DEPLOY="${VERCEL_AUTO_DEPLOY:-1}"
VERCEL_ENV_TARGET="${VERCEL_ENV_TARGET:-production}"
VERCEL_PROJECT_DIR="${VERCEL_PROJECT_DIR:-$PROJECT_ROOT/client}"
VERCEL_BIN="${VERCEL_BIN:-vercel}"
VERCEL_SYNC_STATE_FILE="$RUN_DIR/vercel_synced_backend_url.txt"

mkdir -p "$RUN_DIR"

# -------------------------------------------------------------------
# Python environment bootstrap helpers
# -------------------------------------------------------------------
resolve_venv_paths() {
  # Detect virtual environment path (Windows vs Linux/macOS)
  if [ -f "$PROJECT_ROOT/venv/Scripts/activate" ]; then
    VENV_ACTIVATE="$PROJECT_ROOT/venv/Scripts/activate"
    VENV_PYTHON="$PROJECT_ROOT/venv/Scripts/python"
  else
    VENV_ACTIVATE="$PROJECT_ROOT/venv/bin/activate"
    VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"
  fi
}
resolve_venv_paths

resolve_python_manager() {
  if [ -n "${EFFECTIVE_PY_MANAGER:-}" ]; then
    return 0
  fi

  case "$PY_MANAGER" in
    uv)
      if ! command -v uv >/dev/null 2>&1; then
        echo "❌ PY_MANAGER=uv 이지만 uv를 찾지 못했습니다."
        return 1
      fi
      EFFECTIVE_PY_MANAGER="uv"
      ;;
    pip)
      EFFECTIVE_PY_MANAGER="pip"
      ;;
    auto)
      if command -v uv >/dev/null 2>&1; then
        EFFECTIVE_PY_MANAGER="uv"
      else
        EFFECTIVE_PY_MANAGER="pip"
      fi
      ;;
    *)
      echo "❌ Unsupported PY_MANAGER: $PY_MANAGER (use: auto|uv|pip)"
      return 1
      ;;
  esac
}

resolve_js_manager() {
  if [ -n "${EFFECTIVE_JS_MANAGER:-}" ]; then
    return 0
  fi

  case "$JS_MANAGER" in
    yarn)
      if ! command -v yarn >/dev/null 2>&1; then
        echo "❌ JS_MANAGER=yarn 이지만 yarn을 찾지 못했습니다."
        return 1
      fi
      EFFECTIVE_JS_MANAGER="yarn"
      ;;
    npm)
      if ! command -v npm >/dev/null 2>&1; then
        echo "❌ JS_MANAGER=npm 이지만 npm을 찾지 못했습니다."
        return 1
      fi
      EFFECTIVE_JS_MANAGER="npm"
      ;;
    auto)
      if command -v yarn >/dev/null 2>&1; then
        EFFECTIVE_JS_MANAGER="yarn"
      elif command -v npm >/dev/null 2>&1; then
        EFFECTIVE_JS_MANAGER="npm"
      else
        echo "❌ npm/yarn을 찾지 못했습니다."
        return 1
      fi
      ;;
    *)
      echo "❌ Unsupported JS_MANAGER: $JS_MANAGER (use: auto|yarn|npm)"
      return 1
      ;;
  esac
}

semver_gte() {
  # Returns 0 when $1 >= $2 for x.y.z versions.
  local lhs="${1#v}" rhs="${2#v}"
  local l1 l2 l3 r1 r2 r3
  IFS='.' read -r l1 l2 l3 <<< "$lhs"
  IFS='.' read -r r1 r2 r3 <<< "$rhs"
  l1="${l1:-0}"; l2="${l2:-0}"; l3="${l3:-0}"
  r1="${r1:-0}"; r2="${r2:-0}"; r3="${r3:-0}"

  if ((10#$l1 > 10#$r1)); then return 0; fi
  if ((10#$l1 < 10#$r1)); then return 1; fi
  if ((10#$l2 > 10#$r2)); then return 0; fi
  if ((10#$l2 < 10#$r2)); then return 1; fi
  if ((10#$l3 >= 10#$r3)); then return 0; fi
  return 1
}

resolve_frontend_node_runtime() {
  local required_min_version="${FRONTEND_NODE_MIN_VERSION:-20.19.0}"
  local current_node_version=""

  if command -v node >/dev/null 2>&1; then
    current_node_version="$(node -v 2>/dev/null | sed 's/^v//')"
    if [ -n "$current_node_version" ] && semver_gte "$current_node_version" "$required_min_version"; then
      return 0
    fi
  fi

  local candidate_bins=()
  local nvmrc_version="" nvmrc_major=""
  if [ -f "$PROJECT_ROOT/client/.nvmrc" ]; then
    nvmrc_version="$(tr -d '[:space:]v' < "$PROJECT_ROOT/client/.nvmrc")"
    nvmrc_major="${nvmrc_version%%.*}"
    if [ -n "$nvmrc_major" ]; then
      candidate_bins+=("/opt/homebrew/opt/node@${nvmrc_major}/bin")
      candidate_bins+=("/usr/local/opt/node@${nvmrc_major}/bin")
    fi
  fi

  candidate_bins+=("/opt/homebrew/opt/node@22/bin")
  candidate_bins+=("/usr/local/opt/node@22/bin")
  candidate_bins+=("/opt/homebrew/opt/node@20/bin")
  candidate_bins+=("/usr/local/opt/node@20/bin")

  local bin candidate_version
  for bin in "${candidate_bins[@]}"; do
    if [ ! -x "$bin/node" ]; then
      continue
    fi
    candidate_version="$("$bin/node" -v 2>/dev/null | sed 's/^v//')"
    if [ -n "$candidate_version" ] && semver_gte "$candidate_version" "$required_min_version"; then
      export PATH="$bin:$PATH"
      hash -r
      echo "ℹ️ Frontend Node runtime: v${candidate_version} ($bin)"
      return 0
    fi
  done

  echo "❌ Frontend requires Node >= ${required_min_version}, but current is ${current_node_version:-not found}."
  echo "   Install node@22 or node@20.19+ and ensure it is available on PATH."
  return 1
}

resolve_vercel_bin() {
  if [ -n "${EFFECTIVE_VERCEL_BIN:-}" ]; then
    return 0
  fi

  if command -v "$VERCEL_BIN" >/dev/null 2>&1; then
    EFFECTIVE_VERCEL_BIN="$(command -v "$VERCEL_BIN")"
    return 0
  fi
  if command -v vercel >/dev/null 2>&1; then
    EFFECTIVE_VERCEL_BIN="$(command -v vercel)"
    return 0
  fi
  if [ -x "$HOME/.npm-global/bin/vercel" ]; then
    EFFECTIVE_VERCEL_BIN="$HOME/.npm-global/bin/vercel"
    return 0
  fi

  echo "❌ vercel CLI를 찾지 못했습니다. (npm i -g vercel 필요)"
  return 1
}

sync_vercel_env_and_deploy() {
  local backend_url="$1"
  resolve_vercel_bin || return 1

  if [ ! -d "$VERCEL_PROJECT_DIR" ]; then
    echo "❌ VERCEL_PROJECT_DIR not found: $VERCEL_PROJECT_DIR"
    return 1
  fi

  (
    cd "$VERCEL_PROJECT_DIR" || exit 1
    # Keep value newline-free to avoid malformed target URLs on proxy side.
    printf '%s' "$backend_url" | "$EFFECTIVE_VERCEL_BIN" env add BACKEND_API_URL "$VERCEL_ENV_TARGET" --force >/dev/null
    printf '%s' "$backend_url" | "$EFFECTIVE_VERCEL_BIN" env add NEXT_PUBLIC_API_URL "$VERCEL_ENV_TARGET" --force >/dev/null
    "$EFFECTIVE_VERCEL_BIN" --prod --yes >/dev/null
  )
}

maybe_sync_vercel_on_url_change() {
  local backend_url="$1"
  [ "$VERCEL_AUTO_DEPLOY" = "1" ] || return 0

  local prev_url=""
  prev_url="$(cat "$VERCEL_SYNC_STATE_FILE" 2>/dev/null || true)"
  if [ "$backend_url" = "$prev_url" ]; then
    return 0
  fi

  echo "🚀 Sync Vercel env + deploy (${backend_url})..."
  if sync_vercel_env_and_deploy "$backend_url"; then
    echo "$backend_url" > "$VERCEL_SYNC_STATE_FILE"
    echo "✅ Vercel deploy complete."
    return 0
  fi

  echo "⚠️ Vercel sync/deploy failed. retry는 'run deploy'로 가능합니다."
  return 1
}

detect_host_python() {
  # Prefer explicit PYTHON_BIN when provided.
  if [ -n "${PYTHON_BIN:-}" ] && command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    HOST_PYTHON="$(command -v "$PYTHON_BIN")"
    return 0
  fi
  # Fallback to common interpreter names.
  if command -v python3 >/dev/null 2>&1; then
    HOST_PYTHON="$(command -v python3)"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    HOST_PYTHON="$(command -v python)"
    return 0
  fi
  echo "❌ Python executable not found. Install python3 first."
  return 1
}

hash_stream() {
  # Build deterministic hash regardless of host tooling.
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 | awk '{print $1}'
    return 0
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
    return 0
  fi
  "$HOST_PYTHON" -c 'import hashlib,sys;print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())'
}

build_python_bootstrap_fingerprint() {
  # Reinstall deps only when python/version/requirements actually changed.
  {
    echo "manager=${EFFECTIVE_PY_MANAGER}"
    echo "python=$("$HOST_PYTHON" -V 2>&1)"
    echo "install_root=${INSTALL_ROOT_REQUIREMENTS}"
    if [ -f "$PROJECT_ROOT/server/api/requirements_api.txt" ]; then
      cat "$PROJECT_ROOT/server/api/requirements_api.txt"
    fi
    if [ "$INSTALL_ROOT_REQUIREMENTS" = "1" ] && [ -f "$PROJECT_ROOT/requirements.txt" ]; then
      cat "$PROJECT_ROOT/requirements.txt"
    fi
  } | hash_stream
}

bootstrap_python_runtime() {
  # Opt-out supported for fast local loops.
  [ "$AUTO_BOOTSTRAP" = "1" ] || return 0
  resolve_python_manager || exit 1
  detect_host_python || exit 1

  # Create venv lazily if missing.
  if [ ! -f "$VENV_PYTHON" ]; then
    echo "🔧 Creating virtual environment at $PROJECT_ROOT/venv ..."
    if [ "$EFFECTIVE_PY_MANAGER" = "uv" ]; then
      uv venv --python "$HOST_PYTHON" "$PROJECT_ROOT/venv" || {
        echo "❌ uv venv 생성 실패."
        exit 1
      }
    else
      "$HOST_PYTHON" -m venv "$PROJECT_ROOT/venv" || {
        echo "❌ Failed to create venv."
        exit 1
      }
    fi
    resolve_venv_paths
  fi

  if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ venv python not found: $VENV_PYTHON"
    exit 1
  fi

  local current_fingerprint previous_fingerprint
  current_fingerprint="$(build_python_bootstrap_fingerprint)"
  previous_fingerprint="$(cat "$PY_BOOTSTRAP_STATE" 2>/dev/null || true)"

  if [ "${FORCE_BOOTSTRAP:-0}" = "1" ] || [ "$current_fingerprint" != "$previous_fingerprint" ]; then
    echo "📦 Bootstrapping Python dependencies (${EFFECTIVE_PY_MANAGER})..."
    if [ "$EFFECTIVE_PY_MANAGER" = "uv" ]; then
      uv pip install --python "$VENV_PYTHON" --upgrade pip wheel || exit 1
      if [ -f "$PROJECT_ROOT/server/api/requirements_api.txt" ]; then
        uv pip install --python "$VENV_PYTHON" -r "$PROJECT_ROOT/server/api/requirements_api.txt" || exit 1
      fi
      if [ "$INSTALL_ROOT_REQUIREMENTS" = "1" ] && [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        uv pip install --python "$VENV_PYTHON" -r "$PROJECT_ROOT/requirements.txt" || exit 1
      fi
    else
      # Keep toolchain fresh, but avoid forcing setuptools to prevent torch conflicts.
      "$VENV_PYTHON" -m pip install --upgrade pip wheel || exit 1
      if [ -f "$PROJECT_ROOT/server/api/requirements_api.txt" ]; then
        "$VENV_PYTHON" -m pip install -r "$PROJECT_ROOT/server/api/requirements_api.txt" || exit 1
      fi
      if [ "$INSTALL_ROOT_REQUIREMENTS" = "1" ] && [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        "$VENV_PYTHON" -m pip install -r "$PROJECT_ROOT/requirements.txt" || exit 1
      fi
    fi
    echo "$current_fingerprint" > "$PY_BOOTSTRAP_STATE"
    echo "✅ Python bootstrap complete."
  else
    echo "✅ Python environment is up to date."
  fi
}

build_frontend_bootstrap_fingerprint() {
  {
    echo "manager=${EFFECTIVE_JS_MANAGER}"
    if [ -f "$PROJECT_ROOT/client/package.json" ]; then
      cat "$PROJECT_ROOT/client/package.json"
    fi
    if [ -f "$PROJECT_ROOT/client/yarn.lock" ]; then
      cat "$PROJECT_ROOT/client/yarn.lock"
    fi
    if [ -f "$PROJECT_ROOT/client/package-lock.json" ]; then
      cat "$PROJECT_ROOT/client/package-lock.json"
    fi
  } | hash_stream
}

bootstrap_frontend_runtime() {
  [ "$AUTO_BOOTSTRAP_FRONTEND" = "1" ] || return 0
  resolve_frontend_node_runtime || exit 1
  resolve_js_manager || exit 1

  if [ ! -f "$PROJECT_ROOT/client/package.json" ]; then
    echo "❌ client/package.json not found."
    exit 1
  fi

  local current_fingerprint previous_fingerprint
  current_fingerprint="$(build_frontend_bootstrap_fingerprint)"
  previous_fingerprint="$(cat "$FRONTEND_BOOTSTRAP_STATE" 2>/dev/null || true)"

  if [ "${FORCE_BOOTSTRAP_FRONTEND:-0}" = "1" ] || [ "$current_fingerprint" != "$previous_fingerprint" ]; then
    echo "📦 Bootstrapping frontend dependencies (${EFFECTIVE_JS_MANAGER})..."
    if [ "$EFFECTIVE_JS_MANAGER" = "yarn" ]; then
      if [ ! -f "$PROJECT_ROOT/client/yarn.lock" ] && [ -f "$PROJECT_ROOT/client/package-lock.json" ]; then
        echo "ℹ️ yarn.lock 없음. 현재 package-lock.json 기반 프로젝트를 yarn으로 설치합니다."
      fi
      (cd "$PROJECT_ROOT/client" && yarn install) || exit 1
    else
      (cd "$PROJECT_ROOT/client" && npm install) || exit 1
    fi
    echo "$current_fingerprint" > "$FRONTEND_BOOTSTRAP_STATE"
    echo "✅ Frontend bootstrap complete."
  else
    echo "✅ Frontend environment is up to date."
  fi
}

run_backend_python_module() {
  local module="$1"
  shift
  resolve_python_manager || exit 1
  if [ "$EFFECTIVE_PY_MANAGER" = "uv" ]; then
    uv run --python "$VENV_PYTHON" -m "$module" "$@"
  else
    "$VENV_PYTHON" -m "$module" "$@"
  fi
}

# -------------------------------------------------------------------
# Process / port helpers
# -------------------------------------------------------------------
is_port_listening() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  else
    # Windows fallback
    netstat -ano | grep ":$port " | grep -q "LISTENING"
  fi
}

show_port_owner() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sed -n '2,$p'
  else
    # Windows fallback
    netstat -ano | grep ":$port " | grep "LISTENING"
  fi
}

kill_backend_listener() {
  local port="$1"
  local pids=""

  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      echo "$pids" | xargs kill >/dev/null 2>&1 || true
    fi
  fi

  if [ -z "$pids" ] && [ -f "$API_PID_FILE" ]; then
    local pid=""
    pid="$(cat "$API_PID_FILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  fi

  rm -f "$API_PID_FILE"

  for _ in {1..20}; do
    if ! is_port_listening "$port"; then
      return 0
    fi
    sleep 0.25
  done

  return 1
}

kill_tunnel_processes() {
  # Kill only localtunnel processes targeting this backend port.
  local pids
  pids="$(
    ps ax -o pid= -o command= \
      | awk -v needle="--port ${BACKEND_PORT}" '
          index($0, needle) && ($0 ~ /localtunnel/ || $0 ~ /(^|[[:space:]])lt([[:space:]]|$)|\/lt([[:space:]]|$)/) { print $1 }
        '
  )"
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill >/dev/null 2>&1 || true
    sleep 1
  fi
}

kill_proxy_processes() {
  local pids
  pids="$(lsof -t -iTCP:8082 -sTCP:LISTEN 2>/dev/null)"
  if [ -n "$pids" ]; then
    echo "🛑 Stopping existing NIM proxy (pids: $pids)..."
    echo "$pids" | xargs kill >/dev/null 2>&1 || true
    sleep 1
  fi
}

start_nim_proxy() {
  echo "🚀 Starting NIM Proxy on port 8082..."
  (
    cd "$PROJECT_ROOT/proxy" && \
    source "$VENV_ACTIVATE" && \
    PYTHONPATH="$PROJECT_ROOT" nohup "$VENV_PYTHON" server.py >> "$PROXY_LOG" 2>&1 &
    echo $! > "$PROXY_PID_FILE"
    echo "✅ NIM Proxy started. Log: $PROXY_LOG"
  )
}

run_localtunnel_once() {
  # Try already-installed CLI first, then package runner fallbacks.
  local cmd=()
  if command -v lt >/dev/null 2>&1; then
    cmd=(lt --local-host "$LT_LOCAL_HOST" --port "$BACKEND_PORT")
  elif command -v bunx >/dev/null 2>&1; then
    cmd=(bunx localtunnel --local-host "$LT_LOCAL_HOST" --port "$BACKEND_PORT")
  elif command -v pnpm >/dev/null 2>&1; then
    cmd=(pnpm dlx localtunnel --local-host "$LT_LOCAL_HOST" --port "$BACKEND_PORT")
  else
    cmd=(npx --yes localtunnel --local-host "$LT_LOCAL_HOST" --port "$BACKEND_PORT")
  fi
  # Empty subdomain -> random .loca.lt endpoint
  if [ -n "${TUNNEL_SUBDOMAIN:-}" ]; then
    cmd+=(--subdomain "$TUNNEL_SUBDOMAIN")
  fi
  if [ -n "${LT_HOST:-}" ]; then
    cmd+=(--host "$LT_HOST")
  fi
  "${cmd[@]}"
}

extract_localtunnel_url_from_log() {
  if [ ! -f "$TUNNEL_LOG" ]; then
    return 1
  fi
  local url
  url="$(grep -Eo 'https://[a-z0-9-]+\.loca\.lt' "$TUNNEL_LOG" | tail -n 1 || true)"
  if [ -z "${url:-}" ]; then
    return 1
  fi
  printf "%s" "$url"
}

wait_for_localtunnel_url() {
  local i
  local url
  for i in {1..25}; do
    url="$(extract_localtunnel_url_from_log || true)"
    if [ -n "${url:-}" ]; then
      printf "%s" "$url"
      return 0
    fi
    sleep 1
  done
  return 1
}

has_tunnel_runtime() {
  # Any one of these is enough to bootstrap localtunnel.
  command -v lt >/dev/null 2>&1 \
    || command -v npx >/dev/null 2>&1 \
    || command -v bunx >/dev/null 2>&1 \
    || command -v pnpm >/dev/null 2>&1
}

is_tunnel_running() {
  # Fast check via pid file, then process scan fallback.
  if [ -f "$TUNNEL_PID_FILE" ]; then
    local pid
    pid="$(cat "$TUNNEL_PID_FILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then
      return 0
    fi
  fi

  ps ax -o command= \
    | grep -E "localtunnel|(^|[[:space:]])lt([[:space:]]|$)" \
    | grep -- "--port ${BACKEND_PORT}" >/dev/null 2>&1
}

start_tunnel_autorun() {
  # Used by ./run server so backend users get a stable public endpoint automatically.
  [ "$AUTO_TUNNEL_ON_SERVER" = "1" ] || return 0
  local tunnel_url

  if ! has_tunnel_runtime; then
    echo "⚠️ Tunnel runtime not found (lt/npx/bunx/pnpm). Skipping auto tunnel."
    return 0
  fi

  if is_tunnel_running; then
    echo "ℹ️ tunnel is already running for port ${BACKEND_PORT}."
    if [ -n "${TUNNEL_SUBDOMAIN:-}" ]; then
      tunnel_url="https://${TUNNEL_SUBDOMAIN}.loca.lt"
    else
      tunnel_url="$(extract_localtunnel_url_from_log || true)"
    fi
    if [ -n "${tunnel_url:-}" ]; then
      echo "$tunnel_url" > "$URL_FILE"
      maybe_sync_vercel_on_url_change "$tunnel_url" >> "$AUTO_TUNNEL_LOG" 2>&1 || true
    else
      rm -f "$URL_FILE"
    fi
    return 0
  fi

  (
    echo "⏳ Waiting for backend to bind to port ${BACKEND_PORT}..." > "$AUTO_TUNNEL_LOG"
    for i in {1..60}; do
      if is_port_listening "$BACKEND_PORT"; then
        echo "✅ Backend is up on port ${BACKEND_PORT}. Starting localtunnel..." >> "$AUTO_TUNNEL_LOG"
        kill_tunnel_processes
        : > "$TUNNEL_LOG"

        (
          while true; do
            run_localtunnel_once >> "$TUNNEL_LOG" 2>&1
            EXIT_CODE=$?
            echo "[$(date '+%F %T')] localtunnel exited (code=$EXIT_CODE). reconnect in 3s..." >> "$TUNNEL_LOG"
            sleep 3
          done
        ) &
        echo $! > "$TUNNEL_PID_FILE"
        if [ -n "${TUNNEL_SUBDOMAIN:-}" ]; then
          tunnel_url="https://${TUNNEL_SUBDOMAIN}.loca.lt"
        else
          tunnel_url="$(wait_for_localtunnel_url || true)"
        fi
        if [ -n "${tunnel_url:-}" ]; then
          echo "$tunnel_url" > "$URL_FILE"
          maybe_sync_vercel_on_url_change "$tunnel_url" >> "$AUTO_TUNNEL_LOG" 2>&1 || true
          echo "🌐 Tunnel started: $tunnel_url" >> "$AUTO_TUNNEL_LOG"
        else
          rm -f "$URL_FILE"
          echo "⚠️ Tunnel started but URL could not be detected yet." >> "$AUTO_TUNNEL_LOG"
        fi
        exit 0
      fi
      sleep 1
    done
    echo "❌ Timeout waiting for backend on port ${BACKEND_PORT}" >> "$AUTO_TUNNEL_LOG"
  ) &
}

# -------------------------------------------------------------------
# Command entrypoints
# -------------------------------------------------------------------
case $COMMAND in
  "client"|"front")
    resolve_js_manager || exit 1
    bootstrap_frontend_runtime

    if is_port_listening 3000; then
      echo "ℹ️ Client is already running on port 3000."
      show_port_owner 3000
      exit 0
    fi
    echo "🚀 Starting Trinity Client (Next.js, ${EFFECTIVE_JS_MANAGER})..."
    if [ "$EFFECTIVE_JS_MANAGER" = "yarn" ]; then
      cd "$PROJECT_ROOT/client" && yarn dev
    else
      cd "$PROJECT_ROOT/client" && npm run dev
    fi
    ;;
  "server"|"api")
    # Always bootstrap first so this command works on fresh machines too.
    bootstrap_python_runtime

    # Dev ergonomics: ./run server always restarts backend in hot-reload mode.
    UVICORN_RELOAD=1
    export UVICORN_RELOAD

    if is_port_listening "$BACKEND_PORT"; then
      echo "♻️ Restarting existing backend on port ${BACKEND_PORT}..."
      if ! kill_backend_listener "$BACKEND_PORT"; then
        echo "❌ Failed to stop existing backend on port ${BACKEND_PORT}."
        show_port_owner "$BACKEND_PORT"
        exit 1
      fi
    fi

    # Start NIM Proxy first (Disabled by user request)
    # kill_proxy_processes
    # start_nim_proxy

    echo "⚙️ Starting FastAPI server (hot reload ON)..."
    # Start tunnel watcher before app boot; it will wait until port is open.
    start_tunnel_autorun
    
    cd "$PROJECT_ROOT/server/api" && \
    source "$VENV_ACTIVATE" && \
    set -a && [ -f "$PROJECT_ROOT/.env" ] && source "$PROJECT_ROOT/.env" && set +a && \
    PYTHONPATH="$PROJECT_ROOT" run_backend_python_module server.api.main
    ;;
  "public"|"tunnel")
    # Explicit public mode: run backend (if needed) + foreground tunnel session.
    bootstrap_python_runtime

    if ! has_tunnel_runtime; then
      echo "❌ localtunnel 실행 도구를 찾지 못했습니다. (lt / npx / bunx / pnpm 필요)"
      exit 1
    fi

    if is_port_listening "$BACKEND_PORT"; then
      echo "ℹ️ backend already running on port ${BACKEND_PORT}."
      show_port_owner "$BACKEND_PORT"
    else
      echo "⚙️ Starting FastAPI server in background..."
      case "$UVICORN_ACCESS_LOG" in
        1|true|TRUE|True|yes|YES|on|ON) UVICORN_NO_ACCESS="" ;;
        *) UVICORN_NO_ACCESS="--no-access-log" ;;
      esac

      if [ "$EFFECTIVE_PY_MANAGER" = "uv" ]; then
        nohup uv run --python "$VENV_PYTHON" -m uvicorn server.api.main:app \
          --host 0.0.0.0 --port "$BACKEND_PORT" --log-level "$UVICORN_LOG_LEVEL" \
          $UVICORN_NO_ACCESS >> "$API_LOG" 2>&1 &
      else
        nohup "$VENV_PYTHON" -m uvicorn server.api.main:app \
          --host 0.0.0.0 --port "$BACKEND_PORT" --log-level "$UVICORN_LOG_LEVEL" \
          $UVICORN_NO_ACCESS >> "$API_LOG" 2>&1 &
      fi
      echo $! > "$API_PID_FILE"
      
      # Wait briefly until backend starts listening.
      for i in {1..10}; do
        is_port_listening "$BACKEND_PORT" && break
        sleep 1
      done
    fi

    if ! is_port_listening "$BACKEND_PORT"; then
      echo "❌ backend failed to start. Check log: $API_LOG"
      exit 1
    fi

    kill_tunnel_processes
    : > "$TUNNEL_LOG"

    TUNNEL_URL=""
    if [ -n "${TUNNEL_SUBDOMAIN:-}" ]; then
      TUNNEL_URL="https://${TUNNEL_SUBDOMAIN}.loca.lt"
      echo "$TUNNEL_URL" > "$URL_FILE"
    fi
    if [ -n "$TUNNEL_URL" ]; then
      echo "🌐 Localtunnel 시작 — ${TUNNEL_URL} → 포트 ${BACKEND_PORT}"
    else
      echo "🌐 Localtunnel 시작 — 랜덤 서브도메인 모드 (URL은 실행 로그에 표시)"
    fi
    echo
    echo "✅ Public tunnel starting (foreground)"
    echo "   API Local : http://127.0.0.1:${BACKEND_PORT}"
    if [ -n "$TUNNEL_URL" ]; then
      echo "   API Public: ${TUNNEL_URL} (fixed by subdomain)"
    else
      echo "   API Public: (random .loca.lt, see tunnel output)"
    fi
    echo "   LT Host   : ${LT_HOST}"
    echo "   URL file  : $URL_FILE"
    echo "   API log   : $API_LOG"
    echo "   Tunnel log: $TUNNEL_LOG"
    echo "   Stop      : Ctrl+C (auto-reconnect enabled)"
    echo
    KEEP_RUNNING=1
    trap 'KEEP_RUNNING=0' INT TERM
    while [ "$KEEP_RUNNING" -eq 1 ]; do
      # Foreground loop with auto-reconnect for tunnel stability.
      run_localtunnel_once 2>&1 | tee -a "$TUNNEL_LOG"
      EXIT_CODE=${PIPESTATUS[0]}
      if [ "$KEEP_RUNNING" -eq 0 ] || [ "$EXIT_CODE" -eq 130 ]; then
        break
      fi
      echo "[$(date '+%F %T')] localtunnel exited (code=$EXIT_CODE). reconnect in 3s..." | tee -a "$TUNNEL_LOG"
      sleep 3
    done
    trap - INT TERM
    ;;
  "public-stop"|"tunnel-stop")
    if [ -f "$TUNNEL_PID_FILE" ]; then
      TUNNEL_PID="$(cat "$TUNNEL_PID_FILE" || true)"
      if [ -n "${TUNNEL_PID:-}" ] && ps -p "$TUNNEL_PID" >/dev/null 2>&1; then
        kill "$TUNNEL_PID" >/dev/null 2>&1 || true
        echo "🛑 localtunnel stopped (pid=$TUNNEL_PID)"
      fi
      rm -f "$TUNNEL_PID_FILE"
    fi
    kill_tunnel_processes
    rm -f "$URL_FILE"
    echo "✅ tunnel stopped."
    ;;
  "public-status"|"tunnel-status")
    echo "🔎 backend/tunnel status"
    if is_port_listening "$BACKEND_PORT"; then
      echo "   backend: LISTEN on ${BACKEND_PORT}"
      show_port_owner "$BACKEND_PORT"
    else
      echo "   backend: NOT LISTENING on ${BACKEND_PORT}"
    fi
    if ps aux | grep -v grep | grep -E "localtunnel|lt" | grep -q "${BACKEND_PORT}"; then
      echo "   tunnel : RUNNING"
      ps aux | grep -v grep | grep -E "localtunnel|lt" | grep "${BACKEND_PORT}" || true
    else
      echo "   tunnel : NOT RUNNING"
    fi
    if [ -f "$URL_FILE" ]; then
      echo "   public : $(cat "$URL_FILE")"
    fi
    ;;
  "deploy")
    resolve_vercel_bin || exit 1

    DEPLOY_BACKEND_URL="${DEPLOY_BACKEND_URL:-}"
    if [ -z "$DEPLOY_BACKEND_URL" ] && [ -f "$URL_FILE" ]; then
      DEPLOY_BACKEND_URL="$(cat "$URL_FILE" 2>/dev/null || true)"
    fi

    if [ -n "$DEPLOY_BACKEND_URL" ]; then
      echo "🚀 Deploy with backend sync: ${DEPLOY_BACKEND_URL}"
      sync_vercel_env_and_deploy "$DEPLOY_BACKEND_URL" || exit 1
    else
      echo "🚀 Deploy without backend sync"
      (
        cd "$VERCEL_PROJECT_DIR" && \
        "$EFFECTIVE_VERCEL_BIN" --prod --yes
      ) || exit 1
    fi
    echo "✅ Vercel deployment complete."
    ;;
  "clean")
    echo "🧹 Cleaning runtime logs/state..."
    rm -f "$RUN_DIR"/*.log "$RUN_DIR"/backend_tunnel_url.txt "$RUN_DIR"/vercel_synced_backend_url.txt \
      "$RUN_DIR"/python_bootstrap.state "$RUN_DIR"/frontend_bootstrap.state "$RUN_DIR"/cloudflared.pid || true
    if [ -d "$PROJECT_ROOT/logs" ]; then
      find "$PROJECT_ROOT/logs" -type f -delete
      rmdir "$PROJECT_ROOT/logs" 2>/dev/null || true
    fi
    rm -f "$PROJECT_ROOT/local_api.log" || true
    echo "✅ Cleaned. (runtime: $RUN_DIR, legacy: $PROJECT_ROOT/logs)"
    ;;
  "test")
    bootstrap_python_runtime
    echo "🧪 Running AI Trading Tests..."
    cd "$PROJECT_ROOT" && run_backend_python_module pytest \
      server/ai_trading/tests/test_metrics_buffer.py \
      server/ai_trading/tests/test_integration.py \
      server/ai_trading/tests/test_llm_client.py \
      server/ai_trading/tests/test_costs.py \
      server/ai_trading/tests/test_sandbox.py -v --tb=short
    ;;
  *)
    echo "Usage: ./run [client|server|public|public-status|public-stop|deploy|clean|test]"
    echo "  client: Start the Next.js dashboard (alias: front)"
    echo "  server: Restart backend and run FastAPI with hot reload (alias: api)"
    echo "  public: Start/attach backend + localtunnel"
    echo "          env: TUNNEL_SUBDOMAIN=<name|empty(random)> BACKEND_PORT=<port> LT_LOCAL_HOST=<ip> LT_HOST=<https://loca.lt>"
    echo "  public-status: Show backend/tunnel status"
    echo "  public-stop: Stop localtunnel"
    echo "  deploy: Sync backend URL env + Vercel production deploy"
    echo "          env: DEPLOY_BACKEND_URL=<https://...> VERCEL_ENV_TARGET=production"
    echo "  clean: Remove unnecessary runtime/legacy log files and state files"
    echo "  test: Run AI trading pytest suite"
    echo
    echo "Optional env vars:"
    echo "  PY_MANAGER=auto            # auto|uv|pip (auto prefers uv)"
    echo "  JS_MANAGER=auto            # auto|yarn|npm (auto prefers yarn)"
    echo "  AUTO_BOOTSTRAP=0           # disable auto venv/pip setup"
    echo "  AUTO_BOOTSTRAP_FRONTEND=0  # disable auto frontend install"
    echo "  AUTO_TUNNEL_ON_SERVER=0    # disable tunnel auto-start on ./run server"
    echo "  VERCEL_AUTO_DEPLOY=1       # auto deploy when tunnel URL changes (default: 1)"
    echo "  VERCEL_PROJECT_DIR=...     # frontend directory for vercel deploy"
    echo "  VERCEL_BIN=vercel          # override vercel cli binary"
    echo "  INSTALL_ROOT_REQUIREMENTS=1 # also install ./requirements.txt"
    echo "  FORCE_BOOTSTRAP=1          # force reinstall dependencies once"
    echo "  FORCE_BOOTSTRAP_FRONTEND=1 # force frontend reinstall once"
    exit 1
    ;;
esac
