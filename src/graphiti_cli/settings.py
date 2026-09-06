"""graphiti-cli 配置读写.

配置持久化在 ``~/.graphiti-cli/settings.json``, 由 ``set`` 命令写入.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from .constants import RUNS_DIR

__all__ = [
    "SETTINGS_PATH",
    "EmbedderSettings",
    "FalkorDBSettings",
    "ModelProviderSettings",
    "Settings",
    "load_settings",
    "save_settings",
]


logger = logging.getLogger(__name__)

SETTINGS_PATH = RUNS_DIR / "settings.json"


# ======================================================================================
# 配置模型
# ======================================================================================
class ModelProviderSettings(BaseModel):
    """OpenAI 兼容模型服务的连接配置."""

    base_url: str = ""
    model: str = ""
    api_key: str = ""
    extra_body: dict[str, Any] = Field(default_factory=dict)


class EmbedderSettings(ModelProviderSettings):
    """Embedder 服务配置."""

    dim: int = 1024


class FalkorDBSettings(BaseModel):
    """FalkorDB 连接配置."""

    host: str = "localhost"
    port: int = 6379
    username: str = ""
    password: str = ""
    database: str = "default_db"


class Settings(BaseModel):
    """graphiti-cli 全局配置."""

    llm: ModelProviderSettings = Field(default_factory=ModelProviderSettings)
    embedder: EmbedderSettings = Field(default_factory=EmbedderSettings)
    reranker: ModelProviderSettings = Field(default_factory=ModelProviderSettings)
    falkordb: FalkorDBSettings = Field(default_factory=FalkorDBSettings)


# ======================================================================================
# 读写
# ======================================================================================
def load_settings() -> Settings:
    """从 SETTINGS_PATH 读取配置.

    文件不存在或字段缺失时返回默认值, 由调用方在使用处校验完整性.

    Returns:
        解析后的全局配置.

    """
    if not SETTINGS_PATH.exists():
        logger.debug(
            "Settings file not found, use defaults: path=%r", str(SETTINGS_PATH)
        )
        return Settings()
    data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    return Settings.model_validate(data)


def save_settings(
    *,
    settings: Settings,
) -> None:
    """原子写入配置文件, 并收紧文件权限(文件包含 api_key).

    Args:
        settings: 待写入的全局配置.

    """
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = SETTINGS_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    tmp_path.chmod(0o600)
    tmp_path.replace(SETTINGS_PATH)
    logger.debug("Settings saved: path=%r", str(SETTINGS_PATH))
