"""Consistency of the real repository: every component has a version, and every
current version has its CHANGELOG entry (see the versioning rules in AGENTS.md)."""

import re
import tomllib

import install

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def changelog_headings():
    text = (install.REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    return set(re.findall(r"^#{2,3} (.+?)\s*$", text, re.MULTILINE))


def pyproject_version(path):
    return tomllib.loads(path.read_text(encoding="utf-8"))["project"]["version"]


def test_framework_version_is_semver():
    assert SEMVER.match(install.framework_version(install.REPO) or "")


def test_installer_version_matches_its_pyproject():
    assert install.VERSION == pyproject_version(install.REPO / "installer" / "pyproject.toml")


def test_framework_release_is_in_the_changelog():
    version = install.framework_version(install.REPO)
    assert any(h.startswith(f"Scepsis {version} ") for h in changelog_headings())


def test_every_component_version_is_in_the_changelog():
    headings = changelog_headings()
    expected = [f"installer {install.VERSION}"]
    for tool in install.list_tools(install.REPO):
        expected.append(f"{tool} {pyproject_version(install.REPO / 'tools' / tool / 'pyproject.toml')}")
    for kind in ("skills", "agents"):
        items, errors = install.load_items(install.REPO, kind)
        assert errors == {}
        expected += [f"{kind[:-1]} {i.name} {i.version}" for i in items]
    missing = [e for e in expected if e not in headings]
    assert missing == []
