from datetime import date

import pytest

from idion.errors import FormatError
from idion.frontmatter import Document, dump, load, parse, save

CONTEXT = """\
---
description: 'My team: members, "rituals" # not a comment'   # summary
owner: me
since: 2026-10-15
tags:
  - team
  - area=data
custom_field: {keep: me}
---

# My team

Body with odd   spacing	and tabs.

---

```yaml
---
not: frontmatter
---
```
"""


def test_noop_round_trip_is_identical():
    assert dump(parse(CONTEXT)) == CONTEXT


def test_body_is_everything_after_the_closing_delimiter():
    doc = parse(CONTEXT)
    assert doc.body.startswith("\n# My team\n")
    assert doc.body.endswith("---\n```\n")


def test_values_are_parsed():
    meta = parse(CONTEXT).meta
    assert meta["description"] == 'My team: members, "rituals" # not a comment'
    assert meta["since"] == date(2026, 10, 15)
    assert meta["tags"] == ["team", "area=data"]
    assert meta["custom_field"] == {"keep": "me"}


def test_changing_one_key_changes_only_that_line():
    doc = parse(CONTEXT)
    doc.meta["owner"] = "someone else"
    assert dump(doc) == CONTEXT.replace("owner: me", "owner: someone else")


def test_changing_the_description_keeps_the_rest():
    doc = parse(CONTEXT)
    doc.meta["description"] = "New summary."
    reparsed = parse(dump(doc))
    assert reparsed.meta["description"] == "New summary."
    assert dump(doc).splitlines()[2:] == CONTEXT.splitlines()[2:]


def test_loaded_null_round_trips():
    text = "---\ndescription: null\nother: null\n---\n"
    assert dump(parse(text)) == text


def test_strings_needing_quotes_stay_valid():
    doc = parse("---\ndescription: x\n---\n")
    doc.meta["description"] = "a: b # c"
    doc.meta["other"] = "2026-10-02"
    reparsed = parse(dump(doc))
    assert reparsed.meta["description"] == "a: b # c"
    assert reparsed.meta["other"] == "2026-10-02"


def test_long_values_are_not_folded():
    doc = parse("---\ndescription: a\n---\n")
    description = " ".join(["word"] * 60)
    doc.meta["description"] = description
    assert f"description: {description}\n" in dump(doc)


def test_crlf_round_trip():
    text = "---\r\ndescription: A\r\nother: b\r\n---\r\n\r\n# A\r\n"
    doc = parse(text)
    assert doc.meta["description"] == "A"
    assert doc.body == "\r\n# A\r\n"
    assert dump(doc) == text


def test_empty_body_and_missing_trailing_newline():
    assert parse("---\ndescription: a\n---\n").body == ""
    assert parse("---\ndescription: a\n---").body == ""


@pytest.mark.parametrize(
    "text",
    [
        "",
        "# no frontmatter\n",
        "\n---\ndescription: a\n---\n",
        "---\ndescription: a\n",
        "---\ndescription: [unclosed\n---\n",
        "---\n- a list\n---\n",
        "---\n---\n",
        "---\njust a string\n---\n",
    ],
)
def test_unparseable_frontmatter_raises_format_error(text):
    with pytest.raises(FormatError):
        parse(text)


def test_load_and_save(tmp_path):
    path = tmp_path / "my-team.md"
    path.write_text(CONTEXT, encoding="utf-8")
    doc = load(path)
    doc.meta["owner"] = "you"
    save(path, doc)
    assert path.read_text(encoding="utf-8") == CONTEXT.replace("owner: me", "owner: you")


def test_load_reports_the_path(tmp_path):
    path = tmp_path / "user.md"
    path.write_text("nothing here")
    with pytest.raises(FormatError, match=str(path)):
        load(path)


def test_load_reports_invalid_utf8(tmp_path):
    path = tmp_path / "user.md"
    path.write_bytes(b"---\ndescription: \xff\n---\n")
    with pytest.raises(FormatError, match="not valid UTF-8"):
        load(path)


def test_document_from_scratch():
    doc = Document.new({"description": "The user."}, "\n# User\n")
    assert dump(doc) == "---\ndescription: The user.\n---\n\n# User\n"


def test_shared_values_are_not_written_as_aliases():
    tags = ["a"]
    doc = Document.new({"description": "x", "x": tags, "y": tags}, "")
    out = dump(doc)
    assert "&" not in out and "*" not in out
