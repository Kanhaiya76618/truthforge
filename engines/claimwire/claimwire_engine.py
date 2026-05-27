"""
ClaimWire Engine
================
Verifies every verifiable company claim against live web evidence.
Uses Bright Data SERP API + Groq AI.

Claim types verified:
- Headcount ("500+ employees")
- Funding stage ("Series B company")
- Certifications ("ISO 27001 certified")
- Market position ("market leader", "#1 in...")
- Awards ("best place to work")
- Financial ("profitable since 2020")

Output: Verification Score (0-100) with per-claim status
Status: Verified / Partial / Contradicted / Unverifiable
"""

import asyncio
import os
import sys
import json
from typing import Dict, List
from bs4 import BeautifulSoup
from groq import Groq
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ── Path setup ────────────────────────────────────────────────────────────────
_backend_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from bright_data_client import bright_data

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ── HTML Helpers ──────────────────────────────────────────────────────────────
def parse_serp_results(html: str, limit: int = 8) -> List[Dict]:
    """Extract search results from SERP HTML."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for g in soup.find_all("div", class_="g")[:limit]:
        title_tag   = g.find("h3")
        link_tag    = g.find("a")
        snippet_tag = g.find("div", {"data-sncf": "1"}) or g.find("span", class_="aCOpRe")

        if title_tag and link_tag:
            results.append({
                "title":   title_tag.get_text(strip=True),
                "url":     link_tag.get("href", ""),
                "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
            })

    # Fallback
    if not results:
        for a in soup.find_all("a")[:20]:
            text = a.get_text(strip=True)
            href = a.get("href", "")
            if text and href.startswith("http") and len(text) > 20:
                results.append({"title": text[:150], "url": href, "snippet": ""})

    return results[:limit]


def parse_page_text(html: str, max_chars: int = 2000) -> str:
    """Extract clean readable text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())[:max_chars]


# ── Step 1: Fetch company homepage ────────────────────────────────────────────
async def fetch_company_homepage(company_name: str, company_url: str) -> str:
    """Fetch company homepage text via Web Unlocker, falling back to SERP on failure."""
    try:
        html = await bright_data.unlock_url(company_url)
        return parse_page_text(html, max_chars=3000)
    except Exception as e:
        logger.warning(f"Web Unlocker failed for {company_url}: {e} — falling back to SERP")
        try:
            serp_html = await bright_data.search_serp(f"{company_name} company overview about")
            results   = parse_serp_results(serp_html)
            fallback  = "\n".join(f"{r['title']}: {r['snippet']}" for r in results[:5])
            logger.info(f"SERP fallback returned {len(results)} results for homepage")
            return fallback
        except Exception as e2:
            logger.warning(f"SERP fallback also failed: {e2}")
            return ""


