"""
Celery application configuration for TruthForge.
Uses Redis as message broker and result backend.
"""

import os
import sys
from celery import Celery
from dotenv import load_dotenv

# Load environment variables from backend/.env
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_path = os.path.join(_root, 'backend', '.env')
load_dotenv(_env_path)

# Add project root to path so all engines are importable
if _root not in sys.path:
    sys.path.insert(0, _root)

_backend_dir = os.path.join(_root, 'backend')
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Redis URL from env or default to localhost
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'truthforge',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['workers.tasks']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=600,
    result_expires=3600,
    beat_schedule={
        # Re-analyze all companies every 6 hours
        'reanalyze-all-companies': {
            'task': 'workers.tasks.reanalyze_all_companies',
            'schedule': 21600.0,  # 6 hours in seconds
        },
        # Check for score drops every hour
        'check-score-drops': {
            'task': 'workers.tasks.check_score_drops',
            'schedule': 3600.0,  # 1 hour in seconds
        },
        # Health check every 5 minutes
        'health-check': {
            'task': 'workers.tasks.health_check',
            'schedule': 300.0,
        },
    }
)

if __name__ == '__main__':
    celery_app.start()
