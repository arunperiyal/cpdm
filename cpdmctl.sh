#!/usr/bin/env bash
#
# cpdmctl.sh — run the CPDM workspace as a hosted service.
#
#   ./cpdmctl.sh start          run the server
#   ./cpdmctl.sh stop           stop it
#   ./cpdmctl.sh install        write a systemd unit, enable it, start it
#   ./cpdmctl.sh uninstall      stop, disable and remove that unit
#
# Without a unit installed, start/stop manage a plain background process with a
# pid file; once a unit is installed the same commands drive systemd instead,
# and each command says which it is using.
#
# CPDM keeps its dataset in one process, so the service always runs a single
# worker. Two workers would answer requests from two different in-memory
# datasets, which looks like data loss to whoever is using it.

set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
APP_ENTRY="$PROJECT_DIR/app.py"

SERVICE_NAME="cpdm"
UNIT_FILE="$SERVICE_NAME.service"

HOST="${CPDM_HOST:-127.0.0.1}"
PORT="${CPDM_PORT:-5000}"
PYTHON="${CPDM_PYTHON:-python3}"
SCOPE="user"          # or "system"
SERVER="flask"        # or "gunicorn"
DRY_RUN=0
ASSUME_YES=0
START_AFTER_INSTALL=1
ENABLE_LINGER=0

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/cpdm"
PID_FILE="$STATE_DIR/$SERVICE_NAME.pid"
LOG_FILE="$STATE_DIR/$SERVICE_NAME.log"

# --- output --------------------------------------------------------------
if [[ -t 1 ]]; then
    BOLD=$'\033[1m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; OFF=$'\033[0m'
else
    BOLD=""; RED=""; GREEN=""; YELLOW=""; OFF=""
fi

say()  { printf '%s\n' "$*"; }
ok()   { printf '%s✓%s %s\n' "$GREEN" "$OFF" "$*"; }
warn() { printf '%s!%s %s\n' "$YELLOW" "$OFF" "$*" >&2; }
die()  { printf '%s✗%s %s\n' "$RED" "$OFF" "$*" >&2; exit 1; }

usage() {
    cat <<EOF
${BOLD}cpdmctl.sh${OFF} — host the CPDM workspace

${BOLD}Usage:${OFF} ./cpdmctl.sh <command> [options]

${BOLD}Commands:${OFF}
  start          Start the server (systemd if a unit is installed, else background)
  stop           Stop it
  restart        Stop then start
  status         Whether it is running, and on which URL
  logs           Follow the log (journalctl for a service, the log file otherwise)
  install        Write the systemd unit, reload, enable at boot, and start
  uninstall      Stop, disable and remove the unit
  url            Print the address the app is served on

${BOLD}Options:${OFF}
  --user         Per-user service in ~/.config/systemd/user (default, no sudo)
  --system       System-wide service in /etc/systemd/system (uses sudo)
  --host HOST    Address to bind (default $HOST)
  --port PORT    Port to bind (default $PORT)
  --python PATH  Interpreter to run with (default $PYTHON)
  --gunicorn     Serve through gunicorn instead of Flask's own server
  --linger       With install --user: also allow the service to run when logged out
  --no-start     With install: write and enable the unit but do not start it
  --dry-run      With install/uninstall: show what would happen, change nothing
  -y, --yes      Do not ask for confirmation
  -h, --help     This text

${BOLD}Notes:${OFF}
  The default host $HOST is reachable only from this machine. CPDM has no
  login and no access control, so anyone who can reach the port can read and
  change the loaded dataset — bind it to a wider address only on a network you
  trust, and put a reverse proxy with authentication in front of it otherwise.
EOF
}

# --- helpers -------------------------------------------------------------
unit_path() {
    if [[ "$SCOPE" == "system" ]]; then
        printf '/etc/systemd/system/%s' "$UNIT_FILE"
    else
        printf '%s/systemd/user/%s' "${XDG_CONFIG_HOME:-$HOME/.config}" "$UNIT_FILE"
    fi
}

systemctl_do() {
    if [[ "$SCOPE" == "system" ]]; then
        sudo systemctl "$@"
    else
        systemctl --user "$@"
    fi
}

have_systemd() { command -v systemctl >/dev/null 2>&1; }
unit_installed() { [[ -f "$(unit_path)" ]]; }

app_url() { printf 'http://%s:%s/' "$HOST" "$PORT"; }

python_abs() {
    command -v -- "$PYTHON" 2>/dev/null || printf '%s' "$PYTHON"
}

confirm() {
    (( ASSUME_YES )) && return 0
    [[ -t 0 ]] || return 0            # non-interactive: take the command at its word
    read -r -p "$1 [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]]
}

running_pid() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid; pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null || return 1
    printf '%s' "$pid"
}

port_busy() {
    "$(python_abs)" - "$HOST" "$PORT" <<'PY' 2>/dev/null
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
probe = host if host not in ("0.0.0.0", "::") else "127.0.0.1"
with socket.socket() as sock:
    sock.settimeout(0.4)
    sys.exit(0 if sock.connect_ex((probe, port)) == 0 else 1)
PY
}

