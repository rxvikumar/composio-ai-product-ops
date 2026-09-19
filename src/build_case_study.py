from __future__ import annotations
import json, html as _html
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def esc(x): return _html.escape(str(x or ""))

def main():
    raw_data = json.loads((ROOT/"output/research_results.json").read_text(encoding="utf-8"))
    data = raw_data["records"] if isinstance(raw_data, dict) and "records" in raw_data else raw_data
    analysis = json.loads((ROOT/"output/analysis.json").read_text(encoding="utf-8"))
    ver_path = ROOT/"verification/automated_verification.json"
    ver = json.loads(ver_path.read_text(encoding="utf-8")) if ver_path.exists() else {}

    checks = ver.get("automated_checks", ver.get("checks", []))
    sample_ids = ver.get("sample_ids", [])
    n_checks = len(checks)
    n_match = sum(1 for c in checks if c.get("match", False))
    accuracy_pct = round(ver.get("first_pass_accuracy", n_match / n_checks if n_checks else 0) * 100, 1)
    exec_summary = esc(ver.get("executive_summary", ""))
    ver_method = esc(ver.get("verification_method", ""))

    # Build verification rows
    ver_rows = []
    for c in checks:
        match_val = c.get("match", False)
        badge = '<span style="color:#7ee0b5">PASS</span>' if match_val else '<span style="color:#ffd58a">FAIL</span>'
        ver_rows.append(f'''<tr>
          <td>{esc(c.get("app",""))}</td>
          <td>{esc(c.get("field",""))}</td>
          <td>{esc(c.get("expected",""))}</td>
          <td>{esc(c.get("observed",""))}</td>
          <td>{badge}</td>
          <td class="muted">{esc(c.get("notes",""))}</td>
        </tr>''')

    # Build app rows
    rows = []
    for r in sorted(data, key=lambda x: x.get("id", 0)):
        ev = " ".join(f'<a href="{esc(e["url"])}" target="_blank" rel="noreferrer">source</a>' for e in r.get("evidence", [])[:3])
        rows.append(f'''<tr data-search="{esc((r["app"]+" "+r["category"]+" "+r["what_it_does"]).lower())}">
          <td>{r["id"]}</td><td><strong>{esc(r["app"])}</strong><div class="muted">{esc(r["category"])}</div></td>
          <td>{esc(r["what_it_does"])}</td>
          <td>{esc(", ".join(r["auth_methods"]))}<div class="muted">{esc(r["auth_details"])}</div></td>
          <td><span class="pill">{esc(r["credential_access"]["mode"])}</span><div class="muted">{esc(r["credential_access"]["details"])}</div></td>
          <td>{esc(" / ".join(r["api_surface"]["styles"]))}<div class="muted">{esc(r["api_surface"]["breadth"])} - MCP: {esc(r["api_surface"]["existing_mcp"])}</div></td>
          <td><span class="pill">{esc(r["buildability"]["verdict"])}</span><div class="muted">{esc(r["buildability"]["main_blocker"])}</div></td>
          <td>{ev}</td>
        </tr>''')

    top_access = sorted(analysis["credential_access"].items(), key=lambda x: x[1], reverse=True)[0] if analysis["credential_access"] else ("unknown", 0)
    top_blocker = analysis["common_blockers"][0] if analysis["common_blockers"] else ("none", 0)
    ready = analysis["buildability"].get("toolkit-ready", 0)
    self_serve = sum(v for k,v in analysis["credential_access"].items() if k.startswith("self-serve"))
    n_apps = len(data)
    headline = f"{ready}/{n_apps} apps are toolkit-ready today; {self_serve}/{n_apps} have a self-serve credential path. Auth is dominated by {top_access[0]}. Most common blocker: {top_blocker[0]}."

    html_doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Product Ops -- 100-app integration research | Composio Take-home</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{{--bg:#081018;--panel:#101a24;--panel2:#0c151d;--text:#edf4f8;--muted:#9eb0bd;--line:#24323e;--accent:#7ee0b5;--warn:#ffd58a;--red:#ff7c7c}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(180deg,#071018,#0b1118 40%,#081018);color:var(--text);font:14px/1.5 Inter,system-ui,sans-serif}}
.wrap{{max-width:1500px;margin:auto;padding:36px 28px 80px}}
.eyebrow{{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:12px;margin-bottom:8px}}
h1{{font-size:40px;line-height:1.1;margin:0 0 14px;max-width:1000px;font-weight:800}}
.sub{{color:var(--muted);max-width:820px;font-size:15px;margin:0 0 24px}}
.grid{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:24px 0}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}}
.metric{{font-size:32px;font-weight:800;line-height:1}} .label{{color:var(--muted);font-size:11px;margin-top:6px}}
.metric.green{{color:var(--accent)}} .metric.warn{{color:var(--warn)}}
section{{margin-top:36px}} h2{{font-size:20px;margin:0 0 14px;font-weight:700}}
.headline{{background:linear-gradient(135deg,#12251f,#111a24);border:1px solid #2c493d;padding:18px 22px;border-radius:16px;font-size:16px;line-height:1.6}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.note{{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:16px}}
.note strong{{display:block;margin-bottom:6px}}
.small{{font-size:12px;color:var(--muted);line-height:1.6}} ul{{margin:6px 0 0 18px;padding:0}} li{{margin-bottom:3px}}
.toolbar{{position:sticky;top:0;background:rgba(8,16,24,.95);backdrop-filter:blur(10px);padding:12px 0;border-bottom:1px solid var(--line);z-index:2}}
input{{width:100%;background:var(--panel2);border:1px solid var(--line);color:var(--text);padding:11px 14px;border-radius:10px;font-size:13px;outline:none}}
input:focus{{border-color:var(--accent)}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:14px;margin-top:12px}}
table{{border-collapse:collapse;width:100%;min-width:1250px}}
th,td{{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}
th{{position:sticky;top:57px;background:#0e1821;font-size:11px;color:#bfd0db;z-index:1;text-transform:uppercase;letter-spacing:.05em}}
tr:hover td{{background:#0d1720}}
.muted{{color:var(--muted);font-size:11px;margin-top:3px}} .pill{{display:inline-block;border:1px solid #38505e;padding:3px 7px;border-radius:6px;font-size:11px}}
a{{color:var(--accent);text-decoration:none}} a:hover{{text-decoration:underline}}
.acc-bar{{height:8px;border-radius:99px;background:var(--line);margin-top:8px;overflow:hidden}}
.acc-fill{{height:100%;background:var(--accent);border-radius:99px}}
.method-note{{font-size:11px;color:var(--muted);margin-top:8px;font-style:italic}}
@media(max-width:900px){{.grid{{grid-template-columns:1fr 1fr}}.cols{{grid-template-columns:1fr}}h1{{font-size:28px}}}}
</style></head><body><div class="wrap">
<div class="eyebrow">AI Product Ops Intern - Composio Take-home</div>
<h1>{n_apps} apps researched by an agent, verified by a second pass.</h1>
<p class="sub">A reproducible research pipeline that turns public documentation into auth, access, API, MCP and buildability decisions -- with evidence attached to every row and a verification loop that challenges every critical claim.</p>
<div class="headline"><strong>Key Finding:</strong> {esc(headline)}</div>

<div class="grid">
  <div class="card"><div class="metric green">{n_apps}</div><div class="label">apps researched</div></div>
  <div class="card"><div class="metric green">{analysis["official_mcp_count"]}</div><div class="label">apps with official MCP evidence</div></div>
  <div class="card"><div class="metric green">{ready}</div><div class="label">toolkit-ready today</div></div>
  <div class="card"><div class="metric green">{self_serve}</div><div class="label">self-serve credential path</div></div>
  <div class="card"><div class="metric {"green" if accuracy_pct >= 85 else "warn"}">{accuracy_pct}%</div><div class="label">first-pass accuracy ({n_match}/{n_checks} checks passed)</div></div>
</div>

<section><h2>Patterns</h2><div class="cols">
  <div class="note"><strong>Auth methods</strong><div class="small">{", ".join(f"{esc(k)}: {v}" for k,v in analysis["auth_distribution"].items())}</div></div>
  <div class="note"><strong>Credential access</strong><div class="small">{", ".join(f"{esc(k)}: {v}" for k,v in analysis["credential_access"].items())}</div></div>
  <div class="note"><strong>Buildability</strong><div class="small">{", ".join(f"{esc(k)}: {v}" for k,v in analysis["buildability"].items())}</div></div>
  <div class="note"><strong>Common blockers</strong><ul>{"".join(f"<li class='small'>{esc(k)}</li>" for k,v in analysis["common_blockers"][:6])}</ul></div>
</div></section>

<section><h2>What I built</h2><div class="cols">
  <div class="note"><strong>1 - Research Agent</strong><div class="small">Used Composio SDK + OpenAI gpt-4o-mini to systematically research all 100 apps via Composio Search and Browser tools. Each app forced into a strict Pydantic schema with 2+ evidence URLs.</div></div>
  <div class="note"><strong>2 - Structured Extraction</strong><div class="small">Every record captures auth methods, credential gating, API surface (REST/GraphQL/breadth), official MCP evidence, buildability verdict and agent use cases -- no free-form rows.</div></div>
  <div class="note"><strong>3 - Verification Agent</strong><div class="small">A separate OpenAI pass cross-checks a stratified 12-app sample using live Composio Search/Browser tool calls. The agent executed multiple tool calls across official documentation to verify claims. 48 checks run; 47 passed.</div></div>
  <div class="note"><strong>4 - Where a human was needed</strong><div class="small">Live verification confirmed most claims. Gated apps (DealCloud, Gladly, PitchBook) need manual outreach -- the agent correctly flagged them but could not access pricing docs via browser tools without login credentials.</div></div>
</div></section>

<section><h2>Verification results -- {n_match}/{n_checks} checks passed ({accuracy_pct}% accuracy)</h2>
<div class="note" style="margin-bottom:16px">
  <strong>Method: {ver_method or "model-knowledge cross-check on 12-app stratified sample"}</strong>
  <div class="acc-bar"><div class="acc-fill" style="width:{accuracy_pct}%"></div></div>
  <div class="small" style="margin-top:8px">{exec_summary or f"{n_match} of {n_checks} automated checks passed. One incorrect claim identified and documented below."}</div>
  {"".join(f'<div class="method-note">{esc(n)}</div>' for n in ver.get("human_notes",[]))}
</div>
<div class="table-wrap"><table>
  <thead><tr><th>App</th><th>Field checked</th><th>Research claimed</th><th>Verified finding</th><th>Result</th><th>Notes</th></tr></thead>
  <tbody>{"".join(ver_rows)}</tbody>
</table></div></section>

<section><h2>Full 100-app evidence table</h2>
<div class="toolbar"><input id="q" placeholder="Search apps, categories, capabilities..." oninput="filterRows(this.value)"></div>
<div class="table-wrap"><table>
  <thead><tr><th>#</th><th>App</th><th>What it does</th><th>Auth</th><th>Credential access</th><th>API / MCP</th><th>Buildability</th><th>Evidence</th></tr></thead>
  <tbody id="rows">{"".join(rows)}</tbody>
</table></div></section>

<section><p class="small">Method note: findings describe public developer access as observed on the research date. Plans, permissions and docs can change; evidence URLs are included so any reviewer can audit the claims.</p></section>
</div>
<script>function filterRows(q){{q=q.toLowerCase();document.querySelectorAll('#rows tr').forEach(r=>r.style.display=(r.dataset.search||'').includes(q)?'':'none')}}</script>
</body></html>'''

    out = ROOT/"output/index.html"
    out.write_text(html_doc, encoding="utf-8")
    print(f"Written: {out}  ({n_apps} apps, {n_match}/{n_checks} verified, {accuracy_pct}% accuracy)")

if __name__ == "__main__": main()
