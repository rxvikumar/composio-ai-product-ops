from __future__ import annotations
import argparse, asyncio, json, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import ValidationError

import openai
from composio_openai import OpenAIProvider
from composio import Composio

from .schema import ResearchBatch, ResearchRecord
from .prompts import RESEARCH_SYSTEM, RESEARCH_TASK

import re as _re

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


# ── env validation ─────────────────────────────────────────────────────────────

def _require_env(key: str) -> str:
    """Return env var value or raise clearly — no silent fallbacks."""
    val = os.environ.get(key, "")
    if not val or val.startswith("<"):
        raise RuntimeError(
            f"[STARTUP] {key} is missing or still a placeholder in .env. "
            f"Set it to a real value before running."
        )
    return val

# ── file operations ───────────────────────────────────────────────────────────

OUT_DIR = ROOT / "output"
RESULTS_FILE = OUT_DIR / "research_results.json"
FAILURES_FILE = OUT_DIR / "failed_ids.json"


def load_existing() -> list[dict]:
    if RESULTS_FILE.exists():
        try:
            return json.loads(RESULTS_FILE.read_text("utf-8"))
        except Exception:
            pass
    return []

def atomic_write(records: list[dict]):
    OUT_DIR.mkdir(exist_ok=True, parents=True)
    tmp = RESULTS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, indent=2), "utf-8")
    tmp.replace(RESULTS_FILE)

def log_failures(entries: list[dict]):
    """Append failure reasons to failed_ids.json so we can debug or re-run."""
    OUT_DIR.mkdir(exist_ok=True, parents=True)
    existing = []
    if FAILURES_FILE.exists():
        try:
            existing = json.loads(FAILURES_FILE.read_text("utf-8"))
        except Exception:
            pass
    existing.extend(entries)
    
    tmp = FAILURES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(existing, indent=2), "utf-8")
    tmp.replace(FAILURES_FILE)

def dedup_evidence(r: "ResearchRecord") -> tuple["ResearchRecord", bool]:
    """
    Remove duplicate evidence entries based on URL.
    Returns (record, is_valid) where is_valid is True if min items is met.
    """
    seen_urls = set()
    unique_evidence = []
    
    for ev in r.evidence:
        url = ev.url if hasattr(ev, "url") else ev.get("url")
        if url not in seen_urls:
            seen_urls.add(url)
            unique_evidence.append(ev)
            
    r.evidence = unique_evidence
    return r, len(r.evidence) >= 2

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── composio anthropic setup ────────────────────────────────────────────────────

def make_composio_tools() -> tuple[list[dict], OpenAIProvider, str]:
    """
    Build the OpenAI-format tools list and the provider for handle_tool_calls.
    Returns (tools_list, provider, user_id).
    """
    provider = OpenAIProvider()
    composio = Composio(
        provider=provider,
        api_key=_require_env("COMPOSIO_API_KEY"),
    )
    user_id = os.getenv("COMPOSIO_USER_ID", "ai-product-ops-researcher")
    tools = composio.tools.get(user_id=user_id, toolkits=["COMPOSIO_SEARCH"])
    print(f"[INIT] Loaded {len(tools)} Composio tools for user '{user_id}'")
    return tools, provider, user_id



# ── sanitizer (prevents infinite validation loops) ────────────────────────────

_VALID_ACCESS_MODES = {"self-serve-free","self-serve-trial","self-serve-paid",
                       "admin-approval","partner/contact-sales","mixed","unknown","gated-needs-outreach"}
_VALID_VERDICTS = {"toolkit-ready","toolkit-ready-with-constraints",
                   "gated-needs-outreach","not-agent-ready","unknown"}
_VALID_BREADTHS = {"narrow","moderate","broad","very-broad","unknown"}
_VALID_SOURCE_TYPES = {"official-docs","official-blog","official-repo",
                       "official-pricing","official-mcp","other"}
_VALID_AUTH_METHODS = {"OAuth2","API key","Basic","Bearer/token","JWT",
                       "Session/cookie","Other","Unknown"}
_VALID_QUALITY = {"high","medium","low"}

