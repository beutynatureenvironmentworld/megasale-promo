import os,json,pathlib,datetime
import httpx
from urllib.parse import urlsplit
ROOT=pathlib.Path("public")
ROOT.mkdir(exist_ok=True)
queries=["official Black Friday sale coupon Microsoft", "official Apple refurbished savings", "official Daraz sale voucher", "official AliExpress sale coupon"]
allowed={"www.microsoft.com","www.apple.com","www.daraz.lk","www.aliexpress.com"}
def discover():
    candidates=[]; errors=[]
    endpoint=os.getenv("SEARXNG_URL")
    if not endpoint: return candidates,["SEARXNG_URL not configured"]
    with httpx.Client(timeout=20,follow_redirects=False) as c:
        for q in queries:
            try:
                r=c.get(endpoint.rstrip("/")+"/search",params={"q":q,"format":"json","categories":"general"})
                r.raise_for_status()
                for item in r.json().get("results",[])[:10]:
                    u=urlsplit(item.get("url",""))
                    if u.scheme=="https" and u.netloc in allowed:
                        candidates.append({"url":u.geturl(),"query":q,"status":"policy_review_required"})
            except Exception as e: errors.append(type(e).__name__)
    return list({x["url"]:x for x in candidates}.values()),errors
if __name__=="__main__":
    candidates,errors=discover()
    (ROOT/"discovery-review.json").write_text(json.dumps({"candidates":candidates,"errors":errors,"observed_at":datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2))
    print(len(candidates),errors)
