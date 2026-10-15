"""
Supabase mirror — Phase 1 of moving off MongoDB (15 Oct 2026).

After each Mongo write the bridge hands the same data to Supabase (upgrade-609's doors:
rio_ingest_message / rio_ingest_lifecycle / rio_ingest_note / rio_ingest_email_lead).

Rules:
  * Mongo stays the source of truth: a mirror failure is logged and counted, never raised,
    and never slows the Mongo path — calls run on a small background pool.
  * Off unless SUPABASE_MIRROR=true and SUPABASE_URL + SUPABASE_SERVICE_KEY are set.
  * Every door is insert-or-skip on the respond.io id, so a retry or a redelivered webhook
    is harmless.
"""
import json
import logging
import os
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock

logger = logging.getLogger("supabase_mirror")

URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
KEY = os.getenv("SUPABASE_SERVICE_KEY") or ""
ENABLED = os.getenv("SUPABASE_MIRROR", "false").lower() == "true" and bool(URL and KEY)
COMPANY = {"vip": "VIP", "faster": "Faster"}

_pool = ThreadPoolExecutor(max_workers=int(os.getenv("SUPABASE_MIRROR_WORKERS", "4")), thread_name_prefix="sb-mirror")
_lock = Lock()
stats = {"ok": 0, "failed": 0, "last_error": None, "last_error_at": None}


def _jsonable(v):
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).isoformat()
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def _rpc(fn, args, attempts=3):
    body = json.dumps(_jsonable(args), default=str).encode()
    req = urllib.request.Request(
        f"{URL}/rest/v1/rpc/{fn}", data=body, method="POST",
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "User-Agent": "respondbridge-mirror/1"},
    )
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
            with _lock:
                stats["ok"] += 1
            return
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code < 500 or i == attempts - 1:  # a 4xx won't fix itself
                _fail(f"{fn} {e.code}: {detail}")
                return
        except Exception as e:  # network / timeout
            if i == attempts - 1:
                _fail(f"{fn}: {e}")
                return


def _fail(msg):
    with _lock:
        stats["failed"] += 1
        stats["last_error"] = msg
        stats["last_error_at"] = datetime.now(timezone.utc).isoformat()
    logger.error(f"Supabase mirror failed — {msg}")


def _submit(fn, args):
    if not ENABLED:
        return
    try:
        _pool.submit(_rpc, fn, args)
    except Exception as e:
        _fail(f"{fn} not queued: {e}")


def message(tenant, message_doc, contact, channel, media_type, timestamp_ms):
    """message_doc = the dict the bridge just wrote to Mongo."""
    if tenant not in COMPANY:
        return
    msg = dict(message_doc)
    msg["id"] = str(msg.pop("_id", "") or "")
    msg["direction"] = msg.pop("message_type", None)
    if timestamp_ms:  # respond.io's own time, in UTC (the Mongo copy keeps the server's local clock)
        msg["ts"] = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    msg.pop("created_at", None)
    _submit("rio_ingest_message", {"p_company": COMPANY[tenant], "p_msg": msg, "p_contact": contact or {},
                                   "p_channel": channel or {}, "p_media_type": media_type})


def lifecycle(tenant, contact, lifecycle_value, old_lifecycle, event_id):
    if tenant in COMPANY:
        _submit("rio_ingest_lifecycle", {"p_company": COMPANY[tenant], "p_contact": contact or {},
                                         "p_lifecycle": lifecycle_value, "p_old_lifecycle": old_lifecycle, "p_event_id": event_id})


def internal_note(tenant, note_doc):
    if tenant not in COMPANY:
        return
    note = dict(note_doc)
    note["event_id"] = note.pop("_id", None)
    _submit("rio_ingest_note", {"p_company": COMPANY[tenant], "p_note": note})


def email_lead(tenant, message_id, doc):
    if tenant in COMPANY:
        _submit("rio_ingest_email_lead", {"p_company": COMPANY[tenant], "p_message_id": message_id, "p_doc": doc})
