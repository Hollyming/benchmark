from __future__ import annotations

import re
from typing import List


EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d[\d -]{7,}\d)\b")
SECRET_RE = re.compile(r"\b(?:sk-[A-Za-z0-9]{16,}|AKIA[A-Z0-9]{16})\b")


def privacy_tags(text: str) -> List[str]:
    tags: List[str] = []
    if EMAIL_RE.search(text):
        tags.append("email")
    if PHONE_RE.search(text):
        tags.append("phone")
    if SECRET_RE.search(text):
        tags.append("secret_like")
    return tags


def redact(text: str) -> str:
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    return SECRET_RE.sub("[REDACTED_SECRET]", text)

