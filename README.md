# AI Product Ops Intern — 100-app integration research agent

This repo implements the take-home as a reproducible, evidence-first research pipeline.

## Two-provider design

Research and verification run on **different model families** by design:

| Step | Provider | Model | Why |
|---|---|---|---|
| Research (100 apps) | **Gemini** (Google ADK) | Flash-class | Free tier, higher volume, lower cost per call |
| Verification (12-app sample) | **Claude** (Anthropic) | Haiku-class | Paid, low volume; different model family means the verifier doesn't share the same blind spots as the researcher |

Using a different model family for verification is intentional: if both research and verification ran on the same model, a systematic hallucination or knowledge gap would go undetected because both passes would make the same confident-but-wrong claims. A cross-family verifier is more likely to catch a structural miss.

## Architecture

```
apps.json
  → Research Agent  [Gemini / Google ADK + Composio Search + Browser Tool]
  → research_results.json  [written atomically after every batch — resumable]
  → analyze.py
  → analysis.json
  → Verification Agent  [Claude / claude-agent-sdk + Composio MCP tools]
  → automated_verification.json
  → Human verification notes  →  human_verification.json
  → build_case_study.py
  → case_study.html
```

### Why this design

- **Agentic research:** each app is researched from live public docs, not hand-filled.
- **Evidence-first:** every record requires at least 2 evidence URLs; at least one must be first-party.
- **Atomic incremental writes:** results are flushed to disk after each batch via a temp-file rename, so a crash never corrupts already-saved data and `--resume` always has fresh state.
- **gather() isolation:** each batch catches its own exceptions and returns a failure marker instead of raising, so one bad batch cannot cancel in-flight sibling batches.
- **Separate verifier:** a different agent with a different instruction set reduces self-confirmation bias.
- **Stratified sample:** verification samples across categories, not just easy/obvious apps.
- **Human loop:** a small manual sample is recorded separately; misses stay visible.
- **Structured failure log:** `output/failed_ids.json` records `{id, reason}` for every failed app so the cause of failure is traceable on re-research.

## Requirements

- Python 3.10+ (the f-string syntax used is valid on all Python ≥ 3.10)
- See `requirements.txt` for package dependencies (includes `tenacity` for retries)

## Setup

1. Create a virtual environment: `python -m venv .venv && .venv\Scripts\activate`
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`:
   ```
   cp .env.example .env   # or copy on Windows
   ```
4. **Edit `.env` and set `RESEARCH_MODEL`** — check your OpenAI account dashboard for a model that is currently available on your plan. Do not use a model name you haven't confirmed is live; the code will fail fast if the env var is missing or the model is unavailable.
5. Set `OPENAI_API_KEY` and `COMPOSIO_API_KEY` in `.env`.
6. **Run the pre-flight check before any live API calls:**
   ```bash
   python preflight.py
   ```
   Confirms env vars are set, verifies `COMPOSIO_SEARCH` and `BROWSER_TOOL` are actually connected for your account (not silently empty), and prints a rate-limit estimate. An agent with empty tool lists runs fine but produces fabricated output — the preflight catches this for free before spending API calls.

## Running

### Smoke test (5 apps — confirm the pipeline works end-to-end)

```bash
python -m src.research_agent --smoke
python -m src.analyze
python -m src.verify_agent --sample 3
python -m src.build_case_study
```

Open `output/case_study.html` locally to confirm the 5-row table, headline and verification sections render.

**After the smoke test runs, follow [`POST_SMOKE_CHECKLIST.md`](./POST_SMOKE_CHECKLIST.md) before scaling to 100 apps.** The checklist covers: checking `failed_ids.json`, manually clicking 2–3 evidence links per app to confirm they resolve to real content (the un-automatable accuracy check), and rate-limit math for the full run.

### Full dataset (100 apps)

```bash
python -m src.research_agent --batch-size 5 --workers 4
python -m src.analyze
python -m src.verify_agent --sample 12
python -m src.build_case_study
```

### Resume an interrupted run

```bash
python -m src.research_agent --resume
```

Skips any app IDs already present in `output/research_results.json`. Safe to run repeatedly.

### Research specific app IDs

```bash
python -m src.research_agent --ids 1,5,10,42
```

Useful for re-researching apps listed in `output/failed_ids.json`.

### Verify specific apps

```bash
python -m src.verify_agent --ids 1,5,10
```

### Re-research failed apps

If `output/failed_ids.json` exists after a run, re-research the affected apps:

```bash
# extract comma-separated IDs from the failure log, then:
python -m src.research_agent --ids <comma-separated-ids-from-failed_ids.json>
```

## Failure tracking

`output/failed_ids.json` is a structured list:

```json
[
  {"id": 42, "reason": "api-error", "detail": "TimeoutError after 3 attempts"},
  {"id": 7,  "reason": "evidence-dedup-below-min", "detail": "..."},
  {"id": 15, "reason": "schema-validation-error", "detail": "..."}
]
```

Three distinct `reason` values: `api-error`, `evidence-dedup-below-min`, `schema-validation-error`.

## Human verification protocol

Before submitting, manually open the cited official docs for at least 6 of the 12 sampled apps. For each app, check the auth method, credential access, API surface, and MCP/gating claim. Record any discrepancy in `verification/human_verification.json`.

Do not claim 100% accuracy unless the verification data genuinely supports it.

## Deployment

The final deliverable is a static HTML file. Deploy the `output/` directory to Vercel, Netlify, or GitHub Pages and submit that URL alongside this repo.

```bash
# Example: Vercel CLI
vercel output/
```
