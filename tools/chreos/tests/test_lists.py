import pytest

from chreos.errors import ChreosError
from chreos.lists import (
    Item,
    ListKind,
    append_items,
    read_items,
    replace_items,
    set_checked,
    validate_items,
)
from chreos.sections import TASK_SECTIONS, read_section

TEMPLATE = "\n# T\n\n## Description\n\n## Acceptance criteria\n\n## References\n\n## Notes\n\n"

AC = """\
## Acceptance criteria

Intro prose.

- [x] done one
- [ ] open one
- [X] upper checked
-  [ ] not an item
- plain bullet

```
- [ ] fenced
```

Outro.

## Notes
- n1
some prose
- n2"""

CHECK, BULLETS = ListKind.CHECKLIST, ListKind.BULLETS


def append(body, heading, kind, values):
    return append_items(body, heading, kind, values, TASK_SECTIONS)


def replace(body, heading, kind, values):
    return replace_items(body, heading, kind, values, TASK_SECTIONS)


class TestRead:
    def test_checklist_items(self):
        assert read_items(AC, "Acceptance criteria", CHECK) == [
            Item("done one", True),
            Item("open one", False),
            Item("upper checked", True),
        ]

    def test_bullet_items(self):
        assert read_items(AC, "Notes", BULLETS) == [Item("n1"), Item("n2")]

    def test_empty_and_missing_sections(self):
        assert read_items(TEMPLATE, "Notes", BULLETS) == []
        assert read_items("# T\n", "Notes", BULLETS) == []


class TestAppend:
    def test_into_empty_template_section(self):
        result = append(TEMPLATE, "Acceptance criteria", CHECK, ["a", "b"])
        assert result == TEMPLATE.replace(
            "## Acceptance criteria\n\n", "## Acceptance criteria\n\n- [ ] a\n- [ ] b\n\n"
        )

    def test_after_last_item_keeping_prose(self):
        result = append(AC, "Acceptance criteria", CHECK, ["new"])
        assert "- [X] upper checked\n- [ ] new\n-  [ ] not an item" in result
        assert result.replace("- [ ] new\n", "", 1) == AC

    def test_after_last_item_at_end_without_newline(self):
        result = append(AC, "Notes", BULLETS, ["n3"])
        assert result == AC + "\n- n3\n"

    def test_section_with_only_prose(self):
        body = "## Notes\n\nJust prose.\n"
        assert append(body, "Notes", BULLETS, ["n"]) == "## Notes\n\nJust prose.\n\n- n\n"

    def test_missing_section_is_created(self):
        result = append("# T\n", "Notes", BULLETS, ["n"])
        assert result == "# T\n\n## Notes\n\n- n\n"

    def test_crlf(self):
        body = "## Notes\r\n\r\n- a\r\n"
        assert append(body, "Notes", BULLETS, ["b"]) == "## Notes\r\n\r\n- a\r\n- b\r\n"


class TestReplace:
    def test_replaces_all_items_unchecked_at_first_item_position(self):
        result = replace(AC, "Acceptance criteria", CHECK, ["x", "y"])
        expected = AC.replace(
            "- [x] done one\n- [ ] open one\n- [X] upper checked\n",
            "- [ ] x\n- [ ] y\n",
        )
        assert result == expected

    def test_bullets_with_interleaved_prose(self):
        result = replace(AC, "Notes", BULLETS, ["only"])
        assert result.endswith("## Notes\n- only\nsome prose\n")

    def test_without_existing_items_behaves_like_append(self):
        assert replace(TEMPLATE, "Notes", BULLETS, ["n"]) == append(TEMPLATE, "Notes", BULLETS, ["n"])

    def test_other_sections_untouched(self):
        result = replace(AC, "Notes", BULLETS, ["only"])
        assert read_section(result, "Acceptance criteria") == read_section(AC, "Acceptance criteria")


