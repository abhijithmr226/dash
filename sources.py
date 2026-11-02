"""Multi-Platform Job Fetcher:
Google Jobs, LinkedIn, Internshala, Freshersworld, Jobicy, RemoteOK, Himalayas, Remotive, Arbeitnow, Greenhouse & Lever.
"""
import html
import logging
import os
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Generator, List, Optional

import requests
from bs4 import BeautifulSoup

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

log = logging.getLogger("sources")
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BAD_EMAIL = ("noreply", "no-reply", "donotreply", "example.", "sentry", "privacy", "abuse@", "legal@")


@dataclass
class Job:
    source: str
    company: str
    title: str
    location: str
    url: str
    description: str
    posted: Optional[datetime] = None
    email: Optional[str] = None


def clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def find_email(text: str) -> Optional[str]:
    for m in EMAIL_RE.findall(text or ""):
        if not any(b in m.lower() for b in BAD_EMAIL):
            return m
    return None


def parse_dt(v) -> Optional[datetime]:
    if v is None or v == "":
        return None
    try:
        if isinstance(v, (int, float)):
            v = v / 1000 if v > 1e11 else v
            return datetime.fromtimestamp(v, tz=timezone.utc)
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _get(url, timeout=10, **kw):
    r = requests.get(url, headers=UA, timeout=timeout, **kw)
    r.raise_for_status()
    return r.json()


def _mk(source: str, company: str, title: str, location: str, url: str, desc: str, posted=None) -> Job:
    desc_clean = clean(desc)
    return Job(
        source=source,
        company=clean(company or "Company"),
        title=clean(title or "Job Title"),
        location=clean(location or "Remote / India"),
        url=url.strip(),
        description=desc_clean,
        posted=parse_dt(posted),
        email=find_email(desc_clean),
    )


# -------------------------------------------------------------
# 1. Google Jobs (via Playwright with anti-detection flags)
# -------------------------------------------------------------
def google_jobs(query: str, location: str = "") -> Generator[Job, None, None]:
    try:
        from playwright.sync_api import sync_playwright
        search_str = f"{query} {location}".strip()
        encoded = urllib.parse.quote(search_str)
        target_url = f"https://www.google.com/search?q={encoded}&ibp=htl;jobs"

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-gpu"],
            )
            page = browser.new_page(user_agent=UA["User-Agent"], viewport={"width": 1280, "height": 800})
            page.goto(target_url, timeout=20000)
            page.wait_for_timeout(3000)

            titles = page.locator("div.BjJfJf, div.tNxQIb").all()
            for t in titles[:10]:
                try:
                    parent = t.locator("xpath=..")
                    lines = [x.strip() for x in parent.inner_text().split("\n") if x.strip()]
                    if len(lines) >= 2:
                        job_title = lines[0]
                        company_name = lines[1]
                        loc_snippet = lines[2] if len(lines) > 2 else (location or "India")
                        q_str = f"{job_title} {company_name}"
                        job_url = f"https://www.google.com/search?q={urllib.parse.quote(q_str)}&ibp=htl;jobs"
                        yield _mk(
                            "google_jobs",
                            company_name,
                            job_title,
                            loc_snippet,
                            job_url,
                            f"{job_title} at {company_name}. Location details: {loc_snippet}. Via Google Jobs search.",
                        )
                except Exception:
                    continue
            browser.close()
    except Exception as e:
        log.warning("google_jobs query '%s %s' failed: %s", query, location, e)


# -------------------------------------------------------------
# 2. LinkedIn Jobs (via Public Guest API)
# -------------------------------------------------------------
def linkedin_jobs(query: str, location: str = "India") -> Generator[Job, None, None]:
    try:
        params = urllib.parse.urlencode({"keywords": query, "location": location, "start": 0})
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{params}"
        r = requests.get(url, headers=UA, timeout=12)
        if not r.ok:
            log.warning("linkedin returned status %d for '%s in %s'", r.status_code, query, location)
            return

        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("li"):
            title_el = card.find("h3", class_="base-search-card__title")
            comp_el = card.find("h4", class_="base-search-card__subtitle")
            loc_el = card.find("span", class_="job-search-card__location")
            link_el = card.find("a", class_="base-card__full-link")
            time_el = card.find("time")
            if not (title_el and link_el):
                continue
            title = title_el.text.strip()
            comp = comp_el.text.strip() if comp_el else "Unknown"
            loc = loc_el.text.strip() if loc_el else location
            job_url = link_el.get("href", "").split("?")[0]
            posted = time_el.get("datetime") if time_el else None
            desc = f"{title} at {comp}. Location: {loc}. Posted on LinkedIn."
            yield _mk("linkedin", comp, title, loc, job_url, desc, posted)
    except Exception as e:
        log.warning("linkedin query '%s in %s' failed: %s", query, location, e)


