from __future__ import annotations
import json, html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def esc(x): return html.escape(str(x or ""))

def main():
    raw_data = json.loads((ROOT/"output/research_results.json").read_text())
    data = raw_data["records"] if isinstance(raw_data, dict) and "records" in raw_data else raw_data
    analysis=json.loads((ROOT/"output/analysis.json").read_text())
    verification=(ROOT/"verification/automated_verification.json")
    ver=json.loads(verification.read_text()) if verification.exists() else {}
    rows=[]
    for r in data:
        ev=" ".join(f'<a href="{esc(e["url"])}" target="_blank" rel="noreferrer">source</a>' for e in r["evidence"][:3])
        rows.append(f'''<tr data-search="{esc((r["app"]+" "+r["category"]+" "+r["what_it_does"]).lower())}">
          <td>{r["id"]}</td><td><strong>{esc(r["app"])}</strong><div class="muted">{esc(r["category"])}</div></td>
          <td>{esc(r["what_it_does"])}</td>
          <td>{esc(", ".join(r["auth_methods"]))}<div class="muted">{esc(r["auth_details"])}</div></td>
          <td><span class="pill">{esc(r["credential_access"]["mode"])}</span><div class="muted">{esc(r["credential_access"]["details"])}</div></td>
          <td>{esc(" / ".join(r["api_surface"]["styles"]))}<div class="muted">{esc(r["api_surface"]["breadth"])} · MCP: {esc(r["api_surface"]["existing_mcp"])}</div></td>
          <td><span class="pill">{esc(r["buildability"]["verdict"])}</span><div class="muted">{esc(r["buildability"]["main_blocker"])}</div></td>
          <td>{ev}</td>
        </tr>''')
    top_access = sorted(analysis["credential_access"].items(), key=lambda x: x[1], reverse=True)[0] if analysis["credential_access"] else ("unknown", 0)
    top_blocker = analysis["common_blockers"][0] if analysis["common_blockers"] else ("none", 0)
    ready = analysis["buildability"].get("toolkit-ready", 0)
    self_serve = sum(v for k,v in analysis["credential_access"].items() if k.startswith("self-serve"))
    headline = f"{ready}/{analysis['n']} apps were classified toolkit-ready; {self_serve}/{analysis['n']} had a self-serve credential path. The most common access pattern was {top_access[0]}, while the most common blocker was {top_blocker[0]}."
    html_doc=f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Product Ops — 100-app integration research</title>
