from idion.paths import context_root


def test_context_root_is_under_the_scepsis_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert context_root() == tmp_path / ".scepsis" / "context"
