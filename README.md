# Content draft assistant

A single-file browser tool for Carolina Chabert's Instagram/TikTok content
workflow. It's a personal drafting aid, not an automation pipeline — **it
never posts, schedules, or publishes anything.** Every stage produces a draft
that Karolina reads, edits, and copies out herself.

This replaces an earlier batch/Metricool-automation design in this repo. The
actual decision, reached in a separate planning conversation, was simpler and
fully manual: draft, review, copy, post by hand — nothing auto-publishes.

## What it does

Open `content-draft-assistant.html` in a browser. Three stages:

1. **Plan the shoot** (before filming) — pick a content pillar and format
   (video or carousel), describe the topic (or use "Suggest a piece from my
   collection"), and get a script/slide list, hook & pacing notes, shot list,
   and wardrobe notes. Any shot she can't film gets a reference-image search
   (Unsplash/Pexels/Pixabay via Claude's web search) so she has something to
   look at instead.
2. **Draft captions** (after filming) — describe what's in the footage and
   get two on-brand caption drafts with pillar-matched CTAs, on-screen banner
   text, and a bio-link label, checked against the voice rules baked into the
   prompt (see below).
3. **Format on-screen captions** (after the real, as-spoken video exists) —
   paste the actual final transcript (captured by playing the video to
   Claude in voice mode) and get it split into short CapCut-style on-screen
   lines with words flagged to bold. It never rewrites her words, only
   splits them.

A static reference card between stages 1 and 2 has one-time lighting/camera
notes — that's hands-on setup, not something to regenerate each time.

## Setup

No build step, no server, no install. Open `content-draft-assistant.html`
directly in a browser (double-click it, or `open content-draft-assistant.html`
on macOS).

Paste an Anthropic API key into the field at the top of the page. It's saved
to `localStorage` in that browser and sent directly from the browser to
`api.anthropic.com` — nothing passes through any other server.

**Because the key lives in this file's browser storage and every request
goes straight from the browser:**
- Don't open this file on a shared or public computer with the key saved.
- Don't host this file anywhere public (e.g. a public URL) — anyone who
  loads the page and has (or steals) the key can use it.
- This is a deliberate "internal tool for one person" pattern, not something
  to turn into a shared web app without adding a real backend that holds the
  key server-side instead.

## Brand voice, content pillars, and guardrails are in the prompts, not a config file

Unlike a general-purpose tool, the rules are specific to Carolina's brand and
written directly into the system prompts in the `<script>` block:

- **Content pillars** (`PILLARS` constant): Founder story, Bespoke story,
  Transformation, Education, Behind the scenes, Direct offer, Inspiration.
- **Hook & pacing rules**, a **production rule** (never suggest filming
  outsourced steps like casting or stone-setting — she does bench polishing
  herself, which is a good authentic shot), and a **wardrobe rule** (solid
  saturated colours against the white/cream filming background) live in
  `PLAN_SYSTEM_PROMPT_BASE`.
- **Voice rules** (banned phrases like "timeless elegance", never inventing
  a price or certification) and **CTA-strength-by-pillar rules** (e.g.
  Direct offer gets the strongest CTA, Behind-the-scenes usually gets none)
  live in `CAPTION_SYSTEM_PROMPT`.
- Every plan includes a standing flag: *"Adapt structure and pacing only
  from any reference format — never copy another creator's actual dialogue
  or footage."*

To change brand voice or add a pillar, edit these prompt constants directly
— there's no separate brand-bible file to keep in sync.

## Known limitation: "Suggest a piece from my collection"

This button is meant to search Karolina's Google Drive for pieces from the
permanent collection. **It isn't wired up in this file** — the JS explicitly
refuses the call rather than pointing at a guessed Drive endpoint, because
I couldn't verify a real Google Drive MCP connector URL or obtain an OAuth
token for one in this session. Clicking it will always show a "not
connected yet" message and fall through to the manual topic field, which
still works fine.

To make it real: stand up or subscribe to an actual Drive MCP connector,
get an OAuth token for Carolina's Drive, and add an `mcp_servers` block plus
`anthropic-beta: mcp-client-2025-04-04` header to the relevant `callClaude`
call — see [Anthropic's MCP connector docs](https://docs.anthropic.com/en/docs/agents-and-tools/mcp-connector).
Until then, use "Suggest a piece" as a placeholder for a future upgrade, not
a working feature.

The reference-image search (Unsplash/Pexels/Pixabay, inside the shot list)
is real and doesn't have this limitation — it uses Claude's built-in web
search, which only needs the API key.

## Project layout

```
content-draft-assistant.html   The whole tool — HTML, CSS, and JS in one file
```