class TestValidate:
    def test_strips_and_returns(self):
        assert validate_items([" a ", "b"]) == ["a", "b"]

    def test_requires_at_least_one(self):
        with pytest.raises(ChreosError, match="at least one"):
            validate_items([])

    @pytest.mark.parametrize("value", ["", "   ", "a\nb", "a\rb"])
    def test_rejects_empty_and_multiline(self, value):
        with pytest.raises(ChreosError, match="single line"):
            validate_items([value])

    def test_append_and_replace_validate(self):
        with pytest.raises(ChreosError):
            append(TEMPLATE, "Notes", BULLETS, ["a\nb"])
        with pytest.raises(ChreosError):
            replace(TEMPLATE, "Notes", BULLETS, [])


class TestMapItems:
    BODY = "## References\n\nIntro.\n\n- [x](y)\n- task:a\n- keep\r\n- task:b\n\n## Notes\n- task:a\n"

    def test_replaces_and_drops_only_section_items(self):
        from chreos.lists import map_items

        def fn(text):
            return {"task:a": "task:p/a", "task:b": None}.get(text, text)

        result = map_items(self.BODY, "References", BULLETS, fn)
        assert result == "## References\n\nIntro.\n\n- [x](y)\n- task:p/a\n- keep\r\n\n## Notes\n- task:a\n"

    def test_checklist_keeps_checkbox(self):
        from chreos.lists import map_items

        body = "## Acceptance criteria\n- [x] old\n- [ ] other\n"
        result = map_items(body, "Acceptance criteria", CHECK, lambda t: "new" if t == "old" else t)
        assert result == "## Acceptance criteria\n- [x] new\n- [ ] other\n"

    def test_identity_and_missing_section_return_body_unchanged(self):
        from chreos.lists import map_items

        assert map_items(self.BODY, "References", BULLETS, lambda t: t) == self.BODY
        assert map_items("# T\n", "References", BULLETS, lambda t: None) == "# T\n"

    def test_crlf_line_ending_preserved_on_replacement(self):
        from chreos.lists import map_items

        assert map_items("## Notes\r\n- a\r\n", "Notes", BULLETS, lambda t: "b") == "## Notes\r\n- b\r\n"


class TestSetChecked:
    def test_checks_and_unchecks_by_position(self):
        body = set_checked(AC, "Acceptance criteria", [2], True)
        assert [i.checked for i in read_items(body, "Acceptance criteria", CHECK)] == [True, True, True]
        body = set_checked(body, "Acceptance criteria", [1, 3], False)
        assert [i.checked for i in read_items(body, "Acceptance criteria", CHECK)] == [False, True, False]
        assert "- [ ] upper checked\n" in body

    def test_only_the_marker_changes(self):
        body = set_checked(AC, "Acceptance criteria", [2], True)
        assert body == AC.replace("- [ ] open one", "- [x] open one")
        assert "-  [ ] not an item" in body and "- [ ] fenced" in body

    def test_already_in_state_is_unchanged(self):
        assert set_checked(AC, "Acceptance criteria", [1, 3], True) == AC
        assert set_checked(AC, "Acceptance criteria", [2], False) == AC

    def test_crlf(self):
        body = "## Acceptance criteria\r\n\r\n- [ ] a\r\n- [ ] b\r\n"
        assert set_checked(body, "Acceptance criteria", [2], True) == "## Acceptance criteria\r\n\r\n- [ ] a\r\n- [x] b\r\n"

    @pytest.mark.parametrize("index", [0, -1, 4])
    def test_out_of_range(self, index):
        with pytest.raises(ChreosError, match=f"no acceptance criterion {index}: the task has 3"):
            set_checked(AC, "Acceptance criteria", [1, index], True)

    def test_no_criteria(self):
        with pytest.raises(ChreosError, match="no acceptance criterion 1: the task has 0"):
            set_checked(TEMPLATE, "Acceptance criteria", [1], True)
        with pytest.raises(ChreosError, match="the task has 0"):
            set_checked("\n# T\n", "Acceptance criteria", [1], True)
