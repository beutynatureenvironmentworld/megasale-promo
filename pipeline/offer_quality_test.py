"""Offer completeness benchmark: controlled fixtures, not live merchant claims."""
import json,datetime as dt,re,pathlib
from bs4 import BeautifulSoup
from selectolax.lexbor import LexborHTMLParser
from lxml import html
import extruct
from pydantic import BaseModel, Field
NOW=dt.datetime.now(dt.timezone.utc)
DATE=lambda days:(NOW+dt.timedelta(days=days)).isoformat()
class Offer(BaseModel):
    merchant:str
    code:str|None=None
    discount_percent:float=Field(gt=0,le=100)
    region:str
    starts:dt.datetime
    expires:dt.datetime
    minimum_spend:float=Field(ge=0)
    currency:str
    source:str
def eligible(x,region="US"):
    return x.region==region and x.starts<=NOW<x.expires and bool(x.code)
base=dict(merchant="Fixture shop",code="TEST20",discount_percent=20,region="US",starts=DATE(-1),expires=DATE(1),minimum_spend=50,currency="USD",source="https://fixture.example/sale")
cases=[("active",base,True),("expired",{**base,"expires":DATE(-1)},False),("future",{**base,"starts":DATE(1),"expires":DATE(2)},False),("wrong_region",{**base,"region":"GB"},False),("no_code",{**base,"code":None},False)]
def page(d):
    return '<html><head><script type="application/ld+json">'+json.dumps({"@context":"https://schema.org","@type":"Offer","name":"Synthetic test","description":json.dumps(d)})+'</script></head><body><article id="offer">'+json.dumps(d)+'</article></body></html>'
adapters={
    "beautifulsoup":lambda s:json.loads(BeautifulSoup(s,"html.parser").select_one("#offer").get_text()),
    "selectolax":lambda s:json.loads(LexborHTMLParser(s).css_first("#offer").text()),
    "lxml":lambda s:json.loads(html.fromstring(s).xpath("string(//*[@id='offer'])")),
    "extruct":lambda s:json.loads(extruct.extract(s,syntaxes=["json-ld"])["json-ld"][0]["description"]),
}
def run():
    results={}
    for name,extract in adapters.items():
        rows=[]
        for label,d,expected in cases:
            try:
                extracted=Offer.model_validate(extract(page(d)))
                assert extracted.model_dump(mode="json")==Offer.model_validate(d).model_dump(mode="json")
                assert eligible(extracted)==expected
                rows.append({"case":label,"pass":True})
            except Exception as e:rows.append({"case":label,"pass":False,"error":str(e)[:200]})
        results[name]=rows
    for name,rows in results.items(): print(name,sum(x["pass"] for x in rows),"/",len(rows))
    out=pathlib.Path("public");out.mkdir(exist_ok=True)
    (out/"offer-quality-fixture.json").write_text(json.dumps({"fixture_only":True,"tested_at":NOW.isoformat(),"results":results},indent=2))
    assert all(r["pass"] for rows in results.values() for r in rows)
if __name__=="__main__":run()
