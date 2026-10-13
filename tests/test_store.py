from datetime import datetime
from pathlib import Path

import pytest

from jobradar.store import Offer, Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    with Store(tmp_path / "jobradar.db") as s:
        yield s


def make_offer(**overrides: object) -> Offer:
    defaults = {
        "source": "francetravail",
        "kind": "job",
        "title": "Data Scientist",
        "company_or_lab": "Acme Corp",
        "url": "https://example.com/offer/1",
    }
    defaults.update(overrides)
    return Offer(**defaults)


def test_add_and_get_offer(store: Store) -> None:
    offer_id = store.add_offer(make_offer())

    fetched = store.get_offer(offer_id)

    assert fetched is not None
    assert fetched.title == "Data Scientist"
    assert fetched.company_or_lab == "Acme Corp"
    assert fetched.url == "https://example.com/offer/1"


def test_get_offer_missing_returns_none(store: Store) -> None:
    assert store.get_offer(999) is None


def test_defaults_status_new_and_flags_empty(store: Store) -> None:
    offer_id = store.add_offer(make_offer())

    fetched = store.get_offer(offer_id)

    assert fetched.status == "new"
    assert fetched.flags == []


def test_flags_roundtrip(store: Store) -> None:
    offer_id = store.add_offer(make_offer(flags=["clearance", "senior"]))

    fetched = store.get_offer(offer_id)

    assert fetched.flags == ["clearance", "senior"]


def test_dedup_on_normalized_title_company_url(store: Store) -> None:
    first_id = store.add_offer(make_offer())
    duplicate_id = store.add_offer(
        make_offer(
            title="  Data Scientist  ",
            company_or_lab="ACME CORP",
            url="https://example.com/offer/1",
        )
    )

    assert first_id == duplicate_id
    assert len(store.list_offers()) == 1


def test_distinct_offers_are_not_deduped(store: Store) -> None:
    store.add_offer(make_offer())
    store.add_offer(make_offer(title="ML Engineer", url="https://example.com/offer/2"))

    assert len(store.list_offers()) == 2


def test_list_offers_returns_all_in_insertion_order(store: Store) -> None:
    store.add_offer(make_offer(title="First", url="https://example.com/offer/a"))
    store.add_offer(make_offer(title="Second", url="https://example.com/offer/b"))

    titles = [o.title for o in store.list_offers()]

    assert titles == ["First", "Second"]


def test_posted_at_and_fetched_at_roundtrip(store: Store) -> None:
    posted = datetime(2026, 1, 1, 10, 0, 0)
    fetched_at = datetime(2026, 1, 2, 9, 30, 0)
    offer_id = store.add_offer(make_offer(posted_at=posted, fetched_at=fetched_at))

    fetched = store.get_offer(offer_id)

    assert fetched.posted_at == posted
    assert fetched.fetched_at == fetched_at


def test_phd_kind_is_stored(store: Store) -> None:
    offer_id = store.add_offer(make_offer(kind="phd", company_or_lab="INRIA"))

    fetched = store.get_offer(offer_id)

    assert fetched.kind == "phd"
