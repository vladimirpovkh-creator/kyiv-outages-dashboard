#!/usr/bin/env python3
"""Archive full provider-derived hourly schedules. Never infer missing hours."""
import json,datetime as dt,pathlib,urllib.request
from zoneinfo import ZoneInfo
root=pathlib.Path(__file__).resolve().parent.parent
file=root/"data"/"history.json"
source="https://raw.githubusercontent.com/Baskerville42/outage-data-ua/main/data/kyiv-region.json"
now=dt.datetime.now(dt.timezone.utc)
request=urllib.request.Request(source,headers={"User-Agent":"KyivOutagesDashboard/1.0","Cache-Control":"no-cache"})
with urllib.request.urlopen(request,timeout=35) as response: upstream=json.load(response)
stamp=dt.datetime.fromisoformat(upstream["lastUpdated"].replace("Z","+00:00"))
if not upstream.get("lastUpdateStatus",{}).get("ok") or not (dt.timedelta(0)<=now-stamp<=dt.timedelta(hours=24)):
 raise SystemExit("Upstream unavailable/stale; history not modified")
groups=["GPV%d.%d"%(i,j) for i in range(1,7) for j in (1,2)]
values={"yes","no","first","second"}
existing=json.loads(file.read_text(encoding="utf-8")) if file.exists() else {"days":{}}
days=existing.get("days",{})
added=[]
for key,record in upstream.get("fact",{}).get("data",{}).items():
 day=dt.datetime.fromtimestamp(int(key),dt.timezone.utc).astimezone(ZoneInfo("Europe/Kyiv")).date().isoformat()
 if all(isinstance(record.get(g),dict) and set(record[g])==set(str(i) for i in range(1,25)) and set(record[g].values())<=values for g in groups):
  if day not in days or days[day]!=record:
   days[day]={g:record[g] for g in groups}
   added.append(day)
cutoff=(now.astimezone(ZoneInfo("Europe/Kyiv")).date()-dt.timedelta(days=90)).isoformat()
days={k:v for k,v in sorted(days.items()) if k>=cutoff}
payload={"days":days,"updated_at":now.isoformat(),"source":source,"source_updated_at":upstream["lastUpdated"],"note":"Validated 24 hourly fields per 12 groups. Changes are snapshots of the latest published schedules, not measured outages."}
if added or not file.exists():
 file.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("validated days:",",".join(added) if added else "no changes")
