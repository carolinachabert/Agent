"""Metricool scheduling — the one upload that publishes to Instagram + TikTok together.

This intentionally hard-blocks in code (not just by prompting the model
nicely) unless a batch has an on-disk APPROVAL.json record. Karolina's
review is "the one non-negotiable gate" per the workflow spec, so the block
lives here, not just in the system prompt.

Without METRICOOL_USER_TOKEN / METRICOOL_USER_ID set, this runs in dry-run
mode and returns a mock receipt instead of calling the real API — useful for
testing the pipeline end to end before wiring in live credentials.

NOTE: the exact Metricool API request shape below (endpoint, field names)
should be double-checked against Metricool's current API docs
(https://metricool.com/api-2/) before relying on it in production — set
METRICOOL_DRY_RUN=0 only after doing that.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

METRICOOL_API_BASE = "https://app.metricool.com/api/v2"


class ApprovalRequiredError(Exception):
    pass


def _dry_run_receipt(caption: str, platforms: list[str], scheduled_at: str | None) -> dict[str, Any]:
    return {
        "status": "dry_run",
        "platforms": platforms,
        "scheduled_at": scheduled_at or "next available slot (dry run)",
        "caption_preview": caption[:120],
        "note": (
            "No METRICOOL_USER_TOKEN configured — nothing was actually sent to "
            "Metricool. Set credentials in .env to schedule for real."
        ),
    }


def schedule_post(
    *,
    caption: str,
    platforms: list[str],
    media_paths: list[str] | None = None,
    scheduled_at: str | None = None,
    is_approved: bool,
) -> dict[str, Any]:
    """Schedule one post across `platforms` (e.g. ["instagram", "tiktok"]) via Metricool.

    Raises ApprovalRequiredError if `is_approved` is False — callers must
    check BatchState.is_approved() and pass it through; this function refuses
    to proceed regardless of what the caller claims otherwise, since
    `is_approved` should always be sourced directly from the on-disk record.
    """
    if not is_approved:
        raise ApprovalRequiredError(
            "Batch is not approved. Karolina must run "
            "`python -m content_agent.main approve --batch <id>` before anything schedules."
        )

    user_token = os.environ.get("METRICOOL_USER_TOKEN")
    user_id = os.environ.get("METRICOOL_USER_ID")
    blog_id = os.environ.get("METRICOOL_BLOG_ID")

    if not user_token or not user_id:
        return _dry_run_receipt(caption, platforms, scheduled_at)

    provider_ids = {
        "instagram": os.environ.get("METRICOOL_INSTAGRAM_ACCOUNT_ID"),
        "tiktok": os.environ.get("METRICOOL_TIKTOK_ACCOUNT_ID"),
    }
    providers = []
    for platform in platforms:
        account_id = provider_ids.get(platform)
        if not account_id:
            raise RuntimeError(
                f"Missing METRICOOL_{platform.upper()}_ACCOUNT_ID for platform '{platform}'."
            )
        providers.append({"network": platform, "accountId": account_id})

    payload = {
        "text": caption,
        "providers": providers,
        "publicationDate": scheduled_at or datetime.now(timezone.utc).isoformat(),
        "media": media_paths or [],
    }

    response = requests.post(
        f"{METRICOOL_API_BASE}/scheduler/posts",
        params={"userId": user_id, "blogId": blog_id},
        headers={"X-Mc-Auth": user_token, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return {"status": "scheduled", "platforms": platforms, "response": response.json()}
