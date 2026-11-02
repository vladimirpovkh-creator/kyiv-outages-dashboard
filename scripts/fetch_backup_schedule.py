#!/usr/bin/env python3
"""Fetch independent Svitlo Live source and validate regional outage schedules."""
import datetime as dt
import json
import pathlib
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "backup-schedule.json"
SOURCE = "https://dtek-api.svitlo-proxy.workers.dev/"
now = dt.datetime.now(dt.timezone.utc)
today = now.astimezone(ZoneInfo("Europe/Kyiv")).date()
headers = {"User-Agent":"KyivOutagesDashboard/1.0", "Accept":"application/json"}
with urllib.request.urlopen(urllib.request.Request(SOURCE, headers=headers), timeout=35) as response:
    raw = json.load(response)
    if response.status != 200:
        raise ValueError(f"HTTP {response.status}")
if isinstance(raw.get("body"), str):
    raw = json.loads(raw["body"])
region = next((r for r in raw.get("regions", []) if r.get("cpu") == "kiivska-oblast"), None)
if not region or region.get("emergency"):
    raise ValueError("Region missing or emergency schedule active")
schedule = region.get("schedule", {})
groups = [f"{i}.{j}" for i in range(1,7) for j in (1,2)]
data = {}
for day in (today, today+dt.timedelta(days=1)):
    date = day.isoformat()
    normalized = {}
    for group in groups:
        slots = schedule.get(group, {}).get(date)
        if not isinstance(slots, dict) or len(slots) != 48:
            continue
        bits = []
        for i in range(48):
            slot = f"{i//2:02}:{(i%2)*30:02}"
            v = slots.get(slot)
            if v not in (1, 2) or type(v) is not int:
                break
            bits.append(0 if v == 1 else 1)
        if len(bits) != 48:
            continue
        hourly = {}
        for h in range(24):
            a,b = bits[2*h:2*h+2]
            hourly[str(h+1)] = ("no" if a and b else "yes" if not a and not b else "first" if a else "second")
        normalized["GPV"+group] = hourly
    if len(normalized) == 12:
        data[date] = normalized
if not data:
    raise ValueError("No complete schedules for Kyiv region")
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps({"source": SOURCE,"checked_at":now.isoformat(),"days":data,"note":"Independent source; validated complete 48-slot schedules, not proof of official freshness."},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Valid schedules:", list(data))