def _sanitize_record(rec: dict) -> dict:
    """Clamp any invalid enum values to safe defaults so Pydantic never hard-fails."""
    # credential_access.mode
    ca = rec.get("credential_access", {})
    if isinstance(ca, dict) and ca.get("mode") not in _VALID_ACCESS_MODES:
        ca["mode"] = "unknown"
    # buildability.verdict
    bd = rec.get("buildability", {})
    if isinstance(bd, dict) and bd.get("verdict") not in _VALID_VERDICTS:
        bd["verdict"] = "unknown"
    # api_surface.breadth
    ap = rec.get("api_surface", {})
    if isinstance(ap, dict) and ap.get("breadth") not in _VALID_BREADTHS:
        ap["breadth"] = "unknown"
    # source_quality
    if rec.get("source_quality") not in _VALID_QUALITY:
        rec["source_quality"] = "low"
    # auth_methods - keep only valid values
    if "auth_methods" in rec and isinstance(rec["auth_methods"], list):
        rec["auth_methods"] = [m for m in rec["auth_methods"] if m in _VALID_AUTH_METHODS] or ["Unknown"]
    # evidence - fix source_type
    for ev in rec.get("evidence", []):
        if isinstance(ev, dict) and ev.get("source_type") not in _VALID_SOURCE_TYPES:
            ev["source_type"] = "other"
    return rec

def _sanitize_batch(data: dict) -> dict:
    """Sanitize all records in a batch dict."""
    if "records" in data and isinstance(data["records"], list):
        data["records"] = [_sanitize_record(r) if isinstance(r, dict) else r
                           for r in data["records"]]
    return data

# ── explicit tool-call loop ───────────────────────────────────────────────────

async def _run_once(
    batch: list[dict],
    client: openai.OpenAI,
    tools: list[dict],
    provider: OpenAIProvider,
    user_id: str,
    model: str,
) -> ResearchBatch:
    """
    Explicit OpenAI Messages API tool-calling loop.
    """
    task = RESEARCH_TASK.format(apps=json.dumps(batch, indent=2))
    messages: list[dict] = [
        {"role": "system", "content": RESEARCH_SYSTEM + """

SPEED RULES:
1. Use your own knowledge. Do NOT call any tools or search.
2. Output the JSON immediately in one response.
3. For unknown fields use 'unknown'. Do NOT search."""},
        {"role": "user", "content": task}
    ]
    max_tool_rounds = 2   # 1 answer round + 1 validation retry max
    max_validation_retries = 2  # Hard cap — never loop forever on bad JSON
    validation_retries = 0
    try:
        for round_num in range(max_tool_rounds):
            print(f"[DEBUG] Calling OpenAI for round {round_num + 1}...", flush=True)
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    timeout=45.0
                ),
                timeout=50.0
            )
            print(f"[DEBUG] OpenAI response received for round {round_num + 1}", flush=True)
            
            msg = response.choices[0].message
            msg_dict = {"role": msg.role, "content": msg.content or ""}
            if msg.tool_calls:
                msg_dict["tool_calls"] = [t.model_dump() for t in msg.tool_calls]
            messages.append(msg_dict)
            
            if msg.tool_calls:
                # Execute all tools via Composio — OpenRouter passes tools correctly
                for tcall in msg.tool_calls:
                    print(f"[RESEARCH] round {round_num + 1}: calling {tcall.function.name}({tcall.function.arguments[:80]}...)", flush=True)
                    try:
                        result = await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(
                                None,
                                lambda tc=tcall: provider.execute_tool_call(tool_call=tc, user_id=user_id)
                            ),
                            timeout=25.0
                        )
                        data = result.data if hasattr(result, "data") else result.get("data", result.get("result", str(result)))
                    except asyncio.TimeoutError:
                        print(f"[TOOL TIMEOUT] {tcall.function.name} timed out — skipping")
                        data = "TimeoutError: tool took too long"
                    except Exception as tool_exc:
                        print(f"[TOOL ERROR] {tcall.function.name}: {tool_exc}")
                        data = f"ToolError: {tool_exc}"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tcall.id,
                        "content": json.dumps(data) if not isinstance(data, str) else data,
                    })
                continue
                
            else:
                # Agent thinks it's done.
                if not msg.content:
                    raise ValueError("Stop reason end_turn but no text block found.")
                
                text = msg.content.strip()
                # Aggressively extract JSON if wrapped in markdown anywhere
                import re
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
                if json_match:
                    text = json_match.group(1).strip()
                else:
                    # try to find the first [ or {
                    start_idx = -1
                    for i, c in enumerate(text):
                        if c in '[{':
                            start_idx = i
                            break
                    if start_idx != -1:
                        text = text[start_idx:]
                        # and the last ] or }
                        end_idx = -1
                        for i in range(len(text)-1, -1, -1):
                            if text[i] in ']}':
                                end_idx = i
                                break
                        if end_idx != -1:
                            text = text[:end_idx+1]
                
                try:
                    data = json.loads(text)
                    if isinstance(data, list):
                        data = {"records": data}
                    # ── sanitize FIRST: clamp any invalid enum values ──
                    data = _sanitize_batch(data)
                    return ResearchBatch.model_validate(data)
                except json.JSONDecodeError as e:
                    validation_retries += 1
                    print(f"[JSON ERROR] ({validation_retries}/{max_validation_retries}) Failed to decode JSON: {e}")
                    if validation_retries >= max_validation_retries:
                        raise ValueError(f"JSON decode failed after {max_validation_retries} retries: {e}") from e
                    messages.append({"role": "assistant", "content": text})
                    messages.append({
                        "role": "user",
                        "content": f"Your output was not valid JSON. Error: {e}. Return ONLY the raw JSON with no markdown fences."
                    })
                    continue
                except ValidationError as e:
                    # Sanitizer should have prevented this — but if it still fails,
                    # raise immediately rather than loop.
                    print(f"[VALIDATION ERROR] Pydantic rejected output even after sanitizing: {e.error_count()} errors")
                    for err in e.errors():
                        loc = ".".join(str(x) for x in err["loc"])
                        print(f"  {loc}: {err['msg']} (got {err.get('input')!r})")
                    raise

        raise ValueError(f"Research agent exceeded {max_tool_rounds} tool rounds without finishing")
        
    except Exception as exc:
        exc_str = str(exc)
        print(f"[DEBUG EXCEPTION] {exc_str}", flush=True)
        import traceback
        traceback.print_exc()
        if any(k in exc_str.lower() for k in ["429", "quota", "rate", "503", "504", "timeout", "overloaded", "balance", "insufficient_quota", "payment"]):
            match = _re.search(r"retry.{0,10}?(\d+(?:\.\d+)?)s", exc_str, _re.IGNORECASE)
            wait_secs = float(match.group(1)) + 5 if match else 20
            print(f"[RATE-LIMIT/TIMEOUT] API error — sleeping {wait_secs:.0f}s before retry")
            await asyncio.sleep(wait_secs)
        raise

