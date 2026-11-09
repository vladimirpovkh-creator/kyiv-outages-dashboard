#!/usr/bin/env python3
"""Aggregate historical electricity availability from ForumPrazkyi topic 63.

Only explicit switch-event announcements are used. Time with no credible
event evidence is labelled unknown. No message bodies or user identities
are stored in the public JSON.
"""
import asyncio
import datetime as dt
import json
import os
import pathlib
import re
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = "ForumPrazkyi / тема 63"
TOPIC_ID = 63
KYIV = ZoneInfo("Europe/Kyiv")
UTC = dt.timezone.utc
# A confirmed transition stays in effect until the next confirmed transition.
# No arbitrary duration cap: events can legitimately be >12 hours apart.
MAX_MESSAGES = 4000
OUTPUT = ROOT / "data" / "forum-prazkyi-actual-history.json"
ARCHIVE = ROOT / "data" / "history.json"


def classify_change(text):
    """Actual switch-on/off notice, not schedule or a question.

    The residential building's event notifications start with a headline
    such as 'Світло вимкнулось!' or 'Світло увімкнулось!'.
    """
    first = (text or "").strip().splitlines()
    if not first:
        return None
    line = " ".join(first[0].lower().replace("’", "'").split())
    if "?" in line or any(x in line for x in ("графік", "план", "завтра", "очікується", "можливо")):
        return None
    on = bool(re.search(r"\bсвітло\s+(увімкнулось|увімкнулося|включилось|включилося|з'явилось|з'явилося)\b", line))
    off = bool(re.search(r"\bсвітло\s+(вимкнулось|вимкнулося|відключилось|відключилося|зникло)\b", line))
    return "on" if on and not off else "off" if off and not on else None


def read_dates(now):
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    today = now.astimezone(KYIV).date()
    dates = sorted(
        dt.date.fromisoformat(d)
        for d in archive.get("days", {})
        if dt.date.fromisoformat(d) < today
    )
    return dates


async def read_events(start, now):
    """Backfill topic history, stopping one day before first archive day."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    boundary = dt.datetime.combine(start - dt.timedelta(days=1), dt.time.min, KYIV).astimezone(UTC)
    events = []
    inspected = 0
    reached_boundary = False
    client = TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"]),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"],
    )
    async with client:
        if not await client.is_user_authorized():
            raise PermissionError("Telegram session not authorized")
        entity = await client.get_entity("ForumPrazkyi")
        async for msg in client.iter_messages(entity, reply_to=TOPIC_ID, limit=MAX_MESSAGES):
            when = msg.date.astimezone(UTC)
            if when < boundary:
                reached_boundary = True
                break
            inspected += 1
            state = classify_change(msg.raw_text or "")
            if state and when <= now + dt.timedelta(minutes=5):
                events.append((when, state, msg.id))
    return events, inspected, reached_boundary


def daily_totals(dates, events, now):
    """Account for every second using observed switch transitions.

    A confirmed state carries forward across midnight, without a 12-hour cap,
    until the next switch notice. The interval before the first observed event
    remains unknown: a future event cannot establish its previous state.
    This is event-based inference, not direct power-meter measurement.
    DST and local-day boundaries are calculated in UTC.
    """
    unique = {(stamp, mid): (stamp, state, mid) for stamp, state, mid in events
              if state in ("on", "off") and stamp <= now}
    ordered = sorted(unique.values(), key=lambda item: (item[0], item[2]))
    intervals = []
    for index, (start, state, _) in enumerate(ordered):
        next_start = ordered[index + 1][0] if index + 1 < len(ordered) else now
        end = min(next_start, now)
        if end > start:
            intervals.append((start, end, state))

    output = {}
    for day in dates:
        beginning = dt.datetime.combine(day, dt.time.min, KYIV).astimezone(UTC)
        ending = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min, KYIV).astimezone(UTC)
        possible = (ending - beginning).total_seconds()
        seconds = {"on": 0.0, "off": 0.0}
        for start, end, state in intervals:
            overlap = (min(end, ending) - max(start, beginning)).total_seconds()
            if overlap > 0:
                seconds[state] += overlap
        if seconds["on"] + seconds["off"] > possible + 0.01:
            raise ValueError("Overlapping events exceed local day duration")
        unknown_seconds = max(0.0, possible - seconds["on"] - seconds["off"])
        on = round(seconds["on"] / 3600, 4)
        off = round(seconds["off"] / 3600, 4)
        total = round(possible / 3600, 4)
        unknown = round(unknown_seconds / 3600, 4)
        output[day.isoformat()] = {
            "on_hours": on,
            "off_hours": off,
            "unknown_hours": unknown,
            "day_hours": total,
            "covered_hours": round((seconds["on"] + seconds["off"]) / 3600, 4),
        }
    return output


def build_result(dates, events, now, inspected, reached_boundary):
    days = daily_totals(dates, events, now)
    total = {
        key: round(sum(day[key] for day in days.values()), 3)
        for key in ("on_hours", "off_hours", "unknown_hours", "day_hours", "covered_hours")
    }
    return {
        "source": SOURCE, "group": "5.2", "topic_id": TOPIC_ID,
        "updated_at": now.isoformat(),
        "period_start": dates[0].isoformat() if dates else None,
        "period_end": dates[-1].isoformat() if dates else None,
        "method": "explicit_switch_messages_and_bounded_intervals",
        "interval_policy": "state_carries_until_next_confirmed_switch",
        "max_unconfirmed_interval_hours": None,
        "messages_examined": inspected,
        "switch_events_found": len(events),
        "reached_archive_boundary": reached_boundary,
        "days": days,
        "totals": total,
        "note": "Оцінка за повідомленнями про перемикання: кожен відомий стан переноситься до наступного повідомлення, без довільного ліміту в 12 годин. Пропущені повідомлення можуть змінити оцінку; до першого підтвердженого стану час невідомий. Це не дані лічильника.",
    }


def main():
    now = dt.datetime.now(UTC)
    dates = read_dates(now)
    if not dates:
        raise ValueError("No completed days in DTEK history")
    # Fail closed: do not publish stale or fabricated figures if Telegram fails.
    required = ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION")
    if not all(os.environ.get(k) for k in required):
        raise RuntimeError("Required Telegram session secrets missing")
    events, examined, reached = asyncio.run(read_events(dates[0], now))
    if not reached and examined >= MAX_MESSAGES:
        raise RuntimeError(
            "Telegram message limit reached before archive boundary; "
            "cannot certify archive coverage"
        )
    result = build_result(dates, events, now, examined, reached)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "period": [result["period_start"], result["period_end"]],
        "messages_examined": examined,
        "switch_events_found": result["switch_events_found"],
        "totals": result["totals"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
