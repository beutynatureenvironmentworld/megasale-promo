"""Controlled iterative research benchmark. Not the upstream dzhng engine."""
import asyncio,json,threading,pathlib,datetime
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.robotparser import RobotFileParser
from urllib.parse import urlsplit
import httpx
from scrapy.http import HtmlResponse
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from bs4 import BeautifulSoup
from rank_bm25 import BM25Plus
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
PAGES={
"/robots.txt":b"User-agent: *\nAllow: /\nDisallow: /private\n",
"/":b"<html><body><h1>Fixture shop</h1><a href='/season'>Seasonal promotion</a></body></html>",
"/season":b"<html><body><article><h1>Fixture November sale</h1><p>Example discount 10 percent. Synthetic benchmark only.</p><a href='/terms'>Promotion terms</a></article></body></html>",
"/terms":b"<html><body><h1>Promotion terms</h1><p>Fixture only: eligible region US; expiry 2099-11-30.</p></body></html>"
}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body=PAGES.get(self.path)
        self.send_response(200 if body else 404)
        self.send_header("Content-Type","text/plain" if self.path=="/robots.txt" else "text/html")
        self.end_headers();self.wfile.write(body or b"not found")
class Evidence(BaseModel):
    url:str
    title:str
    text:str
    fixture:bool=True
async def run():
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f"http://127.0.0.1:{server.server_port}"
    try:
        rp=RobotFileParser();rp.parse(httpx.get(base+"/robots.txt").text.splitlines())
        assert not rp.can_fetch("MegaSalePromo",base+"/private")
        queue=["/"];seen=set();evidence=[]
        async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
            for depth in range(3):
                nextq=[]
                for path in queue:
                    if path in seen:continue
                    u=base+path
                    assert rp.can_fetch("MegaSalePromo",u)
                    r=httpx.get(u,follow_redirects=False);r.raise_for_status()
                    a=HtmlResponse(url=u,body=r.content,encoding="utf-8")
                    b=BeautifulSoup(r.content,"html.parser")
                    title=a.css("h1::text").get()
                    assert title==b.h1.get_text()
                    result=await crawler.arun(url=u,config=CrawlerRunConfig())
                    assert result.success and title in str(result.markdown)
                    evidence.append(Evidence(url=u,title=title,text=b.get_text(" ",strip=True)).model_dump())
                    seen.add(path)
                    for href in a.css("a::attr(href)").getall():
                        if href in PAGES and href not in seen:nextq.append(href)
                queue=nextq
        assert seen=={"/","/season","/terms"}
        texts=[x["text"] for x in evidence]
        model=SentenceTransformer("BAAI/bge-small-en-v1.5")
        vectors=model.encode(texts,normalize_embeddings=True)
        q=model.encode(["promotion terms region expiry"],normalize_embeddings=True)
        rank=int((q@vectors.T).argmax())
        assert evidence[rank]["url"].endswith("/terms")
        assert int(BM25Plus([x.lower().split() for x in texts]).get_scores(["expiry","region"]).argmax())==rank
        out={"test":"controlled_three_stage_research","status":"pass","fixture_only":True,"verified_live_offers":0,"evidence":evidence,"engines":["HTTPX","Scrapy selectors","BeautifulSoup","Crawl4AI","BGE","BM25Plus","Pydantic","robots.txt"]}
        pathlib.Path("public").mkdir(exist_ok=True)
        pathlib.Path("public/iterative-research-test.json").write_text(json.dumps(out,indent=2))
        print("ITERATIVE_RESEARCH_PASS",len(evidence),flush=True)
    finally:server.shutdown()
if __name__=="__main__":asyncio.run(run())
