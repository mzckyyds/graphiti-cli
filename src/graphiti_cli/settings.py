"""Configuration R/W for graphiti-cli.

Configuration is persisted in ``~/.graphiti-cli/settings.json``.
Use `graphiti-cli config set` to modify it.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "CLI_HOME",
    "SETTINGS_PATH",
    "EmbedderSettings",
    "FalkorDBSettings",
    "LLMSettings",
    "RerankerSettings",
    "Settings",
    "load_settings",
    "save_settings",
]


logger = logging.getLogger(__name__)

CLI_HOME = Path.home() / ".graphiti-cli"
SETTINGS_PATH = CLI_HOME / "settings.json"


# ======================================================================================
# 配置模型
# ======================================================================================
class LLMSettings(BaseModel):
    """LLM service configuration."""

    base_url: str = ""
    model_name: str = ""
    api_key: str = ""
    extra_body: dict[str, Any] = Field(default_factory=dict)


class EmbedderSettings(BaseModel):
    """Embedder service configuration."""

    base_url: str = ""
    model_name: str = ""
    api_key: str = ""
    dim: int = 1024


class RerankerSettings(BaseModel):
    """Reranker service configuration."""

    base_url: str = ""
    model_name: str = ""
    api_key: str = ""
    extra_body: dict[str, Any] = Field(default_factory=dict)


class FalkorDBSettings(BaseModel):
    """FalkorDB connection configuration."""

    host: str = "localhost"
    port: int = 6379
    username: str = ""
    password: str = ""
    database: str = "default_db"


class Settings(BaseModel):
    """graphiti-cli global configuration."""

    llm: LLMSettings = Field(default_factory=LLMSettings)
    embedder: EmbedderSettings = Field(default_factory=EmbedderSettings)
    reranker: RerankerSettings = Field(default_factory=RerankerSettings)
    falkordb: FalkorDBSettings = Field(default_factory=FalkorDBSettings)


# ======================================================================================
# 读写
# ======================================================================================
def load_settings() -> Settings:
    """Load configuration from ~/.graphiti-cli/settings.json.

    Returns default values if the file does not exist or fields are missing.

    Returns:
        The parsed global configuration.

    Raises:
        ValueError: Raised when the file content is not valid JSON
                or field types do not match.

    """
    if not SETTINGS_PATH.exists():
        logger.debug(
            "Configuration file does not exist, using default settings: path=%r",
            str(SETTINGS_PATH),
        )
        return Settings()
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = (
            f"Configuration file is not valid JSON: {SETTINGS_PATH} ({exc}), "
            "please fix the file or delete it and rerun config set"
        )
        raise ValueError(msg) from exc
    return Settings.model_validate(data)


def save_settings(
    *,
    settings: Settings,
) -> None:
    """Atomically write the configuration file.

    Will tighten file permissions because the file contains API key.

    Args:
        settings: The global configuration to be written.

    """
    CLI_HOME.mkdir(parents=True, exist_ok=True)
    CLI_HOME.chmod(0o700)

    # A unique staging file per write avoids concurrent `config set` runs
    # clobbering each other; `mkstemp` also creates it with 0o600 directly.
    fd, tmp_name = tempfile.mkstemp(
        dir=CLI_HOME, prefix=f"{SETTINGS_PATH.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(settings.model_dump_json(indent=2))
        tmp_path.replace(SETTINGS_PATH)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    logger.debug("Configuration saved: path=%r", str(SETTINGS_PATH))
