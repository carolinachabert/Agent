# Content Pipeline Agent

A Claude-powered assistant for a solo creator's Instagram/TikTok batch
workflow. It automates the drafting steps, and hard-blocks the one step that
should never be automated: posting without Karolina's review.

## The workflow

| Step | Who | Command |
|---|---|---|
| 1. Scan formats | Claude (WebSearch) + Karolina/Pierre forward screenshots | `plan` |
| 2. Draft plan (script, shot list, wardrobe notes) | Claude | `plan` |
| 3. Batch film (every 2–3 weeks, one session) | Karolina, hands-on | *(human — the `plan` output is the filming-day brief)* |
| 4. Draft captions + pillar-matched CTAs | Claude, checked against `brand_bible.md` | `captions` |
| 5. Approve | **Karolina — non-negotiable gate** | `approve` |
| 6. Schedule to Instagram + TikTok together | Metricool | `schedule` |

Everything for one filming cycle ("batch") lives under `data/batches/<batch_id>/`:
`references.md`, `plan.md`, `captions.md`, `APPROVAL.json`, `schedule_receipt.json`.
That folder is the audit trail — what was researched, what was drafted, who
approved it and when, what actually got scheduled.

## Why the approval gate is enforced in code, not just in the prompt

`content_agent/tools/metricool.py`'s `schedule_post()` refuses to run unless
it's passed `is_approved=True`, which is only ever sourced from the presence
of `data/batches/<batch_id>/APPROVAL.json` on disk. That file is only ever
written by a human running `content_agent.main approve` — the agent has no
tool that can create it. So even if a future prompt change told Claude to
"just schedule it," the code path still hard-stops.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY, and Metricool creds when ready
```

Fill in `brand_bible.md` with your actual voice rules, content pillars, and
CTA style — the caption-drafting step reads this file directly and the
placeholder sections are meant to be replaced.

## Running a batch cycle

```bash
# 1-2: scan formats + draft the plan. Pass along anything Karolina/Pierre forwarded.
python -m content_agent.main plan --batch 2026-07-batch \
  --reference "IG reel from @creator, hook: cold open mid-action, text overlay reveals the twist at 3s" \
  --reference-source "Pierre" \
  --brief "Focus on the skincare pillar this cycle"

# 3: Karolina films from data/batches/2026-07-batch/plan.md (out of band)

# 4: draft captions + CTAs once filming is done (or in parallel with editing)
python -m content_agent.main captions --batch 2026-07-batch

# 5: Karolina reviews plan.md + captions.md, then approves herself
python -m content_agent.main approve --batch 2026-07-batch --reviewer Karolina --note "swap CTA on video 2"

# 6: schedule the approved post to Instagram + TikTok together
python -m content_agent.main schedule --batch 2026-07-batch --platforms instagram tiktok

# check state of a batch (or list all batches) at any point
python -m content_agent.main status --batch 2026-07-batch
python -m content_agent.main status
```

Running `schedule` before `approve` fails loudly:

```
BLOCKED: Batch is not approved. Karolina must run
`python -m content_agent.main approve --batch <id>` before anything schedules.
```

## Metricool integration

Without `METRICOOL_USER_TOKEN` / `METRICOOL_USER_ID` set in `.env`, `schedule`
runs in **dry-run mode**: it returns a mock receipt so you can exercise the
whole pipeline before wiring in real credentials. Once you add:

- `METRICOOL_USER_TOKEN`, `METRICOOL_USER_ID`, `METRICOOL_BLOG_ID`
- `METRICOOL_INSTAGRAM_ACCOUNT_ID`, `METRICOOL_TIKTOK_ACCOUNT_ID`

it calls Metricool's scheduler API for real. **Double-check the request shape
in `content_agent/tools/metricool.py` against Metricool's current API docs
before relying on it** — endpoint/field names there are a best-effort based
on their documented scheduler API and may drift.

## Guardrail: never copy another creator's actual content

The system prompt in `content_agent/main.py` explicitly instructs Claude to
adapt only structure and pacing from reference formats — never another
creator's actual dialogue, on-screen text, or footage. This is a prompt-level
guardrail (unlike the approval gate, which is enforced in code) — spot-check
`plan.md` output against the references it cites.

## Project layout

```
content_agent/
  main.py                 CLI entrypoint (plan / captions / approve / schedule / status)
  state.py                Per-batch file-based state
  tools/
    pipeline_tools.py      SDK tools exposed to the agent (log_reference, save_plan, ...)
    metricool.py            Metricool scheduling + the hard approval-gate check
brand_bible.md             Voice rules, content pillars, CTA style — fill this in
data/
  inbox/                   Drop raw screenshots Karolina/Pierre forward here (optional)
  batches/<batch_id>/       One folder per filming cycle — the audit trail
```