<style>
:root{{--bg:#081018;--panel:#101a24;--panel2:#0c151d;--text:#edf4f8;--muted:#9eb0bd;--line:#24323e;--accent:#7ee0b5;--warn:#ffd58a}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(180deg,#071018,#0b1118 40%,#081018);color:var(--text);font:14px/1.45 Inter,system-ui,-apple-system,sans-serif}}
.wrap{{max-width:1500px;margin:auto;padding:36px 28px 64px}} .eyebrow{{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:12px}}
h1{{font-size:42px;line-height:1.05;margin:8px 0 12px;max-width:1000px}} .sub{{color:var(--muted);max-width:900px;font-size:16px}}
.grid{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:24px 0}} .card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px}} .metric{{font-size:28px;font-weight:800}} .label{{color:var(--muted);font-size:12px;margin-top:4px}}
section{{margin-top:32px}} h2{{font-size:20px;margin:0 0 12px}} .headline{{background:linear-gradient(135deg,#12251f,#111a24);border:1px solid #2c493d;padding:18px;border-radius:16px;font-size:18px}}
.flex{{display:flex;gap:12px;align-items:center;flex-wrap:wrap}} .tag{{border:1px solid var(--line);padding:5px 9px;border-radius:999px;color:var(--muted)}}
.toolbar{{position:sticky;top:0;background:rgba(8,16,24,.92);backdrop-filter:blur(10px);padding:12px 0;border-bottom:1px solid var(--line);z-index:2}} input{{width:100%;background:var(--panel2);border:1px solid var(--line);color:var(--text);padding:11px 13px;border-radius:10px}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:14px;margin-top:12px}} table{{border-collapse:collapse;width:100%;min-width:1250px}} th,td{{padding:10px 11px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}} th{{position:sticky;top:57px;background:#0e1821;font-size:12px;color:#bfd0db;z-index:1}} tr:hover td{{background:#0d1720}} .muted{{color:var(--muted);font-size:11px}} .pill{{display:inline-block;border:1px solid #38505e;padding:3px 6px;border-radius:6px;font-size:11px}} a{{color:var(--accent);text-decoration:none}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} .note{{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:14px}} ul{{margin:8px 0 0 20px}} .small{{font-size:12px;color:var(--muted)}}
@media(max-width:900px){{.grid{{grid-template-columns:1fr 1fr}}.cols{{grid-template-columns:1fr}} h1{{font-size:32px}}}}
</style></head><body><div class="wrap">
<div class="eyebrow">AI Product Ops Intern · Take-home</div>
<h1>100 apps researched by an agent, then challenged by a verification loop.</h1>
<p class="sub">A reproducible integration-research pipeline that turns public documentation into auth, access, API, MCP and buildability decisions — with evidence attached to every row.</p>
<div class="headline"><strong>Headline:</strong> {esc(headline)} This is why the table separates API existence from credential access, API breadth, and agent-facing surfaces.</div>
<div class="grid">
<div class="card"><div class="metric">{analysis["n"]}</div><div class="label">apps researched</div></div>
<div class="card"><div class="metric">{analysis["official_mcp_count"]}</div><div class="label">apps with explicit official MCP evidence</div></div>
<div class="card"><div class="metric">{esc(sum(analysis["credential_access"].values()))}</div><div class="label">credential-access classifications</div></div>
<div class="card"><div class="metric">{esc(analysis["buildability"].get("toolkit-ready",0))}</div><div class="label">toolkit-ready in final dataset</div></div>
<div class="card"><div class="metric">{len(ver.get("sample_ids",[]))}</div><div class="label">automatically verified sample</div></div>
</div>
<section><h2>Patterns reviewers should notice</h2><div class="cols">
<div class="note"><strong>Auth</strong><div class="small">{', '.join(f'{esc(k)}: {v}' for k,v in analysis["auth_distribution"].items())}</div></div>
<div class="note"><strong>Credential access</strong><div class="small">{', '.join(f'{esc(k)}: {v}' for k,v in analysis["credential_access"].items())}</div></div>
<div class="note"><strong>Buildability</strong><div class="small">{', '.join(f'{esc(k)}: {v}' for k,v in analysis["buildability"].items())}</div></div>
<div class="note"><strong>Common blockers</strong><ul>{''.join(f'<li>{esc(k)} — {v}</li>' for k,v in analysis["common_blockers"][:6])}</ul></div>
</div></section>
<section><h2>What I built</h2><div class="cols"><div class="note"><strong>1 · Discover</strong><div class="small">Seeded the 100-app research set, then used Composio Search + Browser Tool to find and open first-party sources.</div></div><div class="note"><strong>2 · Extract</strong><div class="small">Structured output forces explicit auth, access, API surface, MCP, buildability and evidence fields. No free-form prose-only rows.</div></div><div class="note"><strong>3 · Critique</strong><div class="small">A separate verification agent re-opens the sources for a stratified sample and challenges critical claims.</div></div><div class="note"><strong>4 · Human check</strong><div class="small">The reviewer-facing verification file records which sample rows were manually checked and where the agent was wrong.</div></div></div></section>
<section><h2>Verification</h2><div class="note"><strong>Do not hide misses.</strong><div class="small">The verification artifact compares first-pass claims with independently inspected documentation. Human review is intentionally separate from the research agent so the “verified” number does not become self-certification.</div><p class="small">Automated report: {esc("verification/automated_verification.json")}. Human checks should be appended before submission.</p></div></section>
<section><h2>100-app evidence table</h2><div class="toolbar"><input id="q" placeholder="Search apps, categories, capabilities…" oninput="filterRows(this.value)"></div><div class="table-wrap"><table><thead><tr><th>#</th><th>App</th><th>What it does</th><th>Auth</th><th>Credential access</th><th>API / MCP</th><th>Buildability</th><th>Evidence</th></tr></thead><tbody id="rows">{''.join(rows)}</tbody></table></div></section>
<section><p class="small">Method note: findings describe public developer access as observed on the research date. Plans, permissions and docs can change; evidence URLs are included so a reviewer can audit the claims.</p></section>
</div><script>function filterRows(q){{q=q.toLowerCase();document.querySelectorAll('#rows tr').forEach(r=>r.style.display=(r.dataset.search||'').includes(q)?'':'none')}}
</script></body></html>'''
    (ROOT/"output/case_study.html").write_text(html_doc)
    print(ROOT/"output/case_study.html")
if __name__=="__main__": main()
