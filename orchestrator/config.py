import os
from dotenv import load_dotenv

load_dotenv()

IMAP_CONFIG = {
    "imap_host": os.getenv("IMAP_HOST", "imap.gmail.com"),
    "username": os.getenv("EMAIL_USER"),
    "password": os.getenv("EMAIL_PASS"),
}

SMTP_CONFIG = {
    "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", 465)),
    "username": os.getenv("EMAIL_USER"),
    "password": os.getenv("EMAIL_PASS"),
}

ATTACHMENT_BUCKET = os.getenv("ATTACHMENT_BUCKET")

if not IMAP_CONFIG["username"] or not IMAP_CONFIG["password"]:
    raise ValueError("IMAP username or password not set in environment variables")

if not ATTACHMENT_BUCKET:
    raise ValueError("ATTACHMENT_BUCKET not set in environment variables")
