"""
GreenwashGuard Engine
=====================
Verifies company ESG claims against live web evidence using Bright Data + Groq AI.

Checks:
- Carbon neutrality claims vs news evidence
- Sustainability report claims vs regulatory filings
- DEI claims vs Glassdoor/employee reviews
- Environmental certifications vs public records
- Social responsibility claims vs news coverage

Output: Integrity Score (0-100) with per-claim verification
"""

import asyncio
import os
import json
import sys
from typing import Dict, List
from bs4 import BeautifulSoup
from groq import Groq
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ── Path setup ────────────────────────────────────────────────────────────────
_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from bright_data_client import bright_data

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ── HTML Parser ───────────────────────────────────────────────────────────────
def parse_html_text(html: str, max_chars: int = 3000) -> str:
    """Extract clean text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())[:max_chars]


def parse_serp_results(html: str, limit: int = 8) -> List[Dict]:
    """Extract search results from SERP HTML."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for g in soup.find_all("div", class_="g")[:limit]:
        title_tag = g.find("h3")
        link_tag = g.find("a")
        snippet_tag = g.find("div", {"data-sncf": "1"}) or g.find("span", class_="aCOpRe")

        if title_tag and link_tag:
            results.append({
                "title":   title_tag.get_text(strip=True),
                "url":     link_tag.get("href", ""),
                "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
            })

    if not results:
        for a in soup.find_all("a")[:20]:
            text = a.get_text(strip=True)
            href = a.get("href", "")
            if text and href.startswith("http") and len(text) > 20:
                results.append({"title": text[:150], "url": href, "snippet": ""})

    return results[:limit]


# ── ESG Data Collection ───────────────────────────────────────────────────────
async def collect_esg_data(company_name: str, company_url: str) -> Dict:
    """Collect ESG-related data from multiple sources."""
    logger.info(f"Collecting ESG data for {company_name}...")

    # Run all 4 SERP searches in parallel
    esg_claims_html, controversies_html, employee_html, regulatory_html = await asyncio.gather(
        bright_data.search_serp(f"{company_name} sustainability ESG claims carbon neutral 2024 2025"),
        bright_data.search_serp(f"{company_name} greenwashing ESG controversy criticism lawsuit"),
        bright_data.search_serp(f"{company_name} Glassdoor employee reviews diversity inclusion workplace"),
        bright_data.search_serp(f"{company_name} environmental certification ISO regulatory filing SEC ESG"),
    )

    # Try sustainability page once — fail fast, no retries
    sustainability_text = ""
    try:
        sustainability_url = company_url.rstrip("/") + "/sustainability"
        html = await bright_data.unlock_url(sustainability_url)
        sustainability_text = parse_html_text(html, max_chars=2000)
        logger.info(f"Fetched sustainability page for {company_name}")
    except Exception:
        try:
            esg_url = company_url.rstrip("/") + "/esg"
            html = await bright_data.unlock_url(esg_url)
            sustainability_text = parse_html_text(html, max_chars=2000)
        except Exception:
            sustainability_text = ""

    return {
        "esg_claims":       parse_serp_results(esg_claims_html),
        "controversies":    parse_serp_results(controversies_html),
        "employee_reviews": parse_serp_results(employee_html),
        "regulatory":       parse_serp_results(regulatory_html),
        "sustainability_page": sustainability_text,
    }


# ── ESG Claim Extraction ──────────────────────────────────────────────────────
async def extract_esg_claims(company_name: str, esg_data: Dict) -> List[Dict]:
    """Use Groq AI to extract specific verifiable ESG claims."""
    claims_text = "\n".join([
        f"- {r['title']}: {r['snippet']}"
        for r in esg_data["esg_claims"][:6]
    ])

    sustainability_text = esg_data["sustainability_page"][:1000]

    prompt = f"""Extract specific verifiable ESG claims made by {company_name} from the following web data.

SUSTAINABILITY PAGE CONTENT:
{sustainability_text}

ESG NEWS/CLAIMS FOUND:
{claims_text}

Return ONLY valid JSON array (no markdown):
[
  {{
    "claim": "<specific verifiable claim made by the company>",
    "category": "<Environmental|Social|Governance>",
    "specificity": "<high|medium|low>"
  }}
]

Extract up to 6 most specific claims. Focus on measurable claims like:
- Carbon neutrality by year X
- X% renewable energy
- X% women in leadership
- ISO/certification claims
- Specific emissions reduction targets

Note: Only extract claims the company actively makes about itself. Do not invent claims."""

    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
        )
        content = chat.choices[0].message.content
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception as e:
        logger.error(f"Claim extraction error: {e}")
        return [
            {"claim": f"{company_name} has sustainability initiatives", "category": "Environmental", "specificity": "low"},
            {"claim": f"{company_name} promotes workplace diversity", "category": "Social", "specificity": "low"},
        ]


