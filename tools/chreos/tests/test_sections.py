import pytest

from chreos.errors import ChreosError
from chreos.sections import (
    PROJECT_SECTIONS,
    TASK_SECTIONS,
    append_text,
    find_section,
    read_section,
    validate_description,
    write_section,
)

TEMPLATE = (
    "\n# T\n\nSummary.\n\n## Description\n\n## Acceptance criteria\n\n"
    "## References\n\n## Notes\n\n"
)

FILLED = """\

# T

## Description

Some text.

```md
## Notes
```

### Detail

More.

## Acceptance criteria

- [ ] one

## Notes
- a note"""


def lines(text):
    return text.splitlines(keepends=True)


class TestFindSection:
    def test_finds_heading_and_content_span(self):
        span = find_section(lines(TEMPLATE), "Description")
        assert (span.heading, span.start, span.end) == (5, 6, 7)

    def test_section_at_end_of_file(self):
        body = lines(TEMPLATE)
        span = find_section(body, "Notes")
        assert span.end == len(body)

    def test_h3_and_fenced_h2_do_not_end_a_section(self):
        body = lines(FILLED)
        span = find_section(body, "Description")
        assert body[span.end] == "## Acceptance criteria\n"

    def test_fenced_heading_is_not_a_section(self):
        body = lines(FILLED)
        assert find_section(body, "Notes").heading == len(body) - 2

    @pytest.mark.parametrize("heading", ["## Notes extra", "### Notes", "## notes", " ## Notes", "##Notes"])
    def test_requires_exact_heading(self, heading):
        assert find_section(lines(f"{heading}\n- x\n"), "Notes") is None

    def test_trailing_crlf_is_ignored(self):
        assert find_section(lines("## Notes\r\n- x\r\n"), "Notes") is not None


class TestReadSection:
    def test_empty_section(self):
        assert read_section(TEMPLATE, "Description") == ""

    def test_trims_surrounding_blank_lines_only(self):
        assert read_section(FILLED, "Description") == (
            "Some text.\n\n```md\n## Notes\n```\n\n### Detail\n\nMore."
        )

    def test_missing_section(self):
        assert read_section("# T\n", "Notes") is None

    def test_section_without_trailing_newline(self):
        assert read_section(FILLED, "Notes") == "- a note"


class TestWriteSection:
    def test_fills_an_empty_section(self):
        result = write_section(TEMPLATE, "Description", "Hello.\n\nWorld.", TASK_SECTIONS)
        assert result == TEMPLATE.replace(
            "## Description\n\n", "## Description\n\nHello.\n\nWorld.\n\n"
        )

    def test_empty_text_restores_template_layout(self):
        filled = write_section(TEMPLATE, "Description", "Hello.", TASK_SECTIONS)
        assert write_section(filled, "Description", "", TASK_SECTIONS) == TEMPLATE

    def test_replaces_existing_content_only(self):
        result = write_section(FILLED, "Description", "New.", TASK_SECTIONS)
        before, after = FILLED.split("## Description\n", 1)[0], FILLED.split("## Acceptance criteria", 1)[1]
        assert result == f"{before}## Description\n\nNew.\n\n## Acceptance criteria{after}"

    def test_section_at_end_of_file_gets_no_trailing_blank_line(self):
        result = write_section(FILLED, "Notes", "- x", TASK_SECTIONS)
        assert result.endswith("## Notes\n\n- x\n")

    def test_text_blank_lines_are_trimmed_and_newlines_normalized(self):
        result = write_section(TEMPLATE, "Notes", "\n\n- a\r\n- b\n\n", TASK_SECTIONS)
        assert result.endswith("## Notes\n\n- a\n- b\n")

    def test_crlf_body(self):
        body = TEMPLATE.replace("\n", "\r\n")
        result = write_section(body, "Description", "a\nb", TASK_SECTIONS)
        assert result == body.replace("## Description\r\n\r\n", "## Description\r\n\r\na\r\nb\r\n\r\n")


class TestMissingSection:
    def without(self, *headings):
        body = TEMPLATE
        for heading in headings:
            body = body.replace(f"## {heading}\n\n", "")
        return body

    def test_after_nearest_preceding_section(self):
        body = self.without("References")
        result = write_section(body, "References", "- r", TASK_SECTIONS)
        assert result == TEMPLATE.replace("## References\n\n", "## References\n\n- r\n\n")

    def test_last_section_goes_to_end(self):
        body = self.without("Notes")
        result = write_section(body, "Notes", "- n", TASK_SECTIONS)
        assert result == TEMPLATE.replace("## Notes\n\n", "## Notes\n\n- n\n")

    def test_before_following_section_when_none_precedes(self):
        body = self.without("Description")
        result = write_section(body, "Description", "d", TASK_SECTIONS)
        assert result == TEMPLATE.replace("## Description\n\n", "## Description\n\nd\n\n")

    def test_end_of_body_when_no_template_section_exists(self):
        body = "\n# T\n\nSummary.\n"
        result = write_section(body, "Description", "d", PROJECT_SECTIONS)
        assert result == "\n# T\n\nSummary.\n\n## Description\n\nd\n"

    def test_end_of_body_without_trailing_newline(self):
        result = write_section("# T", "Notes", "- n", TASK_SECTIONS)
        assert result == "# T\n\n## Notes\n\n- n\n"

    def test_preceding_section_without_blank_line_before_next_heading(self):
        body = "## Description\ntext\n## Notes\n- n\n"
        result = write_section(body, "References", "- r", TASK_SECTIONS)
        assert result == "## Description\ntext\n\n## References\n\n- r\n\n## Notes\n- n\n"

    def test_empty_body(self):
        assert write_section("", "Notes", "- n", TASK_SECTIONS) == "## Notes\n\n- n\n"

    def test_unknown_heading_is_refused(self):
        with pytest.raises(ValueError):
            write_section(TEMPLATE, "Bogus", "x", TASK_SECTIONS)


class TestAppendText:
    def test_append_to_empty_section(self):
        assert append_text(TEMPLATE, "Description", "a", TASK_SECTIONS) == write_section(
            TEMPLATE, "Description", "a", TASK_SECTIONS
        )

    def test_append_separates_with_a_blank_line(self):
        body = write_section(TEMPLATE, "Description", "a", TASK_SECTIONS)
        result = append_text(body, "Description", "b", TASK_SECTIONS)
        assert read_section(result, "Description") == "a\n\nb"

    def test_append_creates_missing_section(self):
        result = append_text("# T\n", "Notes", "- n", TASK_SECTIONS)
        assert read_section(result, "Notes") == "- n"


class TestValidateDescription:
    @pytest.mark.parametrize(
        "text", ["", "plain", "### H3 is fine", "```sh\n# comment\n## also\n```", "a #tag", "#hashtag"]
    )
    def test_valid(self, text):
        assert validate_description(text) == text

    @pytest.mark.parametrize("text", ["# H1", "x\n## H2", "#", "##", "##\tTab"])
    def test_rejects_h1_and_h2(self, text):
        with pytest.raises(ChreosError, match="H1 or H2"):
            validate_description(text)

    def test_rejects_unclosed_fence(self):
        with pytest.raises(ChreosError, match="unclosed code fence"):
            validate_description("```\ncode")
