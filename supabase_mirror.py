"""
Supabase — the bridge's first store since 15 Oct 2026 (mini-erp upgrades 609–612; plan in
mini-erp/docs/MONGO-TO-SUPABASE-PLAN.md).

Every webhook is written to rio_inbox BEFORE the bridge answers respond.io, then processed Supabase
first (rio_ingest_message / _lifecycle / _note / _email_lead) and Mongo second. Each half is marked
done on the inbox row; whatever is still open after 90 seconds is claimed again by the replayer, so a
restart, a full queue, a Supabase hiccup or Mongo's circuit breaker no longer loses a message.

  * On unless SUPABASE_MIRROR=false, and only when SUPABASE_URL + SUPABASE_SERVICE_KEY are set
    (the name is kept from Phase 1 so the Railway variables stay as they are).
  * The ingest doors raise on failure (the worker marks the inbox row and the replayer retries);
    inbox writes never raise (a failed put falls back to the in-memory queue, as before).
  * Every door is insert-or-skip on the respond.io id, so a re-run or a redelivered webhook is harmless.
"""
import json
import logging
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from threading import Lock

logger = logging.getLogger("supabase_mirror")

URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
KEY = os.getenv("SUPABASE_SERVICE_KEY") or ""
ENABLED = os.getenv("SUPABASE_MIRROR", "true").lower() == "true" and bool(URL and KEY)
INBOX = ENABLED and os.getenv("SUPABASE_INBOX", "true").lower() == "true"
COMPANY = {"vip": "VIP", "faster": "Faster"}

_lock = Lock()
stats = {"ok": 0, "failed": 0, "inbox_put": 0, "inbox_put_failed": 0, "replayed": 0,
         "last_error": None, "last_error_at": None}


def _bump(key, n=1):
    with _lock:
        stats[key] = stats.get(key, 0) + n


def _jsonable(v):
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).isoformat()
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def _request(path, body=None, method="POST", timeout=20):
    data = json.dumps(_jsonable(body), default=str).encode() if body is not None else None
    req = urllib.request.Request(
        f"{URL}/rest/v1/{path}", data=data, method=method,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "User-Agent": "respondbridge/2"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def rpc(fn, args, attempts=3, timeout=20):
    """Call a Supabase door; raises after `attempts` tries (1 s, 2 s between). 4xx don't retry."""
    last = None
    for i in range(attempts):
        try:
            out = _request(f"rpc/{fn}", args, timeout=timeout)
            _bump("ok")
            return out
        except urllib.error.HTTPError as e:
            last = f"{fn} {e.code}: {e.read().decode(errors='replace')[:300]}"
            if e.code < 500:
                break
        except Exception as e:  # network / timeout
            last = f"{fn}: {e}"
        if i < attempts - 1:
            time.sleep(2 ** i)
    _fail(last)
    raise RuntimeError(last)


def _fail(msg):
    with _lock:
        stats["failed"] += 1
        stats["last_error"] = msg
        stats["last_error_at"] = datetime.now(timezone.utc).isoformat()
    logger.error(f"Supabase failed — {msg}")


# ── the inbox ────────────────────────────────────────────────────────────────

def inbox_put(tenant, kind, traffic, payload):
    """Write the raw webhook before answering respond.io. Returns the row id, or None (never raises)."""
    if not INBOX or tenant not in COMPANY:
        return None
    try:
        out = _request("rpc/rio_inbox_put", {"p_company": COMPANY[tenant], "p_kind": kind,
                                              "p_traffic": traffic, "p_payload": payload}, timeout=5)
        _bump("inbox_put")
        return out
    except Exception as e:
        _bump("inbox_put_failed")
        logger.error(f"Inbox put failed ({tenant}/{kind}) — kept in memory only: {e}")
        return None


def inbox_mark(inbox_id, part, error=None):
    if not inbox_id:
        return
    try:
        _request("rpc/rio_inbox_mark", {"p_id": inbox_id, "p_part": part,
                                         "p_error": (str(error)[:900] if error else None)}, timeout=10)
    except Exception as e:
        logger.error(f"Inbox mark failed (#{inbox_id} {part}): {e}")


def inbox_claim(older_than_sec, with_mongo, limit=100):
    if not INBOX:
        return []
    try:
        return _request("rpc/rio_inbox_claim", {"p_older_than_sec": older_than_sec, "p_with_mongo": with_mongo,
                                                 "p_limit": limit}, timeout=20) or []
    except Exception as e:
        logger.error(f"Inbox claim failed: {e}")
        return []


# ── the ingest doors (raise on failure) ──────────────────────────────────────

def message(tenant, message_doc, contact, channel, media_type, timestamp_ms):
    """message_doc = the dict the bridge builds for Mongo (same fields)."""
    if not ENABLED or tenant not in COMPANY:
        return
    msg = dict(message_doc)
    msg["id"] = str(msg.pop("_id", "") or "")
    msg["direction"] = msg.pop("message_type", None)
    if timestamp_ms:  # respond.io's own time, in UTC (the Mongo copy keeps the server's local clock)
        msg["ts"] = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    msg.pop("created_at", None)
    rpc("rio_ingest_message", {"p_company": COMPANY[tenant], "p_msg": msg, "p_contact": contact or {},
                               "p_channel": channel or {}, "p_media_type": media_type})


def lifecycle(tenant, contact, lifecycle_value, old_lifecycle, event_id):
    if ENABLED and tenant in COMPANY:
        rpc("rio_ingest_lifecycle", {"p_company": COMPANY[tenant], "p_contact": contact or {},
                                     "p_lifecycle": lifecycle_value, "p_old_lifecycle": old_lifecycle, "p_event_id": event_id})


def internal_note(tenant, note_doc):
    if not ENABLED or tenant not in COMPANY:
        return
    note = dict(note_doc)
    note["event_id"] = note.pop("_id", None)
    rpc("rio_ingest_note", {"p_company": COMPANY[tenant], "p_note": note})


def email_lead(tenant, message_id, doc):
    if ENABLED and tenant in COMPANY:
        rpc("rio_ingest_email_lead", {"p_company": COMPANY[tenant], "p_message_id": message_id, "p_doc": doc})


def conversation_contact(tenant, chat_id):
    """The contact on a chat's Supabase conversation row, or None — the email-lead phone match."""
    if not ENABLED or tenant not in COMPANY or not chat_id:
        return None
    q = urllib.parse.urlencode({"select": "contact", "company": f"eq.{COMPANY[tenant]}", "chat_id": f"eq.{chat_id}"})
    rows = _request(f"rio_conversations?{q}", method="GET", timeout=10) or []
    return (rows[0].get("contact") or {}) if rows else None
