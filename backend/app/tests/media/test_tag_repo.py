from app.models import Tag
from app.repositories.tag_repo import TagRepo


def _seed_tag(db, name: str) -> Tag:
    tag = Tag(name=name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def test_get_all_tags_returns_seeded_rows(db):
    _seed_tag(db, "math")
    _seed_tag(db, "science")
    _seed_tag(db, "history")
    rows = TagRepo(db).get_all_tags()
    assert {t.name for t in rows} == {"math", "science", "history"}
    assert len(rows) == 3


def test_get_or_create_by_names_reuses_stored_case(db):
    _seed_tag(db, "Math")
    rows = TagRepo(db).get_or_create_by_names(["  MATH "])
    assert [t.name for t in rows] == ["Math"]


def test_get_or_create_by_names_creates_missing_lowercased(db):
    rows = TagRepo(db).get_or_create_by_names(["  Sci-Fi ", "MATH"])
    assert [t.name for t in rows] == ["sci-fi", "math"]


def test_get_or_create_by_names_collapses_duplicates_in_first_seen_order(db):
    _seed_tag(db, "math")
    rows = TagRepo(db).get_or_create_by_names(["MATH", "math", "  MATH  "])
    assert [t.name for t in rows] == ["math"]


def test_get_or_create_by_names_empty_returns_empty(db):
    assert TagRepo(db).get_or_create_by_names([]) == []


def test_get_or_create_by_names_skips_blank_names(db):
    rows = TagRepo(db).get_or_create_by_names(["  ", "math"])
    assert [t.name for t in rows] == ["math"]
