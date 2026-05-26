"""
Celery Beat scheduler configuration.
Run with: celery -A workers.celery_app beat --loglevel=info
"""

from workers.celery_app import celery_app

if __name__ == '__main__':
    celery_app.start()
