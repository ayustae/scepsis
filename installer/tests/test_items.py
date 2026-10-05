import json

import pytest

import install


def test_loads_skills_and_agents_sorted_by_name(repo):
    repo.skill("task", requires=["chreos"])
    repo.skill("context")
    repo.agent("verification")

    skills, errors = install.load_items(repo.root, "skills")
    agents, _ = install.load_items(repo.root, "agents")

    assert errors == {}
    assert [s.name for s in skills] == ["context", "task"]
    assert skills[1].meta["requires"] == ["chreos"]
    assert skills[1].body == "# Skill\n\nDo it.\n"
    assert [a.name for a in agents] == ["verification"]


def test_missing_kind_folder_is_empty(repo):
    repo.root.mkdir(parents=True)
    assert install.load_items(repo.root, "agents") == ([], {})


def test_folders_without_definition_are_ignored(repo):
    (repo.root / "skills" / "notes").mkdir(parents=True)
    assert install.load_items(repo.root, "skills") == ([], {})


@pytest.mark.parametrize(
    "meta, problem",
    [
        ({"name": "other", "description": "d"}, "folder name"),
        ({"name": "x", "description": ""}, "description"),
        ({"name": "x"}, "description"),
        ({"name": "x", "description": "d", "requires": "chreos"}, "requires"),
        ({"name": "x", "description": "d", "user_invocable": "yes"}, "user_invocable"),
        ({"name": "x", "description": "d", "tools": ["fly"]}, "tools"),
        ({"name": "x", "description": "d", "model": "gpt"}, "model"),
    ],
)
def test_invalid_frontmatter_is_reported_not_loaded(repo, meta, problem):
    folder = repo.skill("x")
    (folder / "frontmatter.json").write_text(json.dumps(meta))

    items, errors = install.load_items(repo.root, "skills")

    assert items == []
    assert list(errors) == ["x"] and problem in errors["x"]


def test_invalid_name_pattern_is_reported(repo):
    repo.skill("Bad_Name")
    items, errors = install.load_items(repo.root, "skills")
    assert items == [] and "name" in errors["Bad_Name"]


def test_unparseable_json_is_reported(repo):
    folder = repo.skill("x")
    (folder / "frontmatter.json").write_text("{")
    items, errors = install.load_items(repo.root, "skills")
    assert items == [] and "frontmatter.json" in errors["x"]


def test_tools_are_folders_with_pyproject(repo):
    repo.tool("idion")
    repo.tool("chreos")
    (repo.root / "tools" / "notes").mkdir()
    assert install.list_tools(repo.root) == ["chreos", "idion"]


def test_real_repository_definitions_are_valid():
    for kind in ("skills", "agents"):
        items, errors = install.load_items(install.REPO, kind)
        assert errors == {}
        assert items
    assert install.list_tools(install.REPO) == ["chreos", "idion"]
