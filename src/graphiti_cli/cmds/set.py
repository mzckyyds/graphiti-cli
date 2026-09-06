"""``set`` 子命令: 分组配置 LLM/Embedding/Reranker 与 FalkorDB.

每个命令只更新显式传入的选项, 其余字段保持不变, 支持多次增量配置.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import typer

from graphiti_cli.settings import SETTINGS_PATH, load_settings, save_settings

if TYPE_CHECKING:
    from graphiti_cli.settings import FalkorDBSettings, ModelProviderSettings

__all__ = [
    "app",
]


logger = logging.getLogger(__name__)

app = typer.Typer(
    help="配置模型服务与 FalkorDB 连接, 写入 ~/.graphiti-cli/settings.json.",
)


# ======================================================================================
# 内部工具
# ======================================================================================
def _mask_secret(*, value: str) -> str:
    """掩码敏感值, 只保留前 4 位.

    Args:
        value: 原始值.

    Returns:
        掩码后的展示值, 空值原样返回.

    """
    if not value:
        return ""
    return f"{value[:4]}***"


def _update_model_provider(
    *,
    section: ModelProviderSettings,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
) -> None:
    """把命令行传入的选项增量更新到模型服务配置.

    Args:
        section: 目标配置段, 原地修改.
        base_url: OpenAI 兼容端点, None 表示不更新.
        model: 模型名, None 表示不更新.
        api_key: API Key, None 表示不更新.

    """
    if base_url is not None:
        section.base_url = base_url.rstrip("/")
    if model is not None:
        section.model = model
    if api_key is not None:
        section.api_key = api_key


def _echo_provider(*, section: ModelProviderSettings, name: str) -> None:
    """回显某个模型服务配置段的当前值(api_key 掩码).

    Args:
        section: 模型服务配置段.
        name: 配置段名称.

    """
    typer.echo(
        f"{name}: base_url={section.base_url!r}, "
        f"model={section.model!r}, "
        f"api_key={_mask_secret(value=section.api_key)!r}",
    )


def _echo_falkordb(*, section: FalkorDBSettings) -> None:
    """回显 FalkorDB 配置段(password 掩码).

    Args:
        section: FalkorDB 配置段.

    """
    typer.echo(
        f"falkordb: host={section.host!r}, port={section.port!r}, "
        f"username={section.username!r}, "
        f"password={_mask_secret(value=section.password)!r}, "
        f"database={section.database!r}",
    )


# ======================================================================================
# 配置命令
# ======================================================================================
@app.command(name="llm")
def set_llm(
    *,
    base_url: str | None = typer.Option(None, "--base-url", help="OpenAI 兼容端点地址"),
    model: str | None = typer.Option(None, "--model", help="LLM 模型名"),
    api_key: str | None = typer.Option(None, "--api-key", help="API Key"),
) -> None:
    """配置 LLM 服务, 未传入的选项保持不变."""
    settings = load_settings()
    _update_model_provider(
        section=settings.llm,
        base_url=base_url,
        model=model,
        api_key=api_key,
    )
    save_settings(settings=settings)
    _echo_provider(section=settings.llm, name="llm")


@app.command(name="embedding")
def set_embedding(
    *,
    base_url: str | None = typer.Option(None, "--base-url", help="OpenAI 兼容端点地址"),
    model: str | None = typer.Option(None, "--model", help="Embedding 模型名"),
    api_key: str | None = typer.Option(None, "--api-key", help="API Key"),
    dim: int | None = typer.Option(None, "--dim", help="向量维度, 默认 1024"),
) -> None:
    """配置 Embedding 服务, 未传入的选项保持不变."""
    settings = load_settings()
    _update_model_provider(
        section=settings.embedding,
        base_url=base_url,
        model=model,
        api_key=api_key,
    )
    if dim is not None:
        settings.embedding.dim = dim
    save_settings(settings=settings)
    _echo_provider(section=settings.embedding, name="embedding")


@app.command(name="reranker")
def set_reranker(
    *,
    base_url: str | None = typer.Option(None, "--base-url", help="OpenAI 兼容端点地址"),
    model: str | None = typer.Option(None, "--model", help="Reranker 模型名"),
    api_key: str | None = typer.Option(None, "--api-key", help="API Key"),
) -> None:
    """配置 Reranker 服务, 未传入的选项保持不变."""
    settings = load_settings()
    _update_model_provider(
        section=settings.reranker,
        base_url=base_url,
        model=model,
        api_key=api_key,
    )
    save_settings(settings=settings)
    _echo_provider(section=settings.reranker, name="reranker")


@app.command(name="falkordb")
def set_falkordb(
    *,
    host: str | None = typer.Option(None, "--host", help="FalkorDB 主机名"),
    port: int | None = typer.Option(None, "--port", help="FalkorDB 端口"),
    username: str | None = typer.Option(
        None, "--username", help="用户名, 无鉴权时传空字符串"
    ),
    password: str | None = typer.Option(
        None, "--password", help="密码, 无鉴权时传空字符串"
    ),
    database: str | None = typer.Option(None, "--database", help="图名"),
) -> None:
    """配置 FalkorDB 连接, 未传入的选项保持不变."""
    settings = load_settings()
    section = settings.falkordb
    if host is not None:
        section.host = host
    if port is not None:
        section.port = port
    if username is not None:
        section.username = username
    if password is not None:
        section.password = password
    if database is not None:
        section.database = database
    save_settings(settings=settings)
    _echo_falkordb(section=section)


@app.command(name="show")
def set_show(
    *,
    reveal: bool = typer.Option(
        False,  # noqa: FBT003
        "--reveal",
        help="显示完整 api_key/password",
    ),
) -> None:
    """显示当前配置, 默认掩码 api_key/password."""
    settings = load_settings()
    data: dict[str, Any] = settings.model_dump()
    if not reveal:
        for name in ("llm", "embedding", "reranker"):
            data[name]["api_key"] = _mask_secret(value=data[name]["api_key"])
        data["falkordb"]["password"] = _mask_secret(value=data["falkordb"]["password"])
    typer.echo(f"# settings path: {SETTINGS_PATH}")
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
