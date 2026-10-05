import pytest
from click.testing import CliRunner


class IdionRunner(CliRunner):
    def invoke(self, cli, args=None, **kwargs):
        kwargs.setdefault("prog_name", "idion")
        return super().invoke(cli, args, **kwargs)


@pytest.fixture(autouse=True)
def home(tmp_path_factory, monkeypatch):
    """Never touch the real ~/.scepsis; kept outside `tmp_path`, which tests list."""
    path = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(path))
    return path


@pytest.fixture
def runner():
    return IdionRunner()