# -------------------------------------------------------------
# 3. Internshala (Dedicated #1 Fresher Jobs Portal in India)
# -------------------------------------------------------------
def internshala_jobs(category: str) -> Generator[Job, None, None]:
    try:
        url = f"https://internshala.com/jobs/{category}/"
        r = requests.get(url, headers=UA, timeout=12)
        if not r.ok:
            return
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.find_all("div", class_="individual_internship"):
            title_a = item.find("a", class_="job-title-href")
            if not title_a:
                continue
            title = title_a.text.strip()
            href = title_a.get("href", "")
            job_url = f"https://internshala.com{href}" if href.startswith("/") else href
            comp_p = item.find("p", class_="company-name")
            comp = comp_p.text.strip() if comp_p else "Company"
            loc_p = item.find("p", class_="row-1-item locations")
            loc = loc_p.text.strip() if loc_p else "India"
            desc = f"{title} role at {comp} in {loc}. Fresher opportunity on Internshala."
            yield _mk("internshala", comp, title, loc, job_url, desc)
    except Exception as e:
        log.warning("internshala '%s' failed: %s", category, e)


# -------------------------------------------------------------
# 4. Freshersworld (Top Indian Portal for Entry-Level & Freshers)
# -------------------------------------------------------------
def freshersworld_jobs(category: str) -> Generator[Job, None, None]:
    try:
        url = f"https://www.freshersworld.com/jobs/jobsearch/{category}"
        r = requests.get(url, headers=UA, timeout=12)
        if not r.ok:
            return
        soup = BeautifulSoup(r.text, "html.parser")
        for c in soup.find_all("div", class_="job-container"):
            title_el = c.find("span", class_="wrap-title") or c.find("a", class_="bold_font")
            comp_el = c.find("h3", class_="company-name") or c.find("span", class_="bold_font")
            loc_el = c.find("span", class_="job-location")
            link_el = c.find("a", href=True)
            if not (title_el and link_el):
                continue
            raw_title = title_el.text.strip()
            clean_title = re.sub(r"Jobs? Opening in.*", "", raw_title, flags=re.I).strip()
            clean_title = re.sub(r"Less$", "", clean_title).strip()
            comp = comp_el.text.strip() if comp_el else "Company"
            loc = loc_el.text.strip() if loc_el else "India"
            href = link_el.get("href", "")
            job_url = href if href.startswith("http") else f"https://www.freshersworld.com{href}"
            desc = f"{clean_title} opening at {comp} ({loc}). Published on Freshersworld."
            yield _mk("freshersworld", comp, clean_title, loc, job_url, desc)
    except Exception as e:
        log.warning("freshersworld '%s' failed: %s", category, e)


# -------------------------------------------------------------
# 5. Jobicy (Remote Jobs API)
# -------------------------------------------------------------
def jobicy(tag: str = "") -> Generator[Job, None, None]:
    try:
        params = {"count": 40}
        if tag:
            params["tag"] = tag
        d = _get("https://jobicy.com/api/v2/remote-jobs", params=params)
        for j in d.get("jobs", []):
            loc = "Remote - " + (j.get("jobGeo") or "Worldwide")
            yield _mk(
                "jobicy",
                j.get("companyName", "Unknown"),
                j.get("jobTitle", ""),
                loc,
                j.get("url", ""),
                j.get("jobDescription", "") or j.get("jobExcerpt", ""),
                j.get("pubDate"),
            )
    except Exception as e:
        log.warning("jobicy %s failed: %s", tag, e)


# -------------------------------------------------------------
# 6. Himalayas (Remote API)
# -------------------------------------------------------------
def himalayas() -> Generator[Job, None, None]:
    try:
        d = _get("https://himalayas.app/jobs/api?limit=40")
        for j in d.get("jobs", []):
            loc_list = j.get("locationRestrictions") or []
            loc = ("Remote - " + ", ".join(loc_list)) if loc_list else "Remote - Worldwide"
            yield _mk(
                "himalayas",
                j.get("companyName", "Unknown"),
                j.get("title", ""),
                loc,
                j.get("applicationLink") or f"https://himalayas.app/jobs/{j.get('guid', '')}",
                j.get("description", "") or j.get("excerpt", ""),
                j.get("pubDate"),
            )
    except Exception as e:
        log.warning("himalayas failed: %s", e)


# -------------------------------------------------------------
# 7. RemoteOK (Remote API)
# -------------------------------------------------------------
def remoteok(tag: str = "") -> Generator[Job, None, None]:
    try:
        url = f"https://remoteok.com/api?tag={tag}" if tag else "https://remoteok.com/api"
        d = _get(url)
        for j in d:
            if not isinstance(j, dict) or not j.get("position"):
                continue
            loc = "Remote - " + (j.get("location") or "Worldwide")
            yield _mk(
                "remoteok",
                j.get("company", "Unknown"),
                j.get("position", ""),
                loc,
                j.get("url", ""),
                j.get("description", ""),
                j.get("date"),
            )
    except Exception as e:
        log.warning("remoteok %s failed: %s", tag, e)


