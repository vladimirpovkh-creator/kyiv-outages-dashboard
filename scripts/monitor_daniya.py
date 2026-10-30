#!/usr/bin/env python3
"""Best-effort PUBLIC Telegram channel monitor. No credentials, no invented statuses."""
import datetime as dt, json, pathlib, re, urllib.request
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

ROOT=pathlib.Path(__file__).resolve().parent.parent
OUT=ROOT/"data"/"daniya-status.json"
URL="https://t.me/s/svitlobot_daniya"
class Messages(HTMLParser):
    def __init__(self):
        super().__init__();self.depth=0;self.current=None;self.messages=[];self.in_text=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs);classes=d.get("class","").split()
        if "tgme_widget_message_wrap" in classes and self.current is None:
            self.current={"text":"","time":None,"id":None};self.depth=1
        elif self.current is not None:self.depth+=1
        if self.current is not None:
            if "tgme_widget_message_text" in classes:self.in_text=self.depth
            if tag=="time" and d.get("datetime"):self.current["time"]=d["datetime"]
            if d.get("data-post"):self.current["id"]=d["data-post"]
    def handle_endtag(self,tag):
        if self.current is None:return
        if self.in_text==self.depth:self.in_text=0
        self.depth-=1
        if self.depth==0:
            self.messages.append(self.current);self.current=None
    def handle_data(self,data):
        if self.current is not None and self.in_text:self.current["text"]+=data+" "

def classify(s):
    s=" ".join(s.lower().split())
    on=[r"\\bсвітло\\s+(?:є|з'явилось|з’явилось|з'явилося|з’явилося|відновлено|увімкнули)\\b",r"\\bелектропостачання\\s+відновлено\\b",r"\\b(?:світло|електрику)\\s+(?:дали|увімкнули)\\b"]
    off=[r"\\b(?:немає|нема|відсутнє)\\s+світла\\b",r"\\bсвітло\\s+(?:зникло|вимкнули|відключили|відсутнє)\\b",r"\\bвідключення\\s+електроенергії\\b"]
    a=any(re.search(p,s) for p in on);b=any(re.search(p,s) for p in off)
    return "on" if a and not b else "off" if b and not a else None

now=dt.datetime.now(dt.timezone.utc)
result={"state":"unknown","changed_at":None,"checked_at":now.isoformat(),"source":URL,"group":"5.2","place":"ЖК Данія","reason":"Публічні повідомлення каналу не підтверджені","observed_at":None}
try:
    request=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 (compatible; PublicStatusMonitor/1.0)"})
    with urllib.request.urlopen(request,timeout=25) as res:
        if res.status!=200:raise ValueError("HTTP "+str(res.status))
        html=res.read(2000000).decode("utf-8","replace")
    parser=Messages();parser.feed(html)
    events=[]
    for msg in parser.messages:
        kind=classify(msg["text"])
        if not kind or not msg["time"]:continue
        try:timestamp=dt.datetime.fromisoformat(msg["time"].replace("Z","+00:00")).astimezone(dt.timezone.utc)
        except ValueError:continue
        if timestamp>now+dt.timedelta(minutes=5):continue
        events.append((timestamp,kind,msg))
    if not events:result["reason"]="Немає доступних однозначних подій зі штампом часу"
    else:
        stamp,kind,msg=max(events,key=lambda x:x[0])
        if now-stamp>dt.timedelta(hours=24):
            result["reason"]="Остання однозначна подія старша за 24 години"
        else:
            result.update(state=kind,changed_at=stamp.isoformat(),observed_at=stamp.isoformat(),reason="Публічне повідомлення Telegram",message_id=msg["id"])
except Exception as e:
    result["reason"]="Джерело тимчасово недоступне: "+type(e).__name__
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
print(result)
