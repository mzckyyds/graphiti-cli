"""Graphiti 实例的构建逻辑, 供各子命令复用.

模型全部走 OpenAI 兼容端点, 配置统一从 ``~/.graphiti-cli/settings.json`` 读取:
- LLM:       通用 OpenAIGenericClient(json_schema 结构化输出, extra_body 可注入)
- Embedder: 通用 OpenAIEmbedder
- Reranker:  通用 OpenAIRerankerClient(logprobs 零样本打分)
"""

from __future__ import annotations

from typing import Any

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from openai import AsyncOpenAI

from graphiti_cli.settings import Settings, load_settings

__all__ = [
    "build_graphiti",
]


# ======================================================================================
# OpenAI 兼容客户端
# ======================================================================================
def _validate_config(
    *,
    value: str,
    label: str,
    hint: str,
) -> None:
    """校验配置项已填写.

    Args:
        value: 配置项当前值.
        label: 配置项名称, 用于报错.
        hint: 对应的修复命令.

    Raises:
        ValueError: 配置项为空时.

    """
    if len(value.strip()) == 0:
        raise ValueError(f"配置缺失: {label!r}, 请先运行 graphiti-cli set {hint}")


def _build_openai_client(
    *,
    api_key: str,
    base_url: str,
    extra_body: dict[str, Any],
) -> AsyncOpenAI:
    """构建注入了 extra_body 的 AsyncOpenAI 客户端.

    通用客户端没有 extra_body 注入口子, 这里在 client 层包装 create 方法,
    某些大模型通过 extra_body 接收额外参数来启停某些功能, 例如关闭深度思考.

    Args:
        api_key: API Key.
        base_url: OpenAI 兼容端点地址.
        extra_body: 额外的请求体字段, 会在每次请求时注入.

    Returns:
        注入 extra_body 后的 AsyncOpenAI 客户端.

    """
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    original_create = client.chat.completions.create

    async def create_with_extra_body(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        kwargs["extra_body"] = {
            **(kwargs.pop("extra_body", None) or {}),
            **extra_body,
        }
        return await original_create(*args, **kwargs)

    client.chat.completions.create = create_with_extra_body  # type: ignore[method-assign]
    return client


def build_graphiti(
    *,
    settings: Settings | None = None,
) -> Graphiti:
    """按配置构建 Graphiti 实例.

    LLM/Embedder/Reranker 三个配置段各自独立, 互不复用.

    Args:
        settings: 全局配置, 缺省时从配置文件加载.

    Returns:
        就绪的 Graphiti 实例.

    Raises:
        ValueError: 任一配置段的必填项缺失时.

    """
    cfg = settings or load_settings()

    # base_url/model/api_key 校验
    _validate_config(
        value=cfg.llm.base_url,
        label="llm.base_url",
        hint="llm --base-url <URL>",
    )
    _validate_config(
        value=cfg.llm.model,
        label="llm.model",
        hint="llm --model <NAME>",
    )
    _validate_config(
        value=cfg.llm.api_key,
        label="llm.api_key",
        hint="llm --api-key <KEY>",
    )
    _validate_config(
        value=cfg.embedder.model,
        label="embedder.model",
        hint="embedder --model <NAME>",
    )
    _validate_config(
        value=cfg.embedder.base_url,
        label="embedder.base_url",
        hint="embedder --base-url <URL>",
    )
    _validate_config(
        value=cfg.embedder.api_key,
        label="embedder.api_key",
        hint="embedder --api-key <KEY>",
    )
    _validate_config(
        value=cfg.reranker.base_url,
        label="reranker.base_url",
        hint="reranker --base-url <URL>",
    )
    _validate_config(
        value=cfg.reranker.model,
        label="reranker.model",
        hint="reranker --model <NAME>",
    )
    _validate_config(
        value=cfg.reranker.api_key,
        label="reranker.api_key",
        hint="reranker --api-key <KEY>",
    )

    # Driver/LLM/Embedder/Reranker 客户端
    driver = FalkorDriver(
        host=cfg.falkordb.host,
        port=cfg.falkordb.port,
        username=cfg.falkordb.username or None,
        password=cfg.falkordb.password or None,
        database=cfg.falkordb.database,
    )
    llm = OpenAIGenericClient(
        config=LLMConfig(
            api_key=cfg.llm.api_key,
            base_url=cfg.llm.base_url,
            model=cfg.llm.model,
            small_model=cfg.llm.model,
        ),
        client=_build_openai_client(
            api_key=cfg.llm.api_key,
            base_url=cfg.llm.base_url,
            extra_body=cfg.llm.extra_body,
        ),
    )
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=cfg.embedder.api_key,
            base_url=cfg.embedder.base_url,
            embedding_model=cfg.embedder.model,
            embedding_dim=cfg.embedder.dim,
        ),
    )
    reranker = OpenAIRerankerClient(
        config=LLMConfig(
            api_key=cfg.reranker.api_key,
            base_url=cfg.reranker.base_url,
            model=cfg.reranker.model,
        ),
        client=_build_openai_client(
            api_key=cfg.reranker.api_key,
            base_url=cfg.reranker.base_url,
            extra_body=cfg.reranker.extra_body,
        ),
    )

    return Graphiti(
        graph_driver=driver,
        llm_client=llm,
        embedder=embedder,
        cross_encoder=reranker,
    )
