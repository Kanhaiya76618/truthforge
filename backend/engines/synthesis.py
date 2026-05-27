"""
TruthScore Synthesis Engine
============================
Combines SignalForge + GreenwashGuard + ClaimWire into one final TruthScore.
Uses Groq AI to synthesize all three engine outputs intelligently.

Weights:
- Signal Score:       35% (buying intent)
- Integrity Score:    35% (ESG accuracy)
- Verification Score: 30% (claim validity)

Output: TruthScore (0-100) + recommendation + confidence + summary
"""

import os
import sys
import json
from typing import Dict
from groq import Groq
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ── Path setup ────────────────────────────────────────────────────────────────
_backend_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'backend')
)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ── Weighted Score Calculator ─────────────────────────────────────────────────
def calculate_weighted_score(
    signal_score: int,
    integrity_score: int,
    verification_score: int,
) -> int:
    """
    Calculate weighted TruthScore:
    Signal      35%
    Integrity   35%
    Verification 30%
    """
    weighted = (
        signal_score      * 0.35 +
        integrity_score   * 0.35 +
        verification_score * 0.30
    )
    return min(100, max(0, int(weighted)))


# ── AI Synthesis ──────────────────────────────────────────────────────────────
async def synthesize_truth_score(
    company: Dict,
    signal_result: Dict,
    esg_result: Dict,
    claimwire_result: Dict,
) -> Dict:
    """
    Use Groq AI to intelligently synthesize all 3 engine results
    into a final TruthScore with recommendation and summary.
    """
    company_name = company["name"]
    logger.info(f"Synthesizing TruthScore for {company_name}")

    # Extract scores safely
    signal_score      = int(signal_result.get("signal_score", 0))
    integrity_score   = int(esg_result.get("integrity_score", 0))
    verification_score = int(claimwire_result.get("verification_score", 0))

    # Calculate weighted base score
    base_truth_score = calculate_weighted_score(
        signal_score,
        integrity_score,
        verification_score,
    )

    # Build context for AI
    signal_summary = signal_result.get("buying_intent_summary", "No signal data")
    signal_top     = signal_result.get("top_signal", "Unknown")

    esg_summary    = esg_result.get("summary", "No ESG data")
    greenwash_risk = esg_result.get("greenwash_risk", "unknown")
    contradicted_esg = int(esg_result.get("contradicted_claims", 0))

    verified_claims     = int(claimwire_result.get("status_breakdown", {}).get("verified", 0))
    contradicted_claims = int(claimwire_result.get("status_breakdown", {}).get("contradicted", 0))
    trust_level         = claimwire_result.get("overall_trust_level", "medium")

    prompt = f"""You are an enterprise intelligence analyst. Synthesize this 3-engine analysis of {company_name} into a final verdict.

ENGINE RESULTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SIGNAL ENGINE (Buying Intent):
- Signal Score: {signal_score}/100
- Top Signal: {signal_top}
- Summary: {signal_summary}

GREENWASH GUARD (ESG Integrity):
- Integrity Score: {integrity_score}/100
- Greenwash Risk: {greenwash_risk}
- ESG Claims Contradicted: {contradicted_esg}
- Summary: {esg_summary}

CLAIMWIRE (Claim Verification):
- Verification Score: {verification_score}/100
- Claims Verified: {verified_claims}
- Claims Contradicted: {contradicted_claims}
- Trust Level: {trust_level}

WEIGHTED TRUTHSCORE: {base_truth_score}/100

Provide a final synthesis verdict for enterprise decision-makers.

Return ONLY valid JSON (no markdown):
{{
  "truth_score": {base_truth_score},
  "confidence": <0-100 how confident you are in this score>,
  "verdict": "<Trustworthy|Caution Advised|High Risk|Unverifiable>",
  "summary": "<3 sentence executive summary of the company's overall trustworthiness>",
  "recommendation": "<one clear action for the enterprise team>",
  "biggest_strength": "<the most positive finding across all 3 engines>",
  "biggest_risk": "<the most concerning finding across all 3 engines>",
  "use_for_sales": <true|false>,
  "use_for_investment": <true|false>,
  "use_for_vendor": <true|false>
}}"""

    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        result = json.loads(chat.choices[0].message.content)

        # Force truth_score to our calculated value
        result["truth_score"] = base_truth_score

        # Ensure all required fields exist
        result.setdefault("confidence", 70)
        result.setdefault("verdict", "Caution Advised")
        result.setdefault("summary", f"TruthForge analysis of {company_name} complete.")
        result.setdefault("recommendation", "Review all engine findings before proceeding.")
        result.setdefault("biggest_strength", signal_top)
        result.setdefault("biggest_risk", "See individual engine reports")
        result.setdefault("use_for_sales", signal_score >= 60)
        result.setdefault("use_for_investment", integrity_score >= 60)
        result.setdefault("use_for_vendor", verification_score >= 60)

        logger.info(
            f"TruthScore synthesis complete for {company_name}: "
            f"score={base_truth_score}, verdict={result.get('verdict')}"
        )
        return result

    except Exception as e:
        logger.error(f"TruthScore synthesis error: {e}")
        return {
            "truth_score":       base_truth_score,
            "confidence":        60,
            "verdict":           "Caution Advised",
            "summary":           f"Automated analysis of {company_name} completed with {base_truth_score}/100 TruthScore.",
            "recommendation":    "Review individual engine reports for detailed findings.",
            "biggest_strength":  signal_top,
            "biggest_risk":      "Manual review recommended",
            "use_for_sales":     signal_score >= 60,
            "use_for_investment": integrity_score >= 60,
            "use_for_vendor":    verification_score >= 60,
        }