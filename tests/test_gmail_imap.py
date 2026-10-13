import json
from pathlib import Path

import pytest

from jobradar.sources import gmail_imap
from jobradar.sources.gmail_imap import GmailCredentials, fetch_new_messages, load_credentials


class FakeIMAPConnection:
    def __init__(self, messages: dict[bytes, bytes]):
        self.messages = messages
        self.selected: str | None = None
        self.logged_out = False

    def select(self, mailbox: str, readonly: bool = False):
        self.selected = mailbox
        return "OK", [b"1"]

    def uid(self, command: str, *args: object):
        if command == "search":
            uids = b" ".join(sorted(self.messages.keys()))
            return "OK", [uids]
        if command == "fetch":
            uid_bytes = args[0]
            raw = self.messages.get(uid_bytes)
            if raw is None:
                return "NO", [None]
            return "OK", [(uid_bytes, raw)]
        raise ValueError(f"unexpected uid command: {command}")

    def logout(self) -> None:
        self.logged_out = True


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


def test_fetch_new_messages_saves_eml_files(data_dir: Path) -> None:
    connection = FakeIMAPConnection(
        {b"1": b"Subject: Offer A\r\n\r\nBody A", b"2": b"Subject: Offer B\r\n\r\nBody B"}
    )

    saved = fetch_new_messages(connection, data_dir)

    assert connection.selected == f'"{gmail_imap.LABEL}"'
    assert {p.name for p in saved} == {"1.eml", "2.eml"}
    assert (data_dir / "raw" / "1.eml").read_bytes() == b"Subject: Offer A\r\n\r\nBody A"
    assert (data_dir / "raw" / "2.eml").read_bytes() == b"Subject: Offer B\r\n\r\nBody B"


def test_fetch_new_messages_tracks_seen_uids(data_dir: Path) -> None:
    connection = FakeIMAPConnection({b"1": b"Subject: Offer A\r\n\r\nBody A"})

    fetch_new_messages(connection, data_dir)

    seen_path = data_dir / "seen_uids.json"
    assert json.loads(seen_path.read_text()) == ["1"]


def test_fetch_new_messages_skips_already_seen_uids(data_dir: Path) -> None:
    connection = FakeIMAPConnection(
        {b"1": b"Subject: Offer A\r\n\r\nBody A", b"2": b"Subject: Offer B\r\n\r\nBody B"}
    )
    fetch_new_messages(connection, data_dir)

    second_connection = FakeIMAPConnection(
        {b"1": b"Subject: Offer A\r\n\r\nBody A", b"2": b"Subject: Offer B\r\n\r\nBody B"}
    )
    saved = fetch_new_messages(second_connection, data_dir)

    assert saved == []


def test_fetch_new_messages_only_saves_new_uid_on_second_run(data_dir: Path) -> None:
    connection = FakeIMAPConnection({b"1": b"Subject: Offer A\r\n\r\nBody A"})
    fetch_new_messages(connection, data_dir)

    connection_with_new_message = FakeIMAPConnection(
        {b"1": b"Subject: Offer A\r\n\r\nBody A", b"2": b"Subject: Offer B\r\n\r\nBody B"}
    )
    saved = fetch_new_messages(connection_with_new_message, data_dir)

    assert {p.name for p in saved} == {"2.eml"}


def test_fetch_new_messages_with_no_messages(data_dir: Path) -> None:
    connection = FakeIMAPConnection({})

    saved = fetch_new_messages(connection, data_dir)

    assert saved == []


def test_load_credentials_raises_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="GMAIL_USER"):
        load_credentials()


def test_load_credentials_reads_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GMAIL_USER", "someone@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")

    credentials = load_credentials()

    assert credentials == GmailCredentials(user="someone@gmail.com", app_password="app-password")
