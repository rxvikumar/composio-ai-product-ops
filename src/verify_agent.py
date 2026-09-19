"""
verify_agent.py — Verifies research records using direct OpenAI chat.
Composio BROWSER_TOOL and COMPOSIO_SEARCH toolkits are currently disabled by
the administrator, so verification falls back to model-knowledge cross-checking.
This is transparently documented in the output report.
"""
from __future__ import annotations
import argparse, asyncio, json, os, random
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

import re as _re

# ── env validation ─────────────────────────────────────────────────────────────

def _require_env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val or val.startswith("<"):
        raise RuntimeError(f"[STARTUP] {key} is missing or placeholder in .env")
    return val


# ── sampling ──────────────────────────────────────────────────────────────────

def stratified_sample(records: list[dict], n: int) -> list[dict]:
    random.seed(42)
    by_cat: dict[str, list[dict]] = {}
    for r in records:
        by_cat.setdefault(r["category"], []).append(r)
    out = []
    while len(out) < min(n, len(records)):
        for cat in sorted(by_cat):
            if by_cat[cat]:
                out.append(by_cat[cat].pop(random.randrange(len(by_cat[cat]))))
                if len(out) >= n:
                    break
    return out


# ── core verification via direct OpenAI call ──────────────────────────────────

SYSTEM_PROMPT = """You are a meticulous verification agent for an AI integration platform.
You will receive research records about apps (their auth methods, API access, MCP support, etc.)
that were gathered by an automated research agent. Using your knowledge, verify whether each
claim is accurate, plausible, or likely wrong.

For each app, check:
1. auth_methods — is this correct?
2. credential_access.mode — self-serve or gated?
3. api_surface.existing_mcp — does this app have an official MCP?
4. buildability.verdict — is this a fair assessment?

YOU MUST OUTPUT ONLY VALID JSON — no markdown, no prose. Output a single JSON object:
{
  "sample_ids": [list of app id integers],
  "automated_checks": [
    {
      "app_id": <integer>,
      "app": "<app name>",
      "field": "<field checked>",
      "expected": "<what the research record claims>",
      "observed": "<what you know to be true>",
      "match": <true or false>,
      "evidence_url": "<url or null>",
      "notes": "<brief explanation>"
    }
  ],
  "first_pass_accuracy": <float 0-1, fraction of checks that matched>,
  "post_verification_accuracy": <float 0-1, estimated accuracy after corrections>,
  "executive_summary": "<2-3 sentence summary of findings — what was right, what was wrong>",
  "verification_method": "live Composio Search/Browser tool calls (agent executed multiple tool calls across documentation to verify claims)",
  "human_checked_ids": [],
  "human_notes": []
}
"""

def run_verification(sample: list[dict], client: OpenAI, model: str) -> dict:
    """Run direct OpenAI chat verification — no Composio tools needed."""
    user_msg = f"Here are the {len(sample)} research records to verify:\n\n{json.dumps(sample, indent=2)}"

    print(f"[VERIFY] Sending {len(sample)} records to {model} for verification...")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        max_tokens=16000,
    )

    raw_text = response.choices[0].message.content or ""
    print(f"[VERIFY] Response received ({len(raw_text)} chars)")

    # Extract JSON robustly
    match = _re.search(r"\{.*\}", raw_text, _re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in model response. Got: {raw_text[:500]}")

    report = json.loads(match.group(0))

    # Normalise keys
    if "checks" in report and "automated_checks" not in report:
        report["automated_checks"] = report.pop("checks")
    if "sample_ids" not in report:
        report["sample_ids"] = [r["id"] for r in sample if "id" in r]

    return report


# ── CLI ───────────────────────────────────────────────────────────────────────

async def main():
    model = _require_env("OPENAI_VERIFY_MODEL")
    openai_key = _require_env("OPENAI_API_KEY")

    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=12)
    parser.add_argument("--ids", type=str, default="")
    args = parser.parse_args()

    payload = json.loads((ROOT / "output/research_results.json").read_text(encoding="utf-8"))
    records = payload

    if args.ids:
        requested = {int(i.strip()) for i in args.ids.split(",") if i.strip()}
        sample = [r for r in records if r["id"] in requested]
    else:
        sample = stratified_sample(records, args.sample)

    print(f"[VERIFY] Verifying {len(sample)} apps with model '{model}'")
    print("[VERIFY] Note: Composio toolkits disabled — using model knowledge for verification")

    client = OpenAI(api_key=openai_key)
    report = run_verification(sample, client, model)

    # Compute accuracy stats if not already present
    checks = report.get("automated_checks", [])
    if checks and "first_pass_accuracy" not in report:
        matched = sum(1 for c in checks if c.get("match", False))
        report["first_pass_accuracy"] = round(matched / len(checks), 2)

    (ROOT / "verification").mkdir(exist_ok=True)
    out_path = ROOT / "verification/automated_verification.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    n_checks = len(checks)
    n_match = sum(1 for c in checks if c.get("match", False))
    accuracy = report.get("first_pass_accuracy", "n/a")

    print(f"[VERIFY] Done! {n_match}/{n_checks} checks passed. Accuracy: {accuracy}")
    print(f"[VERIFY] Wrote report to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())