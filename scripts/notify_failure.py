"""
Send an HTML-escaped Telegram alert when `.github/workflows/update-data.yml` fails.
Executed by the "Alert on workflow failure" step in GitHub Actions.
"""
from __future__ import annotations

import html
import os
import sys

import requests


def send_failure_alert() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("Telegram credentials not configured; skipping workflow failure alert.")
        return 0

    repo = html.escape(os.getenv("GITHUB_REPOSITORY", "CBM-MILA/CBM-MILA"))
    run_id = html.escape(os.getenv("GITHUB_RUN_ID", ""))
    server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    run_url = html.escape(f"{server_url}/{os.getenv('GITHUB_REPOSITORY', 'CBM-MILA/CBM-MILA')}/actions/runs/{os.getenv('GITHUB_RUN_ID', '')}")

    msg = (
        f"⚠️ <b>فشل تشغيل سير عمل التحديث التلقائي (GitHub Actions)</b>\n"
        f"المستودع: <code>{repo}</code>\n"
        f"الرابط: {run_url}"
    )

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"Telegram API returned status {resp.status_code}", file=sys.stderr)
            return 1
    except Exception as exc:
        print(f"Telegram notification exception: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(send_failure_alert())