# ── retry wrapper ─────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=10, max=60),
    retry=retry_if_exception_type((asyncio.TimeoutError, Exception)),
    reraise=True,
)
async def _run_with_retry(
    batch: list[dict],
    client: openai.OpenAI,
    tools: list[dict],
    provider: OpenAIProvider,
    user_id: str,
    model: str,
) -> ResearchBatch:
    return await _run_once(batch, client, tools, provider, user_id, model)

# ── batch worker ──────────────────────────────────────────────────────────────

async def _worker_loop(queue, results, failed, client, tools, provider, user_id, model, sem, all_records):
    while True:
        try:
            batch = await queue.get()
        except asyncio.CancelledError:
            break
            
        await worker(queue, results, failed, client, tools, provider, user_id, model, sem, all_records, batch)
        queue.task_done()

async def worker(
    queue: asyncio.Queue,
    results: list[dict],
    failed: list[Any],
    client: openai.OpenAI,
    tools: list[dict],
    provider: OpenAIProvider,
    user_id: str,
    model: str,
    sem: asyncio.Semaphore,
    all_records: list[dict],
    batch: list[dict],
) -> dict:
    batch_ids = [a["id"] for a in batch]
    
    fallback_models = [model]
    if "ANTHROPIC_FALLBACK_MODEL" in os.environ and os.environ["ANTHROPIC_FALLBACK_MODEL"] != model:
        fallback_models.append(os.environ["ANTHROPIC_FALLBACK_MODEL"])

    try:
        async with sem:
            success = False
            last_exc = None
            for current_model in fallback_models:
                try:
                    if len(fallback_models) > 1:
                        print(f"[RETRY] Attempting batch {batch_ids} with model {current_model}")
                    parsed: ResearchBatch = await _run_with_retry(batch, client, tools, provider, user_id, current_model)
                    success = True
                    break
                except Exception as exc:
                    import traceback
                    traceback.print_exc()
                    err = str(exc)
                    print(f"[MODEL FAILED] {current_model} failed on batch {batch_ids}: {err[:100]}...")
                    last_exc = exc
                    
            if not success:
                entries = [
                    {"id": bid, "reason": "api-error", "detail": str(last_exc)} for bid in batch_ids
                ]
                log_failures(entries)
                print(f"[FAIL] batch {batch_ids}: All models exhausted. Last error: {last_exc}")
                return {"failed": True, "ids": batch_ids, "reason": str(last_exc)}

            good: list[dict] = []
            fail_entries: list[dict] = []

            # Force correct IDs from the batch onto parsed records (model often hallucinates wrong IDs)
            for i, r in enumerate(parsed.records):
                if i < len(batch):
                    r.id = batch[i]["id"]
                r.researched_at_utc = utc_now()

                # 1. Dedup evidence URLs; guard schema minimum (min=2)
                r, ok = dedup_evidence(r)
                if not ok:
                    fail_entries.append({
                        "id": r.id,
                        "reason": "evidence-dedup-below-min",
                        "detail": f"Evidence collapsed to {len(r.evidence)} unique URLs after dedup (schema min=2)",
                    })
                    print(f"[WARN] app {r.id}: <2 unique evidence URLs after dedup — flagged for re-research")
                    continue

                # 2. Schema validation
                try:
                    validated = ResearchRecord.model_validate(r.model_dump(mode="json"))
                    good.append(validated.model_dump(mode="json"))
                except ValidationError as ve:
                    fail_entries.append({
                        "id": r.id,
                        "reason": "schema-validation-error",
                        "detail": str(ve),
                    })
                    print(f"[WARN] app {r.id}: schema validation failed — flagged for re-research")

            if fail_entries:
                log_failures(fail_entries)

            if good:
                # Overwrite by ID so even stale entries get refreshed
                id_to_idx = {rec["id"]: idx for idx, rec in enumerate(all_records)}
                for rec in good:
                    if rec["id"] in id_to_idx:
                        all_records[id_to_idx[rec["id"]]] = rec
                    else:
                        all_records.append(rec)
                        id_to_idx[rec["id"]] = len(all_records) - 1
                atomic_write(all_records)
                print(f"[OK] batch {batch_ids}: {len(good)} records saved. Total in file: {len(all_records)}", flush=True)

            return {"failed": False, "ids": batch_ids, "count": len(good)}
    except Exception as general_exc:
        import traceback
        traceback.print_exc()
        print(f"[FATAL WORKER ERROR] {general_exc}")
        return {"failed": True, "ids": batch_ids, "reason": str(general_exc)}