# ── Integrity Scoring ─────────────────────────────────────────────────────────
async def score_esg_integrity(
    company_name: str,
    claims: List[Dict],
    esg_data: Dict
) -> Dict:
    """Score ESG integrity using Groq AI cross-referencing claims vs evidence."""

    claims_text = "\n".join([
        f"- [{c['category']}] {c['claim']} (specificity: {c['specificity']})"
        for c in claims
    ])

    controversies_text = "\n".join([
        f"- {r['title']}: {r['snippet']}"
        for r in esg_data["controversies"][:5]
    ])

    regulatory_text = "\n".join([
        f"- {r['title']}: {r['snippet']}"
        for r in esg_data["regulatory"][:5]
    ])

    employee_text = "\n".join([
        f"- {r['title']}: {r['snippet']}"
        for r in esg_data["employee_reviews"][:4]
    ])

    prompt = f"""You are an ESG integrity analyst. Evaluate {company_name}'s ESG claims against web evidence.

COMPANY CLAIMS:
{claims_text}

CONTROVERSIES/CRITICISM FOUND:
{controversies_text or "No controversies found"}

REGULATORY/CERTIFICATION EVIDENCE:
{regulatory_text or "No regulatory data found"}

EMPLOYEE REVIEWS:
{employee_text or "No employee review data found"}

Analyze whether the claims are supported, contradicted, or unverifiable based on the evidence.

Return ONLY valid JSON (no markdown):
{{
  "integrity_score": <0-100>,
  "environmental_score": <0-100>,
  "social_score": <0-100>,
  "governance_score": <0-100>,
  "verified_claims": <number of claims supported by evidence>,
  "contradicted_claims": <number of claims contradicted by evidence>,
  "greenwash_risk": "<low|medium|high>",
  "summary": "<2-3 sentence integrity assessment>",
  "biggest_risk": "<the most concerning gap between claims and evidence>",
  "recommendation": "<one-line action for compliance/risk teams>"
}}

Scoring guide:
- 85-100: Verified ESG claims with strong evidence, no significant controversies
- 70-84: Good ESG integrity, minor gaps or unverified claims but no major contradictions
- 55-69: Moderate integrity, some unverified claims, possible minor controversies
- 40-54: Significant gaps, several unverified claims, notable controversies found
- 0-39: High greenwash risk, claims contradicted by evidence, major controversies

Important: Major tech companies like Microsoft, Google, Apple with published sustainability
reports and third-party verified ESG scores should generally score 65-85 unless specific
contradictions are found. Oil/gas companies with greenwashing lawsuits should score 30-50."""

    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        return json.loads(chat.choices[0].message.content)
    except Exception as e:
        logger.error(f"ESG scoring error: {e}")
        return {
            "integrity_score": 50,
            "environmental_score": 50,
            "social_score": 50,
            "governance_score": 50,
            "verified_claims": 0,
            "contradicted_claims": 0,
            "greenwash_risk": "medium",
            "summary": "ESG analysis could not be completed",
            "biggest_risk": "Insufficient data",
            "recommendation": "Manual ESG review required",
        }


# ── Main Entry Point ──────────────────────────────────────────────────────────
async def analyze_esg(company: Dict) -> Dict:
    """
    Main entry point for the GreenwashGuard engine.
    Returns: integrity_score, claims, greenwash_risk, evidence
    """
    company_name = company.get("name", "Unknown")
    company_url  = company.get("url", "")
    logger.info(f"Starting GreenwashGuard for {company_name}")

    try:
        # 1. Collect ESG data from web
        esg_data = await collect_esg_data(company_name, company_url)

        # 2. Extract specific claims
        claims = await extract_esg_claims(company_name, esg_data)

        # 3. Score integrity
        scores = await score_esg_integrity(company_name, claims, esg_data)

        # 4. Build evidence list
        evidence = []
        for category in ["esg_claims", "controversies", "regulatory"]:
            if esg_data[category]:
                evidence.append({
                    "category": category,
                    "title":    esg_data[category][0]["title"],
                    "url":      esg_data[category][0]["url"],
                })

        result = {
            "company_name":       company_name,
            "integrity_score":    scores["integrity_score"],
            "breakdown": {
                "environmental": scores["environmental_score"],
                "social":        scores["social_score"],
                "governance":    scores["governance_score"],
            },
            "greenwash_risk":     scores["greenwash_risk"],
            "verified_claims":    scores["verified_claims"],
            "contradicted_claims": scores["contradicted_claims"],
            "claims_found":       claims,
            "summary":            scores["summary"],
            "biggest_risk":       scores["biggest_risk"],
            "recommendation":     scores["recommendation"],
            "evidence":           evidence,
            "total_sources_checked": sum(len(v) for v in esg_data.values() if isinstance(v, list)),
        }

        logger.info(f"GreenwashGuard complete for {company_name}: score={scores['integrity_score']}, risk={scores['greenwash_risk']}")
        return result

    except Exception as e:
        logger.error(f"GreenwashGuard failed for {company_name}: {e}")
        return {
            "company_name":        company_name,
            "integrity_score":     0,
            "breakdown":           {"environmental": 0, "social": 0, "governance": 0},
            "greenwash_risk":      "unknown",
            "verified_claims":     0,
            "contradicted_claims": 0,
            "claims_found":        [],
            "summary":             "ESG analysis could not be completed. Manual review required.",
            "biggest_risk":        "Engine error — insufficient data",
            "recommendation":      "Retry analysis or review manually.",
            "evidence":            [],
            "total_sources_checked": 0,
        }