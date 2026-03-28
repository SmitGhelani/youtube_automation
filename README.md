# Autonomous YouTube Channel — Complete Setup Guide

## Overview
This system automatically creates and uploads YouTube Shorts (daily, 9 AM IST) and long-form videos (weekly, Saturday 6 PM IST) with zero human intervention.

---

## Architecture
```
GitHub Actions (free cron scheduler)
    ↓
Trend Agent    → Google Trends + Reddit + NewsAPI (all free)
    ↓
Script Agent   → Claude API (Anthropic)
    ↓
[Parallel]
  Audio Agent  → ElevenLabs TTS (free tier) + Bensound music (free CC)
  Video Agent  → Pexels API (free stock footage)
  Thumb Agent  → Pillow (free Python library)
    ↓
Assembler      → FFmpeg (free, open source)
    ↓
SEO Agent      → Claude API
    ↓
Compliance     → Rule-based check (free)
    ↓
Upload Agent   → YouTube Data API v3 (free)
    ↓
Notification   → SendGrid email (free tier: 100/day)
```

---

## Step-by-Step Setup (estimated time: 2-3 hours)

### Step 1: Get Free API Keys

#### 1a. Anthropic (Claude API)
- Go to: https://console.anthropic.com
- Sign up → API Keys → Create key
- Free tier: $5 credit on signup (enough for ~1 month of videos)
- **Secret name:** `ANTHROPIC_API_KEY`

#### 1b. Pexels API (Stock Video — FREE)
- Go to: https://www.pexels.com/api/
- Sign up → Request API access (instant approval)
- 200 requests/hour, unlimited total — completely free
- **Secret name:** `PEXELS_API_KEY`

#### 1c. ElevenLabs TTS (Optional, better voice quality)
- Go to: https://elevenlabs.io
- Sign up free → API Key tab
- Free tier: 10,000 characters/month (~20 Shorts/month)
- If budget runs out, system auto-falls back to pyttsx3 (free offline TTS)
- **Secret name:** `ELEVENLABS_API_KEY`

#### 1d. NewsAPI (Optional, for trending news)
- Go to: https://newsapi.org
- Sign up free → API key
- Free tier: 100 requests/day
- **Secret name:** `NEWS_API_KEY`

#### 1e. SendGrid (Optional, email notifications)
- Go to: https://sendgrid.com
- Sign up free → Settings → API Keys → Create
- Free tier: 100 emails/day
- **Secret names:** `SENDGRID_API_KEY`, `NOTIFICATION_EMAIL`

---

### Step 2: Set Up YouTube API

1. Go to https://console.cloud.google.com
2. Click "New Project" → Name it "AutoYT"
3. Go to "APIs & Services" → "Library"
4. Search "YouTube Data API v3" → Enable
5. Go to "APIs & Services" → "Credentials"
6. Click "Create Credentials" → "OAuth 2.0 Client ID"
7. Application type: **Desktop app** → Name: "AutoYT Bot" → Create
8. Click download (↓) next to your credentials → Save as `client_secret.json`

Now run the OAuth setup locally:
```bash
pip install google-auth-oauthlib google-api-python-client
python setup_youtube_oauth.py --credentials client_secret.json
```

A browser will open → log in with your YouTube channel account → authorize.

