"""CLI entrypoint for the content pipeline agent.

Maps directly onto the six-step workflow:

  1. scan formats        -> `plan` command (agent researches + logs references)
  2. draft plan          -> `plan` command (script, shot list, wardrobe notes)
  3. batch film          -> human step; `plan` produces the filming-day brief
  4. draft captions      -> `captions` command (checked against brand_bible.md)
  5. Karolina approves   -> `approve` command (the one non-negotiable gate)
  6. Metricool schedules  -> `schedule` command (blocked until step 5 is done)

Usage:
    python -m content_agent.main plan --batch 2026-07-batch --reference "IG @x reel, hook: ..."
    python -m content_agent.main captions --batch 2026-07-batch
    python -m content_agent.main approve --batch 2026-07-batch --reviewer Karolina
    python -m content_agent.main schedule --batch 2026-07-batch --platforms instagram tiktok
    python -m content_agent.main status --batch 2026-07-batch
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from dotenv import load_dotenv

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

from content_agent.state import BatchState, list_batches
from content_agent.tools.metricool import ApprovalRequiredError, schedule_post
from content_agent.tools.pipeline_tools import build_pipeline_server

load_dotenv()

MCP_SERVER_NAME = "content-pipeline"


def _allowed_tools() -> list[str]:
    tool_names = [
        "log_reference",
        "read_references",
        "read_brand_bible",
        "save_plan",
        "save_captions",
        "check_approval_status",
        "schedule_to_metricool",
    ]
    return ["WebSearch"] + [f"mcp__{MCP_SERVER_NAME}__{name}" for name in tool_names]


def _options(batch: BatchState) -> ClaudeAgentOptions:
    server = build_pipeline_server(batch)
    return ClaudeAgentOptions(
        tools=["WebSearch"],
        mcp_servers={MCP_SERVER_NAME: server},
        allowed_tools=_allowed_tools(),
        permission_mode="bypassPermissions",
        system_prompt=(
            "You are the content pipeline assistant for a solo creator's Instagram/TikTok "
            "workflow. Hard rules, non-negotiable:\n"
            "1. When adapting a reference format/hook, adapt only structure and pacing "
            "(beat order, timing, framing ideas). NEVER copy another creator's actual "
            "dialogue, on-screen text, or footage. Describe the format in your own words.\n"
            "2. Always call read_brand_bible before drafting or finalizing captions, and "
            "make sure every caption's CTA maps to one of the listed content pillars.\n"
            "3. Never call schedule_to_metricool without first calling "
            "check_approval_status and confirming it is approved. If it is not approved, "
            "stop and say so — do not attempt to work around it.\n"
            "4. Use the provided tools to persist your work (save_plan, save_captions) "
            "rather than only returning text — the file on disk is what gets reviewed."
        ),
    )


async def _run_agent(batch: BatchState, prompt: str) -> None:
    async for message in query(prompt=prompt, options=_options(batch)):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)


async def cmd_plan(args: argparse.Namespace) -> None:
    batch = BatchState(args.batch)
    for ref in args.reference or []:
        batch.append_reference(args.reference_source, ref)
    prompt = (
        f"Batch '{batch.batch_id}'. Step 1: scan for currently-working short-form formats "
        "and hooks relevant to this creator's niche (use WebSearch, and call "
        "read_references to see anything already forwarded by Karolina/Pierre; log "
        "anything new you find with log_reference). Step 2: draft a plan for the next "
        "filming batch — script beats, shot list, and wardrobe notes — adapting only the "
        "structure/pacing of the strongest reference formats. Save the final plan with "
        "save_plan. This plan is what Karolina will film from in one batch session, so "
        "make it concrete and shootable."
    )
    if args.brief:
        prompt += f"\n\nAdditional brief from Karolina/Pierre: {args.brief}"
    await _run_agent(batch, prompt)


async def cmd_captions(args: argparse.Namespace) -> None:
    batch = BatchState(args.batch)
    plan = batch.read_plan()  # raises clearly if plan isn't drafted yet
    prompt = (
        f"Batch '{batch.batch_id}'. Here is the saved filming plan:\n\n{plan}\n\n"
        "Read the brand bible with read_brand_bible, then draft captions and a "
        "pillar-matched CTA for each piece of content in the plan. Check every caption "
        "against the brand bible's voice rules and hard don'ts before saving. Save the "
        "result with save_captions."
    )
    await _run_agent(batch, prompt)


async def cmd_approve(args: argparse.Namespace) -> None:
    batch = BatchState(args.batch)
    if not batch.captions_path.exists():
        print(
            f"Warning: no captions.md yet for batch '{batch.batch_id}'. "
            "Approving anyway, but there's nothing to review.",
            file=sys.stderr,
        )
    record = batch.record_approval(reviewer=args.reviewer, note=args.note or "")
    print(f"Approved. {record}")


async def cmd_schedule(args: argparse.Namespace) -> None:
    batch = BatchState(args.batch)
    captions = batch.read_captions()
    try:
        receipt = schedule_post(
            caption=captions,
            platforms=args.platforms,
            scheduled_at=args.at,
            is_approved=batch.is_approved(),
        )
    except ApprovalRequiredError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        sys.exit(1)
    batch.record_schedule_receipt(receipt)
    print(f"Scheduled: {receipt}")


async def cmd_status(args: argparse.Namespace) -> None:
    if args.batch is None:
        batches = list_batches()
        print("Batches:" if batches else "No batches yet.")
        for b in batches:
            print(f"  {b}")
        return
    batch = BatchState(args.batch)
    print(f"Batch: {batch.batch_id}")
    print(f"  plan.md:      {'yes' if batch.plan_path.exists() else 'no'}")
    print(f"  captions.md:  {'yes' if batch.captions_path.exists() else 'no'}")
    record = batch.approval_record()
    print(f"  approved:     {'yes — ' + str(record) if record else 'no'}")
    print(f"  scheduled:    {'yes' if batch.schedule_receipt_path.exists() else 'no'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="content_agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Scan formats and draft the batch plan")
    p_plan.add_argument("--batch", required=True)
    p_plan.add_argument(
        "--reference",
        action="append",
        help="A format/hook example forwarded by Karolina or Pierre (repeatable)",
    )
    p_plan.add_argument("--reference-source", default="Karolina/Pierre")
    p_plan.add_argument("--brief", help="Any extra direction for this batch")
    p_plan.set_defaults(func=cmd_plan)

    p_captions = sub.add_parser("captions", help="Draft captions + CTAs for the batch plan")
    p_captions.add_argument("--batch", required=True)
    p_captions.set_defaults(func=cmd_captions)

    p_approve = sub.add_parser("approve", help="Karolina's approval gate — run this yourself")
    p_approve.add_argument("--batch", required=True)
    p_approve.add_argument("--reviewer", default="Karolina")
    p_approve.add_argument("--note", default="")
    p_approve.set_defaults(func=cmd_approve)

    p_schedule = sub.add_parser("schedule", help="Schedule the approved post via Metricool")
    p_schedule.add_argument("--batch", required=True)
    p_schedule.add_argument("--platforms", nargs="+", default=["instagram", "tiktok"])
    p_schedule.add_argument("--at", help="ISO datetime; omit for next available slot")
    p_schedule.set_defaults(func=cmd_schedule)

    p_status = sub.add_parser("status", help="Show batch state")
    p_status.add_argument("--batch", required=False)
    p_status.set_defaults(func=cmd_status)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