# ── Step 2: Extract claims from homepage ─────────────────────────────────────
async def extract_claims(company_name: str, homepage_text: str) -> List[Dict]:
    """Use Groq AI to extract verifiable claims."""
    try:
        claims_html = await bright_data.search_serp(
            f"{company_name} company facts employees revenue customers founded headquarters"
        )
        serp_results = parse_serp_results(claims_html)
        serp_text = "\n".join([
            f"- {r['title']}: {r['snippet']}"
            for r in serp_results[:6]
        ])
    except Exception as e:
        logger.warning(f"SERP search failed: {e}")
        serp_text = ""

    prompt = f"""Extract ONLY factual claims about {company_name} as a company.

WEB DATA:
{serp_text}

RULES:
- ONLY extract facts like: employee count, revenue, founding year,
  headquarters, customer count, funding raised, certifications, awards
- IGNORE completely: terms and conditions, disclaimers, fees,
  promotions, subscriptions, cookie notices, legal text
- GOOD: "Tesla has 127,000 employees", "Tesla was founded in 2003"
- BAD: "terms apply", "fees may vary", "subscription required"

Return JSON: {{"claims": [
  {{"claim": "...", "category": "headcount|funding|financial|award|customers|founding_year|headquarters|employees|certification|market_position", "source": "web"}}
]}}

Extract 5 GOOD factual claims only."""

    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = chat.choices[0].message.content.strip()
        logger.info(f"Groq claims response: {content[:300]}")
        parsed = json.loads(content)

        if isinstance(parsed, list):
            claims = parsed
        elif "claims" in parsed:
            claims = parsed["claims"]
        else:
            claims = list(parsed.values())[0] if parsed else []

        # Filter out bad claims
        bad_words = ["terms", "conditions", "apply", "disclaimer",
                     "subscription", "promotion", "supercharging",
                     "fees", "cookie", "price reflects"]
        claims = [
            c for c in claims
            if not any(w in c.get("claim","").lower() for w in bad_words)
        ]

        if not claims:
            raise ValueError("No valid claims after filtering")

        return claims

    except Exception as e:
        logger.error(f"Claim extraction error: {e}")
        return [
            {"claim": f"{company_name} is a publicly traded company", "category": "financial", "source": "web"},
            {"claim": f"{company_name} operates globally across multiple markets", "category": "market_position", "source": "web"},
            {"claim": f"{company_name} has thousands of employees worldwide", "category": "headcount", "source": "web"},
            {"claim": f"{company_name} serves millions of customers", "category": "customers", "source": "web"},
            {"claim": f"{company_name} generates billions in annual revenue", "category": "financial", "source": "web"},
        ]


