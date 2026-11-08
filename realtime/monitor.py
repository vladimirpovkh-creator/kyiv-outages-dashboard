#!/usr/bin/env python3
"""Low-latency Telegram topic 63 monitor + read-only HTTPS-ready JSON API.

Requires a continuously running host. Does not publish message text or credentials.
"""
import asyncio
import datetime as dt
import json
import logging
import os
from pathlib import Path

from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from monitor_forum_prazkyi import classify

LOG = logging.getLogger("forum-realtime")
UTC = dt.timezone.utc
TOPIC_ID = 63
MAX_AGE = dt.timedelta(hours=24)
SYNC_STALE = dt.timedelta(minutes=2)
ORIGIN = "https://vladimirpovkh-creator.github.io"
PORT = int(os.environ.get("PORT", "8080"))
STATE_PATH = Path(os.environ.get("STATE_PATH", "/state/status.json"))


def topic_header_matches(message):
    """Recognize topic root or replies (nested replies may omit top ID)."""
    reply = getattr(message, "reply_to", None)
    return (getattr(reply, "reply_to_top_id", None) == TOPIC_ID
            or getattr(reply, "reply_to_msg_id", None) == TOPIC_ID
            or getattr(message, "id", None) == TOPIC_ID)


def utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def choose_latest(messages, now):
    candidates = []
    for msg in messages:
        state = classify(getattr(msg, "raw_text", "") or "")
        stamp = utc(msg.date)
        if state and now - MAX_AGE <= stamp <= now + dt.timedelta(minutes=5):
            candidates.append((stamp, msg.id, state))
    if not candidates:
        return None
    return max(candidates, key=lambda x: (x[0], x[1]))


class Store:
    def __init__(self):
        self.last_sync = None
        self.current = None
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            previous = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            # Load latest event only; do not reuse old check-time as an active connection.
            if previous.get("state") in ("on", "off") and previous.get("changed_at"):
                self.current = {
                    "state": previous["state"],
                    "changed_at": previous["changed_at"],
                    "message_id": previous.get("message_id"),
                }
        except (OSError, ValueError, TypeError):
            pass

    def apply(self, winner, now):
        if winner:
            stamp, mid, state = winner
            candidate = {"state": state, "changed_at": stamp.isoformat(), "message_id": mid}
            old = self.current or {}
            old_stamp = dt.datetime.fromisoformat(old["changed_at"]) if old.get("changed_at") else dt.datetime.min.replace(tzinfo=UTC)
            if (stamp, mid) >= (old_stamp, int(old.get("message_id") or 0)):
                self.current = candidate
        self.last_sync = now
        data = self.payload(now)
        temp = STATE_PATH.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        temp.replace(STATE_PATH)

    def payload(self, now):
        checked = self.last_sync
        connected = checked is not None and dt.timedelta(0) <= now - checked < SYNC_STALE
        state = (self.current or {}).get("state", "unknown")
        changed_text = (self.current or {}).get("changed_at")
        try:
            changed = dt.datetime.fromisoformat(changed_text) if changed_text else None
        except (ValueError, TypeError):
            changed = None
        fresh = changed is not None and dt.timedelta(0) <= now - changed < MAX_AGE
        active = connected and fresh and state in ("on", "off")
        return {
            "state": state if active else "unknown",
            "changed_at": changed_text if active else None,
            "checked_at": checked.isoformat() if connected else None,
            "group": "5.2",
            "source": "ForumPrazkyi / тема 63",
            "message_id": (self.current or {}).get("message_id") if active else None,
            "reason": "Останнє підтверджене перемикання" if active else "Немає актуального підтвердженого стану або зв'язку",
        }


store = None
client = None
sync_lock = asyncio.Lock()


async def sync_latest():
    now = dt.datetime.now(UTC)
    async with sync_lock:
        entity = await client.get_entity("ForumPrazkyi")
        # Telegram server scopes this request to topic 63, including nested replies.
        messages = [msg async for msg in client.iter_messages(entity, reply_to=TOPIC_ID, limit=150)]
        store.apply(choose_latest(messages, now), dt.datetime.now(UTC))


async def event_received(event):
    # Always reconcile with server-scoped messages, not arbitrary texts from other topics.
    if topic_header_matches(event.message):
        try:
            await sync_latest()
        except Exception:
            LOG.exception("Reconciliation failed following Telegram message")


async def periodic_reconciliation():
    while True:
        try:
            await sync_latest()
        except Exception:
            LOG.exception("Telegram reconciliation failed")
        await asyncio.sleep(30)


def cors_headers():
    return {"Access-Control-Allow-Origin": ORIGIN,
            "Vary": "Origin",
            "Cache-Control": "no-store, max-age=0",
            "X-Content-Type-Options": "nosniff"}


async def get_status(request):
    data = store.payload(dt.datetime.now(UTC)) if store is not None else {"state":"unknown"}
    response = web.json_response(data, headers=cors_headers())
    return response


async def health(request):
    now = dt.datetime.now(UTC)
    healthy = client is not None and client.is_connected() and store is not None and store.last_sync is not None and now - store.last_sync < SYNC_STALE
    return web.json_response({"ok": healthy}, status=200 if healthy else 503,
                             headers={"Cache-Control": "no-store"})


async def main():
    global client, store
    store = Store()
    logging.basicConfig(level=logging.INFO)
    required = ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION")
    if not all(os.environ.get(key) for key in required):
        raise RuntimeError("TELEGRAM_API_ID, TELEGRAM_API_HASH and TELEGRAM_SESSION required")
    client = TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"]),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"],
        auto_reconnect=True,
    )
    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("Telegram session unauthorized")
    entity = await client.get_entity("ForumPrazkyi")
    client.add_event_handler(event_received, events.NewMessage(chats=entity))
    client.add_event_handler(event_received, events.MessageEdited(chats=entity))
    app = web.Application()
    app.router.add_get("/status", get_status)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    task = asyncio.create_task(periodic_reconciliation())
    LOG.info("Realtime monitor started for topic 63 on port %s", PORT)
    try:
        await client.run_until_disconnected()
    finally:
        task.cancel()
        await runner.cleanup()
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
