#!/usr/bin/env python3
"""Conservative monitoring of the official DTEK page.
No guessed hours. Writes status JSON, keeps past snapshots."""
import datetime as dt,json,urllib.request,hashlib,pathlib
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).resolve().parent.parent
now=dt.datetime.now(ZoneInfo("Europe/Kyiv"))
url="https://www.dtek-krem.com.ua/ua/shutdowns"
result={"checked_at":now.isoformat(),"source":url,"source_status":"unavailable","confirmed_daily_schedules":False,"data_status":"not_connected","message":"Офіційні графіки за 12 чергами ще не підключено. Дані рейтингу історичні та неперевірені."}
try:
 req=urllib.request.Request(url,headers={"User-Agent":"KyivOutagesDashboard/1.0 (+https://github.com/vladimirpovkh-creator/kyiv-outages-dashboard)","Accept":"text/html"})
 with urllib.request.urlopen(req,timeout=25) as resp:
  body=resp.read(1024*1024)
  if resp.status==200 and len(body)>1000 and (b"DTEK" in body or b"\xd0\x94\xd0\xa2\xd0\x95\xd0\x9a" in body):
   result["source_status"]="reachable"
   result["page_sha256"]=hashlib.sha256(body).hexdigest()
   result["message"]="Сторінка ДТЕК доступна, але машинозчитувані графіки для всіх черг ще не підтверджені."
except Exception as exc: result["error_type"]=type(exc).__name__
(ROOT/"data").mkdir(exist_ok=True)
(ROOT/"data"/"status.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,ensure_ascii=False))
