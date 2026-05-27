"""
SignalForge Engine
==================
Detects buying signals across the live web using Bright Data + Groq AI.

Signal types:
- Funding announcements
- Hiring trends (job postings)
- Executive changes
- Tech stack changes
- Press releases / news

Output: Signal Score (0-100) with evidence
"""

import asyncio
import sys
import os
import json
from typing import Dict, List
from bs4 import BeautifulSoup
from groq import Groq
from loguru import logger

_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
from bright_data_client import bright_data


groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def parse_serp_html(html: str, limit: int = 10) -> List[Dict]:
    """Parse Google SERP HTML and extract top results."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for g in soup.find_all("div", class_="g")[:limit]:
        title_tag = g.find("h3")
        link_tag = g.find("a")
        snippet_tag = g.find("div", {"data-sncf": "1"}) or g.find("span", class_="aCOpRe")

        if title_tag and link_tag:
            results.append({
                "title": title_tag.get_text(strip=True),
                "url": link_tag.get("href", ""),
                "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
            })

    # Fallback: any link with text
    if not results:
        for a in soup.find_all("a")[:30]:
            text = a.get_text(strip=True)
            href = a.get("href", "")
            if text and href.startswith("http") and len(text) > 20:
                results.append({"title": text[:150], "url": href, "snippet": ""})

    return results[:limit]


async def collect_signals(company_name: str) -> Dict:
    """Gather raw signal data from 4 Bright Data SERP searches."""
    logger.info(f"Collecting signals for {company_name}...")

    funding_html, hiring_html, exec_html, news_html = await asyncio.gather(
        bright_data.search_funding(company_name),
        bright_data.search_hiring(company_name),
        bright_data.search_executive(company_name),
        bright_data.search_news(company_name),
    )

    return {
        "funding":   parse_serp_html(funding_html),
        "hiring":    parse_serp_html(hiring_html),
        "executive": parse_serp_html(exec_html),
        "news":      parse_serp_html(news_html),
    }


def calculate_signal_score(signals: Dict, ai_analysis: Dict) -> int:
    """
    Compute weighted Signal Score (0-100):
    - Funding signal:   30 pts
    - Hiring signal:    25 pts
    - Executive moves:  25 pts
    - News momentum:    20 pts
    """
    score = 0

    funding_strength = ai_analysis.get("funding_strength", 0)
    score += int(funding_strength * 0.30)

    hiring_strength = ai_analysis.get("hiring_strength", 0)
    score += int(hiring_strength * 0.25)

    exec_strength = ai_analysis.get("exec_strength", 0)
    score += int(exec_strength * 0.25)

    news_strength = ai_analysis.get("news_strength", 0)
    score += int(news_strength * 0.20)

    return min(100, max(0, score))


async def analyze_with_ai(company_name: str, signals: Dict) -> Dict:
    """Pass signals to Groq AI for intelligent scoring."""
    funding_text = "\n".join([f"- {s['title']}: {s['snippet']}" for s in signals["funding"][:5]])
    hiring_text  = "\n".join([f"- {s['title']}: {s['snippet']}" for s in signals["hiring"][:5]])
    exec_text    = "\n".join([f"- {s['title']}: {s['snippet']}" for s in signals["executive"][:5]])
    news_text    = "\n".join([f"- {s['title']}: {s['snippet']}" for s in signals["news"][:5]])

    prompt = f"""You are an enterprise buying signal analyst. Analyze the following web data for {company_name} and score each signal category from 0-100.

FUNDING SIGNALS:
{funding_text or "No data"}

HIRING SIGNALS:
{hiring_text or "No data"}

EXECUTIVE SIGNALS:
{exec_text or "No data"}

NEWS MOMENTUM:
{news_text or "No data"}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "funding_strength": <0-100>,
  "hiring_strength": <0-100>,
  "exec_strength": <0-100>,
  "news_strength": <0-100>,
  "top_signal": "<the most important signal found>",
  "buying_intent_summary": "<2-sentence summary of buying intent>",
  "recommendation": "<one-line recommended action for sales team>"
}}"""

    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return json.loads(chat.choices[0].message.content)
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return {
            "funding_strength": 0,
            "hiring_strength": 0,
            "exec_strength": 0,
            "news_strength": 0,
            "top_signal": "AI analysis failed",
            "buying_intent_summary": "Unable to analyze signals",
            "recommendation": "Manual review required",
        }


async def analyze_signals(company: Dict) -> Dict:
    """
    Main entry point for the Signal Engine.
    Returns: signal_score, signals_found, top_signal, recommendation
    """
    company_name = company.get("name", "Unknown")
    logger.info(f"Starting Signal Engine for {company_name}")

    try:
        # 1. Collect raw signals
        signals = await collect_signals(company_name)

        # 2. AI analysis
        ai_analysis = await analyze_with_ai(company_name, signals)

        # 3. Calculate weighted score
        signal_score = calculate_signal_score(signals, ai_analysis)

        # 4. Build response
        top_signals = []
        for category in ["funding", "hiring", "executive", "news"]:
            if signals[category]:
                top_signals.append({
                    "category": category,
                    "title": signals[category][0]["title"],
                    "url": signals[category][0]["url"],
                    "snippet": signals[category][0]["snippet"],
                })

        result = {
            "company_name": company_name,
            "signal_score": signal_score,
            "breakdown": {
                "funding_strength": ai_analysis["funding_strength"],
                "hiring_strength":  ai_analysis["hiring_strength"],
                "exec_strength":    ai_analysis["exec_strength"],
                "news_strength":    ai_analysis["news_strength"],
            },
            "top_signal":            ai_analysis["top_signal"],
            "buying_intent_summary": ai_analysis["buying_intent_summary"],
            "recommendation":        ai_analysis["recommendation"],
            "evidence":              top_signals,
            "total_signals_found":   sum(len(v) for v in signals.values()),
        }

        logger.info(f"Signal Engine complete for {company_name}: score={signal_score}")
        return result

    except Exception as e:
        logger.error(f"Signal Engine failed for {company_name}: {e}")
        return {
            "company_name":          company_name,
            "signal_score":          0,
            "breakdown":             {"funding_strength": 0, "hiring_strength": 0, "exec_strength": 0, "news_strength": 0},
            "top_signal":            "Engine error — analysis could not be completed",
            "buying_intent_summary": "Signal analysis failed. Manual review required.",
            "recommendation":        "Retry analysis or review manually.",
            "evidence":              [],
            "total_signals_found":   0,
        }