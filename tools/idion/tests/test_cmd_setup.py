import stat

from idion.cli import main


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_init_creates_a_private_root(runner, home):
    result = runner.invoke(main, ["init"])
    root = home / ".scepsis" / "context"
    assert result.exit_code == 0, result.output
    assert result.output == f"Created {root}\n"
    assert root.is_dir()
    assert mode(root) == 0o700


def test_init_keeps_an_existing_root(runner, home):
    root = home / ".scepsis" / "context"
    root.mkdir(parents=True)
    root.chmod(0o750)
    (root / "user.md").write_text("---\ndescription: x\n---\n")
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    assert result.output == f"{root} already exists\n"
    assert mode(root) == 0o750
    assert (root / "user.md").read_text() == "---\ndescription: x\n---\n"


def test_init_works_when_the_scepsis_home_exists(runner, home):
    (home / ".scepsis").mkdir()
    (home / ".scepsis" / "config.toml").write_text("[workspace]\n")
    assert runner.invoke(main, ["init"]).exit_code == 0
    assert (home / ".scepsis" / "context").is_dir()
    assert (home / ".scepsis" / "config.toml").read_text() == "[workspace]\n"


def test_init_fails_when_the_root_is_a_file(runner, home):
    (home / ".scepsis").mkdir()
    (home / ".scepsis" / "context").write_text("x")
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 1
    assert "is not a folder" in result.stderr


def test_init_help(runner):
    result = runner.invoke(main, ["init", "-h"])
    assert result.exit_code == 0
    assert result.output.startswith("Usage: idion init")
