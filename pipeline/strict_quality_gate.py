"""Strict evidence scoring for publication candidates; no invented details."""
import datetime as dt,json,pathlib,re
from urllib.parse import urlsplit
from pydantic import BaseModel,Field
class Evidence(BaseModel):
    merchant:str
    official_host:str
    source:str
    observed_at:dt.datetime
    start:dt.datetime
    expiry:dt.datetime
    region:str
    kind:str
    title:str
    code:str|None=None
    discount:str
    terms:str
    permission_evidence:str
    evidence_excerpt:str
    source_sha256:str=Field(pattern=r"^[a-f0-9]{64}$")
def evaluate(r,now):
    reasons=[]
    u=urlsplit(r.source)
    if u.scheme!="https" or u.hostname not in (r.official_host,"www."+r.official_host) or u.username or u.password:reasons.append("unofficial source")
    if any(x.tzinfo is None for x in [r.observed_at,r.start,r.expiry]):return ["missing timezone"]
    if not dt.timedelta(0)<=now-r.observed_at<=dt.timedelta(hours=24):reasons.append("stale evidence")
    if not r.start<=now<r.expiry:reasons.append("inactive")
    if not r.permission_evidence.strip():reasons.append("permission missing")
    if not all(x.strip() for x in [r.title,r.region,r.terms,r.discount,r.evidence_excerpt]):reasons.append("incomplete")
    if r.discount not in r.evidence_excerpt:reasons.append("unsupported discount")
    if r.kind=="coupon" and (not r.code or r.code not in r.evidence_excerpt):reasons.append("unsupported coupon")
    if r.kind not in ("coupon","sale"):reasons.append("unsupported type")
    return reasons
def test():
    now=dt.datetime.now(dt.timezone.utc)
    fixture=dict(merchant="Synthetic only",official_host="example.com",source="https://example.com/promo",observed_at=now,start=now-dt.timedelta(hours=1),expiry=now+dt.timedelta(days=1),region="US",kind="coupon",title="Fixture sale",code="LAB20",discount="20%",terms="Minimum USD 50",permission_evidence="synthetic fixture only",evidence_excerpt="LAB20 gives 20% off",source_sha256="0"*64)
    scenarios=[("complete",{},True),("expired",{"expiry":now},False),("future",{"start":now+dt.timedelta(hours=1)},False),("stale",{"observed_at":now-dt.timedelta(days=2)},False),("future observation",{"observed_at":now+dt.timedelta(minutes=1)},False),("third party",{"source":"https://coupon.example.net/a"},False),("missing permission",{"permission_evidence":""},False),("fabricated coupon",{"code":"FAKE"},False),("fabricated discount",{"discount":"90%"},False),("missing region",{"region":""},False),("missing terms",{"terms":""},False),("sale without code",{"kind":"sale","code":None},True)]
    rows=[]
    for name,change,expected in scenarios:
        failures=evaluate(Evidence.model_validate({**fixture,**change}),now)
        rows.append({"case":name,"pass":(not failures)==expected,"reasons":failures})
    print("QUALITY_GATE",sum(x["pass"] for x in rows),len(rows))
    assert all(x["pass"] for x in rows)
    pathlib.Path("public").mkdir(exist_ok=True)
    pathlib.Path("public/strict-quality-fixture.json").write_text(json.dumps({"fixture_only":True,"tests":rows},indent=2))
if __name__=="__main__":test()