preflight() {
    [[ -f "$APP_ENTRY" ]] || die "app.py not found next to this script ($PROJECT_DIR)."
    command -v -- "$PYTHON" >/dev/null 2>&1 || die "Interpreter '$PYTHON' not found. Pass --python /path/to/python3."

    local missing
    missing="$("$PYTHON" - <<'PY'
import importlib.util
need = {"flask": "flask", "pandas": "pandas", "openpyxl": "openpyxl"}
print(" ".join(pip for mod, pip in need.items() if importlib.util.find_spec(mod) is None))
PY
)"
    if [[ -n "$missing" ]]; then
        die "'$PYTHON' is missing: $missing
    Install them with:  $PYTHON -m pip install -r $PROJECT_DIR/requirements.txt"
    fi

    if [[ "$SERVER" == "gunicorn" ]] && ! "$PYTHON" -c "import gunicorn" >/dev/null 2>&1; then
        die "gunicorn is not installed for '$PYTHON'. Drop --gunicorn, or: $PYTHON -m pip install gunicorn"
    fi
}

# The unit file is parsed by systemd, which understands the quoting; the
# background path needs a real argv, so the two are built separately.
exec_start_line() {
    local py; py="$(python_abs)"
    if [[ "$SERVER" == "gunicorn" ]]; then
        # one worker only: the dataset lives in the process, not in a store
        printf '%s -m gunicorn --workers 1 --threads 4 --timeout 120 --bind %s:%s "cpdm:create_app()"' \
            "$py" "$HOST" "$PORT"
    else
        printf '%s %s' "$py" "$APP_ENTRY"
    fi
}

# fills the SERVER_ARGV array
build_argv() {
    local py; py="$(python_abs)"
    if [[ "$SERVER" == "gunicorn" ]]; then
        SERVER_ARGV=("$py" -m gunicorn --workers 1 --threads 4 --timeout 120
                     --bind "$HOST:$PORT" "cpdm:create_app()")
    else
        SERVER_ARGV=("$py" "$APP_ENTRY")
    fi
}

# --- systemd unit --------------------------------------------------------
render_unit() {
    local identity=""
    if [[ "$SCOPE" == "system" ]]; then
        identity="User=$(id -un)
Group=$(id -gn)
"
    fi

    cat <<EOF
[Unit]
Description=CPDM — Comprehensive Package for Data Management
Documentation=https://github.com/arunperiyal/cpdm
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
${identity}WorkingDirectory=$PROJECT_DIR
Environment=CPDM_HOST=$HOST
Environment=CPDM_PORT=$PORT
Environment=CPDM_NO_BROWSER=1
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=$PROJECT_DIR/src
ExecStart=$(exec_start_line)
Restart=on-failure
RestartSec=3
# the workspace holds one dataset in memory; never run a second copy of it
KillMode=mixed
TimeoutStopSec=20

[Install]
WantedBy=$( [[ "$SCOPE" == "system" ]] && printf 'multi-user.target' || printf 'default.target' )
EOF
}

cmd_install() {
    have_systemd || die "systemd is not available here; use './cpdmctl.sh start' instead."
    preflight

    local path; path="$(unit_path)"

    if (( DRY_RUN )); then
        say "${BOLD}Would write $path:${OFF}"
        say ""
        render_unit
        return 0
    fi

    if [[ -f "$path" ]] && ! confirm "$path exists. Overwrite it?"; then
        die "Left alone."
    fi

    if [[ "$SCOPE" == "system" ]]; then
        render_unit | sudo tee "$path" >/dev/null
    else
        mkdir -p "$(dirname "$path")"
        render_unit > "$path"
    fi
    ok "Wrote $path"

    systemctl_do daemon-reload
    systemctl_do enable "$UNIT_FILE" >/dev/null
    ok "Enabled $UNIT_FILE — it will come back after a reboot"

    if [[ "$SCOPE" == "user" ]]; then
        if (( ENABLE_LINGER )); then
            sudo loginctl enable-linger "$(id -un)"
            ok "Lingering enabled — the service runs even when you are logged out"
        elif ! loginctl show-user "$(id -un)" -p Linger 2>/dev/null | grep -q 'Linger=yes'; then
            warn "A user service stops when you log out. To keep it running:"
            warn "    sudo loginctl enable-linger $(id -un)     (or re-run install --linger)"
        fi
    fi

    if (( START_AFTER_INSTALL )); then
        systemctl_do start "$UNIT_FILE"
        sleep 1
        cmd_status
    else
        say "Not started (--no-start). Start it with: ./cpdmctl.sh start"
    fi
}

cmd_uninstall() {
    have_systemd || die "systemd is not available here."
    local path; path="$(unit_path)"

    if [[ ! -f "$path" ]]; then
        warn "No unit at $path — nothing to remove."
        return 0
    fi

    if (( DRY_RUN )); then
        say "${BOLD}Would stop, disable and delete $path${OFF}"
        return 0
    fi

    confirm "Stop, disable and delete $path?" || die "Left alone."

    systemctl_do stop "$UNIT_FILE" 2>/dev/null || true
    systemctl_do disable "$UNIT_FILE" >/dev/null 2>&1 || true

    if [[ "$SCOPE" == "system" ]]; then
        sudo rm -f "$path"
    else
        rm -f "$path"
    fi
    systemctl_do daemon-reload
    systemctl_do reset-failed "$UNIT_FILE" 2>/dev/null || true

    ok "Removed $path. The project itself is untouched."
}