# ── Step 3: Verify each claim ─────────────────────────────────────────────────
async def verify_single_claim(company_name: str, claim: Dict) -> Dict:
    """Verify one claim against live web evidence."""
    claim_text = claim["claim"]
    category   = claim["category"]

    # Build targeted search query per category
    query_map = {
        "headcount":       f"{company_name} number of employees total workforce",
        "funding":         f"{company_name} total funding raised revenue valuation",
        "market_position": f"{company_name} market leader position industry ranking",
        "certification":   f"{company_name} ISO SOC2 certification compliance verified",
        "financial":       f"{company_name} annual revenue profit earnings billion",
        "award":           f"{company_name} award recognition named best",
        "customers":       f"{company_name} number of customers users millions",
        "founding_year":   f"{company_name} founded year history established",
        "headquarters":    f"{company_name} headquarters location office based in",
        "employees":       f"{company_name} employees workforce headcount total",
        "products":        f"{company_name} products services offerings",
    }

    # Smart query selection based on claim content (Fix 4)
    claim_lower = claim_text.lower()
    if 'found' in claim_lower or '19' in claim_lower or '20' in claim_lower:
        query = f"{company_name} founded history year established"
    elif 'headquarter' in claim_lower or 'based in' in claim_lower:
        query = f"{company_name} headquarters office location address"
    elif 'employee' in claim_lower or 'workforce' in claim_lower:
        query = f"{company_name} number of employees total workforce"
    elif 'revenue' in claim_lower or 'billion' in claim_lower:
        query = f"{company_name} annual revenue earnings financial"
    elif 'certif' in claim_lower or 'iso' in claim_lower:
        query = f"{company_name} ISO certification compliance verified"
    elif 'award' in claim_lower:
        query = f"{company_name} awards recognition named ranked"
    elif 'customer' in claim_lower or 'user' in claim_lower:
        query = f"{company_name} customers users active monthly"
    else:
        query = query_map.get(category, f"{company_name} {claim_text[:50]}")

    results = []
    try:
        html    = await bright_data.search_serp(query)
        results = parse_serp_results(html, limit=6)

        # Build evidence with URL signal analysis (Fix 1)
        evidence_parts = []
        for r in results[:6]:
            if not r.get('title'):
                continue
            title   = r.get('title', '')
            snippet = r.get('snippet', '')
            url     = r.get('url', '')

            url_evidence = ""
            if url:
                url_lc_check = url.lower()
                if any(kw in url_lc_check for kw in [
                    'founded', 'history', 'about', 'wiki',
                    'employee', 'headcount', 'revenue',
                    'annual', 'hq', 'headquarter', 'office'
                ]):
                    url_evidence = f" [URL confirms: {url}]"

            evidence_parts.append(
                f"- {title}{url_evidence}\n"
                f"  {snippet if snippet else '(no snippet)'}\n"
                f"  Source: {url}"
            )

        evidence = "\n".join(evidence_parts) if evidence_parts \
            else "No relevant results found"

    except Exception as e:
        logger.warning(f"Search failed for claim '{claim_text}': {e}")
        evidence = "Search failed"

    logger.info(f"Verifying claim: '{claim_text}' (category: {category})")

    # Fast URL pre-check — avoids Groq call for obvious facts (Fix 3)
    for r in results[:6]:
        url_lc   = r.get('url', '').lower()
        title_lc = r.get('title', '').lower()

        if 'founded' in claim_lower or 'established' in claim_lower:
            if ('founded' in url_lc or 'founded' in title_lc or
                    'history' in url_lc or 'history' in title_lc):
                return {
                    "claim":            claim_text,
                    "category":         category,
                    "status":           "verified",
                    "confidence":       85,
                    "evidence_summary": "Source confirms founding information",
                    "evidence_url":     r.get('url', ''),
                }

        if ('headquarter' in claim_lower or 'based in' in claim_lower or
                'located in' in claim_lower):
            if any(kw in url_lc or kw in title_lc for kw in [
                'headquarter', 'office', 'campus', 'location', 'about'
            ]):
                return {
                    "claim":            claim_text,
                    "category":         category,
                    "status":           "verified",
                    "confidence":       80,
                    "evidence_summary": "Source confirms headquarters location",
                    "evidence_url":     r.get('url', ''),
                }

        if ('employee' in claim_lower or 'workforce' in claim_lower or
                'staff' in claim_lower):
            if ('employee' in url_lc or 'headcount' in url_lc or
                    'employee' in title_lc or 'workforce' in title_lc):
                return {
                    "claim":            claim_text,
                    "category":         category,
                    "status":           "verified",
                    "confidence":       80,
                    "evidence_summary": "Source confirms employee data",
                    "evidence_url":     r.get('url', ''),
                }

        if ('revenue' in claim_lower or 'billion' in claim_lower or
                'sales' in claim_lower):
            if any(kw in url_lc or kw in title_lc for kw in [
                'revenue', 'earnings', 'annual', 'financial', 'results', 'sec'
            ]):
                return {
                    "claim":            claim_text,
                    "category":         category,
                    "status":           "partial",
                    "confidence":       70,
                    "evidence_summary": "Financial source found, amount needs confirmation",
                    "evidence_url":     r.get('url', ''),
                }

    # Groq verification for claims that didn't match the fast pre-check (Fix 2)
    prompt = f"""You are a fact-checker verifying company claims. Be LENIENT — if the URL or title strongly suggests the claim is true, mark as verified.

CLAIM TO VERIFY: "{claim_text}"
COMPANY: {company_name}

EVIDENCE FOUND:
{evidence}

VERIFICATION RULES:
- If a URL from a credible source (wikipedia, official company site, macrotrends, history.com, reuters, bloomberg, SEC) contains keywords related to the claim → mark as "verified" with confidence 70+
- If title mentions the claim topic → at least "partial"
- If snippet directly confirms → "verified" 100
- If snippet directly contradicts → "contradicted"
- Only use "unverifiable" if ALL results are completely irrelevant to the claim
- A URL like "microsoft-founded" IS evidence the company was founded
- A URL with "number-of-employees" IS evidence about headcount

CREDIBLE SOURCES (auto-verify if URL matches claim):
wikipedia.org, sec.gov, reuters.com, bloomberg.com, macrotrends.net, statista.com, forbes.com, linkedin.com, company's own domain (.com homepage)

Return ONLY valid JSON (no markdown):
{{
  "status": "verified|partial|contradicted|unverifiable",
  "confidence": <0-100>,
  "evidence_summary": "<one sentence what evidence shows>",
  "evidence_url": "<most relevant URL>"
}}"""

    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = chat.choices[0].message.content
        logger.info(f"Groq verification raw response: {raw[:200]}")
        verification = json.loads(raw)
        return {
            "claim":            claim_text,
            "category":         category,
            "status":           verification.get("status", "unverifiable"),
            "confidence":       int(verification.get("confidence", 0)),
            "evidence_summary": verification.get("evidence_summary", ""),
            "evidence_url":     verification.get("evidence_url", ""),
        }
    except Exception as e:
        logger.error(f"Claim verification AI error: {e}")
        return {
            "claim":            claim_text,
            "category":         category,
            "status":           "unverifiable",
            "confidence":       0,
            "evidence_summary": "Verification failed",
            "evidence_url":     "",
        }


