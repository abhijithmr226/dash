"""Write a concise, tailored application note with Gemini / Claude / OpenAI or smart dynamic template."""
import html
import logging
import os
import re

log = logging.getLogger("writer")


def load_env():
    for p in [".env", os.path.join("job_agent", ".env")]:
        if os.path.exists(p):
            try:
                for line in open(p, encoding="utf-8"):
                    if "=" in line and not line.startswith("#"):
                        k, v = line.strip().split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"\''))
            except Exception:
                pass


load_env()

SYSTEM = (
    "You write short, compelling job application notes for a fresher candidate. Use ONLY the facts provided; "
    "never invent employers, years of experience, or fake metrics. Keep to 80-110 words, professional, direct, "
    "no buzzwords, no clichés like 'I am writing to express my interest'. Mention the specific role and company, "
    "then highlight 1-2 exact relevant projects or skills matching the job. End with an invitation to review the CV "
    "and a clean sign-off with candidate contact details. Output format:\n"
    "SUBJECT: Application: <Role> - <Candidate Name>\n\n<Body>"
)


def _smart_fallback(job, profile, cfg):
    """Dynamically construct a sharp, tailored fresher note using the best matching facts."""
    c = cfg["candidate"]
    facts = profile.get("facts", [])
    desc_lower = job.description.lower()
    title_lower = job.title.lower()

    is_support = any(
        k in title_lower or k in desc_lower
        for k in ["customer", "support", "care", "service", "bpo", "voice", "chat", "helpdesk", "telecalling"]
    )

    if is_support:
        subject = f"Application: {job.title} - {c['name']}"
        body = (
            f"Dear Hiring Team,\n\n"
            f"I am applying for the {job.title} position at {job.company}. As a proactive Computer Science "
            f"graduate (Class of 2026) with strong communication and problem-solving skills, I am excited about "
            f"the opportunity to assist your customers and deliver high-quality support.\n\n"
            f"Key strengths I offer:\n"
            f"• Clear, empathetic communication in English, Malayalam, and Hindi across voice, email, and chat.\n"
            f"• Strong technical troubleshooting aptitude to quickly learn your product, CRM tools, and ticketing workflows.\n"
            f"• Customer-first dedication with hands-on adaptability in fast-paced operational environments.\n\n"
            f"My resume is attached for your review. I would appreciate the chance to discuss how I can contribute to {job.company}.\n\n"
            f"Best regards,\n"
            f"{c['name']}\n"
            f"{c['phone']} | {c['email']}\n"
            f"{c['links']}"
        )
        return subject, body

    chosen_facts = []
    for f in facts:
        if any(w in desc_lower for w in ["webrtc", "socket", "real-time", "chat"]) and "omeagle" in f.lower():
            chosen_facts.append(f)
        elif any(w in desc_lower for w in ["react", "frontend", "tailwind", "ui", "javascript"]) and "react" in f.lower():
            chosen_facts.append(f)
        elif any(w in desc_lower for w in ["tool", "utility", "productivity"]) and "krynn" in f.lower():
            chosen_facts.append(f)
        elif any(w in desc_lower for w in ["recon", "vulnerability", "pentest", "security"]) and "reconx" in f.lower():
            chosen_facts.append(f)
        elif any(w in desc_lower for w in ["siem", "splunk", "soc", "log", "incident"]) and "rednox" in f.lower():
            chosen_facts.append(f)
        elif any(w in desc_lower for w in ["nmap", "network", "scan"]) and "nmap" in f.lower():
            chosen_facts.append(f)

    if not chosen_facts:
        chosen_facts = [facts[1] if len(facts) > 1 else facts[0]]
    if len(chosen_facts) < 2 and len(facts) > 2:
        for f in facts:
            if f not in chosen_facts:
                chosen_facts.append(f)
                break

    project_highlight = chosen_facts[0]

    subject = f"Application: {job.title} - {c['name']}"
    body = (
        f"Dear Hiring Team,\n\n"
        f"I am applying for the {job.title} role at {job.company}. As a Computer Science with Cyber Security "
        f"graduate (Class of 2026), my practical background aligns well with your requirements.\n\n"
        f"Relevant highlights:\n"
        f"• {project_highlight}\n"
    )
    if len(chosen_facts) > 1:
        body += f"• {chosen_facts[1]}\n"

    body += (
        f"\nMy CV is attached. I would appreciate the opportunity to contribute to {job.company} and look forward to discussing the role.\n\n"
        f"Best regards,\n"
        f"{c['name']}\n"
        f"{c['phone']} | {c['email']}\n"
        f"{c['links']}"
    )
    return subject, body


def write_note(job, profile, cfg):
    load_env()

    # 1. Try Google Gemini API
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            c = cfg["candidate"]
            prompt = (
                f"{SYSTEM}\n\nCandidate: {c['name']}, Phone: {c['phone']}, Email: {c['email']}, Links: {c['links']}\n"
                "Facts:\n- " + "\n- ".join(profile.get("facts", [])) +
                f"\n\nJob: {job.title} at {job.company} ({job.location})\n"
                f"Description:\n{job.description[:2500]}"
            )
            # Try gemini-2.5-flash then fallback
            for model_name in ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"]:
                try:
                    model = genai.GenerativeModel(model_name)
                    resp = model.generate_content(prompt)
                    text = resp.text.strip()
                    if text.upper().startswith("SUBJECT:"):
                        first, _, rest = text.partition("\n")
                        return first.split(":", 1)[1].strip(), rest.strip()
                    return f"Application: {job.title} - {c['name']}", text
                except Exception:
                    continue
        except Exception as e:
            log.warning("Gemini note generation failed: %s; falling back", e)

    # 2. Try Anthropic Claude
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            c = cfg["candidate"]
            prompt = (
                f"Candidate: {c['name']}, {c['phone']}, {c['email']}, {c['links']}\n"
                "Facts:\n- " + "\n- ".join(profile.get("facts", [])) +
                f"\n\nJob: {job.title} at {job.company} ({job.location})\n"
                f"Description:\n{job.description[:2500]}"
            )
            msg = anthropic.Anthropic().messages.create(
                model=cfg["run"].get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=400,
                system=SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()
            if text.upper().startswith("SUBJECT:"):
                first, _, rest = text.partition("\n")
                return first.split(":", 1)[1].strip(), rest.strip()
            return f"Application: {job.title} - {c['name']}", text
        except Exception as e:
            log.warning("Anthropic note generation failed: %s; falling back", e)

    # 3. Smart Dynamic Fallback
    return _smart_fallback(job, profile, cfg)
