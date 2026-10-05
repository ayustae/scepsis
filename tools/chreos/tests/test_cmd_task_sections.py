import json
from datetime import datetime, timezone

import pytest

from chreos.frontmatter import load, save
from conftest import run_cli as run

OLD = datetime(2000, 1, 1, tzinfo=timezone.utc)


def ok(*args, input=None):
    result = run(*args, input=input)
    assert result.exit_code == 0, result.output + result.stderr
    return result


@pytest.fixture
def task(cli_home):
    ok("task", "create", "t")
    ok("task", "create", "other")
    return cli_home / "ws/default/tasks/t/TASK.md"


def test_description(task):
    before = load(task).meta["updated"]
    ok("task", "description", "append", "t", "First.")
    ok("task", "description", "append", "t", input="Second.\n\n### Detail\n")
    assert ok("task", "description", "show", "t").output == "First.\n\nSecond.\n\n### Detail\n"
    assert load(task).meta["updated"] >= before
    result = run("task", "description", "replace", "t", "# H1")
    assert result.exit_code == 1 and "H1 or H2" in result.stderr


def test_acceptance_criteria(task):
    ok("task", "ac", "append", "t", "-a", "One", "--ac", "Two")
    task.write_text(task.read_text().replace("- [ ] One", "- [x] One"))
    ok("task", "ac", "append", "t", "--acceptance-criteria", "Three")
    assert ok("task", "ac", "show", "t").output == "- [x] One\n- [ ] Two\n- [ ] Three\n"
    data = json.loads(ok("task", "ac", "show", "t", "--json").output)
    assert data[0] == {"text": "One", "checked": True}
    ok("task", "ac", "replace", "t", "-a", "Only")
    assert ok("task", "ac", "show", "t").output == "- [ ] Only\n"
    assert run("task", "ac", "append", "t").exit_code == 2
    assert run("task", "ac", "append", "t", "-a", "a\nb").exit_code == 1


def test_refs(task):
    ok("task", "refs", "append", "t", "-r", "[Spec](https://x.example)", "-r", "https://web.dev", "-r", "task:other")
    data = json.loads(ok("task", "refs", "show", "t", "--json").output)
    assert [entry["kind"] for entry in data] == ["link", "url", "item"]
    result = run("task", "refs", "append", "t", "-r", "task:missing")
    assert result.exit_code == 1 and "does not resolve" in result.stderr
    result = run("task", "refs", "append", "t", "-r", "other")
    assert result.exit_code == 1 and "did you mean 'task:other'" in result.stderr
    task.write_text(task.read_text().replace("- https://web.dev", "- not a reference"))
    data = json.loads(ok("task", "refs", "show", "t", "--json").output)
    assert data[1] == {"text": "not a reference", "kind": None}
    ok("task", "refs", "replace", "t", "-r", "task:other")
    assert ok("task", "refs", "show", "t").output == "- task:other\n"


def test_notes_and_missing_section(task):
    task.write_text(task.read_text().replace("## Notes\n", ""))
    ok("task", "notes", "append", "t", "-N", "Layout done", "--note", "Perf at 82")
    assert ok("task", "notes", "show", "t").output == "- Layout done\n- Perf at 82\n"
    assert json.loads(ok("task", "notes", "show", "t", "--json").output) == ["Layout done", "Perf at 82"]
    assert task.read_text().rstrip().endswith("## Notes\n\n- Layout done\n- Perf at 82")


def test_show_works_on_archived_tasks(task, cli_home):
    ok("task", "notes", "append", "t", "-N", "kept")
    ok("task", "update", "t", "--status", "cancelled")
    ok("task", "archive", "t")
    assert ok("task", "notes", "show", "t").output == "- kept\n"
    assert run("task", "notes", "append", "t", "-N", "x").exit_code == 1
    result = run("task", "ac", "check", "t", "1")
    assert result.exit_code == 1 and "archived" in result.stderr


def test_check_and_uncheck_criteria(task):
    ok("task", "ac", "append", "t", "-a", "One", "-a", "Two", "-a", "Three")
    doc = load(task)
    doc.meta["updated"] = OLD
    save(task, doc)
    ok("task", "ac", "check", "t", "1", "3")
    assert ok("task", "ac", "show", "t").output == "- [x] One\n- [ ] Two\n- [x] Three\n"
    assert load(task).meta["updated"] > OLD
    ok("task", "ac", "uncheck", "default/t", "3")
    data = json.loads(ok("task", "ac", "show", "t", "--json").output)
    assert [entry["checked"] for entry in data] == [True, False, False]


def test_check_errors_leave_the_file_alone(task):
    ok("task", "ac", "append", "t", "-a", "One")
    before = task.read_text()
    result = run("task", "ac", "check", "t", "1", "2")
    assert result.exit_code == 1 and "no acceptance criterion 2: the task has 1" in result.stderr
    assert run("task", "ac", "check", "t", "one").exit_code == 2
    assert run("task", "ac", "check", "t").exit_code == 2
    assert task.read_text() == before


def test_checked_criteria_let_the_task_close_without_confirmation(task, cli_home, tmp_path):
    ok("task", "ac", "append", "t", "-a", "One")
    ok("task", "update", "t", "--source-type", "local", "--source-path", str(tmp_path))
    ok("task", "open", "t")
    result = run("task", "close", "t", "--status", "done")
    assert result.exit_code == 1 and "1 unchecked acceptance criterion" in result.stderr
    ok("task", "ac", "check", "t", "1")
    ok("task", "close", "t", "--status", "done")