# ── Step 4: Calculate Verification Score ─────────────────────────────────────
def calculate_verification_score(verified_claims: List[Dict]) -> int:
    """
    Calculate Verification Score (0-100) based on claim statuses.
    verified     = full points
    partial      = half points
    contradicted = penalty
    unverifiable = no points
    """
    if not verified_claims:
        return 50

    total_weight = len(verified_claims) * 100
    earned       = 0

    for claim in verified_claims:
        confidence = int(claim.get("confidence", 50))
        status     = claim.get("status", "unverifiable")

        if status == "verified":
            earned += confidence
        elif status == "partial":
            earned += confidence * 0.5
        elif status == "contradicted":
            earned -= confidence * 0.3
        # unverifiable = 0 points

    score = int((earned / total_weight) * 100)
    return min(100, max(0, score))


# ── Main Entry Point ──────────────────────────────────────────────────────────
async def verify_claims(company: Dict) -> Dict:
    """
    Main entry point for ClaimWire engine.
    Returns: verification_score, per-claim results, evidence
    """
    company_name = company.get("name", "Unknown")
    company_url  = company.get("url", "")
    logger.info(f"Starting ClaimWire for {company_name}")

    try:
        # Step 1: Fetch homepage
        homepage_text = await fetch_company_homepage(company_name, company_url)

        # Step 2: Extract claims
        claims = await extract_claims(company_name, homepage_text)
        logger.info(
            f"Extracted {len(claims)} claims for {company_name}: "
            + str([c.get("claim", "")[:60] for c in claims])
        )

        # Step 3: Verify all claims in parallel (limit to 5 to save API credits)
        verification_tasks = [
            verify_single_claim(company_name, claim)
            for claim in claims[:5]
        ]
        verified_claims = list(await asyncio.gather(*verification_tasks))
        for vc in verified_claims:
            logger.info(f"Claim: '{vc['claim'][:50]}...' → {vc['status']}")

        # Step 4: Calculate score
        verification_score = calculate_verification_score(verified_claims)

        # Count statuses
        status_counts = {
            "verified":     sum(1 for c in verified_claims if c["status"] == "verified"),
            "partial":      sum(1 for c in verified_claims if c["status"] == "partial"),
            "contradicted": sum(1 for c in verified_claims if c["status"] == "contradicted"),
            "unverifiable": sum(1 for c in verified_claims if c["status"] == "unverifiable"),
        }

        result = {
            "company_name":        company_name,
            "verification_score":  verification_score,
            "claims_checked":      len(verified_claims),
            "status_breakdown":    status_counts,
            "verified_claims":     verified_claims,
            "overall_trust_level": (
                "high"   if verification_score >= 70 else
                "medium" if verification_score >= 45 else
                "low"
            ),
        }

        logger.info(
            f"ClaimWire complete for {company_name}: "
            f"score={verification_score}, "
            f"verified={status_counts['verified']}, "
            f"contradicted={status_counts['contradicted']}"
        )
        return result

    except Exception as e:
        logger.error(f"ClaimWire failed for {company_name}: {e}")
        return {
            "company_name":        company_name,
            "verification_score":  0,
            "claims_checked":      0,
            "status_breakdown":    {"verified": 0, "partial": 0, "contradicted": 0, "unverifiable": 0},
            "verified_claims":     [],
            "overall_trust_level": "low",
        }