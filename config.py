from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    pass


def _load_env() -> None:
    """
    Loads environment variables from .env files (first wins for each key).

    Order:
    1. secrets/.env — private keys, DB, Firebase paths (preferred)
    2. repo root .env — legacy / local overrides
    3. app/.env — legacy
    """
    here = os.path.dirname(__file__)
    secrets_env = os.path.join(here, "secrets", ".env")
    repo_env = os.path.join(here, ".env")
    app_env = os.path.join(here, "app", ".env")

    # Don't override actual environment variables (e.g., CI/production).
    load_dotenv(secrets_env, override=False)
    load_dotenv(repo_env, override=False)
    load_dotenv(app_env, override=False)


_load_env()


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if value is None or not str(value).strip():
        raise ConfigError(
            f"Missing required environment variable: {key}. "
            f"Set it in your environment or in a .env file."
        )
    return str(value).strip()


@dataclass(frozen=True)
class Config:
    DB_HOST: str = _require_env("DB_HOST")
    DB_NAME: str = _require_env("DB_NAME")
    DB_USER: str = _require_env("DB_USER")
    DB_PASSWORD: str = _require_env("DB_PASSWORD")
    SECRET_KEY: str = _require_env("SECRET_KEY")