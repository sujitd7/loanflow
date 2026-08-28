import pytest

from app.config import Settings

_STRONG = "s" * 40


def test_local_environments_allow_the_insecure_default() -> None:
    for env in ("dev", "test", "local"):
        settings = Settings(environment=env, jwt_secret="dev-only-change-me")
        assert settings.jwt_secret == "dev-only-change-me"


def test_non_local_environment_rejects_the_default_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(environment="prod", jwt_secret="dev-only-change-me")


def test_non_local_environment_rejects_a_short_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(environment="staging", jwt_secret="too-short")


def test_non_local_environment_accepts_a_strong_secret() -> None:
    settings = Settings(environment="prod", jwt_secret=_STRONG)
    assert settings.jwt_secret == _STRONG
