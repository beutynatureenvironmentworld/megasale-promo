import json, sqlite3, pathlib, datetime, html, urllib.request, urllib.parse, urllib.robotparser
from pydantic import BaseModel, HttpUrl, Field
from typing import Literal
from bs4 import BeautifulSoup
import feedparser
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'public'
OUT.mkdir(exist_ok=True)
now=datetime.datetime.now(datetime.timezone.utc)
class Offer(BaseModel):
    title:str=Field(min_length=1,max_length=300)
    source:HttpUrl
    region:str=Field(min_length=2)
    expiry:datetime.datetime
    evidence_at:datetime.datetime
    category:str
    code:str|None=None
    verification:Literal['source_reported']='source_reported'
def fetch(url,host):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.hostname!=host: raise ValueError('not allowlisted')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*a,**kw): return None
    opener=urllib.request.build_opener(NoRedirect())
    def read(u):
        with opener.open(urllib.request.Request(u,headers={'User-Agent':'MegaSalePromo/1.0'}),timeout=20) as r:
            return r.read(2000001)
    rp=urllib.robotparser.RobotFileParser()
    rp.parse(read('https://'+host+'/robots.txt').decode().splitlines())
    if not rp.can_fetch('MegaSalePromo',url): raise ValueError('robots denied')
    data=read(url)
    if len(data)>2000000: raise ValueError('response too large')
    return data
offers=[]; errors=[]
for s in json.loads((ROOT/'pipeline/sources.json').read_text()):
    if not s.get('approved') or not s.get('permission_evidence'): continue
    try:
        data=fetch(s['url'],s['host'])
        # Only explicitly structured merchant JSON is eligible; no inferred offers.
        for item in json.loads(data):
            o=Offer.model_validate({**item,'source':s['url'],'evidence_at':now,'verification':'source_reported'})
            if o.expiry.tzinfo and o.expiry>now: offers.append(o.model_dump(mode='json'))
    except Exception as e: errors.append({'source':s['url'],'error':str(e)})
(OUT/'offers.json').write_text(json.dumps(offers,indent=2))
(OUT/'status.json').write_text(json.dumps({'generated_at':now.isoformat(),'offers':len(offers),'errors':errors}))
db=OUT/'offers.sqlite'
if db.exists(): db.unlink()
with sqlite3.connect(db) as c:
    c.execute('create virtual table offers using fts5(title, category, region, source, expiry, code)')
    c.executemany('insert into offers values (?,?,?,?,?,?)',[(o['title'],o['category'],o['region'],o['source'],o['expiry'],o['code']) for o in offers])
(OUT/'index.html').write_text("""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>MegaSale Promo | Global offers</title><meta name="description" content="Source-reported global offers and seasonal sales"><link rel="canonical" href="https://promo.megasale.win/"><style>body{font:18px system-ui;max-width:900px;margin:40px auto;padding:20px}input,select{padding:12px;max-width:100%}article{border-bottom:1px solid #ccc;padding:16px 0}</style><h1>MegaSale Promo</h1><p>Source-reported offers, not checkout verified.</p><label>Search <input id="q"></label> <label>Category <select id="cat"><option value="">All</option></select></label><h2>Sale calendar and offers</h2><main id="results">Loading…</main><script>fetch('offers.json').then(r=>r.json()).then(a=>{const q=document.querySelector('#q'),cat=document.querySelector('#cat'),out=document.querySelector('#results');for(const c of new Set(a.map(x=>x.category)))cat.add(new Option(c,c));function draw(){out.replaceChildren();for(const x of a.filter(x=>(!cat.value||x.category===cat.value)&&JSON.stringify(x).toLowerCase().includes(q.value.toLowerCase())).sort((a,b)=>a.expiry.localeCompare(b.expiry))){const e=document.createElement('article');e.textContent=x.title+' | '+x.region+' | expires '+x.expiry+' | '+(x.code||'No code supplied');const l=document.createElement('a');l.href=x.source;l.textContent=' Source';e.append(l);out.append(e)}if(!out.children.length)out.textContent='No eligible offers currently available.'}q.oninput=cat.onchange=draw;draw()}).catch(()=>document.querySelector('#results').textContent='Offer feed unavailable.')</script></html>""")
(OUT/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: https://promo.megasale.win/sitemap.xml\n')
(OUT/'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://promo.megasale.win/</loc></url></urlset>')
print('Snapshot:',len(offers),'eligible offers;',len(errors),'errors')
