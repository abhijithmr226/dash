"""Interactive Telegram Bot for Job Agent.
Provides real-time commands, instant alert notifications, and inline button actions.

Commands:
  /start   - Initialize bot, auto-pair Chat ID, and view menu
  /alerts  - Search all job boards right now and push new match cards
  /stats   - View total applications, applied jobs, and tracker statistics
  /digest  - Generate and view today's job digest summary
  /status  - Check bot connectivity, CV files, and system health
  /help    - List all available commands and shortcuts
"""
import html
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import requests
import yaml

from mailer import send_email
from matcher import classify, eligible
from notifier import (
    create_job_buttons,
    format_alert,
    get_chat_id,
    get_token,
    save_chat_id,
    send_telegram,
    telegram_enabled,
)
from sources import fetch_all
from tracker import Tracker
from writer import write_note

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("bot")

TG_API = "https://api.telegram.org"


def load_env():
    for p in [".env", os.path.join("job_agent", ".env")]:
        if os.path.exists(p):
            try:
                for line in open(p, encoding="utf-8"):
                    if "=" in line and not line.startswith("#"):
                        k, v = line.strip().split("=", 1)
                        os.environ.setdefault(k, v.strip('"\''))
            except Exception:
                pass


def load_cfg():
    load_env()
    for path in ["config.yaml", os.path.join("job_agent", "config.yaml")]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    raise FileNotFoundError("config.yaml not found")


