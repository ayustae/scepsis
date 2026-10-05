import pytest

from chreos.errors import ChreosError
from chreos.model import Kind
from chreos.refs import ItemRef, classify_reference, parse_ref, validate_reference


class TestParseRef:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("task:migrate-cms", ItemRef(Kind.TASK, None, "migrate-cms")),
            ("decision:hosting", ItemRef(Kind.DECISION, None, "hosting")),
            ("task:other/build-cli", ItemRef(Kind.TASK, "other", "build-cli")),
            ("decision:p2/x", ItemRef(Kind.DECISION, "p2", "x")),
        ],
    )
    def test_valid(self, text, expected):
        ref = parse_ref(text)
        assert ref == expected
        assert str(ref) == text

    @pytest.mark.parametrize("text", ["migrate-cms", "other/build-cli"])
    def test_missing_prefix_gets_a_hint(self, text):
        with pytest.raises(ChreosError, match=f"did you mean 'task:{text}' or 'decision:{text}'"):
            parse_ref(text)

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "project:x",
            "Task:x",
            "task:",
            "task:Bad",
            "task:a/b/c",
            "task:../x",
            "task:/x",
            "task:p/",
            " task:x",
            "task:x ",
            "Not A Name",
        ],
    )
    def test_invalid(self, text):
        with pytest.raises(ChreosError, match="invalid item reference"):
            parse_ref(text)

    def test_qualified_fills_in_the_holder_project(self):
        assert parse_ref("task:a").qualified("p") == ItemRef(Kind.TASK, "p", "a")
        assert parse_ref("task:q/a").qualified("p") == ItemRef(Kind.TASK, "q", "a")

    def test_relative_to_drops_the_own_project(self):
        assert ItemRef(Kind.TASK, "p", "a").relative_to("p") == ItemRef(Kind.TASK, None, "a")
        assert ItemRef(Kind.TASK, "q", "a").relative_to("p") == ItemRef(Kind.TASK, "q", "a")


class TestClassifyReference:
    @pytest.mark.parametrize(
        ("text", "kind"),
        [
            ("[Hero pattern](https://design.example.com/hero)", "link"),
            ("[notes](../docs/notes.md)", "link"),
            ('[spec](https://x.example "Spec")', "link"),
            ("https://web.dev/articles/lcp", "url"),
            ("file:///tmp/x", "url"),
            ("task:migrate-cms", "item"),
            ("decision:other/hosting", "item"),
        ],
    )
    def test_kinds(self, text, kind):
        assert classify_reference(text) == kind

    @pytest.mark.parametrize(
        "text", ["just words", "[broken](", "https://has space", "[a](b) trailing", "ftp:/x"]
    )
    def test_invalid(self, text):
        with pytest.raises(ChreosError, match="invalid reference"):
            classify_reference(text)

    def test_bare_name_gets_the_prefix_hint(self):
        with pytest.raises(ChreosError, match="did you mean 'task:migrate-cms'"):
            classify_reference("migrate-cms")


class TestValidateReference:
    def test_links_and_urls_need_no_workspace_lookup(self, ws):
        assert validate_reference(ws.workspace, "p", "https://x.example") == "url"
        assert validate_reference(ws.workspace, "p", "[a](b)") == "link"

    def test_item_reference_must_resolve(self, ws):
        ws.project("p")
        ws.task("p", "t", archived=True)
        assert validate_reference(ws.workspace, "p", "task:t") == "item"
        with pytest.raises(ChreosError, match="'decision:t' does not resolve"):
            validate_reference(ws.workspace, "p", "decision:t")