async def amain():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=5, help="Apps per LLM prompt")
    parser.add_argument("--limit", type=int, default=None, help="Max apps to process (for testing)")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent batches (watch rate limits)")
    args = parser.parse_args()

    # Load apps (Fixing the CSV bug -> JSON)
    json_path = ROOT / "data" / "apps.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Expected apps JSON at {json_path}")

    all_apps = json.loads(json_path.read_text("utf-8"))

    if args.limit:
        all_apps = all_apps[:args.limit]

    all_records = load_existing()
    done_ids = {r["id"] for r in all_records}
    pending = [a for a in all_apps if a["id"] not in done_ids]

    if not pending:
        print("[INIT] All apps already researched. Nothing to do.")
        return

    # Init native OpenAI SDK
    model = "gpt-4o-mini"
    client = openai.AsyncOpenAI(
        api_key=_require_env("OPENAI_API_KEY").strip()
    )
    tools, provider, user_id = make_composio_tools()

    print(f"Researching {len(pending)} apps in {max(1, (len(pending) + args.batch_size - 1)//args.batch_size)} batch(es) with {args.workers} worker(s)")
    print(f"Model: {model}")

    queue = asyncio.Queue()
    for i in range(0, len(pending), args.batch_size):
        batch = pending[i:i + args.batch_size]
        queue.put_nowait(batch)

    results = []
    failed = []
    sem = asyncio.Semaphore(args.workers)

    tasks = []
    for _ in range(args.workers):
        t = asyncio.create_task(
            _worker_loop(queue, results, failed, client, tools, provider, user_id, model, sem, all_records)
        )
        tasks.append(t)

    await queue.join()
    for t in tasks:
        t.cancel()
    
    print(f"\nDone: {len(results)} records written.")
    print(f"Output: {RESULTS_FILE}")
    if failed:
        print(f"Failures: {FAILURES_FILE}")

if __name__ == "__main__":
    asyncio.run(amain())

