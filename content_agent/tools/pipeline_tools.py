"""SDK tools the agent can call during a pipeline run, bound to one batch.

Each stage of the workflow gets a narrow tool rather than one do-everything
tool, so the agent's actions map 1:1 onto the steps Karolina actually
reviews (references logged, plan saved, captions saved, approval checked,
schedule attempted).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from content_agent.state import BatchState
from content_agent.tools.metricool import ApprovalRequiredError, schedule_post

BRAND_BIBLE_PATH = Path(__file__).resolve().parent.parent.parent / "brand_bible.md"


def build_pipeline_server(batch: BatchState):
    """Create an in-process MCP server exposing this batch's tools to the agent."""

    @tool(
        "log_reference",
        (
            "Log a reference format/hook into this batch's research trail — either a "
            "screenshot/example forwarded by Karolina or Pierre, or a format Claude found "
            "itself while scanning what's currently performing well. Call this once per "
            "reference before drafting the plan."
        ),
        {"source": str, "note": str},
    )
    async def log_reference(args: dict[str, Any]) -> dict[str, Any]:
        batch.append_reference(args["source"], args["note"])
        return {"content": [{"type": "text", "text": f"Logged reference from {args['source']}."}]}

    @tool(
        "read_references",
        "Read back every reference logged so far for this batch.",
        {},
    )
    async def read_references(_args: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": batch.read_references()}]}

    @tool(
        "read_brand_bible",
        (
            "Read the Brand Bible — voice rules, content pillars, CTA style, and hard "
            "don'ts. Always call this before drafting or finalizing captions."
        ),
        {},
    )
    async def read_brand_bible(_args: dict[str, Any]) -> dict[str, Any]:
        if not BRAND_BIBLE_PATH.exists():
            text = "(brand_bible.md not found — proceed with generic best practices and flag this.)"
        else:
            text = BRAND_BIBLE_PATH.read_text(encoding="utf-8")
        return {"content": [{"type": "text", "text": text}]}

    @tool(
        "save_plan",
        (
            "Save the drafted plan (script, shot list, wardrobe notes) for this batch. "
            "The plan must adapt only structure/pacing from reference formats — never "
            "another creator's actual dialogue or footage."
        ),
        {"content": str},
    )
    async def save_plan(args: dict[str, Any]) -> dict[str, Any]:
        batch.save_plan(args["content"])
        return {
            "content": [
                {"type": "text", "text": f"Saved plan to {batch.plan_path}. Ready for filming day."}
            ]
        }

    @tool(
        "save_captions",
        (
            "Save the drafted captions + pillar-matched CTAs for this batch, after checking "
            "them against the Brand Bible voice rules."
        ),
        {"content": str},
    )
    async def save_captions(args: dict[str, Any]) -> dict[str, Any]:
        batch.save_captions(args["content"])
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Saved captions to {batch.captions_path}. Nothing posts until Karolina "
                        "approves — run `python -m content_agent.main approve --batch "
                        f"{batch.batch_id}`."
                    ),
                }
            ]
        }

    @tool(
        "check_approval_status",
        "Check whether Karolina has approved this batch yet. Never schedule without this.",
        {},
    )
    async def check_approval_status(_args: dict[str, Any]) -> dict[str, Any]:
        record = batch.approval_record()
        if record is None:
            text = "NOT APPROVED. Do not schedule. Wait for Karolina's review."
        else:
            text = f"Approved by {record['reviewer']} at {record['approved_at']}."
        return {"content": [{"type": "text", "text": text}]}

    @tool(
        "schedule_to_metricool",
        (
            "Schedule the approved caption/post to Instagram + TikTok together via "
            "Metricool. Will refuse if the batch is not approved — this is a hard, "
            "non-negotiable gate, not a suggestion."
        ),
        {
            "caption": str,
            "platforms": list[str],
            "scheduled_at": Annotated[
                str, "ISO datetime, or empty string for the next available slot"
            ],
        },
    )
    async def schedule_to_metricool(args: dict[str, Any]) -> dict[str, Any]:
        try:
            receipt = schedule_post(
                caption=args["caption"],
                platforms=args.get("platforms") or ["instagram", "tiktok"],
                scheduled_at=args.get("scheduled_at") or None,
                is_approved=batch.is_approved(),
            )
        except ApprovalRequiredError as exc:
            return {"content": [{"type": "text", "text": f"BLOCKED: {exc}"}], "isError": True}
        batch.record_schedule_receipt(receipt)
        return {"content": [{"type": "text", "text": f"Schedule result: {receipt}"}]}

    return create_sdk_mcp_server(
        name="content-pipeline",
        tools=[
            log_reference,
            read_references,
            read_brand_bible,
            save_plan,
            save_captions,
            check_approval_status,
            schedule_to_metricool,
        ],
    )
