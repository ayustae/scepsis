from conftest import fake_command

import install


def test_nothing_detected_on_a_clean_home(home):
    assert install.detect_assistants() == []


def test_detected_by_config_dir(home):
    (home / ".claude").mkdir()
    (home / ".config" / "opencode").mkdir(parents=True)
    assert install.detect_assistants() == ["claude", "opencode"]


def test_detected_by_binary_on_path(home):
    fake_command(home.bin, "codex")
    assert install.detect_assistants() == ["codex"]


def test_detection_honours_env_overrides(home, tmp_path, monkeypatch):
    for var, name in (("CLAUDE_CONFIG_DIR", "c"), ("CODEX_HOME", "x"), ("XDG_CONFIG_HOME", "xdg")):
        monkeypatch.setenv(var, str(tmp_path / name))
    (tmp_path / "c").mkdir()
    (tmp_path / "x").mkdir()
    (tmp_path / "xdg" / "opencode").mkdir(parents=True)
    (home / ".claude").mkdir()  # ignored: CLAUDE_CONFIG_DIR wins
    assert install.detect_assistants() == ["claude", "codex", "opencode"]


def test_user_scope_targets(home):
    t = install.targets("user")
    assert t["claude"] == install.Targets(home / ".claude/skills", home / ".claude/agents")
    assert t["codex"] == install.Targets(home / ".agents/skills", home / ".codex/agents")
    assert t["opencode"] == install.Targets(
        home / ".config/opencode/skills", home / ".config/opencode/agents"
    )


def test_user_scope_targets_honour_env(home, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "c"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "x"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    t = install.targets("user")
    assert t["claude"].agents == tmp_path / "c/agents"
    assert t["codex"] == install.Targets(home / ".agents/skills", tmp_path / "x/agents")
    assert t["opencode"].skills == tmp_path / "xdg/opencode/skills"


def test_project_scope_targets(home, tmp_path):
    p = tmp_path / "proj"
    t = install.targets("project", project_dir=p)
    assert t["claude"] == install.Targets(p / ".claude/skills", p / ".claude/agents")
    assert t["codex"] == install.Targets(p / ".agents/skills", p / ".codex/agents")
    assert t["opencode"] == install.Targets(p / ".opencode/skills", p / ".opencode/agents")


def test_config_dir_override(home, tmp_path):
    t = install.targets("user", overrides={"claude": tmp_path / "c", "codex": tmp_path / "x"})
    assert t["claude"] == install.Targets(tmp_path / "c/skills", tmp_path / "c/agents")
    # Codex reads user skills from ~/.agents/skills, not from its config dir.
    assert t["codex"] == install.Targets(home / ".agents/skills", tmp_path / "x/agents")


def test_opencode_shared_skill_dirs(home, tmp_path):
    assert install.opencode_shared_skill_dirs("user") == [
        home / ".claude/skills",
        home / ".agents/skills",
    ]
    p = tmp_path / "proj"
    assert install.opencode_shared_skill_dirs("project", project_dir=p) == [
        p / ".claude/skills",
        p / ".agents/skills",
    ]
