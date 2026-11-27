"""Fail-closed candidate gate. Approved exact feed URLs only, never search snippets."""
import json,pathlib,urllib.parse,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
def gate(candidates, sources):
    approved={s["url"]:s for s in sources if s.get("approved") is True and s.get("permission_evidence") and s.get("host") and s.get("url")}
    out=[]
    for candidate in candidates:
        url=candidate.get("url","")
        try:
            p=urllib.parse.urlsplit(url)
            source=approved.get(url)
            eligible=bool(source and p.scheme=="https" and p.hostname==source["host"] and p.port in (None,443) and not p.username and not p.password and not p.fragment)
        except ValueError:
            eligible=False
        out.append({"url":url,"status":"approved_feed_candidate" if eligible else "hold_for_policy_review"})
    return out
def test():
    u="https://merchant.example/feed.json"
    s={"url":u,"host":"merchant.example","approved":True,"permission_evidence":"fixture only"}
    assert gate([{"url":u}], [s])[0]["status"]=="approved_feed_candidate"
    for bad in [u+"?other=1","http://merchant.example/feed.json","https://merchant.example@evil.example/feed.json"]:
        assert gate([{"url":bad}], [s])[0]["status"]=="hold_for_policy_review"
    assert gate([{"url":u}], [{**s,"permission_evidence":""}])[0]["status"]=="hold_for_policy_review"
if __name__=="__main__":
    test()
    f=ROOT/"public/discovery-review.json"
    candidates=json.loads(f.read_text()).get("candidates",[]) if f.exists() else []
    sources=json.loads((ROOT/"pipeline/sources.json").read_text())
    rows=gate(candidates,sources)
    report={"checked":len(rows),"approved":sum(x["status"]=="approved_feed_candidate" for x in rows),"rows":rows,"generated_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (ROOT/"public").mkdir(exist_ok=True)
    (ROOT/"public/policy-review.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
