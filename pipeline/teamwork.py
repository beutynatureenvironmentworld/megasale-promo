"""Offline-tested extraction adapters; never infer a coupon or expiry."""
import json
from bs4 import BeautifulSoup
from selectolax.lexbor import LexborHTMLParser
import extruct
import feedparser
from urllib.parse import urlsplit

def extract(raw, kind, url):
    if kind == 'json':
        data=json.loads(raw)
        if not isinstance(data,list): raise ValueError('expected explicit offer list')
        return data
    if kind == 'rss':
        entries=feedparser.parse(raw)
        if entries.bozo: raise ValueError('invalid feed')
        return [dict(x) for x in entries.entries]
    if kind != 'html': raise ValueError('unsupported format')
    a=BeautifulSoup(raw,'html.parser')
    b=LexborHTMLParser(raw)
    def parse(nodes, getter):
        out=[]
        for n in nodes:
            value=json.loads(getter(n))
            out.extend(value if isinstance(value,list) else [value])
        return out
    x=parse(a.select('script[type="application/ld+json"]'),lambda n:n.get_text())
    y=parse(b.css('script[type="application/ld+json"]'),lambda n:n.text())
    z=extruct.extract(raw,base_url=url,syntaxes=['json-ld'])['json-ld']
    if x!=y or x!=z: raise ValueError('extractor disagreement')
    return x

def test():
    fixture=b'<html><script type="application/ld+json">{"@type":"Offer","price":"10","priceCurrency":"USD"}</script></html>'
    assert extract(fixture,'html','https://example.org')[0]['price']=='10'
    assert extract(b'[{"title":"fixture"}]','json','https://example.org')[0]['title']=='fixture'
    assert extract(b'<rss version="2.0"><channel><title>Test</title><link>https://example.org</link><description>Fixture</description><item><title>Fixture</title></item></channel></rss>','rss','https://example.org')[0]['title']=='Fixture'
    print('Fixture tests passed; no live merchant data acquired')
if __name__=='__main__': test()
