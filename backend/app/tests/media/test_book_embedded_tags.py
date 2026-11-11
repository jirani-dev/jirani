from app.schemas.book_schema import MAX_TAGS_PER_BOOK
from app.schemas.tag_schema import TagCreate
from app.services.book_service import BookService


def _names(tags: list[TagCreate]) -> list[str]:
    return [tag.name for tag in tags]


def test_valid_subjects_are_appended_after_the_uploaders_tags() -> None:
    merged = BookService._with_embedded_tags(
        [TagCreate(name="math")], ["algebra", "Year 4"]
    )
    assert _names(merged) == ["math", "algebra", "Year 4"]


def test_subjects_that_are_not_valid_tag_names_are_skipped() -> None:
    merged = BookService._with_embedded_tags(
        [], ["Science & Technology", "Fiction / General", "x" * 51, "history"]
    )
    assert _names(merged) == ["history"]


def test_repeated_subjects_are_added_once() -> None:
    merged = BookService._with_embedded_tags(
        [TagCreate(name="Math")], ["math", "fiction", "Fiction", " fiction "]
    )
    assert _names(merged) == ["Math", "fiction"]


def test_subjects_never_push_a_book_past_the_tag_limit() -> None:
    own = [TagCreate(name=f"own{i}") for i in range(MAX_TAGS_PER_BOOK - 2)]
    merged = BookService._with_embedded_tags(own, [f"subject {i}" for i in range(10)])
    assert len(merged) == MAX_TAGS_PER_BOOK
    assert _names(merged)[-2:] == ["subject 0", "subject 1"]


def test_the_uploaders_list_is_not_mutated() -> None:
    own = [TagCreate(name="math")]
    BookService._with_embedded_tags(own, ["algebra"])
    assert _names(own) == ["math"]
