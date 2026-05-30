# System Summary

User visits index.html (landing page)
      ↓
Clicks Dashboard → dashboard.html
      ↓
Enters company → FastAPI /api/analyze
      ↓
Bright Data feeds 3 engines (SERP, Unlocker, MCP, Scraper, Browser)
      ↓
3 engines run in parallel via asyncio.gather() (60-90 seconds)
  ├── SignalForge   (buying signals)
  ├── GreenwashGuard (ESG integrity)
  └── ClaimWire     (claim verification)
      ↓
Groq Llama 3.3-70B synthesizes → TruthScore (0-100)
      ↓
Result stored in Supabase → Dashboard shows score + verdict
      ↓
─────────────── SignalJobs (separate flow) ───────────────
Enter company → Bright Data SERP (LinkedIn/Indeed/Glassdoor/Careers)
      ↓
AI/ML API (GPT-4o) structures roles → one-click AI briefs
      ↓
─────────────── Background Workers (always on) ───────────────
Celery Worker auto re-analyzes every company every 6 hours
      ↓
Beat Scheduler triggers all recurring tasks automatically
      ↓
Score drops 10+ points → Slack alert sent
      ↓
Flower monitors all workers at :5555