Copy the tokens shown in terminal to GitHub Secrets:
- `YOUTUBE_REFRESH_TOKEN`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`

---

### Step 3: Set Up GitHub Repository

1. Go to https://github.com → New repository → name: `auto-youtube-channel`
2. Make it **Private** (your API keys will be in secrets, not code)
3. Upload all project files:
   ```bash
   git init
   git add .
   git commit -m "Initial autonomous YouTube pipeline"
   git remote add origin https://github.com/YOUR_USERNAME/auto-youtube-channel.git
   git push -u origin main
   ```

4. Go to your repo → Settings → Secrets and variables → Actions → New repository secret

Add each secret:
| Secret Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | sk-ant-... |
| `PEXELS_API_KEY` | your_pexels_key |
| `ELEVENLABS_API_KEY` | your_elevenlabs_key (optional) |
| `NEWS_API_KEY` | your_newsapi_key (optional) |
| `YOUTUBE_CLIENT_ID` | your_client_id |
| `YOUTUBE_CLIENT_SECRET` | your_client_secret |
| `YOUTUBE_REFRESH_TOKEN` | your_refresh_token |
| `NOTIFICATION_EMAIL` | your@email.com (optional) |
| `SENDGRID_API_KEY` | your_sendgrid_key (optional) |

---

### Step 4: Test the Pipeline

1. Go to your GitHub repo → Actions tab
2. Click "Autonomous YouTube Pipeline"
3. Click "Run workflow" → select `short` → Run
4. Watch the logs — should complete in 10-15 minutes
5. Check your YouTube channel for the uploaded video

---

### Step 5: Enable Automated Schedule

The workflow will automatically run:
- **Daily at 9:00 AM IST** (3:30 AM UTC) — creates and uploads a Short
- **Every Saturday at 6:00 PM IST** (12:30 PM UTC) — creates and uploads a long video

GitHub Actions runs automatically once you push the workflow file. No server needed.

---

## Cost Breakdown (Monthly)

| Service | Free Tier | Monthly Cost |
|---|---|---|
| GitHub Actions | 2,000 min/month free | $0 |
| Anthropic API | $5 credit on signup | ~$3-8/month after credit |
| Pexels API | Unlimited free | $0 |
| ElevenLabs TTS | 10k chars/month free | $0 (or $5 for more) |
| NewsAPI | 100 req/day free | $0 |
| YouTube API | Free (quota based) | $0 |
| SendGrid | 100 emails/day free | $0 |
| **TOTAL** | | **$0-8/month** |

---

## YouTube Monetization Path (Within a Week)

To qualify for YouTube Partner Program (YPP):
- **1,000 subscribers** + **4,000 watch hours** (long videos)
- OR **1,000 subscribers** + **10 million Shorts views**

### Week 1 Strategy:
1. **Day 1-2:** Test pipeline, post first 2-3 Shorts
2. **Day 3-4:** Check analytics, see which topics get views
3. **Day 5-6:** Pipeline running autonomously, focus on niche
4. **Day 7:** First long-form video (Saturday)

### To Speed Up Monetization:
- Choose a niche with high CPM: AI Tools, Finance, Tech Reviews (₹80-300 CPM)
- Cross-post Shorts to Instagram Reels and TikTok manually
- Reply to every comment in the first 24 hours (boosts algorithm)

---

## Compliance & Safety Rules

The pipeline enforces these automatically:

✅ **Always includes:**
- Music attribution in video description
- No medical/financial advice without disclaimers
- Family-friendly content rating
- Standard YouTube license

🚫 **Never creates:**
- Content mentioning religion, politics, violence
- Content targeting any country, ethnicity, or group
- Misleading thumbnails or titles (clickbait without delivery)
- Copyright-infringing music or footage

---

## Troubleshooting

**Video not uploading?**
- Check `YOUTUBE_REFRESH_TOKEN` hasn't expired (re-run `setup_youtube_oauth.py`)
- Ensure YouTube channel has no strikes or restrictions
- Check daily upload quota (YouTube allows ~6 uploads/day via API)

**Audio sounds robotic?**
- Add `ELEVENLABS_API_KEY` for much better voice quality
- Or adjust pyttsx3 rate in `audio_agent.py`

**No trending topics found?**
- Add `NEWS_API_KEY` for more news sources
- Check pytrends isn't rate-limited (try again in 1 hour)

**FFmpeg errors?**
- The GitHub Actions workflow installs FFmpeg automatically
- For local testing: `sudo apt-get install ffmpeg` (Linux) or `brew install ffmpeg` (Mac)

---

## Customizing Your Channel

Edit `config.py` or set environment variable:
```
CHANNEL_NICHE = "Personal Finance & Money Tips for Young Indians"
```

Popular niches for India (high CPM):
- AI & Technology Tools
- Personal Finance & Investing  
- Health & Wellness Science
- Science Discoveries & Space
- Business & Entrepreneurship

---

## File Structure

```
autonomous_youtube/
├── main.py                    # Master orchestrator
├── config.py                  # All configuration
├── requirements.txt           # Python dependencies
├── setup_youtube_oauth.py     # One-time OAuth setup
├── .github/
│   └── workflows/
│       └── youtube_pipeline.yml  # GitHub Actions cron
└── agents/
    ├── __init__.py
    ├── trend_agent.py         # Find trending topics
    ├── script_agent.py        # Generate video script
    ├── audio_agent.py         # TTS + background music
    ├── video_agent.py         # Download B-roll footage
    ├── thumbnail_agent.py     # Generate thumbnail
    ├── assembler_agent.py     # FFmpeg video assembly
    ├── seo_agent.py           # Generate metadata
    ├── compliance_agent.py    # Policy checks
    ├── upload_agent.py        # YouTube upload
    └── notification_agent.py  # Email reports
```
