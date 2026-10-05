from datetime import date

import pytest

from chreos.errors import ChreosError
from chreos.model import (
    ALLOWED_STATUSES,
    Phase,
    Priority,
    TaskStatus,
    check_status_for_phase,
    normalize_labels,
    parse_assignee,
    parse_due,
    parse_optional,
    parse_priority,
    validate_name,
)


class TestValidateName:
    @pytest.mark.parametrize("name", ["a", "redesign-homepage", "v2", "a-b-c", "x" * 64])
    def test_accepts_valid_names(self, name):
        assert validate_name(name) == name

    @pytest.mark.parametrize(
        "name",
        ["", "x" * 65, "-a", "a-", "a--b", "Abc", "a_b", "a b", "a.b", "a/b", "é", "a\n"],
    )
    def test_rejects_invalid_names(self, name):
        with pytest.raises(ChreosError, match="invalid name"):
            validate_name(name)

    def test_rejects_non_strings(self):
        with pytest.raises(ChreosError):
            validate_name(None)


class TestNormalizeLabels:
    def test_lowercases_and_keeps_order(self):
        assert normalize_labels(["Urgent", "Area=Frontend"]) == ["urgent", "area=frontend"]

    def test_removes_duplicates_after_normalization(self):
        assert normalize_labels(["a", "A", "k=v", "k=V", "k=w"]) == ["a", "k=v", "k=w"]

    def test_empty_list(self):
        assert normalize_labels([]) == []

    @pytest.mark.parametrize(
        "label", ["", "=v", "a=", "a=b c", "a=b,c", "a=b=c", "a b", "a.b", "a\tb", "a=b\n"]
    )
    def test_rejects_invalid_labels(self, label):
        with pytest.raises(ChreosError, match="invalid label"):
            normalize_labels([label])

    def test_rejects_non_string_items(self):
        with pytest.raises(ChreosError, match="invalid label"):
            normalize_labels([3])


class TestPhaseStatus:
    def test_allowed_statuses_per_phase(self):
        assert ALLOWED_STATUSES[Phase.CLOSED] == {TaskStatus.NEW, TaskStatus.DONE, TaskStatus.CANCELLED}
        assert ALLOWED_STATUSES[Phase.OPEN] == {
            TaskStatus.TODO,
            TaskStatus.ON_HOLD,
            TaskStatus.IN_PROGRESS,
            TaskStatus.DONE,
            TaskStatus.CANCELLED,
        }

    @pytest.mark.parametrize("phase", list(Phase))
    @pytest.mark.parametrize("status", list(TaskStatus))
    def test_check_status_for_phase(self, phase, status):
        if status in ALLOWED_STATUSES[phase]:
            check_status_for_phase(phase, status)
        else:
            with pytest.raises(ChreosError, match=f"not allowed in phase '{phase}'"):
                check_status_for_phase(phase, status)

    def test_enum_values_match_design(self):
        assert TaskStatus.IN_PROGRESS == "in-progress"
        assert TaskStatus.ON_HOLD == "on-hold"


class TestTaskFields:
    def test_parse_priority(self):
        assert parse_priority("high") is Priority.HIGH

    @pytest.mark.parametrize("value", ["High", "urgent", ""])
    def test_parse_priority_rejects_unknown(self, value):
        with pytest.raises(ChreosError, match="invalid priority"):
            parse_priority(value)

    def test_parse_due(self):
        assert parse_due("2026-10-15") == date(2026, 10, 15)

    @pytest.mark.parametrize("value", ["2026-13-01", "2026-02-30", "15/10/2026", "2026-1-5", "20261015", ""])
    def test_parse_due_rejects_invalid(self, value):
        with pytest.raises(ChreosError, match="invalid due date"):
            parse_due(value)

    def test_parse_assignee_strips(self):
        assert parse_assignee("  claude ") == "claude"

    @pytest.mark.parametrize("value", ["", "   ", "a\nb", "a\rb"])
    def test_parse_assignee_rejects_invalid(self, value):
        with pytest.raises(ChreosError, match="invalid assignee"):
            parse_assignee(value)

    def test_parse_optional_none_clears(self):
        assert parse_optional("none", parse_due) is None

    def test_parse_optional_delegates(self):
        assert parse_optional("low", parse_priority) is Priority.LOW
