"""SQLite tracker so nothing is applied to twice, with stats and export features."""
import csv
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

log = logging.getLogger("tracker")


class Tracker:
    def __init__(self, path="data/applications.db"):
        # Resolve path relative to current or job_agent directory
        if not os.path.isabs(path):
            if not os.path.exists("data") and os.path.exists("job_agent/data"):
                path = os.path.join("job_agent", path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS applications(
            url TEXT PRIMARY KEY, company TEXT, title TEXT, profile TEXT, score INT,
            status TEXT, email TEXT, note TEXT, created TEXT)""")
        self.db.commit()

    def seen_url(self, url: str) -> bool:
        cur = self.db.execute("SELECT 1 FROM applications WHERE url=?", (url,))
        return cur.fetchone() is not None

    def recent_company(self, company: str, days: int) -> bool:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cur = self.db.execute(
            "SELECT 1 FROM applications WHERE lower(company)=? AND created>=?",
            (company.lower().strip(), since),
        )
        return cur.fetchone() is not None

    def add(self, job, profile: str, score: int, status: str, note: str):
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "INSERT OR REPLACE INTO applications (url, company, title, profile, score, status, email, note, created) VALUES (?,?,?,?,?,?,?,?,?)",
            (job.url, job.company, job.title, profile, score, status, job.email, note, now),
        )
        self.db.commit()

    def mark_applied(self, url: str):
        self.db.execute("UPDATE applications SET status='applied' WHERE url=?", (url,))
        self.db.commit()

    def get_stats(self) -> Dict[str, int]:
        total = self.db.execute("SELECT count(*) FROM applications").fetchone()[0]
        applied = self.db.execute("SELECT count(*) FROM applications WHERE status='applied'").fetchone()[0]
        alerted = self.db.execute("SELECT count(*) FROM applications WHERE status='alerted'").fetchone()[0]
        emailed = self.db.execute("SELECT count(*) FROM applications WHERE status='emailed'").fetchone()[0]
        digest = self.db.execute("SELECT count(*) FROM applications WHERE status='digest'").fetchone()[0]
        return {
            "total": total,
            "applied": applied,
            "alerted": alerted,
            "emailed": emailed,
            "digest": digest,
        }

    def get_recent(self, limit: int = 10) -> List[dict]:
        rows = self.db.execute(
            "SELECT created, company, title, profile, score, status, url, email FROM applications ORDER BY created DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def export_csv(self, path="data/applications.csv"):
        if not os.path.isabs(path):
            if not os.path.exists("data") and os.path.exists("job_agent/data"):
                path = os.path.join("job_agent", path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        rows = self.db.execute(
            "SELECT created, company, title, profile, score, status, url, email FROM applications ORDER BY created DESC"
        ).fetchall()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["date", "company", "title", "cv", "score", "status", "url", "email"])
            for r in rows:
                w.writerow([r["created"], r["company"], r["title"], r["profile"], r["score"], r["status"], r["url"], r["email"]])
