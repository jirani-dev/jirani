import pytest

import app.config as config


def test_secret_key_default_is_not_resolved_at_import() -> None:
    # The default used to be get_secret_key() itself, evaluated when the class
    # body ran: importing app.config wrote the key file even when SECRET_KEY
    # came from the environment.
    assert config.Settings.model_fields["SECRET_KEY"].default == ""


def test_secret_key_from_env_does_not_touch_the_key_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail() -> str:
        raise AssertionError("the key file must not be consulted")

    monkeypatch.setattr(config, "get_secret_key", fail)
    monkeypatch.setenv("SECRET_KEY", "from-env")

    assert config.Settings().SECRET_KEY == "from-env"


def test_secret_key_falls_back_to_the_key_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "get_secret_key", lambda: "from-file")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    assert config.Settings().SECRET_KEY == "from-file"


def test_sql_echo_is_opt_in() -> None:
    assert config.Settings.model_fields["DEBUG"].default is False
