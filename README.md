# TruthForge — Enterprise Verification Intelligence

<div align="center">

![TruthForge](https://img.shields.io/badge/TruthForge-v1.0.0-00E5FF?style=for-the-badge&logo=shield&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Bright Data](https://img.shields.io/badge/Bright_Data-MCP-00E5FF?style=for-the-badge)
![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-F59E0B?style=for-the-badge)
![Vercel](https://img.shields.io/badge/Vercel-Deployed-black?style=for-the-badge&logo=vercel)
![Railway](https://img.shields.io/badge/Railway-Deployed-purple?style=for-the-badge)

**AI-powered enterprise verification platform that cross-references every company claim against live web data.**

[Live Demo](https://truthforge-iota.vercel.app) · [API Docs](https://truthforge-production.up.railway.app/docs) · [Pitch Deck](https://truthforge-iota.vercel.app/pitch.html) · [Whitepaper](https://truthforge-iota.vercel.app/whitepaper.html)

</div>

---

## What is TruthForge?

TruthForge is an autonomous enterprise verification intelligence platform. Enter any company name and URL — TruthForge deploys **three specialized AI engines in parallel**, making **15+ real-time Bright Data API calls** across the live web, and returns a comprehensive **TruthScore (0-100)** in under 90 seconds.

> *"The web already knows which companies are telling the truth. TruthForge just asks it."*

### Real Results

| Company | Signal | ESG | Claims | TruthScore | Verdict |
|---------|--------|-----|--------|------------|---------|
| Microsoft | 86 | 62 | 64 | **61** | Caution Advised |
| Tesla | 74 | 58 | 56 | **63** | Caution Advised |

All scores generated from **live web data**. Nothing hardcoded. Nothing cached.

---

## The Problem

Enterprises lose **$12.9M annually** to unverified company claims:

- **Blind Trust Risk** — 83% of procurement teams rely on self-reported data with zero independent verification
- **Greenwashing Epidemic** — 73% of ESG claims cannot be independently verified; EU CSRD now mandates it
- **Data Quality Crisis** — CRM records decay 30% per year; manual research takes 4-6 hours per company

---

## Three Engines

### 📡 SignalForge — Buying Intent Engine (35% weight)
Detects live buying signals from the web:
- Job postings indicating growth
- Funding announcements and valuations
- Executive hires and leadership changes
- Tech stack changes
- News momentum and sentiment

**Output:** Signal Score (0-100) + top signal detected + recommendation

### 🌿 GreenwashGuard — ESG Integrity Engine (35% weight)
Verifies ESG claims against live evidence:
- Sustainability reports and SEC ESG disclosures
- Regulatory filings and certification databases
- Glassdoor employee reviews
- Greenwashing lawsuits and controversies

**Output:** Integrity Score (0-100) + greenwash risk level (low/medium/high)

### 🔍 ClaimWire — Claim Verification Engine (30% weight)
Cross-references every company claim:
- Extracts verifiable claims from company's public presence
- Searches 10+ live sources per claim
- Returns: Verified / Partial / Contradicted / Unverifiable
- Provides evidence links and confidence scores

**Output:** Verification Score (0-100) + per-claim verdicts with evidence

### TruthScore Formula
```
TruthScore = (Signal × 0.35) + (ESG × 0.35) + (Claims × 0.30)
```

---

## Architecture

```
User Input (Company Name + URL)
         │
         ▼
   FastAPI Backend
         │
         ▼
  Bright Data Layer
  ┌──────────────────────────────────────────┐
  │  SERP API  │  Web Unlocker  │  MCP Server │
  │  Scraping Browser  │  Web Scraper API     │
  └──────────────────────────────────────────┘
         │
         ▼ asyncio.gather() — ALL 3 PARALLEL
  ┌──────┬──────────┬────────────┐
  │      │          │            │
  ▼      ▼          ▼            │
Signal  ESG     ClaimWire        │
Engine  Engine  Engine           │
  │      │          │            │
  └──────┴──────────┘            │
         │                       │
         ▼                       │
  Groq Llama 3.3-70B             │
  (AI Synthesis)                 │
         │                       │
         ▼                       │
  TruthScore + Report            │
         │                       │
         ▼                       │
  Supabase PostgreSQL ◄──────────┘
         │
         ▼
  Celery Workers (Background)
  ├── Auto re-analyze every 6h
  ├── Score drop alerts
  └── Health monitoring
```

---

## Tech Stack

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11 | Runtime |
| FastAPI | 0.104+ | REST API framework |
| Uvicorn | latest | ASGI server |
| Pydantic | v2 | Data validation |
| HTTPX | latest | Async HTTP client |
| Loguru | latest | Structured logging |
| Sentry | latest | Error monitoring |

### AI & Data
| Technology | Purpose |
|------------|---------|
| Groq Llama 3.3-70B | AI synthesis and claim verification |
| Bright Data SERP API | News and signal searches (8-12 calls/analysis) |
| Bright Data Web Unlocker | Protected page access (ESG reports, filings) |
| Bright Data MCP Server | Direct AI-to-web integration |
| Bright Data Scraping Browser | JavaScript-rendered pages |
| Bright Data Web Scraper API | Structured data extraction |

### Database & Queue
| Technology | Purpose |
|------------|---------|
| Supabase (PostgreSQL) | Primary database — companies, scores, claims, alerts |
| Celery 5.4 | Background task queue |
| Redis | Message broker for Celery |
| Flower | Celery monitoring dashboard |

### Frontend & Deployment
| Technology | Purpose |
|------------|---------|
| HTML/CSS/JavaScript | Frontend (no framework) |
| Vercel | Frontend hosting |
| Railway | Backend hosting |

---

## Project Structure

```
truthforge/
├── backend/
│   ├── main.py                    # FastAPI app — 12 routes
│   ├── bright_data_client.py      # Bright Data API wrapper
│   ├── requirements.txt           # Python dependencies
│   ├── Procfile                   # Railway deployment
│   ├── runtime.txt                # Python 3.11.9
│   ├── .env                       # Environment variables
│   ├── engines/
│   │   ├── signal/
│   │   │   └── signal_engine.py   # SignalForge engine
│   │   ├── greenwash/
│   │   │   └── greenwash_engine.py # GreenwashGuard engine
│   │   ├── claimwire/
│   │   │   └── claimwire_engine.py # ClaimWire engine
│   │   └── synthesis.py           # TruthScore synthesis
│   └── workers/
│       ├── celery_app.py          # Celery configuration
│       ├── tasks.py               # Background task definitions
│       ├── alerts.py              # Slack alert system
│       └── scheduler.py          # Beat scheduler
├── frontend/
│   ├── index.html                 # Landing page
│   ├── dashboard.html             # Main dashboard app
│   ├── pitch.html                 # Interactive pitch deck
│   ├── whitepaper.html           # Technical whitepaper
│   ├── landing.css                # Landing page styles
│   ├── style.css                  # Shared design system
│   ├── logo.png                   # TruthForge logo
│   └── vercel.json                # Vercel configuration
└── README.md
```

---

## API Reference

### Base URL
```
https://truthforge-production.up.railway.app
```

### Endpoints

#### `GET /`
Health check
```json
{
  "status": "TruthForge API is running",
  "version": "1.0.0",
  "engines": ["SignalForge", "GreenwashGuard", "ClaimWire"]
}
```

#### `POST /api/analyze` ⭐ Main endpoint
One-shot analysis — always runs fresh, never cached
```json
// Request
{
  "name": "Tesla",
  "url": "https://tesla.com"
}

// Response
{
  "company": { "id": "uuid", "name": "Tesla", "url": "https://tesla.com" },
  "truth_score": 63,
  "verdict": "Caution Advised",
  "confidence": 72,
  "summary": "Tesla's overall trustworthiness...",
  "biggest_risk": "Greenwashing allegations...",
  "signal": { "signal_score": 74, "top_signal": "News Momentum", ... },
  "esg": { "integrity_score": 58, "greenwash_risk": "medium", ... },
  "claimwire": { "verification_score": 56, "verified_claims": [...], ... }
}
```

#### `GET /api/companies`
List all analyzed companies with latest scores

#### `POST /api/chat/{company_id}`
AI chat about a specific company using its analysis data

#### `POST /api/chat/general`
General TruthForge AI assistant

#### `GET /api/scores/{company_id}`
Get score history for a company

#### `GET /api/alerts`
Get all score drop alerts

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- Redis (for background workers)
- Node.js (optional, for frontend development)

### 1. Clone the repository
```bash
git clone https://github.com/Kanhaiya76618/truthforge.git
cd truthforge
```

### 2. Set up Python environment
```bash
cd backend
python -m venv venv

# Windows
source venv/Scripts/activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment variables
Create `backend/.env`:
```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_role_key
GROQ_API_KEY=your_groq_api_key
BRIGHT_DATA_API_KEY=your_bright_data_token
BRIGHT_DATA_SERP_URL=https://api.brightdata.com/request
BRIGHT_DATA_UNLOCKER_URL=https://api.brightdata.com/request
BRIGHT_DATA_ZONE_SERP=serp_api1
BRIGHT_DATA_ZONE_UNLOCKER=web_unlocker1
SENTRY_DSN_BACKEND=your_sentry_dsn
APP_ENV=development
REDIS_URL=redis://localhost:6379/0
SLACK_WEBHOOK_URL=your_slack_webhook (optional)
```

### 4. Set up Supabase database
Run this SQL in your Supabase SQL editor:
```sql
-- Companies table
CREATE TABLE companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Scores table
CREATE TABLE scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  truth_score INTEGER,
  signal_score INTEGER,
  integrity_score INTEGER,
  verification_score INTEGER,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Claims table
CREATE TABLE claims (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  claim_text TEXT,
  status TEXT,
  evidence_links TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alerts table
CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5. Start the backend
```bash
cd backend
python main.py
```

API available at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

### 6. Open the frontend
Open `frontend/index.html` in your browser (no server needed).

---

## Background Workers

TruthForge includes a production-grade Celery worker system for continuous monitoring.

### Install Redis
Download from [tporadowski/redis](https://github.com/tporadowski/redis/releases) (Windows) or:
```bash
# Mac
brew install redis
redis-server

# Ubuntu
sudo apt install redis-server
sudo service redis-server start
```

### Run Workers (4 terminals)

**Terminal 1 — Backend API:**
```bash
cd backend && python main.py
```

**Terminal 2 — Celery Worker:**
```bash
cd truthforge
celery -A workers.celery_app worker --loglevel=info --pool=solo
```

**Terminal 3 — Beat Scheduler:**
```bash
cd truthforge
celery -A workers.celery_app beat --loglevel=info
```

**Terminal 4 — Flower Dashboard:**
```bash
cd truthforge
celery -A workers.celery_app flower --port=5555
```

Open Flower at `http://localhost:5555`

### Registered Tasks
| Task | Schedule | Purpose |
|------|----------|---------|
| `analyze_single_company` | On demand | Run full analysis for one company |
| `reanalyze_all_companies` | Every 6 hours | Auto re-analyze all monitored companies |
| `check_score_drops` | Every 1 hour | Detect significant TruthScore drops |
| `health_check` | Every 5 minutes | Verify workers are running |
| `queue_company_analysis` | On demand | Queue a company for background analysis |

---

## Deployment

### Backend — Railway
1. Connect GitHub repo to Railway
2. Set Root Directory to `backend`
3. Add all environment variables
4. Railway auto-deploys on push

### Frontend — Vercel
1. Connect GitHub repo to Vercel
2. Set Root Directory to `frontend`
3. Deploy — no environment variables needed

### Update API URL
After Railway deployment, update in `frontend/dashboard.html`:
```javascript
const API = 'https://your-railway-url.railway.app';
```

---

## How It Works — Deep Dive

### Parallel Execution
All three engines run simultaneously using Python's `asyncio.gather()`:

```python
signal_result, esg_result, claimwire_result = await asyncio.gather(
    analyze_signals(company_data),
    analyze_esg(company_data),
    verify_claims(company_data),
)
```

Each engine also runs its own internal searches in parallel:
- SignalForge: 4 SERP searches simultaneously
- GreenwashGuard: 4 SERP searches + Web Unlocker simultaneously
- ClaimWire: 5 claim verifications simultaneously

**Result: 60-90 seconds total** (down from 5-6 minutes sequential)

### Bright Data Integration
```
Per analysis:
- SERP API: 8-12 calls (news, signals, ESG, claims)
- Web Unlocker: 1-3 calls (protected pages)
- MCP Server: AI-driven calls
- Total: 15+ API calls per company
```

### AI Synthesis
Groq Llama 3.3-70B synthesizes all engine outputs into:
- Final TruthScore
- Verdict (Trustworthy / Caution Advised / High Risk)
- Summary paragraph
- Use case recommendations (Sales / Investment / Vendor)
- Biggest risk identified

---

## Features

- **Live Dashboard** — Real-time TruthScore with animated score ring
- **3 Engine Cards** — Detailed breakdown per engine
- **Claims Table** — Per-claim verdicts with evidence links
- **Evidence Sources** — Direct links to sources found
- **Company Watchlist** — All analyzed companies with scores
- **AI Chat** — Ask questions about any analyzed company
- **Pitch Deck** — 10-slide interactive presentation
- **Technical Whitepaper** — Full architecture documentation
- **Background Workers** — Auto re-analysis every 6 hours
- **Slack Alerts** — Score drop notifications
- **Flower Monitor** — Live worker dashboard

---

## Built For

**Web Data UNLOCKED Hackathon 2026**
by lablab.ai × Bright Data

Built **solo** in **4.5 days** by Kanhaiya Kumar.

---

## Connect

- 🌐 **Live Demo:** [truthforge-iota.vercel.app](https://truthforge-iota.vercel.app)
- 💻 **GitHub:** [github.com/Kanhaiya76618/truthforge](https://github.com/Kanhaiya76618/truthforge)
- 💬 **Discord:** kanhaiya9650
- 📊 **API Docs:** [truthforge-production.up.railway.app/docs](https://truthforge-production.up.railway.app/docs)

---

<div align="center">

*Every Claim. Verified. Live.*

</div>