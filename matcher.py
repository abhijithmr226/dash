"""Decide whether a job is suitable, strictly in India (or remote within India), and which CV profile fits it."""
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:to|-|–)?\s*(?:\d{1,2})?\s*\+?\s*years?[^.]{0,50}experience", re.I)
YEARS_RE2 = re.compile(r"experience[^.]{0,40}?(\d{1,2})\s*\+?\s*years?", re.I)

FRESHER_KEYWORDS = [
    "fresher", "freshers", "intern", "internship", "junior", "jr.", "jr ",
    "entry level", "entry-level", "graduate", "trainee", "associate", "0-1 year", "0-2 year"
]

# Strict list of foreign countries and regions - any mention without explicit India will be rejected
FOREIGN_LOCATIONS = [
    "united states", "usa", " u.s.", " u.s ", "us only", "us remote", "us - remote", "us-based",
    "canada", "mexico", "united kingdom", " uk ", "uk only", "london", "germany", "berlin",
    "france", "paris", "australia", "sydney", "melbourne", "brazil", "latam", "latin america",
    "emea", "europe", "poland", "spain", "madrid", "barcelona", "netherlands", "amsterdam",
    "ireland", "dublin", "israel", "tel aviv", "philippines", "manila", "japan", "tokyo",
    "singapore", "new zealand", "south africa", "colombia", "argentina", "chile", "sweden",
    "switzerland", "italy", "rome", "milan", "austria", "belgium", "denmark", "norway",
    "finland", "portugal", "czech", "romania", "hungary", "costa rica", "pakistan", "bangladesh"
]

INDIAN_LOCATIONS = [
    "india", "kerala", "kochi", "cochin", "trivandrum", "thiruvananthapuram", "calicut", "kozhikode",
    "thrissur", "kottayam", "kannur", "kollam", "palakkad", "malappuram", "alappuzha",
    "bangalore", "bengaluru", "karnataka", "mysore", "hubli", "mangalore",
    "chennai", "tamil nadu", "coimbatore", "madurai", "salem", "trichy",
    "hyderabad", "secunderabad", "telangana", "visakhapatnam", "vijayawada", "andhra",
    "mumbai", "navi mumbai", "thane", "pune", "nagpur", "nashik", "maharashtra",
    "delhi", "new delhi", "noida", "greater noida", "gurgaon", "gurugram", "ghaziabad", "faridabad", "ncr",
    "kolkata", "west bengal", "ahmedabad", "surat", "vadodara", "gujarat",
    "jaipur", "rajasthan", "indore", "bhopal", "madhya pradesh", "chandigarh", "mohali", "punjab",
    "bhubaneswar", "odisha", "lucknow", "kanpur", "uttar pradesh", "dehradun"
]


def _is_indian_location(loc_text: str, desc_text: str) -> Tuple[bool, str]:
    """Strictly verify if a job is in India (or Remote within India)."""
    full_loc = f" {loc_text.lower()} "
    desc_start = desc_text[:400].lower()

    # 1. Reject any foreign country/region
    for f_loc in FOREIGN_LOCATIONS:
        if f_loc in full_loc:
            # If foreign region is explicitly mentioned in location, reject
            return False, f"outside India ({f_loc.strip()})"

    # 2. Check if an Indian city or state or 'India' is mentioned in the location string
    for ind in INDIAN_LOCATIONS:
        if ind in full_loc:
            return True, "Indian location"

    # 3. If location says 'Remote' or 'Anywhere', it MUST explicitly specify India in location or description
    if any(r in full_loc for r in ["remote", "work from home", "wfh", "anywhere", "pan-india", "pan india"]):
        if any(ind in full_loc or ind in desc_start for ind in INDIAN_LOCATIONS):
            return True, "Remote in India"
        return False, "generic remote without India specification"

    return False, "location not in India"


def eligible(job, cfg) -> Optional[str]:
    """Return None if eligible, else a reason string for rejection."""
    run = cfg["run"]
    title = job.title.lower()

    # 1. Reject strict seniority in title (Senior, Lead, Staff, Principal, Director, VP)
    for w in cfg.get("reject_title_words", []):
        pattern = rf"(?<![a-z]){re.escape(w.strip().lower())}(?![a-z])"
        if re.search(pattern, title):
            return f"seniority in title ({w})"

    # 2. Strict India-only location check
    is_india, loc_reason = _is_indian_location(job.location, job.description)
    if not is_india:
        return loc_reason

    # 3. Check posting freshness
    if job.posted:
        age_days = (datetime.now(timezone.utc) - job.posted).days
        if age_days > run.get("max_age_days", 25):
            return f"too old ({age_days} days)"

    # 4. Check years of experience required
    is_explicit_fresher = any(fk in title or fk in job.description[:500].lower() for fk in FRESHER_KEYWORDS)
    if not is_explicit_fresher:
        years = [int(x) for x in YEARS_RE.findall(job.description) + YEARS_RE2.findall(job.description)]
        if years and min(years) > run.get("max_years_required", 2):
            return f"needs {min(years)}+ years experience"

    return None


def classify(job, cfg) -> Optional[Tuple[str, int]]:
    """Return (profile_name, score) for the best profile, or None."""
    best = None
    desc_lower = job.description.lower()
    title_lower = job.title.lower()

    for name, p in cfg.get("profiles", {}).items():
        title_hit = any(k.lower() in title_lower for k in p.get("title_keywords", []))
        if not title_hit:
            continue

        # Count matched skills in description
        skills_matched = sum(1 for k in p.get("skill_keywords", []) if k.lower() in desc_lower)
        score = 5 + min(skills_matched, 5)

        # Boost score if explicit fresher/junior/entry/intern
        if any(fk in title_lower for fk in ["intern", "junior", "jr.", "fresher", "graduate", "trainee", "entry", "associate"]):
            score += 2
        if any(fk in desc_lower for fk in ["fresher", "entry-level", "0-1 year", "0-2 year", "new grad", "campus", "walk-in"]):
            score += 1

        if best is None or score > best[1]:
            best = (name, score)

    min_score = cfg.get("run", {}).get("min_score", 5)
    if best and best[1] >= min_score:
        return best
    return None
