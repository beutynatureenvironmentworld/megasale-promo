import json, sqlite3, datetime, pathlib, html
from rank_bm25 import BM25Plus
from rapidfuzz.fuzz import ratio
from diskcache import Cache
from tenacity import retry, stop_after_attempt
import httpx
from teamwork import extract
from pydantic import BaseModel
class Demo(BaseModel):
    title: str
    category: str
    test_only: bool = True
raw=b'<script type="application/ld+json">{"title":"Sample laptop offer","category":"Electronics"}</script>'
items=[Demo.model_validate(x).model_dump() for x in extract(raw,'html','https://example.org')]
items.append(Demo(title='Sample clothing offer',category='Fashion').model_dump())
items=[x for i,x in enumerate(items) if not any(ratio(x['title'],y['title'])>95 for y in items[:i])]
rank=BM25Plus([x['title'].lower().split() for x in items])
assert rank.get_top_n(['laptop'],items,n=1)[0]['category']=='Electronics'
with Cache('.preview-cache',size_limit=10000000) as c:
    c.set('demo',items,expire=300); assert c.get('demo')==items
with sqlite3.connect(':memory:') as c:
    c.execute('create virtual table offers using fts5(title)')
    c.executemany('insert into offers values (?)',[(x['title'],) for x in items])
    assert c.execute("select count(*) from offers where offers match 'laptop'").fetchone()[0]==1
@retry(stop=stop_after_attempt(2))
def fetch(client):
    r=client.get('https://example.org'); r.raise_for_status(); return r
with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,text='fixture'))) as client:
    assert fetch(client).text=='fixture'
out=pathlib.Path('public');out.mkdir(exist_ok=True)
report={'mode':'fixture_only','live_offers':0,'tests':['BeautifulSoup/selectolax/extruct agreement','Pydantic validation','RapidFuzz deduplication','BM25 ranking','DiskCache','SQLite FTS5','HTTPX mock transport and Tenacity wrapper'],'items':items,'time':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(out/'teamwork-test.json').write_text(json.dumps(report,indent=2))
(out/'teamwork-test.html').write_text('<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width"><title>MegaSale teamwork test</title><style>body{font:18px system-ui;max-width:850px;margin:40px auto;padding:20px}article{padding:20px;background:#eef2ff;margin:12px 0;border-radius:12px}</style><h1>MegaSale Teamwork Lab</h1><p>TEST ONLY — synthetic offers, not redeemable. Live offers: 0.</p><h2>Integration checks passed</h2><ul>'+''.join('<li>'+html.escape(t)+'</li>' for t in report['tests'])+'</ul><h2>Sample offers</h2>'+''.join('<article>'+html.escape(x['title'])+' — '+html.escape(x['category'])+'</article>' for x in items))
print(json.dumps(report))
