"""
Pre-flight check — run this BEFORE the smoke test.

Verifies:
  1. All required env vars are set and non-placeholder
  2. Composio toolkits (COMPOSIO_SEARCH, BROWSER_TOOL) are actually connected
     for the configured user_id — prints real tool names and exits 1 if missing.
  3. Gemini research model name is non-placeholder
  4. Claude verify model name is non-placeholder

No paid API calls are made here. The Composio call is read-only.

Usage:
    python preflight.py
"""
from __future__ import annotations
import os, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

REQUIRED = {
    "COMPOSIO_API_KEY":     "your_composio_key_here",
    "GOOGLE_API_KEY":       "your_google_ai_studio_key_here",
    "GEMINI_RESEARCH_MODEL": "<confirm-in-google-ai-studio>",
    "ANTHROPIC_API_KEY":    "your_anthropic_key_here",
    "CLAUDE_VERIFY_MODEL":  "<confirm-in-anthropic-console>",
}

ok = True


def check(label: str, passed: bool, detail: str = "") -> None:
    global ok
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label}" + (f"\n         {detail}" if detail else ""))
    if not passed:
        ok = False


print("\n=== Pre-flight check ===\n")

# ── 1. Env vars ───────────────────────────────────────────────────────────────
print("1. Environment variables")
for var, placeholder in REQUIRED.items():
    val = os.getenv(var, "")
    is_set = bool(val) and val != placeholder
    check(
        var,
        is_set,
        f'value: "{val[:20]}..."' if is_set else f"MISSING or still placeholder: '{val}'",
    )

if not ok:
    print("\n  [ERR] Fix env vars above. Copy .env.example to .env and fill in real values.")
    sys.exit(1)

# ── 2. Composio toolkit connectivity ─────────────────────────────────────────
print("\n2. Composio toolkit connectivity")
try:
    from composio_google_adk import GoogleAdkProvider
    from composio import Composio

    composio = Composio(
        provider=GoogleAdkProvider(),
        api_key=os.environ["COMPOSIO_API_KEY"],
    )
    user_id = os.getenv("COMPOSIO_USER_ID", "ai-product-ops-researcher")
    tools = composio.tools.get(user_id=user_id, toolkits=["COMPOSIO_SEARCH", "BROWSER_TOOL"])
    tool_names = [getattr(t, "name", getattr(t, "func", t).__name__ if callable(getattr(t, "func", None)) else str(t)) for t in tools]

    check(
        f"Tool count for user '{user_id}'",
        len(tools) > 0,
        f"{len(tools)} tool(s) returned",
    )

    search_tools = [n for n in tool_names if "search" in str(n).lower()]
    browser_tools = [n for n in tool_names if "browser" in str(n).lower()]

    check(
        "COMPOSIO_SEARCH toolkit present",
        bool(search_tools),
        f"tools: {search_tools[:3]}" if search_tools else
        "NOT FOUND — connect COMPOSIO_SEARCH at https://app.composio.dev",
    )
    check(
        "BROWSER_TOOL toolkit present",
        bool(browser_tools),
        f"tools: {browser_tools[:3]}" if browser_tools else
        "NOT FOUND — connect BROWSER_TOOL at https://app.composio.dev",
    )
    print(f"         First 5 tools: {tool_names[:5]}")

except Exception as exc:
    check("Composio SDK call", False, f"Error: {exc}")

# Hard-stop if toolkit check failed
if not ok:
    print("\n  [ERR] Toolkit check failed. Fix before running the smoke test.")
    print("     Without COMPOSIO_SEARCH and BROWSER_TOOL the agent runs but")
    print("     never actually searches — output will be fabricated.")
    sys.exit(1)

# ── 3. Model name sanity ──────────────────────────────────────────────────────
print("\n3. Model name sanity")

gemini_model = os.getenv("GEMINI_RESEARCH_MODEL", "")
gemini_ok = bool(gemini_model) and gemini_model != "<confirm-in-google-ai-studio>" and len(gemini_model) > 3
check(
    "GEMINI_RESEARCH_MODEL",
    gemini_ok,
    f"value: '{gemini_model}'" if gemini_ok else f"STILL A PLACEHOLDER: '{gemini_model}'",
)

claude_model = os.getenv("CLAUDE_VERIFY_MODEL", "")
claude_ok = bool(claude_model) and claude_model != "<confirm-in-anthropic-console>" and len(claude_model) > 3
check(
    "CLAUDE_VERIFY_MODEL",
    claude_ok,
    f"value: '{claude_model}' — confirm active in Anthropic console" if claude_ok
    else f"STILL A PLACEHOLDER: '{claude_model}'",
)

# ── 4. Rate limit estimate ────────────────────────────────────────────────────
print("\n4. Rate limit estimate (informational)")
APPS = 100
BATCH = int(os.getenv("BATCH_SIZE", "5"))
batches = -(-APPS // BATCH)
print(f"   {APPS} apps / batch-size {BATCH} = {batches} batches")
print(f"   GEMINI_RESEARCH_MODEL: free tier has RPM + RPD limits.")
print(f"   workers=1 recommended — get first 10-20 apps reliable before increasing.")
print(f"   CLAUDE_VERIFY_MODEL: low-volume (3 smoke / 12 full) — direct Messages API loop.")

print("\n=== Summary ===")
if ok:
    print("  [OK]  All checks passed. Run the smoke test:")
    print("        python -m src.research_agent --limit 5 --batch-size 5 --workers 1")
else:
    print("  [ERR] Fix the FAIL items above before running the smoke test.")
    sys.exit(1)
