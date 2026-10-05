from pathlib import Path

import pytest

from chreos.errors import ChreosError
from chreos.paths import parse_path, parse_source_path


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_absolute_path_is_accepted():
    assert parse_path("/srv/work") == Path("/srv/work")


def test_tilde_is_expanded(home):
    assert parse_path("~/work") == home / "work"
    assert parse_path("~") == home


@pytest.mark.parametrize("value", ["work", "./work", "../work", "~user/work"])
def test_relative_paths_are_rejected(value):
    with pytest.raises(ChreosError, match="absolute or start with '~'"):
        parse_path(value)


@pytest.mark.parametrize("value", ["", "/a\0b", "/a\nb"])
def test_empty_nul_and_newlines_are_rejected(value):
    with pytest.raises(ChreosError, match="invalid path"):
        parse_path(value)


def test_source_path_accepts_relative_unchanged():
    assert parse_source_path("website") == "website"
    assert parse_source_path("~/code/site") == "~/code/site"
    assert parse_source_path("/srv/site") == "/srv/site"


@pytest.mark.parametrize("value", ["", "a\0b", "a\nb"])
def test_source_path_rejects_empty_nul_and_newlines(value):
    with pytest.raises(ChreosError, match="invalid path"):
        parse_source_path(value)
