"""Merge official-domain search candidates from independently run engines.
No search result becomes a verified sale merely because it was cited by an AI."""
import json,pathlib,datetime,collections
from marketplace_discovery import MARKETS,safe_url
from strict_quality_gate import test as quality_test
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"public"
def read(name,default):
    p=OUT/name
    return json.loads(p.read_text()) if p.exists() else default
def merge():
    primary=read("marketplace-discovery.json",{})
    probes=read("multi-engine-review.json",{})
    vane=read("vane-provider-test.json",{})
    rows={}
    def add(raw,provider):
        if not isinstance(raw,str):return
        for merchant,domain,region in MARKETS:
            u=safe_url(raw,domain)
            if u:
                row=rows.setdefault(u,{"url":u,"marketplace":merchant,"region":region,"providers":[],"status":"hold_for_policy_review"})
                if provider not in row["providers"]:row["providers"].append(provider)
                return
    for x in primary.get("candidates",[]):add(x.get("url"),"searxng")
    for x in probes.get("candidates",[]):
        for p in x.get("providers",[]):add(x.get("url"),p)
    for u in vane.get("sources",[]):add(u,"vane")
    report={"generated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"candidates":list(rows.values()),"provider_counts":dict(collections.Counter(p for r in rows.values() for p in r["providers"])),"marketplaces_with_candidates":len({r["marketplace"] for r in rows.values()}),"verified_offers":0}
    (OUT/"discovery-review.json").write_text(json.dumps(report,indent=2))
    print("SUPER_TEAM_DISCOVERY",json.dumps({k:v for k,v in report.items() if k!="candidates"}),flush=True)
if __name__=="__main__":
    quality_test()
    merge()