# -------------------------------------------------------------
# 8. Remotive
# -------------------------------------------------------------
def remotive(query: str) -> Generator[Job, None, None]:
    try:
        d = _get("https://remotive.com/api/remote-jobs", params={"search": query, "limit": 40})
        for j in d.get("jobs", []):
            yield _mk(
                "remotive",
                j.get("company_name", "Unknown"),
                j["title"],
                "Remote - " + (j.get("candidate_required_location") or "Worldwide"),
                j["url"],
                j.get("description", ""),
                j.get("publication_date"),
            )
    except Exception as e:
        log.warning("remotive %s failed: %s", query, e)


# -------------------------------------------------------------
# 9. Arbeitnow
# -------------------------------------------------------------
def arbeitnow() -> Generator[Job, None, None]:
    try:
        d = _get("https://www.arbeitnow.com/api/job-board-api")
        for j in d.get("data", []):
            loc = ("Remote - " if j.get("remote") else "") + (j.get("location") or "Worldwide")
            yield _mk(
                "arbeitnow",
                j.get("company_name", "Unknown"),
                j["title"],
                loc,
                j["url"],
                j.get("description", ""),
                j.get("created_at"),
            )
    except Exception as e:
        log.warning("arbeitnow failed: %s", e)


# -------------------------------------------------------------
# 10. Greenhouse & Lever
# -------------------------------------------------------------
def greenhouse(token: str) -> Generator[Job, None, None]:
    try:
        d = _get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", params={"content": "true"})
        for j in d.get("jobs", []):
            yield _mk(
                f"greenhouse:{token}",
                j.get("company_name") or token,
                j["title"],
                (j.get("location") or {}).get("name", ""),
                j["absolute_url"],
                j.get("content", ""),
                j.get("updated_at"),
            )
    except Exception as e:
        log.warning("greenhouse %s failed: %s", token, e)


def lever(slug: str) -> Generator[Job, None, None]:
    try:
        for j in _get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}):
            yield _mk(
                f"lever:{slug}",
                slug,
                j["text"],
                (j.get("categories") or {}).get("location", ""),
                j["hostedUrl"],
                j.get("descriptionPlain", "") or j.get("description", ""),
                j.get("createdAt"),
            )
    except Exception as e:
        log.warning("lever %s failed: %s", slug, e)


# -------------------------------------------------------------
# Master Collector
# -------------------------------------------------------------
def fetch_all(cfg) -> List[Job]:
    tasks = []

    # 1. LinkedIn Jobs
    for item in cfg.get("linkedin_queries", []):
        q = item.get("query", "")
        loc = item.get("location", "India")
        tasks.append(("linkedin", lambda arg: linkedin_jobs(arg[0], arg[1]), (q, loc)))

    # 2. Internshala
    for cat in cfg.get("internshala_categories", []):
        tasks.append(("internshala", internshala_jobs, cat))

    # 3. Freshersworld
    for cat in cfg.get("freshersworld_categories", []):
        tasks.append(("freshersworld", freshersworld_jobs, cat))

    # 4. Google Jobs
    for item in cfg.get("google_jobs_queries", []):
        q = item.get("query", "")
        loc = item.get("location", "")
        tasks.append(("google_jobs", lambda arg: google_jobs(arg[0], arg[1]), (q, loc)))

    # 5. Remote APIs
    for tag in cfg.get("jobicy_tags", ["frontend", "security", "react", "support"]):
        tasks.append(("jobicy", jobicy, tag))

    for tag in cfg.get("remoteok_tags", ["react", "security", "junior"]):
        tasks.append(("remoteok", remoteok, tag))

    for q in cfg.get("remotive_queries", ["frontend", "security analyst", "junior developer", "customer support"]):
        tasks.append(("remotive", remotive, q))

    tasks.append(("himalayas", lambda _: himalayas(), ""))
    tasks.append(("arbeitnow", lambda _: arbeitnow(), ""))

    # 6. Greenhouse & Lever
    for token in cfg.get("greenhouse", []):
        tasks.append(("greenhouse", greenhouse, token))
    for slug in cfg.get("lever", []):
        tasks.append(("lever", lever, slug))

    jobs, seen = [], set()
    for name, fn, arg in tasks:
        try:
            n = 0
            for j in fn(arg):
                norm_url = j.url.lower().rstrip("/")
                if norm_url not in seen:
                    seen.add(norm_url)
                    jobs.append(j)
                    n += 1
            if n > 0:
                log.info("%s (%s) -> %d jobs", name, arg, n)
        except Exception as e:
            log.warning("%s (%s) failed: %s", name, arg, e)
        time.sleep(0.15)

    log.info("Total unique jobs fetched across all sources: %d", len(jobs))
    return jobs
