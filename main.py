"""Job Agent - Automated Job Application & Alert System.
Usage:
  python main.py                  # Dry-run digest generation
  python main.py --live           # Live execution (send emails / save digest)
  python main.py --alerts         # Search & notify new matching jobs immediately
  python main.py --bot            # Launch interactive Telegram bot daemon (@Jobmailer3629bot)
  python main.py --watch          # Run continuous background job alert monitor
  python main.py --telegram-setup # Interactive Telegram pairing helper
  python main.py --test-telegram  # Send a test alert card to verify Telegram notifications
  python main.py --stats          # Print tracker metrics & application stats
  python main.py --mark-applied URL # Mark a job as applied
"""
import argparse
import html
import logging
import os
import sys
import time
from datetime import date, datetime, timezone

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import yaml

from mailer import send_email
from matcher import classify, eligible
from notifier import (
    create_job_buttons,
    format_alert,
    get_chat_id,
    get_telegram_updates,
    get_token,
    save_chat_id,
    send_telegram,
    setup_chat_id,
    telegram_enabled,
)
from sources import fetch_all
from tracker import Tracker
from writer import write_note

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("main")


def load_env():
    for p in [".env", os.path.join("job_agent", ".env")]:
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def load_cfg():
    load_env()
    for path in ["config.yaml", os.path.join("job_agent", "config.yaml")]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    raise FileNotFoundError("config.yaml not found")


def is_dry(cfg, live_flag: bool) -> bool:
    env_dry = os.getenv("DRY_RUN")
    dry = (env_dry.lower() != "false") if env_dry else cfg["run"].get("dry_run", True)
    return False if live_flag else dry


def build_digest(rows, cfg, dry: bool) -> str:
    parts = [f"<h2>Job digest {date.today()} {'(DRY RUN)' if dry else ''}</h2>"]
    for r in rows:
        j = r["job"]
        parts.append(
            f"<hr><h3>{html.escape(j.title)} - {html.escape(j.company)}</h3>"
            f"<p><b>Status:</b> {r['status']} | <b>CV:</b> {r['profile']} | <b>Score:</b> {r['score']} | "
            f"{html.escape(j.location)}<br><a href='{html.escape(j.url)}'>Apply link</a>"
            + (f" | contact: {html.escape(j.email)}" if j.email else "") + "</p>"
            f"<p><b>Subject:</b> {html.escape(r['subject'])}</p>"
            f"<pre style='white-space:pre-wrap;font-family:inherit'>{html.escape(r['body'])}</pre>"
        )
    if not rows:
        parts.append("<p>No new matching jobs today.</p>")
    return "\n".join(parts)


def collect(cfg, tr: Tracker, company_rule: bool):
    jobs = fetch_all(cfg)
    log.info("Fetched %d unique jobs", len(jobs))
    cands = []
    for j in jobs:
        if tr.seen_url(j.url):
            continue
        if company_rule and tr.recent_company(j.company, cfg["run"]["reapply_after_days"]):
            continue
        if eligible(j, cfg):
            continue
        m = classify(j, cfg)
        if m:
            cands.append((m[1], j, m[0]))
    cands.sort(key=lambda x: (-x[0], -(x[1].posted.timestamp() if x[1].posted else 0)))
    return cands


def alerts(live_flag: bool, limit: int = None):
    """Scan for new matching jobs and dispatch real-time alerts."""
    cfg = load_cfg()
    dry = is_dry(cfg, live_flag)
    tr = Tracker()
    max_alerts = limit or cfg["run"].get("max_alerts_per_run", 10)
    cands = collect(cfg, tr, company_rule=False)[:max_alerts]
    log.info("%d new matches found to alert", len(cands))

    sent_count = 0
    for score, j, prof in cands:
        profile_cfg = cfg["profiles"][prof]
        subject, body = write_note(j, profile_cfg, cfg)
        msg = format_alert(j, prof, score, subject, body)
        buttons = create_job_buttons(j.url)

        if dry:
            print("\n--- ALERT (dry run) ---\n" + msg + "\nURL: " + j.url)
            continue

        try:
            if telegram_enabled():
                send_telegram(msg, inline_keyboard=buttons)
            elif os.getenv("GMAIL_USER") and os.getenv("GMAIL_APP_PASSWORD"):
                send_email(
                    cfg["candidate"]["email"],
                    f"New Job Match: {j.title} - {j.company}",
                    f"{j.url}\nCV to use: {prof}\n\nSubject: {subject}\n\n{body}",
                    [profile_cfg["cv"]],
                    cfg,
                )
            else:
                log.warning("Neither Telegram nor Gmail credentials configured for live alert delivery.")
                print(msg)

            tr.add(j, prof, score, "alerted", body)
            sent_count += 1
        except Exception as e:
            log.warning("Alert failed for %s: %s", j.url, e)

    if not dry and sent_count > 0:
        tr.export_csv()
    log.info("Alert cycle completed. %d alerts dispatched.", sent_count)
    return sent_count


