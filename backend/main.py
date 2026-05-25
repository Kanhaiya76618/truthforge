import sys
import os

# Ensure the project root (truthforge/) is on sys.path so `engines.*` is importable
# regardless of whether the server is launched from backend/ or from the project root.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import sentry_sdk
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from loguru import logger
import os

# ── Load environment variables ────────────────────────────────────────────────
load_dotenv()

# ── Sentry setup ──────────────────────────────────────────────────────────────
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN_BACKEND"),
    traces_sample_rate=1.0,
)

# ── Supabase client ───────────────────────────────────────────────────────────
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="TruthForge API",
    description="AI-powered enterprise verification platform — Signal + ESG + ClaimWire",
    version="1.0.0",
)

# ── CORS middleware ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request/Response models ───────────────────────────────────────────────────
class CompanyRequest(BaseModel):
    name: str
    url: str

class VerifyRequest(BaseModel):
    company_id: str

class FullAnalysisRequest(BaseModel):
    name: str
    url: str

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "status": "TruthForge API is running",
        "version": "1.0.0",
        "engines": ["SignalForge", "GreenwashGuard", "ClaimWire"],
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ── Companies ─────────────────────────────────────────────────────────────────
@app.post("/api/companies")
async def create_company(payload: CompanyRequest):
    """Add a new company to monitor."""
    try:
        existing = supabase.table("companies").select("*").eq("url", payload.url).execute()
        if existing.data:
            return {"message": "Company already exists", "company": existing.data[0]}

        result = supabase.table("companies").insert({
            "name": payload.name,
            "url": payload.url,
        }).execute()

        logger.info(f"Company created: {payload.name}")
        return {"message": "Company created", "company": result.data[0]}

    except Exception as e:
        logger.error(f"Error creating company: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/companies")
async def get_companies():
    """Get all monitored companies with their latest scores."""
    try:
        companies = supabase.table("companies").select("*").execute()

        result = []
        for company in companies.data:
            scores = supabase.table("scores")\
                .select("*")\
                .eq("company_id", company["id"])\
                .order("updated_at", desc=True)\
                .limit(1)\
                .execute()

            result.append({
                "company": company,
                "scores": scores.data[0] if scores.data else None,
            })

        return {"companies": result}

    except Exception as e:
        logger.error(f"Error fetching companies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/companies/{company_id}")
