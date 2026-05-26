# System Summary

User visits landing.html
      ↓
Clicks Dashboard → index.html
      ↓
Enters company → FastAPI /api/analyze
      ↓
3 engines run in parallel (60 seconds)
      ↓
TruthScore returned → Dashboard shows results
      ↓
Celery Worker auto re-analyzes every 6 hours
      ↓
Beat Scheduler triggers tasks automatically
      ↓
Score drops → Slack alert sent
      ↓
Flower monitors everything at :5555