def test_telegram():
    load_env()
    token = get_token()
    chat_id = get_chat_id()

    print(f"Testing Telegram configuration...")
    print(f"Bot Token: {'Found (' + token[:12] + '...)' if token else '❌ Missing'}")
    print(f"Chat ID:   {chat_id if chat_id else '❌ Not set yet'}")

    if not chat_id:
        print("\nChat ID not found in .env. Attempting automatic detection from recent bot updates...")
        cid = setup_chat_id()
        if not cid:
            return

    test_msg = (
        "🚀 <b>Job Agent Notification Test</b>\n\n"
        "✅ Your Telegram notifications are <b>working properly</b>!\n"
        "• <b>Bot:</b> @Jobmailer3629bot\n"
        f"• <b>Time:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n\n"
        "You will receive real-time alerts whenever new Frontend or Cybersecurity jobs are discovered."
    )
    keyboard = [
        [
            {"text": "⚡ Check New Matches Now", "callback_data": "cmd:alerts"},
            {"text": "📊 View Stats", "callback_data": "cmd:stats"},
        ]
    ]

    ok = send_telegram(test_msg, inline_keyboard=keyboard)
    if ok:
        print("🎉 SUCCESS! Test notification sent to your Telegram phone app.")
    else:
        print("❌ Failed to send Telegram message. Please check token or verify you messaged @Jobmailer3629bot.")


def wait_and_setup_telegram(timeout_secs: int = 60):
    load_env()
    token = get_token()
    print("=" * 60)
    print("🤖 TELEGRAM AUTO-PAIRING SETUP")
    print("=" * 60)
    print(f"Bot: @Jobmailer3629bot")
    print(f"Direct Link: https://t.me/Jobmailer3629bot\n")
    print(f"👉 Please open Telegram, search @Jobmailer3629bot, and send '/start' or 'hi'")
    print(f"⏳ Listening for incoming message (waiting up to {timeout_secs} seconds)...")

    start_t = time.time()
    while time.time() - start_t < timeout_secs:
        updates = get_telegram_updates()
        for u in updates:
            msg = u.get("message") or u.get("callback_query", {}).get("message")
            if msg and "chat" in msg:
                chat = msg["chat"]
                cid = str(chat["id"])
                name = chat.get("first_name", "User")
                print(f"\n🎉 Message detected from: {name} (Chat ID: {cid})!")
                save_chat_id(cid)
                test_telegram()
                return cid
        time.sleep(2)
        remaining = int(timeout_secs - (time.time() - start_t))
        print(f"\rListening... {remaining}s remaining", end="", flush=True)

    print("\n\n⚠️ No message detected within time limit.")
    print("Make sure you searched @Jobmailer3629bot in Telegram and tapped 'Start', then run again.")


def watch_daemon(interval_mins: int = 60):
    print(f"🔄 Starting background Job Alert Monitor (running every {interval_mins} minutes)...")
    print("Press Ctrl+C to exit.\n")
    while True:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now_str}] 🔍 Running scheduled alert scan...")
            alerts(live_flag=True)
            print(f"[{now_str}] 💤 Sleeping for {interval_mins} minutes...")
            time.sleep(interval_mins * 60)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            log.warning("Watch loop error: %s", e)
            time.sleep(30)


