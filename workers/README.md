# TruthForge Workers

## Requirements
- Redis server running on localhost:6379

## Install Redis on Windows
Download from: https://github.com/tporadowski/redis/releases
Run: redis-server

## Start Celery Worker
From project root:
celery -A workers.celery_app worker --loglevel=info

## Start Celery Beat Scheduler
From project root:
celery -A workers.celery_app beat --loglevel=info

## Monitor with Flower (dashboard)
From project root:
celery -A workers.celery_app flower --port=5555
Then open: http://localhost:5555

## Environment Variables needed in backend/.env
REDIS_URL=redis://localhost:6379/0
SLACK_WEBHOOK_URL=your_slack_webhook_url (optional)
