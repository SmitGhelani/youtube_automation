#!/usr/bin/env bash
# =============================================================================
# aws/setup_ec2.sh
#
# One-shot bootstrap script for the Autonomous YouTube Pipeline on EC2.
# Run this ONCE on a fresh Ubuntu 22.04 instance as the ubuntu user.
#
# Usage:
#   chmod +x setup_ec2.sh
#   ./setup_ec2.sh
#
# What this does:
#   1. Installs all system packages (FFmpeg with libsoxr, Python 3.11, git)
#   2. Clones your repo from GitHub
#   3. Creates a Python virtualenv and installs all pip deps
#   4. Downloads and caches Kokoro TTS model files
#   5. Creates /etc/youtube-pipeline.env for secrets (you fill in the values)
#   6. Installs two systemd services (short + long video)
#   7. Installs two systemd timers (cron replacement — more reliable than crontab)
#   8. Sets up log rotation
#   9. Starts everything and prints a health check
#
# After running:
#   - Edit /etc/youtube-pipeline.env with your real API keys
#   - Run: sudo systemctl daemon-reload && sudo systemctl start youtube-short.timer
# =============================================================================

set -euo pipefail

# ── Config — edit these before running ───────────────────────────────────────
REPO_URL="https://github.com/YOUR_USERNAME/autonomous_youtube.git"   # <-- change this
REPO_BRANCH="main"
APP_DIR="/opt/youtube-pipeline"
VENV_DIR="$APP_DIR/venv"
APP_USER="ubuntu"          # EC2 default user; change if using a custom AMI
LOG_DIR="/var/log/youtube-pipeline"
KOKORO_MODEL_DIR="$APP_DIR"   # model files live in project root (expected by audio_agent.py)

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

info "=== Autonomous YouTube Pipeline — EC2 Bootstrap ==="
info "App dir   : $APP_DIR"
info "App user  : $APP_USER"
info "Log dir   : $LOG_DIR"

# ── 1. System packages ────────────────────────────────────────────────────────
info "Step 1/9 | Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    ffmpeg \
    libsox-fmt-all \
    fonts-open-sans \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    git \
    curl \
    wget \
    logrotate \
    htop \
    unzip

# Verify soxr resampler (critical for audio quality)
ffmpeg -filters 2>/dev/null | grep -i soxr \
    && info "soxr resampler: AVAILABLE" \
    || warn "soxr not found — audio may use lower-quality resampler"

info "ffmpeg: $(ffmpeg -version 2>&1 | head -1)"
info "python: $(python3.11 --version)"

# ── 2. Clone repository ───────────────────────────────────────────────────────
info "Step 2/9 | Cloning repository..."
if [ -d "$APP_DIR/.git" ]; then
    warn "$APP_DIR already exists — pulling latest instead of cloning"
    cd "$APP_DIR" && git pull origin "$REPO_BRANCH"
else
    sudo git clone --branch "$REPO_BRANCH" "$REPO_URL" "$APP_DIR"
    sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR"
fi
cd "$APP_DIR"
info "Repo cloned to $APP_DIR"

# ── 3. Python virtualenv + dependencies ───────────────────────────────────────
info "Step 3/9 | Creating Python virtualenv and installing dependencies..."
python3.11 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip wheel
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"
info "Python dependencies installed"

# ── 4. Kokoro TTS model files ─────────────────────────────────────────────────
info "Step 4/9 | Downloading Kokoro TTS model files (~330 MB total)..."
KOKORO_ONNX="$KOKORO_MODEL_DIR/kokoro-v1.0.onnx"
KOKORO_VOICES="$KOKORO_MODEL_DIR/voices-v1.0.bin"
KOKORO_BASE="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"

if [ ! -f "$KOKORO_ONNX" ]; then
    info "Downloading kokoro-v1.0.onnx..."
    wget -q --show-progress --retry-connrefused --tries=3 \
        -O "$KOKORO_ONNX" "$KOKORO_BASE/kokoro-v1.0.onnx"
else
    info "kokoro-v1.0.onnx already present — skipping download"
fi

if [ ! -f "$KOKORO_VOICES" ]; then
    info "Downloading voices-v1.0.bin..."
    wget -q --show-progress --retry-connrefused --tries=3 \
        -O "$KOKORO_VOICES" "$KOKORO_BASE/voices-v1.0.bin"
else
    info "voices-v1.0.bin already present — skipping download"
fi

# Verify model files
test -f "$KOKORO_ONNX"   || error "kokoro-v1.0.onnx download failed"
test -f "$KOKORO_VOICES" || error "voices-v1.0.bin download failed"
info "Kokoro model: $(du -sh $KOKORO_ONNX | cut -f1)"
info "Kokoro voices: $(du -sh $KOKORO_VOICES | cut -f1)"

# ── 5. Environment file (secrets) ─────────────────────────────────────────────
info "Step 5/9 | Creating environment file at /etc/youtube-pipeline.env..."
ENV_FILE="/etc/youtube-pipeline.env"

if [ -f "$ENV_FILE" ]; then
    warn "$ENV_FILE already exists — not overwriting. Check it has all required keys."
else
    sudo tee "$ENV_FILE" > /dev/null << 'ENVEOF'
# /etc/youtube-pipeline.env
# Fill in ALL values before starting the pipeline.
# Permissions are set to 640 (root:ubuntu readable only).