class JobBot:
    def __init__(self):
        load_env()
        self.token = get_token()
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not configured in .env")
        self.offset = 0
        self.tracker = Tracker()
        self.url_map = {}

    def send_msg(self, chat_id: str, text: str, keyboard: Optional[list] = None) -> bool:
        payload = {
            "chat_id": chat_id,
            "text": text[:4000],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if keyboard:
            payload["reply_markup"] = {"inline_keyboard": keyboard}
        try:
            r = requests.post(f"{TG_API}/bot{self.token}/sendMessage", json=payload, timeout=20)
            if not r.ok and "can't parse entities" in r.text.lower():
                payload["parse_mode"] = None
                r = requests.post(f"{TG_API}/bot{self.token}/sendMessage", json=payload, timeout=20)
            return r.ok
        except Exception as e:
            log.warning("send_msg error: %s", e)
            return False

    def answer_callback(self, callback_query_id: str, text: str):
        try:
            requests.post(
                f"{TG_API}/bot{self.token}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text, "show_alert": True},
                timeout=10,
            )
        except Exception as e:
            log.warning("answer_callback error: %s", e)

    def edit_message_reply_markup(self, chat_id: str, message_id: int, keyboard: list):
        try:
            requests.post(
                f"{TG_API}/bot{self.token}/editMessageReplyMarkup",
                json={"chat_id": chat_id, "message_id": message_id, "reply_markup": {"inline_keyboard": keyboard}},
                timeout=10,
            )
        except Exception as e:
            log.warning("edit_message_reply_markup error: %s", e)

    def handle_start(self, chat_id: str, user_name: str):
        save_chat_id(chat_id)
        cfg = load_cfg()
        cand = cfg.get("candidate", {})
        cand_name = cand.get("name", "Abhijith MR")

        welcome_text = (
            f"👋 <b>Welcome to Job Agent, {html.escape(user_name)}!</b>\n\n"
            f"✅ <b>Telegram Phone Notifications: ACTIVE</b>\n"
            f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
            f"👤 <b>Candidate:</b> {html.escape(cand_name)}\n\n"
            f"🎯 <b>Active Career Tracks:</b>\n"
            f"• 🎧 <b>Customer Care & Support</b> (Top Cities: Kochi, Bengaluru, Hyderabad, Chennai, Mumbai, Pune, Remote)\n"
            f"• 💻 <b>Frontend Developer</b> (React, JS, HTML/CSS, WebRTC)\n"
            f"• 🛡️ <b>Cybersecurity & SOC Analyst</b> (Splunk, SIEM, Pentest, IAM)\n\n"
            f"🌐 <b>Platforms Monitored:</b>\n"
            f"Google Jobs, LinkedIn, Internshala, Freshersworld, Jobicy, RemoteOK, Himalayas, Remotive, Greenhouse & Lever.\n\n"
            f"👇 Tap a button below to get started:"
        )

        keyboard = [
            [
                {"text": "⚡ Scan Jobs Now", "callback_data": "cmd:alerts"},
                {"text": "📊 Application Stats", "callback_data": "cmd:stats"},
            ],
            [
                {"text": "📰 Today's Digest", "callback_data": "cmd:digest"},
                {"text": "⚙️ System Status", "callback_data": "cmd:status"},
            ],
            [
                {"text": "❓ Help & Commands", "callback_data": "cmd:help"},
            ],
        ]
        self.send_msg(chat_id, welcome_text, keyboard)

    def handle_help(self, chat_id: str):
        help_text = (
            "🤖 <b>Job Agent Commands Manual</b>\n\n"
            "🔍 <b>/alerts</b> or <b>/find</b> — Scan Google Jobs, LinkedIn, Internshala, Freshersworld & more right now\n"
            "📊 <b>/stats</b> — View applications database metrics & statuses\n"
            "📰 <b>/digest</b> — Generate & read today's complete job digest\n"
            "⚙️ <b>/status</b> — Check configured profiles, CVs, and bot connectivity\n"
            "✅ <b>/mark &lt;url&gt;</b> — Mark a job URL as applied in your database\n"
            "❓ <b>/help</b> — Show this command manual\n\n"
            "💡 <i>Tip: When an alert arrives, tap <b>'✅ Mark Applied'</b> directly on the card to update your tracker!</i>"
        )
        keyboard = [
            [
                {"text": "⚡ Scan Jobs Now", "callback_data": "cmd:alerts"},
                {"text": "📊 My Stats", "callback_data": "cmd:stats"},
            ]
        ]
        self.send_msg(chat_id, help_text, keyboard)

    def handle_status(self, chat_id: str):
        cfg = load_cfg()
        cand = cfg.get("candidate", {})
        profiles = cfg.get("profiles", {})

        cv_status = []
        for p_name, p_info in profiles.items():
            cv_path = p_info.get("cv", "")
            exists = os.path.exists(cv_path) or os.path.exists(os.path.join("job_agent", cv_path))
            status_icon = "✅" if exists else "⚠️ Missing"
            cv_status.append(f"• <b>{p_name.capitalize()}:</b> {status_icon} (<code>{cv_path}</code>)")

        anthropic_key = bool(os.getenv("ANTHROPIC_API_KEY"))
        gemini_key = bool(os.getenv("GEMINI_API_KEY"))
        ai_status = "Claude AI" if anthropic_key else ("Gemini AI" if gemini_key else "Smart Tailored Generator (Active)")

        text = (
            "⚙️ <b>Job Agent System Status</b>\n\n"
            f"👤 <b>Candidate:</b> {html.escape(cand.get('name', 'N/A'))}\n"
            f"✉️ <b>Email:</b> <code>{cand.get('email', 'N/A')}</code>\n"
            f"🤖 <b>Telegram Bot:</b> Connected (@Jobmailer3629bot)\n"
            f"🆔 <b>Target Chat ID:</b> <code>{chat_id}</code>\n"
            f"✍️ <b>Cover Note Engine:</b> {ai_status}\n\n"
            f"📄 <b>Profile Targets & CVs:</b>\n" + "\n".join(cv_status) + "\n\n"
            f"🌐 <b>Active Platforms:</b>\n"
            f"• Google Jobs\n"
            f"• LinkedIn Jobs\n"
            f"• Internshala (Fresher Portal)\n"
            f"• Freshersworld\n"
            f"• Jobicy, RemoteOK, Himalayas, Remotive, Arbeitnow\n"
            f"• Greenhouse & Lever Tech Boards\n\n"
            f"📍 <b>Top Cities:</b> Kochi, Bengaluru, Hyderabad, Chennai, Mumbai, Pune, Delhi NCR, Remote"
        )
        keyboard = [[{"text": "⚡ Scan Jobs Now", "callback_data": "cmd:alerts"}]]
        self.send_msg(chat_id, text, keyboard)

    def handle_stats(self, chat_id: str):
        stats = self.tracker.get_stats()
        recent = self.tracker.get_recent(5)

        text = (
            "📊 <b>Application Tracker Statistics</b>\n\n"
            f"🎯 <b>Total Jobs Tracked:</b> {stats.get('total', 0)}\n"
            f"✅ <b>Marked as Applied:</b> {stats.get('applied', 0)}\n"
            f"🔔 <b>Instant Alerts Sent:</b> {stats.get('alerted', 0)}\n"
            f"📧 <b>Auto-Emailed Directly:</b> {stats.get('emailed', 0)}\n"
            f"📰 <b>Added to Digest:</b> {stats.get('digest', 0)}\n"
        )

        if recent:
            text += "\n🕒 <b>Recent Applications:</b>\n"
            for r in recent:
                badge = "✅" if r.get("status") == "applied" else "🔔"
                text += f"{badge} <b>{html.escape(r.get('company', 'Unknown'))}</b> — {html.escape(r.get('title', 'Role'))} ({r.get('status')})\n"
        else:
            text += "\n<i>No applications recorded yet. Start scanning to find matches!</i>"

        keyboard = [
            [
                {"text": "⚡ Scan & Alert Now", "callback_data": "cmd:alerts"},
                {"text": "📰 View Digest", "callback_data": "cmd:digest"},
            ]
        ]
        self.send_msg(chat_id, text, keyboard)

    def handle_digest(self, chat_id: str):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        digest_paths = [f"digests/{today}.html", f"job_agent/digests/{today}.html"]
        found_digest = None
        for p in digest_paths:
            if os.path.exists(p):
                found_digest = p
                break

        if not found_digest:
            self.send_msg(
                chat_id,
                f"📰 <b>Daily Digest ({today})</b>\n\n"
                f"No digest generated yet for today. Would you like to scan and generate it now?",
                [[{"text": "🚀 Scan & Generate Now", "callback_data": "cmd:alerts"}]],
            )
            return

        recent = self.tracker.get_recent(8)
        text = f"📰 <b>Daily Job Digest ({today})</b>\n\n"
        if recent:
            text += "Top matching opportunities recorded:\n\n"
            for r in recent:
                url = r.get("url", "#")
                comp = html.escape(r.get("company", "Company"))
                title = html.escape(r.get("title", "Job Title"))
                status = r.get("status", "digest")
                prof = r.get("profile", "tech")
                text += f"• <a href='{url}'><b>{title}</b></a> @ {comp} [{prof}] (<i>{status}</i>)\n"
            text += f"\n📁 Full HTML saved at: <code>{found_digest}</code>"
        else:
            text += "Digest file is empty or no jobs recorded today."

        self.send_msg(chat_id, text, [[{"text": "⚡ Scan For More", "callback_data": "cmd:alerts"}]])

    def run_alerts(self, chat_id: str, limit: int = 10):
        self.send_msg(
            chat_id,
            "🔎 <b>Scanning Google Jobs, LinkedIn, Internshala, Freshersworld, Jobicy, RemoteOK...</b>\n"
            "<i>Targeting Customer Care, Frontend Developer, and Cybersecurity fresher roles across top cities...</i>",
        )
        try:
            cfg = load_cfg()
            jobs = fetch_all(cfg)
            cands = []
            for j in jobs:
                if self.tracker.seen_url(j.url):
                    continue
                if eligible(j, cfg):
                    continue
                m = classify(j, cfg)
                if m:
                    cands.append((m[1], j, m[0]))

            cands.sort(key=lambda x: (-x[0], -(x[1].posted.timestamp() if x[1].posted else 0)))
            picked = cands[:limit]

            if not picked:
                self.send_msg(
                    chat_id,
                    "✨ <b>Scan Complete:</b> No brand new un-alerted matches found at this moment.\n"
                    "All current postings have already been alerted or reviewed.",
                    [[{"text": "📊 View Application Stats", "callback_data": "cmd:stats"}]],
                )
                return

            self.send_msg(chat_id, f"🎯 <b>Found {len(picked)} new high-relevance matches!</b> Pushing alert cards to your phone now...")

            for score, job, prof in picked:
                profile_cfg = cfg["profiles"].get(prof, {})
                subject, body = write_note(job, profile_cfg, cfg)
                alert_text = format_alert(job, prof, score, subject, body)

                short_id = str(abs(hash(job.url)) % 10000000)
                self.url_map[short_id] = job.url

                keyboard = [
                    [
                        {"text": "🌐 Open & Apply", "url": job.url},
                        {"text": "✅ Mark Applied", "callback_data": f"app:{short_id}"},
                    ]
                ]

                sent = self.send_msg(chat_id, alert_text, keyboard)
                if sent:
                    self.tracker.add(job, prof, score, "alerted", body)
                time.sleep(0.4)

            self.tracker.export_csv()
            self.send_msg(
                chat_id,
                f"✅ <b>Finished!</b> Dispatched {len(picked)} job alert cards.\n"
                f"Tap <b>'✅ Mark Applied'</b> on any card once you've applied.",
                [[{"text": "📊 Check Stats", "callback_data": "cmd:stats"}]],
            )
        except Exception as e:
            log.exception("run_alerts error: %s", e)
            self.send_msg(chat_id, f"⚠️ Error while fetching jobs: <code>{html.escape(str(e))}</code>")

    def handle_callback(self, cb: dict):
        cb_id = cb["id"]
        data = cb.get("data", "")
        msg = cb.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        message_id = msg.get("message_id")

        if data.startswith("cmd:"):
            cmd = data.split(":", 1)[1]
            self.answer_callback(cb_id, f"Executing {cmd}...")
            if cmd == "alerts":
                self.run_alerts(chat_id)
            elif cmd == "stats":
                self.handle_stats(chat_id)
            elif cmd == "digest":
                self.handle_digest(chat_id)
            elif cmd == "status":
                self.handle_status(chat_id)
            elif cmd == "help":
                self.handle_help(chat_id)
        elif data.startswith("app:"):
            short_id = data.split(":", 1)[1]
            url = self.url_map.get(short_id)
            if url:
                self.tracker.mark_applied(url)
                self.tracker.export_csv()
                self.answer_callback(cb_id, "🎉 Marked as Applied! Recorded in your database.")
                new_keyboard = [
                    [
                        {"text": "🌐 Open Job Posting", "url": url},
                        {"text": "✅ Applied ✓", "callback_data": "noop"},
                    ]
                ]
                self.edit_message_reply_markup(chat_id, message_id, new_keyboard)
            else:
                self.answer_callback(cb_id, "✅ Marked application status!")
        elif data == "noop":
            self.answer_callback(cb_id, "Already marked as applied! ✨")

    def handle_message(self, m: dict):
        chat = m.get("chat", {})
        chat_id = str(chat.get("id", ""))
        user_name = chat.get("first_name", "") or chat.get("username", "User")
        text = (m.get("text") or "").strip()

        save_chat_id(chat_id)

        if text.startswith("/start"):
            self.handle_start(chat_id, user_name)
        elif text.startswith("/alerts") or text.startswith("/find"):
            self.run_alerts(chat_id)
        elif text.startswith("/stats"):
            self.handle_stats(chat_id)
        elif text.startswith("/digest"):
            self.handle_digest(chat_id)
        elif text.startswith("/status"):
            self.handle_status(chat_id)
        elif text.startswith("/help"):
            self.handle_help(chat_id)
        elif text.startswith("/mark"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                target_url = parts[1].strip()
                self.tracker.mark_applied(target_url)
                self.tracker.export_csv()
                self.send_msg(chat_id, f"✅ Marked as applied:\n<code>{html.escape(target_url)}</code>")
            else:
                self.send_msg(chat_id, "Usage: <code>/mark &lt;job_url&gt;</code>")
        else:
            self.send_msg(
                chat_id,
                f"🤖 Hello {html.escape(user_name)}!\n\n"
                f"Tap below to scan for customer care & tech fresher jobs:",
                [
                    [
                        {"text": "⚡ Scan Jobs Now", "callback_data": "cmd:alerts"},
                        {"text": "📊 Application Stats", "callback_data": "cmd:stats"},
                    ]
                ],
            )

    def poll(self):
        log.info("🤖 Starting Telegram Bot listener (@Jobmailer3629bot)...")
        log.info("Press Ctrl+C to stop.")
        while True:
            try:
                params = {"timeout": 20, "offset": self.offset}
                r = requests.get(f"{TG_API}/bot{self.token}/getUpdates", params=params, timeout=25)
                if not r.ok:
                    log.warning("getUpdates returned %d: %s", r.status_code, r.text)
                    time.sleep(3)
                    continue

                updates = r.json().get("result", [])
                for u in updates:
                    self.offset = max(self.offset, u["update_id"] + 1)
                    if "message" in u:
                        self.handle_message(u["message"])
                    elif "callback_query" in u:
                        self.handle_callback(u["callback_query"])

            except KeyboardInterrupt:
                log.info("Telegram Bot stopped by user.")
                break
            except Exception as e:
                log.warning("Polling error: %s", e)
                time.sleep(2)


def main():
    bot = JobBot()
    bot.poll()


if __name__ == "__main__":
    main()
