"""Bounded multi-provider search and local extraction benchmark."""
import os,json,pathlib,datetime,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import httpx
from bs4 import BeautifulSoup
from selectolax.lexbor import LexborHTMLParser
from lxml import html
import trafilatura
import extruct
from playwright.sync_api import sync_playwright
from rank_bm25 import BM25Plus
from sentence_transformers import SentenceTransformer
from marketplace_discovery import MARKETS,safe_url
OUT=pathlib.Path("public");OUT.mkdir(exist_ok=True)
report={}
def check(name,fn):
    try:
        result=fn()
        report[name]={"status":"pass","result":result}
    except Exception as e:
        report[name]={"status":"fail","error":str(e)[:350]}
    print(name,json.dumps(report[name]),flush=True)
def searx():
    r=httpx.get(os.environ["SEARXNG_URL"]+"/search",params={"q":"site:ebay.com Black Friday deals","format":"json"},timeout=30)
    r.raise_for_status()
    urls=[u for x in r.json().get("results",[]) if (u:=safe_url(x.get("url",""),"ebay.com"))]
    assert urls,"No official results"
    return list(dict.fromkeys(urls))[:5]
def fourget():
    r=httpx.get(os.environ["FOURGET_URL"]+"/api/v1/web",params={"s":"site:ebay.com Black Friday deals"},timeout=40)
    r.raise_for_status()
    j=r.json();assert j.get("status")=="ok",str(j.get("status"))
    urls=[u for x in j.get("web",[]) if (u:=safe_url(x.get("url",""),"ebay.com"))]
    assert urls,"No official results"
    return list(dict.fromkeys(urls))[:5]
def vane():
    base=os.environ["VANE_URL"]
    p=httpx.get(base+"/api/providers",timeout=30);p.raise_for_status()
    providers=p.json().get("providers",[])
    chat=next(({"providerId":x["id"],"key":m["key"]} for x in providers for m in x.get("chatModels",[])),None)
    embed=next(({"providerId":x["id"],"key":m["key"]} for x in providers for m in x.get("embeddingModels",[])),None)
    assert chat and embed,"Vane model providers not configured"
    r=httpx.post(base+"/api/search",json={"chatModel":chat,"embeddingModel":embed,"optimizationMode":"speed","sources":["web"],"query":"Find official eBay Black Friday sale sources","history":[],"stream":False},timeout=180)
    r.raise_for_status();j=r.json()
    assert j.get("sources"),"No sources returned"
    return {"sources":len(j["sources"])}
FIXTURE=b'<html><head><title>Test shop</title><script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Fixture item"}</script></head><body><article><h1>Fixture seasonal offer</h1><p>This is synthetic test content for a controlled crawler benchmark. No real offer is asserted.</p></article></body></html>'
def extract():
    a=BeautifulSoup(FIXTURE,"html.parser").h1.get_text()
    b=LexborHTMLParser(FIXTURE).css_first("h1").text()
    c=html.fromstring(FIXTURE).xpath("string(//h1)")
    assert a==b==c=="Fixture seasonal offer"
    assert extruct.extract(FIXTURE.decode(),syntaxes=["json-ld"])["json-ld"][0]["name"]=="Fixture item"
    assert "synthetic test content" in trafilatura.extract(FIXTURE.decode())
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page();page.set_content(FIXTURE.decode())
        assert page.locator("h1").inner_text()==a
        browser.close()
    return {"engines":["BeautifulSoup","selectolax","lxml","extruct","Trafilatura","Playwright"],"fixture":True}
def ground():
    docs=["Official seasonal deal source","Unrelated cooking recipe","Merchant coupon policy"]
    model=SentenceTransformer("BAAI/bge-small-en-v1.5")
    emb=model.encode(docs,normalize_embeddings=True)
    q=model.encode(["seasonal deal"],normalize_embeddings=True)
    assert int((q@emb.T).argmax())==0
    assert int(BM25Plus([d.lower().split() for d in docs]).get_scores(["seasonal","deal"]).argmax())==0
    return {"embedding":"BAAI/bge-small-en-v1.5","ranker":"BM25Plus","fixture":True}
if __name__=="__main__":
    check("searxng",searx)
    check("4get",fourget)
    check("vane",vane)
    check("extractor_consensus",extract)
    check("hybrid_grounding",ground)
    candidates={}
    for engine in ("searxng","4get"):
        if report[engine]["status"]=="pass":
            for url in report[engine]["result"]:candidates.setdefault(url,[]).append(engine)
    (OUT/"multi-engine-review.json").write_text(json.dumps({"tests":report,"candidates":[{"url":u,"providers":p,"status":"hold_for_policy_review"} for u,p in candidates.items()]},indent=2))
    print("INTEGRATION_SUMMARY",json.dumps({k:v["status"] for k,v in report.items()}))
    assert all(report[x]["status"]=="pass" for x in ["searxng","extractor_consensus","hybrid_grounding"])
