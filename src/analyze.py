from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def load():
    data = json.loads((ROOT / "output/research_results.json").read_text())
    return data["records"] if isinstance(data, dict) and "records" in data else data

def pct(n, d): return round(100*n/d, 1) if d else 0

def main():
    records = load(); n = len(records)
    auth = Counter(a for r in records for a in r["auth_methods"])
    access = Counter(r["credential_access"]["mode"] for r in records)
    verdict = Counter(r["buildability"]["verdict"] for r in records)
    breadth = Counter(r["api_surface"]["breadth"] for r in records)
    mcp = sum(bool(r["api_surface"].get("existing_mcp")) for r in records)
    categories = defaultdict(list)
    for r in records: categories[r["category"]].append(r)
    category_stats = []
    for cat, rows in categories.items():
        category_stats.append({"category":cat,"count":len(rows),"ready_pct":pct(sum(x["buildability"]["verdict"]=="toolkit-ready" for x in rows),len(rows)),"gated_pct":pct(sum(x["credential_access"]["mode"] in {"partner/contact-sales","admin-approval"} for x in rows),len(rows))})
    common_blockers=Counter(r["buildability"]["main_blocker"] for r in records if r["buildability"]["main_blocker"])
    out={
      "n":n,
      "auth_distribution":auth,
      "credential_access":access,
      "buildability":verdict,
      "api_breadth":breadth,
      "official_mcp_count":mcp,
      "category_stats":sorted(category_stats,key=lambda x:x["category"]),
      "common_blockers":common_blockers.most_common(12)
    }
    (ROOT / "output/analysis.json").write_text(json.dumps(out,indent=2,default=dict))
    print(json.dumps(out,indent=2,default=dict))
if __name__=="__main__": main()
