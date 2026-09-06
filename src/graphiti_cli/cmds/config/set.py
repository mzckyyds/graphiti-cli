"""CLI: ``config set {llm|embedder|reranker|falkordb}``.

只更新显式传入的选项, 其余字段保持不变.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import typer

from graphiti_cli.settings import load_settings, save_settings

from ._base import mask_secret

if TYPE_CHECKING:
    from graphiti_cli.settings import (
        EmbedderSettings,
        FalkorDBSettings,
        LLMSettings,
        RerankerSettings,
    )

    # 三个模型服务配置段的公共字段类型, 即 base_url/model/api_key 三项
    ProviderSettings = LLMSettings | EmbedderSettings | RerankerSettings

__all__ = [
    "set_embedder",
    "set_falkordb",
    "set_llm",
    "set_reranker",
]


# ======================================================================================
# 内部工具
# ======================================================================================
def _parse_extra_body(*, raw: str) -> dict[str, Any]:
    """解析 --extra-body 传入的 JSON 字符串.

    Args:
        raw: JSON 对象字符串, 如 ``'{"enable_thinking": false}'``.

    Returns:
        解析后的字典.

    Raises:
        BadParameter: 不是合法的 JSON 对象时.

    """
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"--extra-body 不是合法 JSON: {e}") from e
    if not isinstance(value, dict):
        raise typer.BadParameter("--extra-body 必须是 JSON 对象")
    # NOTE: JSON 对象的 key 恒为字符串, json.loads 返回 Any 需显式收窄
    return cast("dict[str, Any]", value)


def _update_model_provider(
    *,
    section: ProviderSettings,
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


def _echo_provider(
    *,
    section: ProviderSettings,
    name: str,
    extra_body: dict[str, Any] | None = None,
) -> None:
    """回显某个模型服务配置段的当前值(api_key 掩码).

    Args:
        section: 模型服务配置段.
        name: 配置段名称.
        extra_body: LLM/Reranker 特有的额外请求体字段, Embedder 不展示.

    """
    suffix = "" if extra_body is None else f", extra_body={extra_body!r}"
    typer.echo(
        f"{name}: base_url={section.base_url!r}, "
        f"model={section.model!r}, "
        f"api_key={mask_secret(value=section.api_key)!r}"
        f"{suffix}",
    )


def _echo_falkordb(*, section: FalkorDBSettings) -> None:
    """回显 FalkorDB 配置段(password 掩码).

    Args:
        section: FalkorDB 配置段.

    """
    typer.echo(
        f"falkordb: host={section.host!r}, port={section.port!r}, "
        f"username={section.username!r}, "
        f"password={mask_secret(value=section.password)!r}, "
        f"database={section.database!r}",
    )


# ======================================================================================
# CLI: ``config set llm``
# ======================================================================================
def set_llm(
    *,
    base_url: str | None = typer.Option(None, "--base-url", help="OpenAI 兼容端点地址"),
    model: str | None = typer.Option(None, "--model", help="LLM 模型名"),
    api_key: str | None = typer.Option(None, "--api-key", help="API Key"),
    extra_body: str | None = typer.Option(
        None,
        "--extra-body",
        help="额外请求体字段(JSON 对象), 如 '{\"enable_thinking\": false}'",
    ),
) -> None:
    """配置 LLM 服务, 未传入的选项保持不变."""
    settings = load_settings()
    _update_model_provider(
        section=settings.llm,
        base_url=base_url,
        model=model,
        api_key=api_key,
    )
    if extra_body is not None:
        settings.llm.extra_body = _parse_extra_body(raw=extra_body)
    save_settings(settings=settings)
    _echo_provider(
        section=settings.llm,
        name="llm",
        extra_body=settings.llm.extra_body,
    )


# ======================================================================================
# CLI: ``config set embedder``
# ======================================================================================
def set_embedder(
    *,
    base_url: str | None = typer.Option(None, "--base-url", help="OpenAI 兼容端点地址"),
    model: str | None = typer.Option(None, "--model", help="Embedding 模型名"),
    api_key: str | None = typer.Option(None, "--api-key", help="API Key"),
    dim: int | None = typer.Option(None, "--dim", help="向量维度, 默认 1024"),
) -> None:
    """配置 Embedder 服务, 未传入的选项保持不变."""
    settings = load_settings()
    _update_model_provider(
        section=settings.embedder,
        base_url=base_url,
        model=model,
        api_key=api_key,
    )
    if dim is not None:
        settings.embedder.dim = dim
    save_settings(settings=settings)
    _echo_provider(section=settings.embedder, name="embedder")


# ======================================================================================
# CLI: ``config set reranker``
# ======================================================================================
def set_reranker(
    *,
    base_url: str | None = typer.Option(None, "--base-url", help="OpenAI 兼容端点地址"),
    model: str | None = typer.Option(None, "--model", help="Reranker 模型名"),
    api_key: str | None = typer.Option(None, "--api-key", help="API Key"),
    extra_body: str | None = typer.Option(
        None,
        "--extra-body",
        help="额外请求体字段(JSON 对象), 如 '{\"enable_thinking\": false}'",
    ),
) -> None:
    """配置 Reranker 服务, 未传入的选项保持不变."""
    settings = load_settings()
    _update_model_provider(
        section=settings.reranker,
        base_url=base_url,
        model=model,
        api_key=api_key,
    )
    if extra_body is not None:
        settings.reranker.extra_body = _parse_extra_body(raw=extra_body)
    save_settings(settings=settings)
    _echo_provider(
        section=settings.reranker,
        name="reranker",
        extra_body=settings.reranker.extra_body,
    )


# ======================================================================================
# CLI: ``config set falkordb``
# ======================================================================================
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