def show_stats():
    tr = Tracker()
    stats = tr.get_stats()
    print("=" * 45)
    print("📊 JOB AGENT TRACKER STATISTICS")
    print("=" * 45)
    print(f"Total Applications Recorded: {stats.get('total', 0)}")
    print(f"  • Marked as Applied:       {stats.get('applied', 0)}")
    print(f"  • Alerts Dispatched:       {stats.get('alerted', 0)}")
    print(f"  • Auto-Emailed:            {stats.get('emailed', 0)}")
    print(f"  • Daily Digest Listed:     {stats.get('digest', 0)}")
    print("-" * 45)
    recent = tr.get_recent(5)
    if recent:
        print("Recent 5 opportunities:")
        for r in recent:
            print(f"  [{r['status'].upper():8}] {r['company']} - {r['title']} ({r['created'][:10]})")
    print("=" * 45)


def run(live_flag: bool):
    cfg = load_cfg()
    r = cfg["run"]
    dry = is_dry(cfg, live_flag)
    tr = Tracker()
    cands = collect(cfg, tr, company_rule=True)

    picked, companies = [], set()
    for score, j, prof in cands:
        key = j.company.lower().strip()
        if key in companies:
            continue
        companies.add(key)
        picked.append((score, j, prof))
        if len(picked) >= r.get("daily_limit", 15):
            break
    log.info("%d candidates evaluated, %d picked for digest", len(cands), len(picked))

    rows, emails_sent = [], 0
    for score, j, prof in picked:
        profile = cfg["profiles"][prof]
        subject, body = write_note(j, profile, cfg)
        status = "digest"
        cv_path = profile["cv"]
        cv_exists = os.path.exists(cv_path) or os.path.exists(os.path.join("job_agent", cv_path))

        if j.email and emails_sent < r.get("max_auto_emails", 5) and cv_exists:
            if dry:
                status = "would_email"
            else:
                try:
                    send_email(j.email, subject, body, [cv_path], cfg)
                    status, emails_sent = "emailed", emails_sent + 1
                except Exception as e:
                    log.warning("Email to %s failed: %s", j.email, e)

        rows.append(dict(job=j, profile=prof, score=score, status=status, subject=subject, body=body))
        if not dry:
            tr.add(j, prof, score, status, body)

    page = build_digest(rows, cfg, dry)
    os.makedirs("digests", exist_ok=True)
    path = f"digests/{date.today()}.html"
    open(path, "w", encoding="utf-8").write(page)
    log.info("Digest saved to %s", path)

    if not dry:
        tr.export_csv()
        todo = [x for x in rows if x["status"] == "digest"]
        cvs = sorted({cfg["profiles"][x["profile"]]["cv"] for x in todo})
        try:
            send_email(
                cfg["candidate"]["email"],
                f"Job digest {date.today()}: {len(todo)} to apply manually, {emails_sent} emailed",
                "Open this email in HTML view.",
                cvs,
                cfg,
                html_body=page,
            )
        except Exception as e:
            log.warning("Digest email failed: %s", e)
    else:
        print(f"\nDRY RUN: Digest created at {path}. Run with --live to send live.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Job Agent: Auto Matcher, Telegram Notifier & Application Assistant")
    ap.add_argument("--live", action="store_true", help="Execute live actions (send emails / alerts)")
    ap.add_argument("--mark-applied", metavar="URL", help="Mark a specific job URL as applied")
    ap.add_argument("--alerts", action="store_true", help="Scan for fresh matches and push notifications now")
    ap.add_argument("--bot", action="store_true", help="Run interactive Telegram Bot listener daemon")
    ap.add_argument("--watch", action="store_true", help="Run continuous background alert monitor")
    ap.add_argument("--interval", type=int, default=60, help="Watch interval in minutes (default 60)")
    ap.add_argument("--telegram-setup", action="store_true", help="Interactive Telegram Chat ID setup")
    ap.add_argument("--test-telegram", action="store_true", help="Send a test notification to your phone")
    ap.add_argument("--stats", action="store_true", help="Show application tracker statistics")
    
    a = ap.parse_args()

    if a.bot:
        import bot
        bot.main()
    elif a.watch:
        watch_daemon(a.interval)
    elif a.telegram_setup:
        wait_and_setup_telegram(timeout_secs=60)
    elif a.test_telegram:
        test_telegram()
    elif a.stats:
        show_stats()
    elif a.alerts:
        alerts(a.live)
    elif a.mark_applied:
        t = Tracker()
        t.mark_applied(a.mark_applied)
        t.export_csv()
        print("✅ Successfully marked as applied.")
    else:
        run(a.live)
