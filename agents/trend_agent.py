"""
agents/trend_agent.py
Finds trending topics from Google Trends, Reddit, and News APIs.
All sources used are free.
"""

import logging
import random
import requests
from typing import Optional
from pytrends.request import TrendReq

logger = logging.getLogger("TrendAgent")


class TrendAgent:
    def __init__(self, config):
        self.cfg = config
        self.pytrends = TrendReq(hl="en-US", tz=330)  # tz=330 for India (IST)

    def find_trending_topic(self, video_type: str) -> dict:
        """
        Finds a trending topic suitable for the channel niche.
        Returns: {topic, context, search_volume, source}
        """
        candidates = []

        # Source 1: Google Trends (free, no API key needed)
        try:
            candidates += self._from_google_trends()
        except Exception as e:
            logger.warning(f"Google Trends failed: {e}")

        # Source 2: Reddit trending (free)
        try:
            candidates += self._from_reddit()
        except Exception as e:
            logger.warning(f"Reddit scrape failed: {e}")

        # Source 3: NewsAPI (free tier: 100 requests/day)
        try:
            candidates += self._from_newsapi()
        except Exception as e:
            logger.warning(f"NewsAPI failed: {e}")

        if not candidates:
            # Fallback: evergreen tech topics
            candidates = self._fallback_topics()

        # Pick the best topic using Claude to score relevance
        best = self._rank_with_claude(candidates, video_type)
        logger.info(f"Selected topic: {best['topic']}")
        return best

    def _from_google_trends(self) -> list:
        """Fetch trending searches from Google Trends — completely free."""
        self.pytrends.build_payload(
            kw_list=["AI", "technology", "science", "innovation"],
            timeframe="now 1-d",
            geo="",
        )
        related = self.pytrends.related_queries()
        topics = []
        for kw, data in related.items():
            if data["top"] is not None:
                for _, row in data["top"].head(5).iterrows():
                    topics.append({
                        "topic": row["query"],
                        "search_volume": int(row["value"]),
                        "source": "google_trends",
                        "context": f"Trending search related to {kw}",
                    })
        return topics

    def _from_reddit(self) -> list:
        """Scrape r/technology, r/artificial, r/science hot posts — free."""
        subreddits = ["technology", "artificial", "science", "MachineLearning", "Futurology"]
        topics = []
        headers = {"User-Agent": "AutoYT-Bot/1.0 (educational project)"}

        for sub in subreddits[:3]:
            try:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=5"
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    posts = resp.json()["data"]["children"]
                    for post in posts:
                        d = post["data"]
                        if d["score"] > 500 and not d["over_18"]:
                            topics.append({
                                "topic": d["title"],
                                "search_volume": d["score"],
                                "source": f"reddit_r/{sub}",
                                "context": d.get("selftext", "")[:200],
                            })
            except Exception as e:
                logger.warning(f"Reddit r/{sub} failed: {e}")

        return topics

    def _from_newsapi(self) -> list:
        """
        NewsAPI free tier: 100 requests/day, news from last 24h.
        Sign up free at newsapi.org
        """
        import os
        api_key = os.environ.get("NEWS_API_KEY", "")
        if not api_key:
            return []

        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "apiKey": api_key,
            "category": "technology",
            "language": "en",
            "pageSize": 10,
        }
        resp = requests.get(url, params=params, timeout=10)
        topics = []
        if resp.status_code == 200:
            for article in resp.json().get("articles", []):
                if article.get("title") and article.get("description"):
                    topics.append({
                        "topic": article["title"],
                        "search_volume": 1000,  # estimate
                        "source": "newsapi",
                        "context": article["description"],
                    })
        return topics

    def _fallback_topics(self) -> list:
        """Evergreen topics that always perform well."""
        evergreen = [
            "How AI is changing everyday life in 2025",
            "Top 5 free AI tools you need to try today",
            "Scientists discover breakthrough in quantum computing",
            "How to use ChatGPT to make money online",
            "The future of jobs in an AI world",
            "New robot that can do household chores",
            "Self-driving cars update 2025",
            "Brain-computer interface breakthrough",
        ]
        return [
            {"topic": t, "search_volume": 500, "source": "fallback", "context": ""}
            for t in random.sample(evergreen, 5)
        ]

    def _rank_with_claude(self, candidates: list, video_type: str) -> dict:
        """Use Claude to pick the best topic for the channel."""
        import anthropic
        client = anthropic.Anthropic(api_key=self.cfg.anthropic_api_key)

        topic_list = "\n".join(
            f"{i+1}. {c['topic']} [score:{c.get('search_volume',0)}] (source:{c['source']})"
            for i, c in enumerate(candidates[:15])
        )

        prompt = f"""You are a YouTube content strategist. 
Channel niche: {self.cfg.channel_niche}
Target audience: {self.cfg.target_audience}
Video type: {video_type} ({'60-second Short' if video_type=='short' else '8-12 min long video'})

Here are trending topics:
{topic_list}

Select the SINGLE BEST topic that:
1. Fits the channel niche perfectly
2. Has strong viewer appeal and curiosity factor
3. Is safe — no politics, religion, adult content, violence
4. Is factual and educational
5. Will perform well as a {video_type} video

Respond ONLY with valid JSON, no markdown:
{{
  "topic": "exact topic title",
  "angle": "specific creative angle to approach it",
  "hook": "first 5 words to grab attention",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "source": "source name",
  "search_volume": 0,
  "context": "brief context about why this is trending"
}}"""

        message = client.messages.create(
            model=self.cfg.claude_model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        text = message.content[0].text.strip()
        # Remove any markdown fences if present
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
