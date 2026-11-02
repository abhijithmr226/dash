"""Send email through Gmail SMTP using an App Password."""
import mimetypes, os, smtplib
from email.message import EmailMessage


def send_email(to, subject, body, attachments, cfg, html_body=None):
    user, pw = os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD")
    if not (user and pw):
        raise RuntimeError("Set GMAIL_USER and GMAIL_APP_PASSWORD")
    msg = EmailMessage()
    msg["From"] = f"{cfg['candidate']['name']} <{user}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    for path in attachments:
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        main, sub = ctype.split("/", 1)
        with open(path, "rb") as f:
            msg.add_attachment(f.read(), maintype=main, subtype=sub,
                               filename=f"{cfg['candidate']['name'].replace(' ', '_')}_CV.pdf")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.send_message(msg)
