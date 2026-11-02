"""Instant phone alerts via Telegram with interactive buttons and notification management.
Falls back to email if Telegram isn't configured.
"""
import html
import logging
import os
import re
import sys
from typing import Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import requests

log = logging.getLogger("notifier")

TG_API = "https://api.telegram.org"


def load_env_val(key: str, default: str = "") -> str:
    val = os.getenv(key, "")
    if val:
        return val.strip()
    for env_path in [".env", os.path.join("job_agent", ".env")]:
        if os.path.exists(env_path):
            try:
                for line in open(env_path, encoding="utf-8"):
                    line = line.strip()
                    if line.startswith(f"{key}=") and not line.startswith("#"):
                        return line.split("=", 1)[1].strip().strip('"\'')
            except Exception:
                pass
    return default


def get_token() -> str:
    return load_env_val("TELEGRAM_BOT_TOKEN", "9298472471:AAFOl3KSWDJ0rOSxnvJRDRea-4-EuMbrxA4")


def get_chat_id() -> str:
    return load_env_val("TELEGRAM_CHAT_ID", "8288731777")


def telegram_enabled() -> bool:
    return bool(get_token() and get_chat_id())


def save_chat_id(chat_id: str):
    chat_id = str(chat_id).strip()
    if not chat_id:
        return
    os.environ["TELEGRAM_CHAT_ID"] = chat_id
    for env_path in [".env", os.path.join("job_agent", ".env")]:
        try:
            lines = []
            found = False
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("TELEGRAM_CHAT_ID="):
                            lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
                            found = True
                        else:
                            lines.append(line)
            if not found:
                lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            log.info("Saved TELEGRAM_CHAT_ID=%s to %s", chat_id, env_path)
        except Exception as e:
            log.warning("Could not save chat id to %s: %s", env_path, e)


def send_telegram(
    text: str,
    button_url: Optional[str] = None,
    inline_keyboard: Optional[list] = None,
    chat_id: Optional[str] = None,
) -> bool:
    token = get_token()
    target_chat = chat_id or get_chat_id()
    if not token or not target_chat:
        log.warning("Telegram send failed: missing token or chat_id (token=%s, chat=%s)", bool(token), bool(target_chat))
        return False

    payload = {
        "chat_id": target_chat,
        "text": text[:4000],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if inline_keyboard:
        payload["reply_markup"] = {"inline_keyboard": inline_keyboard}
    elif button_url and button_url.startswith("http"):
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {"text": "🌐 Open & Apply", "url": button_url},
                ]
            ]
        }

    try:
        r = requests.post(f"{TG_API}/bot{token}/sendMessage", json=payload, timeout=20)
        if not r.ok:
            log.warning("Telegram API error %d: %s", r.status_code, r.text)
            if "can't parse entities" in r.text.lower():
                payload["parse_mode"] = None
                r = requests.post(f"{TG_API}/bot{token}/sendMessage", json=payload, timeout=20)
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning("Failed to send telegram notification: %s", e)
        return False


def format_alert(job, profile_name: str, score: int, subject: str, body: str) -> str:
    e = html.escape
    prof_lower = profile_name.lower()
    if "support" in prof_lower or "care" in prof_lower:
        icon = "🎧"
        profile_label = "Customer Care / Support"
    elif "front" in prof_lower:
        icon = "💻"
        profile_label = "Frontend Developer"
    else:
        icon = "🛡️"
        profile_label = "Cybersecurity / SOC"

    # Human-friendly source platform name
    src_raw = (job.source or "").lower()
    if "google" in src_raw:
        source_name = "Google Jobs"
    elif "linkedin" in src_raw:
        source_name = "LinkedIn"
    elif "internshala" in src_raw:
        source_name = "Internshala"
    elif "freshersworld" in src_raw:
        source_name = "Freshersworld"
    elif "jobicy" in src_raw:
        source_name = "Jobicy"
    elif "remoteok" in src_raw:
        source_name = "RemoteOK"
    elif "himalayas" in src_raw:
        source_name = "Himalayas"
    elif "greenhouse" in src_raw:
        source_name = f"Greenhouse ({job.source.split(':', 1)[-1]})"
    elif "lever" in src_raw:
        source_name = f"Lever ({job.source.split(':', 1)[-1]})"
    else:
        source_name = job.source.capitalize()

    head = (
        f"🔔 <b>NEW MATCH: {e(job.title)}</b>\n"
        f"🏢 <b>Company:</b> {e(job.company)}\n"
        f"📍 <b>Location:</b> {e(job.location or 'India / Remote')}\n"
        f"💼 <b>Platform:</b> <code>{e(source_name)}</code>\n"
        f"{icon} <b>Profile:</b> <code>{e(profile_label)}</code> (Match Score: <b>{score}/10</b>)\n"
    )
    if job.email:
        head += f"✉️ <b>Direct Email:</b> <code>{e(job.email)}</code>\n"

    head += f"\n📝 <b>Cover Note Draft</b> (Subject: <i>{e(subject)}</i>):\n"

    max_body_len = 3800 - len(head) - 30
    snippet = e(body.strip())
    if len(snippet) > max_body_len:
        snippet = snippet[:max_body_len] + "..."

    return head + "<pre>" + snippet + "</pre>"


def create_job_buttons(job_url: str, job_id: Optional[str] = None) -> list:
    buttons = []
    first_row = []
    if job_url and job_url.startswith("http"):
        first_row.append({"text": "🌐 Open & Apply", "url": job_url})

    cb_data = f"app:{job_id}" if job_id else f"app:{abs(hash(job_url)) % 10000000}"
    first_row.append({"text": "✅ Mark Applied", "callback_data": cb_data})
    buttons.append(first_row)
    return buttons


def get_telegram_updates(offset: Optional[int] = None) -> list:
    token = get_token()
    if not token:
        return []
    try:
        params = {"timeout": 10}
        if offset:
            params["offset"] = offset
        r = requests.get(f"{TG_API}/bot{token}/getUpdates", params=params, timeout=15)
        if r.ok:
            return r.json().get("result", [])
    except Exception as e:
        log.warning("Failed to fetch telegram updates: %s", e)
    return []


def setup_chat_id():
    token = get_token()
    if not token:
        print("❌ Set TELEGRAM_BOT_TOKEN in .env first.")
        return None

    print(f"🤖 Connected to Telegram Bot: {token[:10]}...")
    print("Checking for existing messages...")
    updates = get_telegram_updates()
    chats = {}
    for m in updates:
        msg = m.get("message") or m.get("callback_query", {}).get("message")
        if msg and "chat" in msg:
            c = msg["chat"]
            cid = c["id"]
            name = c.get("first_name", "") or c.get("title", "User")
            chats[cid] = name

    if chats:
        for cid, name in chats.items():
            print(f"✅ Found Telegram User: {name} (Chat ID: {cid})")
            save_chat_id(str(cid))
            send_telegram(
                f"🎉 <b>Job Agent Successfully Connected!</b>\n\n"
                f"Hello {html.escape(name)}!\n"
                f"Your Telegram notifications are now active. You will receive real-time job alerts here.",
                chat_id=str(cid),
            )
            print("🚀 Confirmation message sent to your Telegram!")
            return str(cid)
    else:
        print("\n⚠️ No incoming messages found yet.")
        print("👉 Follow these 2 quick steps:")
        print("   1. Open Telegram and search for: @Jobmailer3629bot")
        print("      (or click: https://t.me/Jobmailer3629bot)")
        print("   2. Send any message (e.g. /start or 'hi') to your bot.")
        print("\nOnce you send a message, run: python main.py --telegram-setup")
        return None
