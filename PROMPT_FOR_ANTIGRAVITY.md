# Antigravity build prompt

You are the senior engineer responsible for finishing this take-home assignment. Work directly in this repository and do not replace the architecture with a one-off manual dataset.

## Objective
Build and polish a production-quality research pipeline for the 100 apps in `data/apps.json`. The final artifact is `output/case_study.html`; the source repo must explain how the research agent runs.

## Required behavior
1. Use Composio SDK tools for current web research. Prefer `COMPOSIO_SEARCH` and `BROWSER_TOOL`.
2. For every app, retrieve first-party sources for:
   - what the app does
   - auth method(s)
   - self-serve vs gated credential access
   - API surface and breadth
   - existing official MCP if any
   - buildability and blocker
3. Return strict Pydantic structured output defined in `src/schema.py`.
4. Never fabricate URLs or infer gating from generic marketing pages.
5. Keep evidence attached to claims.
6. Run an independent verification pass over a stratified sample of at least 12 apps.
7. Make the verification process measure mismatches, not just confidence.
8. Generate `output/analysis.json` and `output/case_study.html`.
9. Keep a manual verification file separate from automated verification.
10. Make the final HTML self-explanatory in about two minutes: headline patterns first, then method/agent, verification proof, then the searchable 100-row table.

## Quality bar
- Favor official docs over blogs and third-party sources.
- Resolve ambiguous companies/products before writing a finding.
- Capture dates or accessed timestamps.
- Distinguish end-user OAuth from developer credential issuance.
- Explain mixed access policies rather than forcing them into one bucket.
- Keep buildability practical: a broad public API plus self-serve auth generally means a toolkit is feasible; partner-gated or admin-gated access is an outreach blocker, not a failed research result.
- Show misses honestly. A reviewer should be able to audit the table.

## Engineering expectations
- Add retries and timeouts around tool calls.
- Preserve partial results so an interrupted run can resume.
- Deduplicate evidence URLs.
- Log failed apps separately and allow `--ids` or `--resume`.
- Add a smoke-test mode for 3–5 apps.
- Validate all records before generating the HTML.
- Do not commit `.env` or API keys.
- Pin dependencies where practical after verifying the versions available in the environment.

## Presentation expectations
Make the HTML look like a polished internal product case study, not a raw export. The reviewer should immediately see:
- the main patterns
- counts and distributions
- the agent workflow
- where human intervention was needed
- first-pass vs post-verification accuracy
- examples of hits and misses
- the searchable 100-app table with evidence links

## Finish criteria
A complete run should leave:
- `output/research_results.json`
- `output/analysis.json`
- `verification/automated_verification.json`
- `verification/human_verification.json`
- `output/case_study.html`

Then test the HTML locally and update the README with exact run/deploy commands.
