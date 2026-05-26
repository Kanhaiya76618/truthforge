"""
Celery tasks for TruthForge background processing.
All tasks connect to the same Supabase database
and use the same engines as the FastAPI backend.
"""

import os
import sys
import asyncio
from loguru import logger
from dotenv import load_dotenv

# Path setup — MUST match backend path setup exactly
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_path = os.path.join(_root, 'backend', '.env')
load_dotenv(_env_path)

if _root not in sys.path:
    sys.path.insert(0, _root)

_backend_dir = os.path.join(_root, 'backend')
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from workers.celery_app import celery_app
from supabase import create_client, Client

# Initialize Supabase using same env vars as backend
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
)


def run_async(coro):
    """Helper to run async code in Celery sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(
    name='workers.tasks.analyze_single_company',
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def analyze_single_company(self, company_id: str, company_name: str, company_url: str):
    """
    Run full TruthForge analysis for a single company.
    Same logic as /api/truthscore/{company_id} in main.py.
    """
    logger.info(f"[WORKER] Starting analysis for {company_name}")

    try:
        # Import engines here to avoid circular imports
        from engines.signal.signal_engine import analyze_signals
        from engines.greenwash.greenwash_engine import analyze_esg
        from engines.claimwire.claimwire_engine import verify_claims
        from engines.synthesis import synthesize_truth_score

        company_data = {
            "id": company_id,
            "name": company_name,
            "url": company_url,
        }

        async def run_analysis():
            # Run all 3 engines in parallel
            signal_result, esg_result, claimwire_result = await asyncio.gather(
                analyze_signals(company_data),
                analyze_esg(company_data),
                verify_claims(company_data),
                return_exceptions=True
            )

            # Handle any engine exceptions
            if isinstance(signal_result, Exception):
                logger.error(f"Signal engine failed: {signal_result}")
                signal_result = {"signal_score": 0, "top_signal": "Error",
                               "buying_intent_summary": "", "recommendation": "",
                               "evidence": [], "total_signals_found": 0}

            if isinstance(esg_result, Exception):
                logger.error(f"ESG engine failed: {esg_result}")
                esg_result = {"integrity_score": 0, "greenwash_risk": "unknown",
                             "verified_claims": 0, "contradicted_claims": 0,
                             "claims_found": [], "summary": "",
                             "biggest_risk": "", "recommendation": "",
                             "evidence": [], "total_sources_checked": 0}

            if isinstance(claimwire_result, Exception):
                logger.error(f"ClaimWire engine failed: {claimwire_result}")
                claimwire_result = {"verification_score": 0, "claims_checked": 0,
                                   "status_breakdown": {}, "verified_claims": [],
                                   "overall_trust_level": "low"}

            # Synthesize TruthScore
            truth_result = await synthesize_truth_score(
                company_data,
                signal_result,
                esg_result,
                claimwire_result,
            )

            return signal_result, esg_result, claimwire_result, truth_result

        signal_result, esg_result, claimwire_result, truth_result = run_async(run_analysis())

        # Save scores to database
        supabase.table("scores").insert({
            "company_id":         company_id,
            "signal_score":       signal_result.get("signal_score", 0),
            "integrity_score":    esg_result.get("integrity_score", 0),
            "verification_score": claimwire_result.get("verification_score", 0),
            "truth_score":        truth_result.get("truth_score", 0),
        }).execute()

        # Save claims to database
        claims = claimwire_result.get("verified_claims", [])
        if claims:
            claim_records = [{
                "company_id":     company_id,
                "claim_text":     c.get("claim", ""),
                "status":         c.get("status", "unverifiable"),
                "evidence_links": [c.get("evidence_url", "")]
                    if c.get("evidence_url") else [],
            } for c in claims]
            supabase.table("claims").insert(claim_records).execute()

        truth_score = truth_result.get("truth_score", 0)
        logger.info(
            f"[WORKER] Analysis complete for {company_name}: "
            f"TruthScore={truth_score}"
        )

        return {
            "status": "success",
            "company": company_name,
            "truth_score": truth_score,
        }

    except Exception as exc:
        logger.error(f"[WORKER] Analysis failed for {company_name}: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name='workers.tasks.reanalyze_all_companies',
    bind=True,
)
def reanalyze_all_companies(self):
    """
    Re-analyze ALL companies in the database.
    Runs every 6 hours via beat scheduler.
    """
    logger.info("[WORKER] Starting scheduled re-analysis of all companies")

    try:
        companies = supabase.table("companies").select("*").execute()

        if not companies.data:
            logger.info("[WORKER] No companies to re-analyze")
            return {"status": "success", "analyzed": 0}

        count = 0
        for company in companies.data:
            analyze_single_company.delay(
                company_id=company["id"],
                company_name=company["name"],
                company_url=company["url"],
            )
            count += 1
            logger.info(f"[WORKER] Queued analysis for {company['name']}")

        logger.info(f"[WORKER] Queued {count} companies for re-analysis")
        return {"status": "success", "queued": count}

    except Exception as exc:
        logger.error(f"[WORKER] Reanalyze all failed: {exc}")
        return {"status": "error", "error": str(exc)}


@celery_app.task(
    name='workers.tasks.check_score_drops',
    bind=True,
)
def check_score_drops(self):
    """
    Check if any company TruthScore dropped significantly.
    Triggers alert if score drops more than 10 points.
    Runs every hour via beat scheduler.
    """
    logger.info("[WORKER] Checking for score drops")

    try:
        companies = supabase.table("companies").select("*").execute()
        alerts_sent = 0

        for company in companies.data or []:
            # Get last 2 scores to compare
            scores = supabase.table("scores")\
                .select("*")\
                .eq("company_id", company["id"])\
                .order("updated_at", desc=True)\
                .limit(2)\
                .execute()

            if not scores.data or len(scores.data) < 2:
                continue

            latest = scores.data[0]["truth_score"]
            previous = scores.data[1]["truth_score"]
            drop = previous - latest

            if drop >= 10:
                logger.warning(
                    f"[WORKER] Score drop detected for "
                    f"{company['name']}: {previous} → {latest} "
                    f"(dropped {drop} points)"
                )

                # Save alert to database
                supabase.table("alerts").insert({
                    "company_id": company["id"],
                    "message": (
                        f"TruthScore dropped {drop} points for "
                        f"{company['name']}: {previous} → {latest}"
                    ),
                }).execute()

                # Send Slack alert if configured
                from workers.alerts import send_slack_alert
                send_slack_alert(
                    company_name=company["name"],
                    previous_score=previous,
                    current_score=latest,
                    drop=drop,
                )
                alerts_sent += 1

        logger.info(
            f"[WORKER] Score drop check complete. "
            f"Alerts sent: {alerts_sent}"
        )
        return {"status": "success", "alerts_sent": alerts_sent}

    except Exception as exc:
        logger.error(f"[WORKER] Score drop check failed: {exc}")
        return {"status": "error", "error": str(exc)}


@celery_app.task(name='workers.tasks.health_check')
def health_check():
    """
    Simple health check task.
    Verifies Celery workers are running every 5 minutes.
    """
    logger.info("[WORKER] Health check OK")
    return {"status": "healthy", "worker": "truthforge-worker"}


@celery_app.task(name='workers.tasks.queue_company_analysis')
def queue_company_analysis(
    company_id: str,
    company_name: str,
    company_url: str
):
    """
    Public task to queue a single company analysis.
    Called from FastAPI when a new company is added.
    """
    analyze_single_company.delay(
        company_id=company_id,
        company_name=company_name,
        company_url=company_url,
    )
    return {"status": "queued", "company": company_name}
