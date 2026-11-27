import datetime, json, pathlib, re, urllib.robotparser
from urllib.parse import urlsplit
import httpx
from bs4 import BeautifulSoup
from selectolax.lexbor import LexborHTMLParser
from rapidfuzz.fuzz import ratio
from diskcache import Cache
from pydantic import BaseModel, HttpUrl
from tenacity import retry, stop_after_attempt, retry_if_exception_type, wait_fixed
class Evidence(BaseModel):
    merchant:str
    source:HttpUrl
    title:str
    observed_at:str
    region:str='US'
    verification:str='merchant_page_observed'
    expiry:str|None=None
sources=[('Microsoft','https://www.microsoft.com/en-us/store/b/sale'),('Microsoft','https://www.microsoft.com/en-us/store/b/black-friday'),('Apple','https://www.apple.com/shop/refurbished')]
ua='MegaSalePromo/1.0'
@retry(stop=stop_after_attempt(2),retry=retry_if_exception_type(httpx.TransportError),wait=wait_fixed(2))
def get(client,url):
    with client.stream('GET',url) as r:
        r.raise_for_status()
        data=bytearray()
        for chunk in r.iter_bytes():
            data.extend(chunk)
            if len(data)>2000000: raise ValueError('oversize')
        return bytes(data)
def norm(s): return ' '.join(s.replace('\u200b','').split())
records=[]; errors=[]
with httpx.Client(headers={'User-Agent':ua},timeout=15,follow_redirects=False) as client, Cache('.live-cache',size_limit=10000000) as cache:
    for merchant,url in sources:
        try:
            host=urlsplit(url).netloc
            rp=urllib.robotparser.RobotFileParser()
            rp.parse(get(client,'https://'+host+'/robots.txt').decode().splitlines())
            if not rp.can_fetch(ua,url): raise ValueError('robots denied')
            raw=get(client,url)
            a=BeautifulSoup(raw,'html.parser')
            b=LexborHTMLParser(raw)
            second={norm(x.text(separator=' ')) for x in b.css('h1,h2,h3')}
            for node in a.select('h1,h2,h3'):
                title=norm(node.get_text(' ',strip=True))
                if title not in second or not re.search(r'\b(?:off|deals|save|refurbished|free)\b',title,re.I): continue
                if any(x['merchant']==merchant and ratio(x['title'],title)>95 for x in records): continue
                records.append(Evidence(merchant=merchant,source=url,title=title,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()).model_dump(mode='json'))
            cache.set(url,raw,expire=900)
        except Exception as e: errors.append({'source':url,'error':str(e)})
out=pathlib.Path('public');out.mkdir(exist_ok=True)
(out/'merchant-evidence.json').write_text(json.dumps({'records':records,'errors':errors},indent=2))
print(json.dumps({'records':records,'errors':errors},indent=2))
