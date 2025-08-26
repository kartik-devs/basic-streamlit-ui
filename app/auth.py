from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import re

import bcrypt
import yaml


CONFIG_PATH = Path("config.yaml")


def load_config() -> Dict:
    if not CONFIG_PATH.exists():
        return {"credentials": {"usernames": {}}}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"credentials": {"usernames": {}}}


def save_config(config: Dict) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)


def user_exists(config: Dict, username: str) -> bool:
    return username in config.get("credentials", {}).get("usernames", {})


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


ALLOWED_EMAIL_DOMAINS: List[str] = [
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
]


def is_allowed_email(email: str) -> bool:
    if not email:
        return False
    email = email.strip().lower()
    # Basic email format check
    if not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email):
        return False
    domain = email.split("@", 1)[-1]
    return domain in ALLOWED_EMAIL_DOMAINS


def register_user(username: str, name: str, email: str, password: str) -> None:
    # Enforce email-only usernames and whitelist domains
    if not is_allowed_email(email):
        raise ValueError("Email domain not allowed. Use a common provider like gmail.com or outlook.com.")

    config = load_config()
    credentials = config.setdefault("credentials", {}).setdefault("usernames", {})

    # Use chosen username as the key; store email separately
    credentials[username] = {
        "email": email,
        "name": name,
        "password": hash_password(password),
    }

    save_config(config)