# --- run without systemd -------------------------------------------------
start_background() {
    preflight

    if running_pid >/dev/null; then
        warn "Already running (pid $(running_pid)) on $(app_url)"
        return 0
    fi
    if port_busy; then
        die "Something is already listening on $HOST:$PORT. Use --port to pick another."
    fi

    mkdir -p "$STATE_DIR"
    local SERVER_ARGV=()
    build_argv
    (
        cd "$PROJECT_DIR"
        CPDM_HOST="$HOST" CPDM_PORT="$PORT" CPDM_NO_BROWSER=1 \
        PYTHONUNBUFFERED=1 PYTHONPATH="$PROJECT_DIR/src" \
            nohup "${SERVER_ARGV[@]}" >>"$LOG_FILE" 2>&1 &
        printf '%s' "$!" > "$PID_FILE"
    )

    sleep 1.5
    if running_pid >/dev/null && port_busy; then
        ok "Running on $(app_url) (pid $(running_pid))"
        say "  log: $LOG_FILE"
    else
        rm -f "$PID_FILE"
        die "It did not come up. Last lines of $LOG_FILE:
$(tail -n 15 "$LOG_FILE" 2>/dev/null || echo '  (no log written)')"
    fi
}

stop_background() {
    local pid
    if ! pid="$(running_pid)"; then
        warn "Not running."
        rm -f "$PID_FILE"
        return 0
    fi

    kill "$pid" 2>/dev/null || true
    for _ in $(seq 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
        warn "Did not stop politely; sending SIGKILL."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    ok "Stopped (pid $pid)."
}

# --- commands ------------------------------------------------------------
cmd_start() {
    if unit_installed; then
        say "Using the systemd unit at $(unit_path)."
        systemctl_do start "$UNIT_FILE"
        sleep 1
        cmd_status
    else
        start_background
    fi
}

cmd_stop() {
    if unit_installed; then
        systemctl_do stop "$UNIT_FILE"
        ok "Stopped $UNIT_FILE."
    else
        stop_background
    fi
}

cmd_status() {
    if unit_installed; then
        local state; state="$(systemctl_do is-active "$UNIT_FILE" 2>/dev/null || true)"
        say "unit:   $(unit_path)"
        say "state:  $state"
        if [[ "$state" == "active" ]]; then
            ok "Serving $(app_url)"
        else
            warn "Not active. Recent log:"
            systemctl_do status "$UNIT_FILE" --no-pager --lines 8 2>/dev/null || true
        fi
    elif running_pid >/dev/null; then
        ok "Running in the background (pid $(running_pid)) on $(app_url)"
        say "  log: $LOG_FILE"
    else
        say "Not running, and no systemd unit installed."
        say "  ./cpdmctl.sh start     run it now"
        say "  ./cpdmctl.sh install   run it at boot"
    fi
}

cmd_logs() {
    if unit_installed; then
        systemctl_do status "$UNIT_FILE" --no-pager --lines 5 2>/dev/null || true
        if [[ "$SCOPE" == "system" ]]; then
            sudo journalctl -u "$UNIT_FILE" -f
        else
            journalctl --user -u "$UNIT_FILE" -f
        fi
    elif [[ -f "$LOG_FILE" ]]; then
        tail -n 40 -f "$LOG_FILE"
    else
        die "No log yet — nothing has been started."
    fi
}

# --- arguments -----------------------------------------------------------
COMMAND=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        start|stop|restart|status|logs|install|uninstall|url)
            COMMAND="$1" ;;
        --user)      SCOPE="user" ;;
        --system)    SCOPE="system" ;;
        --host)      HOST="${2:?--host needs a value}"; shift ;;
        --port)      PORT="${2:?--port needs a value}"; shift ;;
        --python)    PYTHON="${2:?--python needs a value}"; shift ;;
        --gunicorn)  SERVER="gunicorn" ;;
        --linger)    ENABLE_LINGER=1 ;;
        --no-start)  START_AFTER_INSTALL=0 ;;
        --dry-run)   DRY_RUN=1 ;;
        -y|--yes)    ASSUME_YES=1 ;;
        -h|--help)   usage; exit 0 ;;
        *)           die "Unknown argument '$1'. Try --help." ;;
    esac
    shift
done

[[ -n "$COMMAND" ]] || { usage; exit 1; }

case "$COMMAND" in
    start)     cmd_start ;;
    stop)      cmd_stop ;;
    restart)   cmd_stop; cmd_start ;;
    status)    cmd_status ;;
    logs)      cmd_logs ;;
    install)   cmd_install ;;
    uninstall) cmd_uninstall ;;
    url)       app_url; echo ;;
esac