# ── Required API keys ─────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=your_anthropic_api_key_here
PEXELS_API_KEY=your_pexels_api_key_here
YOUTUBE_CLIENT_ID=your_youtube_client_id_here
YOUTUBE_CLIENT_SECRET=your_youtube_client_secret_here
YOUTUBE_REFRESH_TOKEN=your_youtube_refresh_token_here

# ── Optional API keys ─────────────────────────────────────────────────────────
ELEVENLABS_API_KEY=
FREESOUND_API_KEY=
SENDGRID_API_KEY=
NOTIFICATION_EMAIL=

# ── Channel settings ──────────────────────────────────────────────────────────
CHANNEL_NICHE=AI & Technology — Latest discoveries, tools, and breakthroughs

# ── AWS-specific (optional — for CloudWatch log shipping) ─────────────────────
AWS_DEFAULT_REGION=ap-south-1
ENVEOF
    sudo chmod 640 "$ENV_FILE"
    sudo chown root:"$APP_USER" "$ENV_FILE"
    warn "IMPORTANT: Edit $ENV_FILE with your real API keys before starting the pipeline"
fi

# ── 6. Log directory ──────────────────────────────────────────────────────────
info "Step 6/9 | Creating log directory..."
sudo mkdir -p "$LOG_DIR"
sudo chown "$APP_USER:$APP_USER" "$LOG_DIR"

# ── 7. Systemd service units ──────────────────────────────────────────────────
info "Step 7/9 | Installing systemd service units..."

# Short video service
sudo tee /etc/systemd/system/youtube-short.service > /dev/null << SVCEOF
[Unit]
Description=Autonomous YouTube Pipeline — Short Video
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_DIR/bin/python main.py --type short
StandardOutput=append:$LOG_DIR/short.log
StandardError=append:$LOG_DIR/short.log
TimeoutStartSec=3600
# Restart on failure (up to 3 times with 5 min gap)
Restart=on-failure
RestartSec=300
StartLimitBurst=3
StartLimitIntervalSec=900

[Install]
WantedBy=multi-user.target
SVCEOF

# Long video service
sudo tee /etc/systemd/system/youtube-long.service > /dev/null << SVCEOF
[Unit]
Description=Autonomous YouTube Pipeline — Long Video
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_DIR/bin/python main.py --type long
StandardOutput=append:$LOG_DIR/long.log
StandardError=append:$LOG_DIR/long.log
TimeoutStartSec=10800
Restart=on-failure
RestartSec=300
StartLimitBurst=3
StartLimitIntervalSec=900

[Install]
WantedBy=multi-user.target
SVCEOF

info "Service units installed"

# ── 8. Systemd timer units (replaces cron) ────────────────────────────────────
info "Step 8/9 | Installing systemd timer units..."

# Short video timer — daily at 9:00 AM IST (3:30 AM UTC)
sudo tee /etc/systemd/system/youtube-short.timer > /dev/null << TIMEREOF
[Unit]
Description=Trigger Short YouTube Video — Daily 9:00 AM IST
Requires=youtube-short.service

[Timer]
# IST = UTC+5:30 → 9:00 AM IST = 03:30 UTC
OnCalendar=*-*-* 03:30:00 UTC
AccuracySec=60
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
TIMEREOF

# Long video timer — every Saturday at 6:00 PM IST (12:30 PM UTC)
sudo tee /etc/systemd/system/youtube-long.timer > /dev/null << TIMEREOF
[Unit]
Description=Trigger Long YouTube Video — Saturday 6:00 PM IST
Requires=youtube-long.service

[Timer]
# IST = UTC+5:30 → 6:00 PM IST = 12:30 UTC, Saturday = 6
OnCalendar=Sat *-*-* 12:30:00 UTC
AccuracySec=60
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
TIMEREOF

info "Timer units installed"

# ── 9. Log rotation ───────────────────────────────────────────────────────────
info "Step 9/9 | Configuring log rotation..."
sudo tee /etc/logrotate.d/youtube-pipeline > /dev/null << 'LOGEOF'
/var/log/youtube-pipeline/*.log /opt/youtube-pipeline/pipeline.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ubuntu ubuntu
}
LOGEOF

# ── Enable and start timers ───────────────────────────────────────────────────
sudo systemctl daemon-reload
sudo systemctl enable youtube-short.timer youtube-long.timer
sudo systemctl start  youtube-short.timer youtube-long.timer

# ── Health check ──────────────────────────────────────────────────────────────
echo ""
info "=== Setup Complete — Health Check ==="
echo ""

echo "--- Systemd timers ---"
sudo systemctl list-timers --all | grep youtube

echo ""
echo "--- Service status ---"
sudo systemctl status youtube-short.timer --no-pager -l | head -15
sudo systemctl status youtube-long.timer  --no-pager -l | head -15

echo ""
echo "--- Kokoro model files ---"
ls -lh "$KOKORO_ONNX" "$KOKORO_VOICES"

echo ""
echo "--- Python environment ---"
"$VENV_DIR/bin/python" -c "import kokoro_onnx, soundfile, scipy, numpy; print('All Python deps OK')"

echo ""
warn "ACTION REQUIRED: Edit /etc/youtube-pipeline.env with your real API keys"
warn "Then test manually: cd $APP_DIR && $VENV_DIR/bin/python main.py --type short"
echo ""
info "=== Bootstrap complete ==="
