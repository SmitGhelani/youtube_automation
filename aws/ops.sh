#!/usr/bin/env bash
# =============================================================================
# aws/ops.sh
# Usage:
#   ./ops.sh run-short       — run short video pipeline right now
#   ./ops.sh run-long        — run long video pipeline right now
#   ./ops.sh status          — show timer and service status
#   ./ops.sh logs-short      — tail short video logs
#   ./ops.sh logs-long       — tail long video logs
#   ./ops.sh logs-main       — tail main pipeline log
#   ./ops.sh update          — git pull + pip install + restart timers
#   ./ops.sh next-runs       — show when next runs are scheduled
#   ./ops.sh disk            — show disk usage
#   ./ops.sh clean           — delete workspace dirs older than 7 days
# =============================================================================

set -euo pipefail

APP_DIR="/opt/youtube-pipeline"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="/var/log/youtube-pipeline"
ENV_FILE="/etc/youtube-pipeline.env"

# ── Load /etc/youtube-pipeline.env into the current shell ────────────────────
# This is needed when running ops.sh directly (not via systemd, which loads it
# automatically via EnvironmentFile=). Without this, ANTHROPIC_API_KEY etc.
# are missing and the pipeline crashes immediately with KeyError.
_load_env() {
    if [ ! -f "$ENV_FILE" ]; then
        echo "ERROR: $ENV_FILE not found."
        echo "Run: sudo cp aws/user_data.sh /etc/youtube-pipeline.env (then edit with real keys)"
        exit 1
    fi
    # set -a exports every variable defined after it; source reads the file;
    # set +a stops auto-export. This is the standard portable approach.
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    echo "[ops] Loaded env from $ENV_FILE"
}

case "${1:-help}" in

  run-short)
    _load_env
    echo "Running short video pipeline..."
    cd "$APP_DIR"
    "$VENV_DIR/bin/python" main.py --type short
    ;;

  run-long)
    _load_env
    echo "Running long video pipeline..."
    cd "$APP_DIR"
    "$VENV_DIR/bin/python" main.py --type long
    ;;

  status)
    echo "=== Timer status ==="
    sudo systemctl list-timers youtube-short.timer youtube-long.timer --no-pager
    echo ""
    echo "=== Last short run ==="
    sudo systemctl status youtube-short.service --no-pager -l 2>/dev/null | tail -20 || true
    echo ""
    echo "=== Last long run ==="
    sudo systemctl status youtube-long.service --no-pager -l 2>/dev/null | tail -20 || true
    ;;

  logs-short)
    tail -f "$LOG_DIR/short.log"
    ;;

  logs-long)
    tail -f "$LOG_DIR/long.log"
    ;;

  logs-main)
    tail -f "$APP_DIR/pipeline.log"
    ;;

  update)
    echo "Pulling latest code..."
    cd "$APP_DIR"
    sudo git pull origin main
    echo "Updating Python dependencies..."
    "$VENV_DIR/bin/pip" install -r requirements.txt --quiet
    echo "Reloading systemd..."
    sudo systemctl daemon-reload
    sudo systemctl restart youtube-short.timer youtube-long.timer
    echo "Update complete."
    ;;

  next-runs)
    echo "=== Scheduled runs ==="
    sudo systemctl list-timers --all | grep youtube
    ;;

  disk)
    echo "=== Disk usage ==="
    df -h /
    echo ""
    echo "=== Workspace size ==="
    du -sh "$APP_DIR/workspace" 2>/dev/null || echo "No workspace yet"
    echo ""
    echo "=== Log size ==="
    du -sh "$LOG_DIR" 2>/dev/null || echo "No logs yet"
    ;;

  clean)
    echo "Cleaning workspace dirs older than 7 days..."
    find "$APP_DIR/workspace" -maxdepth 1 -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true
    echo "Done."
    ;;

  help|*)
    echo "Usage: $0 {run-short|run-long|status|logs-short|logs-long|logs-main|update|next-runs|disk|clean}"
    ;;

esac
