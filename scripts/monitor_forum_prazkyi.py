#!/usr/bin/env python3
"""Read only authorized ForumPrazkyi topic updates; never infer unverified power state."""
import datetime as dt
import json
import os
import pathlib
import re
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "forum-prazkyi-status.json"
TOPIC_ID = 63
SOURCE = "ForumPrazkyi / тема 63"
MAX_AGE = dt.timedelta(hours=24)

def classify(text):
    """Only clear state declarations, not questions or schedule predictions."""
    s = " ".join(text.casefold().replace("’", "'").split())
    if not s or "?" in s or any(x in s for x in ("за графіком", "планують", "можливо", "коли буде", "очікуємо")):
        return None
    on = (
        r"(?:світло|електрик[ау]|електроенергію)\s+(?:є|дали|увімкнули|увімкнулось|увімкнулося|включили|включилось|включилося|з'явилося|з'явилось|повернулося)\b",
        r"(?:відновили|відновлено)\s+(?:світло|електропостачання|подачу електроенергії)",
    )
    off = (
        r"(?:нема|немає|відсутнє)\s+(?:світла|електрики|електроенергії)",
        r"(?:світла|електрики|електроенергії)\s+(?:немає|нема|відсутнє)",
        r"(?:світло|електрик[ау])\s+(?:зникло|зникла|вимкнули|вимкнулось|вимкнулося|відключили|відключилось|відключилося|пропало|відсутнє)\b",
        r"(?:відключили|вимкнули)\s+(?:світло|електрику|електроенергію)",
    )
    a = any(re.search(p, s) for p in on)
    b = any(re.search(p, s) for p in off)
    return "on" if a and not b else "off" if b and not a else None

def request_updates(token, offset):
    qs = urllib.parse.urlencode({"offset": offset, "timeout": 0, "limit": 100, "allowed_updates": json.dumps(["message", "edited_message"])})
    req = urllib.request.Request("https://api.telegram.org/bot" + token + "/getUpdates?" + qs)
    with urllib.request.urlopen(req, timeout=25) as response:
        data = json.load(response)
    if not data.get("ok") or not isinstance(data.get("result"), list):
        raise ValueError("Telegram returned an invalid response")
    return data["result"]

async def fetch_user_topic_messages():
    """Read recent replies of forum topic 63 via an authorized member session."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session = os.environ["TELEGRAM_SESSION"]
    out = []
    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        if not await client.is_user_authorized():
            raise PermissionError("Telegram session is not authorized")
        entity = await client.get_entity("ForumPrazkyi")
        async for msg in client.iter_messages(entity, limit=100, reply_to=TOPIC_ID):
            # iter_messages(reply_to=TOPIC_ID) is already server-scoped
            # to this forum topic. A second reply_to_top_id check wrongly
            # drops replies to other messages in the same thread.
            out.append((msg.date, classify(msg.raw_text or ""), msg.id))
    return out

def main():
    now = dt.datetime.now(dt.timezone.utc)
    previous = {}
    if OUTPUT.exists():
        try:
            previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    result = {
        "state": "unknown", "changed_at": None, "checked_at": now.isoformat(),
        "source": SOURCE, "group": "5.2", "place": "ЖК Форум Празький",
        "reason": "Немає перевірених повідомлень у темі «Світло»",
        "message_id": None, "last_update_id": int(previous.get("last_update_id") or 0),
    }
    user_config = all(os.environ.get(key) for key in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION"))
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if user_config:
        try:
            import asyncio
            messages = asyncio.run(fetch_user_topic_messages())
            result["topic_messages_read"] = len(messages)
            result["topic_events_recognized"] = sum(1 for _, kind, _ in messages if kind)
            candidates = []
            for stamp, kind, mid in messages:
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=dt.timezone.utc)
                if kind and now - MAX_AGE <= stamp <= now + dt.timedelta(minutes=5):
                    candidates.append((stamp, kind, mid))
            if candidates:
                stamp, kind, mid = max(candidates, key=lambda item: (item[0], item[2]))
                result.update(state=kind, changed_at=stamp.isoformat(), message_id=mid,
                              reason="Підтверджене повідомлення Telegram-теми 63")
            else:
                result["reason"] = "Немає однозначного повідомлення в темі за останні 24 години"
        except Exception as exc:
            result["reason"] = "Читання теми не вдалося: " + type(exc).__name__
    elif not token:
        result["reason"] = "Потрібна авторизована Telegram-сесія учасника"
    else:
        try:
            last = result["last_update_id"]
            candidates = []
            for _ in range(5):
                updates = request_updates(token, last + 1)
                if not updates:
                    break
                for update in updates:
                    last = max(last, int(update.get("update_id", 0)))
                    msg = update.get("message") or update.get("edited_message") or {}
                    chat = msg.get("chat") or {}
                    # Never accept messages from another group or topic.
                    if str(chat.get("username", "")).casefold() != "forumprazkyi":
                        continue
                    if int(msg.get("message_thread_id") or 0) != TOPIC_ID:
                        continue
                    state = classify(msg.get("text") or msg.get("caption") or "")
                    stamp = dt.datetime.fromtimestamp(int(msg.get("date") or 0), tz=dt.timezone.utc)
                    if state and now - MAX_AGE <= stamp <= now + dt.timedelta(minutes=5):
                        candidates.append((stamp, state, int(msg.get("message_id") or 0)))
                if len(updates) < 100:
                    break
            result["last_update_id"] = last
            # Previous verified status may remain only if not stale.
            if previous.get("state") in ("on", "off") and previous.get("changed_at"):
                try:
                    oldstamp = dt.datetime.fromisoformat(previous["changed_at"])
                    if now - MAX_AGE <= oldstamp <= now:
                        candidates.append((oldstamp, previous["state"], int(previous.get("message_id") or 0)))
                except (ValueError, TypeError):
                    pass
            if candidates:
                stamp, state, mid = max(candidates, key=lambda item: (item[0], item[2]))
                result.update(state=state, changed_at=stamp.isoformat(), message_id=mid, reason="Повідомлення з Telegram-теми 63")
            else:
                result["reason"] = "Немає однозначного свіжого повідомлення з теми 63"
        except Exception as exc:
            result["reason"] = "Telegram недоступний: " + type(exc).__name__
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "last_update_id"}, ensure_ascii=False))

if __name__ == "__main__":
    main()
