"""
Alert system for TruthForge workers.
Sends Slack notifications when TruthScore changes.
"""

import os
import httpx
from loguru import logger
from dotenv import load_dotenv

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_root, 'backend', '.env'))

SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')


def send_slack_alert(
    company_name: str,
    previous_score: int,
    current_score: int,
    drop: int,
):
    """Send Slack alert when TruthScore drops significantly."""

    if not SLACK_WEBHOOK_URL:
        logger.info(
            f"[ALERTS] Slack not configured. Alert for "
            f"{company_name}: score dropped {drop} points"
        )
        return False

    # Build Slack message
    emoji = "🔴" if drop >= 20 else "🟡"
    message = {
        "text": f"{emoji} *TruthScore Alert — {company_name}*",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} TruthScore Alert"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Company:*\n{company_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Score Drop:*\n{previous_score} → {current_score} (-{drop})"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"TruthForge detected a *{drop} point drop* in "
                        f"{company_name}'s TruthScore. "
                        f"Recommend reviewing their latest analysis."
                    )
                }
            }
        ]
    }

    try:
        response = httpx.post(
            SLACK_WEBHOOK_URL,
            json=message,
            timeout=10.0,
        )
        response.raise_for_status()
        logger.info(f"[ALERTS] Slack alert sent for {company_name}")
        return True
    except Exception as e:
        logger.error(f"[ALERTS] Slack alert failed: {e}")
        return False


def send_analysis_complete_alert(
    company_name: str,
    truth_score: int,
    verdict: str,
):
    """Send Slack notification when analysis completes."""

    if not SLACK_WEBHOOK_URL:
        return False

    emoji = "✅" if truth_score >= 70 else "⚠️" if truth_score >= 45 else "❌"

    try:
        response = httpx.post(
            SLACK_WEBHOOK_URL,
            json={
                "text": (
                    f"{emoji} *Analysis Complete: {company_name}* — "
                    f"TruthScore: {truth_score}/100 | {verdict}"
                )
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"[ALERTS] Alert failed: {e}")
        return False
