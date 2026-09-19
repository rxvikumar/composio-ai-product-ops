# Post-Smoke-Test Manual Review Checklist

Run this after `python -m src.research_agent --smoke` completes.
Everything below is a human step — it can't be automated.

---

## Step 1 — Check `output/failed_ids.json`

```bash
# Should either not exist, or be an empty array []
type output\failed_ids.json
```

If it has entries, note the reason for each:
- `api-error` → retries exhausted (Composio/OpenAI issue)
- `evidence-dedup-below-min` → agent returned duplicate evidence URLs
- `schema-validation-error` → structured output violated the schema

Re-research failures before scaling to 100:
```bash
python -m src.research_agent --ids <comma-separated-failed-ids>
```

---

## Step 2 — Open `output/case_study.html` in your browser

Confirm these render correctly:
- [ ] Headline section is populated (not blank or "unknown")
- [ ] The 5-row table shows all 5 apps with non-empty values in every column
- [ ] Auth, credential access, buildability verdict are populated
- [ ] Evidence links appear in the last column

---

## Step 3 — Click and verify 2–3 evidence links per app (the only un-automatable check)

For each of the 5 apps, click at least one evidence link in the table and verify:

| What to check | Pass | Fail |
|---|---|---|
| URL resolves (no 404 / domain-not-found) | Page loads | Dead link → hallucinated URL |
| Page content matches the claim shown in the table | Confirmed | Mismatch → agent inferred, didn't read |
| Page is first-party (official docs/pricing, not a blog or third-party writeup) | Yes | Low-quality source |

**This is the core accuracy check.** A fabricated-URL failure here means the agent is producing structured output without real web research — likely because `COMPOSIO_SEARCH` or `BROWSER_TOOL` returned empty tool lists. Fix the toolkit connection before running 100 apps.

Suggested apps to spot-check (pick apps you already know something about):
- App 21: **Slack** — auth should be OAuth2, docs at api.slack.com
- App 61: **GitHub** — auth should be OAuth2 + token, docs at docs.github.com/rest
- App 81: **Stripe** — auth should be API key, docs at stripe.com/docs/api

---

## Step 4 — Rate limit check before scaling

```
100 apps / batch-size 5 = 20 batches
~3–5 LLM calls per app (search + browse + structured extraction)
+ 1 verification call over 12 apps
```

Recommended settings:
- **Tier 1 OpenAI account:** `--workers 2 --batch-size 5`
- **Tier 2+ OpenAI account:** `--workers 4 --batch-size 5`

Run the full dataset only after smoke test evidence links pass manual review.

---

## Step 5 — Scale to 100 apps

```bash
python -m src.research_agent --batch-size 5 --workers 2
python -m src.analyze
python -m src.verify_agent --sample 12
python -m src.build_case_study
```

---

## Step 6 — Human verification (6 of 12 sampled apps)

Per the README protocol: manually open the cited official docs for at least 6 of the 12 apps in `verification/automated_verification.json`. For each:
- Auth method
- Credential access / gating
- API surface claim
- MCP claim (if any)

Record discrepancies in `verification/human_verification.json`. Do not claim high accuracy unless the data supports it.
