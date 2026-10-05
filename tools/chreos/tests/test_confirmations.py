import pytest

from chreos.confirmations import decided_message, done_message, require
from chreos.errors import ChreosError
from chreos.graph import DependencyStatus, Node
from chreos.model import Kind

BODY = "## Acceptance criteria\n\n- [x] a\n- [ ] b\n- [ ] c\n\n## Notes\n- [ ] not a criterion\n"
OK = DependencyStatus("task:a", Node(Kind.TASK, "p", "a"), "done", True)
OPEN = DependencyStatus("task:b", Node(Kind.TASK, "p", "b"), "in-progress", False)
MISSING = DependencyStatus("decision:gone", None, None, False)


def test_nothing_to_confirm():
    assert done_message("## Acceptance criteria\n\n- [x] a\n", [OK]) is None
    assert done_message("", []) is None
    assert decided_message([OK]) is None


def test_done_with_unchecked_criteria_and_dependencies():
    message = done_message(BODY, [OK, OPEN, MISSING])
    assert "2 unchecked acceptance criteria" in message
    assert "task:b (in-progress)" in message
    assert "decision:gone (unresolved)" in message
    assert "task:a" not in message


def test_done_with_one_criterion():
    assert "1 unchecked acceptance criterion" in done_message("## Acceptance criteria\n- [ ] x\n", [])


def test_decided_with_unsatisfied_dependencies():
    message = decided_message([OPEN])
    assert "decided" in message and "task:b (in-progress)" in message


def test_require(yes, no):
    require(None, no)
    assert no.messages == []
    require("sure?", yes)
    assert yes.messages == ["sure?"]
    with pytest.raises(ChreosError, match="cancelled"):
        require("sure?", no)
