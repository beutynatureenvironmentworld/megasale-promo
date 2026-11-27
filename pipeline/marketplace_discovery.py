"""Regional marketplace discovery. Search evidence is never a verified offer."""
import os,json,time,datetime,pathlib,re,html
from urllib.parse import urlsplit,urlunsplit
import httpx
from rapidfuzz.fuzz import ratio
from pydantic import BaseModel,HttpUrl
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"public"
OUT.mkdir(exist_ok=True)
MARKETS=[
("AliExpress","aliexpress.com","Global"),("eBay","ebay.com","US"),("Amazon","amazon.com","US"),("Temu","temu.com","US"),
("Walmart","walmart.com","US"),("Target","target.com","US"),("Etsy","etsy.com","US"),("Best Buy","bestbuy.com","US"),("Newegg","newegg.com","US"),
("Daraz","daraz.lk","LK"),("Shopee","shopee.sg","SG"),("Lazada","lazada.sg","SG"),("Flipkart","flipkart.com","IN"),
("Myntra","myntra.com","IN"),("Meesho","meesho.com","IN"),("JioMart","jiomart.com","IN"),
("Mercado Libre","mercadolibre.com.mx","MX"),("Allegro","allegro.pl","PL"),("bol","bol.com","NL"),("Cdiscount","cdiscount.com","FR"),
("Fnac","fnac.com","FR"),("Kaufland","kaufland.de","DE"),("OnBuy","onbuy.com","UK"),("noon","noon.com","AE"),
("Trendyol","trendyol.com","TR"),("Hepsiburada","hepsiburada.com","TR"),("Coupang","coupang.com","KR"),
("Gmarket","gmarket.co.kr","KR"),("Qoo10 Japan","qoo10.jp","JP"),("JD.com","jd.com","CN")]
class Candidate(BaseModel):
    marketplace:str
    region:str
    url:HttpUrl
    query:str
    observed_at:str
    status:str="hold_for_policy_review"
def safe_url(value,domain):
    try:
        p=urlsplit(value)
        if p.scheme!="https" or p.username or p.password or p.port not in (None,443) or not p.hostname: return None
        if p.hostname not in (domain,"www."+domain): return None
        return urlunsplit((p.scheme,p.netloc,p.path or "/","",""))
    except ValueError:return None
def seasons():
    m=datetime.datetime.now(datetime.timezone.utc).month
    return {11:["Black Friday","Cyber Monday"],12:["Christmas","year end"],1:["New Year"],2:["Lunar New Year","Valentine"],3:["spring sale","Ramadan"],4:["spring sale","Eid"],5:["May sale"],6:["summer sale","6.6"],7:["summer sale"],8:["back to school","8.8"],9:["9.9","autumn sale"],10:["10.10","autumn sale"]}[m]
def plan():
    labels=seasons()
    if os.getenv("AI_MODEL"):
        try:
            from transformers import AutoTokenizer,AutoModelForCausalLM
            model=os.environ["AI_MODEL"]
            t=AutoTokenizer.from_pretrained(model)
            m=AutoModelForCausalLM.from_pretrained(model)
            prompt="Choose the most relevant seasonal shopping event from this list: "+", ".join(labels)+". Answer with one exact event name only."
            x=t(prompt,return_tensors="pt")
            y=m.generate(**x,max_new_tokens=24,do_sample=False,pad_token_id=t.eos_token_id)
            answer=t.decode(y[0][x.input_ids.shape[1]:],skip_special_tokens=True)
            chosen=next((s for s in labels if s.lower() in answer.lower()),None)
            if chosen:return [chosen]+[s for s in labels if s!=chosen],"ai_selected:"+model
        except Exception as e:print("AI fallback:",type(e).__name__)
    return labels,"calendar_fallback"
def run():
    labels,planner=plan()
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    endpoint=os.environ["SEARXNG_URL"].rstrip("/")+"/search"
    candidates=[]; status=[]
    with httpx.Client(timeout=20,follow_redirects=False) as c:
        for name,domain,region in MARKETS:
            q=f'site:{domain} {name} {" OR ".join(labels)} deals offers {datetime.datetime.now().year}'
            rows=[]; error=None
            try:
                response=c.get(endpoint,params={"q":q,"format":"json","categories":"general"})
                response.raise_for_status()
                for item in response.json().get("results",[]):
                    u=safe_url(item.get("url",""),domain)
                    if not u or u in rows:continue
                    rows.append(u)
                    candidates.append(Candidate(marketplace=name,region=region,url=u,query=q,observed_at=stamp).model_dump(mode="json"))
                    if len(rows)>=5:break
            except Exception as e:error=type(e).__name__
            status.append({"marketplace":name,"region":region,"domain":domain,"candidates":len(rows),"error":error})
            print(name,len(rows),error,flush=True)
            time.sleep(1.5)
    report={"generated_at":stamp,"planner":planner,"season_queries":labels,"marketplaces":status,"candidates":candidates,"verified_offers":0}
    (OUT/"marketplace-discovery.json").write_text(json.dumps(report,indent=2))
    (OUT/"discovery-review.json").write_text(json.dumps({"candidates":candidates},indent=2))
    lines=["<!doctype html><meta charset=utf-8><meta name=robots content=noindex><meta name=viewport content='width=device-width'><title>Marketplace discovery audit</title><style>body{font:16px system-ui;max-width:960px;margin:30px auto;padding:16px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}table{width:100%}</style><h1>Marketplace discovery audit</h1><p>Internal preview. Candidate links are not confirmed discounts. Publication approval required.</p>",f"<p>{html.escape(stamp)} | {len(candidates)} candidates | 0 verified offers</p><table><tr><th>Marketplace<th>Region<th>Candidates<th>Result"]
    for row in status:lines.append("<tr>"+"".join("<td>"+html.escape(str(v)) for v in [row["marketplace"],row["region"],row["candidates"],row["error"] or "Search completed"]))
    lines.append("</table>")
    (OUT/"marketplace-audit.html").write_text("".join(lines))
    print("MARKETPLACE_SUMMARY",json.dumps({"markets":len(status),"with_candidates":sum(s["candidates"]>0 for s in status),"candidates":len(candidates),"errors":sum(bool(s["error"]) for s in status),"planner":planner}),flush=True)
    assert len(status)==30
if __name__=="__main__":
    assert len(MARKETS)==30 and len({x[1] for x in MARKETS})==30
    assert safe_url("https://www.amazon.com/deals?tracking=x","amazon.com")=="https://www.amazon.com/deals"
    assert safe_url("https://amazon.com.evil.test/deals","amazon.com") is None
    run()
