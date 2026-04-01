#!/usr/bin/env bash
# =============================================================================
# aws/ops.sh
#
# Day-to-day operations helper for the EC2 pipeline.
# Run on the EC2 instance after setup_ec2.sh has been executed.
#
# Usage:
#   ./ops.sh status          — show timer and service status
#   ./ops.sh run-short       — run short video pipeline right now
#   ./ops.sh run-long        — run long video pipeline right now
#   ./ops.sh logs-short      — tail short video logs
#   ./ops.sh logs-long       — tail long video logs
#   ./ops.sh update          — git pull + pip install + restart timers
#   ./ops.sh next-runs       — show when next runs are scheduled
#   ./ops.sh disk            — show disk usage (workspace can grow large)
#   ./ops.sh clean           — delete workspace dirs older than 7 days
# =============================================================================

set -euo pipefail

APP_DIR="/opt/youtube-pipeline"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="/var/log/youtube-pipeline"

case "${1:-help}" in

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

  run-short)
    echo "Running short video pipeline now..."
    cd "$APP_DIR"
    sudo -u ubuntu "$VENV_DIR/bin/python" main.py --type short
    ;;

  run-long)
    echo "Running long video pipeline now..."
    cd "$APP_DIR"
    sudo -u ubuntu "$VENV_DIR/bin/python" main.py --type long
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
    sudo -u ubuntu "$VENV_DIR/bin/pip" install -r requirements.txt --quiet
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
    du -sh "$APP_DIR/workspace" 2>/dev/null || echo "No workspace directory yet"
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
    echo "Usage: $0 {status|run-short|run-long|logs-short|logs-long|logs-main|update|next-runs|disk|clean}"
    ;;

esac
