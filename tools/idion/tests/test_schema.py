import pytest

from idion.errors import IdionError
from idion.schema import DESCRIPTION_MAX_LENGTH, description_problems, validate_description


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("The user: role and preferences.", "The user: role and preferences."),
        ("  padded  ", "padded"),
        ("Équipe données — ñ", "Équipe données — ñ"),
        ("x" * DESCRIPTION_MAX_LENGTH, "x" * DESCRIPTION_MAX_LENGTH),
        ("  " + "x" * DESCRIPTION_MAX_LENGTH + "  ", "x" * DESCRIPTION_MAX_LENGTH),
    ],
)
def test_valid_descriptions_are_accepted_and_stripped(value, expected):
    assert validate_description(value) == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (None, "must be text"),
        (42, "must be text"),
        ("", "empty"),
        ("   ", "empty"),
        ("two\nlines", "single line"),
        ("two\rlines", "single line"),
        ("a\tb", "single line"),
        ("a\0b", "single line"),
        ("x" * (DESCRIPTION_MAX_LENGTH + 1), "at most 200"),
    ],
)
def test_invalid_descriptions_are_rejected(value, message):
    with pytest.raises(IdionError, match=message):
        validate_description(value)


def test_valid_frontmatter_has_no_problems():
    assert description_problems({"description": "The user.", "unknown": [1, 2]}) == []


@pytest.mark.parametrize(
    ("meta", "message"),
    [
        ({}, "missing"),
        ({"other": "x"}, "missing"),
        ({"description": None}, "must be text"),
        ({"description": 42}, "must be text"),
        ({"description": ""}, "empty"),
        ({"description": "a\nb"}, "single line"),
        ({"description": "x" * 201}, "at most 200"),
    ],
)
def test_frontmatter_problems_are_reported(meta, message):
    problems = description_problems(meta)
    assert len(problems) == 1
    assert message in problems[0]
