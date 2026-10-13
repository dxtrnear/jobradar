from __future__ import annotations

import imaplib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

IMAP_HOST = "imap.gmail.com"
LABEL = "job-alerts"


@dataclass
class GmailCredentials:
    user: str
    app_password: str


def load_credentials() -> GmailCredentials:
    load_dotenv()
    user = os.environ.get("GMAIL_USER")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not app_password:
        raise RuntimeError("GMAIL_USER and GMAIL_APP_PASSWORD must be set in .env")
    return GmailCredentials(user=user, app_password=app_password)


def connect(credentials: GmailCredentials) -> imaplib.IMAP4_SSL:
    connection = imaplib.IMAP4_SSL(IMAP_HOST)
    connection.login(credentials.user, credentials.app_password)
    return connection


def _seen_uids_path(data_dir: Path) -> Path:
    return data_dir / "seen_uids.json"


def _load_seen_uids(data_dir: Path) -> set[str]:
    path = _seen_uids_path(data_dir)
    if not path.exists():
        return set()
    return set(json.loads(path.read_text()))


def _save_seen_uids(data_dir: Path, uids: set[str]) -> None:
    _seen_uids_path(data_dir).write_text(json.dumps(sorted(uids)))


def fetch_new_messages(connection: imaplib.IMAP4_SSL, data_dir: Path) -> list[Path]:
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    seen_uids = _load_seen_uids(data_dir)

    status, _ = connection.select(f'"{LABEL}"', readonly=True)
    if status != "OK":
        raise RuntimeError(f"could not select Gmail label {LABEL!r}")

    status, data = connection.uid("search", None, "ALL")
    if status != "OK":
        raise RuntimeError("IMAP UID search failed")
    all_uids = data[0].split() if data and data[0] else []

    saved_paths: list[Path] = []
    new_seen = set(seen_uids)
    for uid_bytes in all_uids:
        uid = uid_bytes.decode()
        if uid in seen_uids:
            continue
        status, msg_data = connection.uid("fetch", uid_bytes, "(RFC822)")
        if status != "OK" or not msg_data or msg_data[0] is None:
            continue
        raw_bytes = msg_data[0][1]
        eml_path = raw_dir / f"{uid}.eml"
        eml_path.write_bytes(raw_bytes)
        saved_paths.append(eml_path)
        new_seen.add(uid)

    _save_seen_uids(data_dir, new_seen)
    return saved_paths


def fetch_new_messages_from_env(data_dir: Path = Path("data")) -> list[Path]:
    data_dir.mkdir(parents=True, exist_ok=True)
    credentials = load_credentials()
    connection = connect(credentials)
    try:
        return fetch_new_messages(connection, data_dir)
    finally:
        connection.logout()


if __name__ == "__main__":
    saved = fetch_new_messages_from_env()
    print(f"Connected and selected {LABEL!r}. Saved {len(saved)} new message(s):")
    for path in saved:
        print(f"  {path}")