async def get_company(company_id: str):
    """Get a single company with all scores and claims."""
    try:
        company = supabase.table("companies").select("*").eq("id", company_id).execute()
        if not company.data:
            raise HTTPException(status_code=404, detail="Company not found")

        scores = supabase.table("scores")\
            .select("*")\
            .eq("company_id", company_id)\
            .order("updated_at", desc=True)\
            .limit(1)\
            .execute()

        claims = supabase.table("claims")\
            .select("*")\
            .eq("company_id", company_id)\
            .execute()

        alerts = supabase.table("alerts")\
            .select("*")\
            .eq("company_id", company_id)\
            .order("sent_at", desc=True)\
            .limit(10)\
            .execute()

        return {
            "company": company.data[0],
            "scores": scores.data[0] if scores.data else None,
            "claims": claims.data,
            "alerts": alerts.data,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Signal Engine ─────────────────────────────────────────────────────────────
@app.post("/api/signal/{company_id}")
async def run_signal_engine(company_id: str):
    """Run SignalForge engine — detect buying signals for a company."""
    try:
        from engines.signal.signal_engine import analyze_signals

        company = supabase.table("companies").select("*").eq("id", company_id).execute()
        if not company.data:
            raise HTTPException(status_code=404, detail="Company not found")

        result = await analyze_signals(company.data[0])
        logger.info(f"Signal analysis complete for {company.data[0]['name']}: {result['signal_score']}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signal engine error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── GreenwashGuard Engine ─────────────────────────────────────────────────────
@app.post("/api/greenwash/{company_id}")
async def run_greenwash_engine(company_id: str):
    """Run GreenwashGuard engine — verify ESG claims for a company."""
    try:
        from engines.greenwash.greenwash_engine import analyze_esg

        company = supabase.table("companies").select("*").eq("id", company_id).execute()
        if not company.data:
            raise HTTPException(status_code=404, detail="Company not found")

        result = await analyze_esg(company.data[0])
        logger.info(f"ESG analysis complete for {company.data[0]['name']}: {result['integrity_score']}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Greenwash engine error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── ClaimWire Engine ──────────────────────────────────────────────────────────
@app.post("/api/claimwire/{company_id}")
async def run_claimwire_engine(company_id: str):
    """Run ClaimWire engine — verify all company claims against live web."""
    try:
        from engines.claimwire.claimwire_engine import verify_claims

        company = supabase.table("companies").select("*").eq("id", company_id).execute()
        if not company.data:
            raise HTTPException(status_code=404, detail="Company not found")

        result = await verify_claims(company.data[0])
        logger.info(f"Claim verification complete for {company.data[0]['name']}: {result['verification_score']}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ClaimWire engine error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── TruthScore Synthesis ──────────────────────────────────────────────────────
@app.post("/api/truthscore/{company_id}")
async def run_truth_score(company_id: str):
    """Run full TruthForge analysis — all 3 engines + AI synthesis = TruthScore."""
    try:
        from engines.signal.signal_engine import analyze_signals
        from engines.greenwash.greenwash_engine import analyze_esg
        from engines.claimwire.claimwire_engine import verify_claims
        from engines.synthesis import synthesize_truth_score

        company = supabase.table("companies").select("*").eq("id", company_id).execute()
        if not company.data:
            raise HTTPException(status_code=404, detail="Company not found")

        company_data = company.data[0]
        logger.info(f"Starting full TruthForge analysis for {company_data['name']}")

        # Run all 3 engines
        signal_result    = await analyze_signals(company_data)
        esg_result       = await analyze_esg(company_data)
        claimwire_result = await verify_claims(company_data)

        # AI synthesis → TruthScore
        truth_result = await synthesize_truth_score(
            company_data,
            signal_result,
            esg_result,
            claimwire_result,
        )

        # Save scores to database
        supabase.table("scores").insert({
            "company_id":         company_id,
            "signal_score":       signal_result["signal_score"],
            "integrity_score":    esg_result["integrity_score"],
            "verification_score": claimwire_result["verification_score"],
            "truth_score":        truth_result["truth_score"],
        }).execute()

        logger.info(f"TruthScore for {company_data['name']}: {truth_result['truth_score']}")

        return {
            "company":        company_data,
            "signal":         signal_result,
            "esg":            esg_result,
            "claimwire":      claimwire_result,
            "truth_score":    truth_result["truth_score"],
            "recommendation": truth_result["recommendation"],
            "confidence":     truth_result["confidence"],
            "summary":        truth_result["summary"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TruthScore error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Full pipeline (one shot) ──────────────────────────────────────────────────
@app.post("/api/analyze")
async def full_analysis(payload: FullAnalysisRequest):
    """
    One-shot endpoint: paste a company name + URL,
    get back a full TruthScore report in one API call.
    """
    try:
        # Create or fetch company
        existing = supabase.table("companies").select("*").eq("url", payload.url).execute()
        if existing.data:
            company_id = existing.data[0]["id"]
        else:
            new_company = supabase.table("companies").insert({
                "name": payload.name,
                "url":  payload.url,
            }).execute()
            company_id = new_company.data[0]["id"]

        # Run full TruthScore pipeline
        from fastapi.testclient import TestClient
        result = await run_truth_score(company_id)
        return result

    except Exception as e:
        logger.error(f"Full analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Scores history ────────────────────────────────────────────────────────────
@app.get("/api/scores/{company_id}")
async def get_scores(company_id: str):
    """Get full score history for a company."""
    try:
        scores = supabase.table("scores")\
            .select("*")\
            .eq("company_id", company_id)\
            .order("updated_at", desc=True)\
            .execute()
        return {"scores": scores.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Claims ────────────────────────────────────────────────────────────────────
@app.get("/api/claims/{company_id}")
async def get_claims(company_id: str):
    """Get all verified/contradicted claims for a company."""
    try:
        claims = supabase.table("claims")\
            .select("*")\
            .eq("company_id", company_id)\
            .execute()
        return {"claims": claims.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Alerts ────────────────────────────────────────────────────────────────────
@app.get("/api/alerts")
async def get_all_alerts():
    """Get all recent alerts across all companies."""
    try:
        alerts = supabase.table("alerts")\
            .select("*, companies(name, url)")\
            .order("sent_at", desc=True)\
            .limit(50)\
            .execute()
        return {"alerts": alerts.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Run server ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)