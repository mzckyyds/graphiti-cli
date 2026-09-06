"""Graphiti 实例的构建逻辑, 供各子命令复用.

模型全部走 OpenAI 兼容端点, 配置统一从 ``~/.graphiti-cli/settings.json`` 读取:
- LLM:       通用 OpenAIGenericClient(json_schema 结构化输出, 关闭深度思考)
- Embedding: 通用 OpenAIEmbedder
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
def _require_config(*, value: str, label: str, hint: str) -> str:
    """校验配置项已填写.

    Args:
        value: 配置项当前值.
        label: 配置项名称, 用于报错.
        hint: 对应的修复命令.

    Returns:
        原始值.

    Raises:
        ValueError: 配置项为空时.

    """
    if not value:
        raise ValueError(f"配置缺失: {label!r}, 请先运行 graphiti-cli set {hint}")
    return value


def _build_openai_client(*, api_key: str, base_url: str) -> AsyncOpenAI:
    """构建注入了 enable_thinking=False 的 AsyncOpenAI 客户端.

    通用客户端没有 extra_body 注入口子, 这里在 client 层包装 create 方法,
    让 LLM 与 reranker 的每次请求都关闭深度思考, 避免 qwen3 卡在推理阶段.

    Args:
        api_key: API Key.
        base_url: OpenAI 兼容端点地址.

    Returns:
        注入 extra_body 后的 AsyncOpenAI 客户端.

    """
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    original_create = client.chat.completions.create

    async def create_without_thinking(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        extra_body: dict[str, Any] = kwargs.pop("extra_body", None) or {}
        kwargs["extra_body"] = {**extra_body, "enable_thinking": False}
        return await original_create(*args, **kwargs)

    client.chat.completions.create = create_without_thinking  # type: ignore[method-assign]
    return client


def build_graphiti(*, settings: Settings | None = None) -> Graphiti:
    """按配置构建 Graphiti 实例.

    LLM/Embedding/Reranker 三个配置段各自独立, 互不复用.

    Args:
        settings: 全局配置, 缺省时从配置文件加载.

    Returns:
        就绪的 Graphiti 实例.

    Raises:
        ValueError: 任一配置段的必填项缺失时.

    """
    settings = settings or load_settings()
    llm_cfg = settings.llm
    llm_base_url = _require_config(
        value=llm_cfg.base_url,
        label="llm.base_url",
        hint="llm --base-url <URL>",
    )
    llm_model = _require_config(
        value=llm_cfg.model,
        label="llm.model",
        hint="llm --model <NAME>",
    )
    llm_api_key = _require_config(
        value=llm_cfg.api_key,
        label="llm.api_key",
        hint="llm --api-key <KEY>",
    )
    embedding_cfg = settings.embedding
    embedding_model = _require_config(
        value=embedding_cfg.model,
        label="embedding.model",
        hint="embedding --model <NAME>",
    )

    llm_config = LLMConfig(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model=llm_model,
        small_model=llm_model,
    )
    openai_client = _build_openai_client(api_key=llm_api_key, base_url=llm_base_url)
    llm_client = OpenAIGenericClient(config=llm_config, client=openai_client)

    embedding_base_url = _require_config(
        value=embedding_cfg.base_url,
        label="embedding.base_url",
        hint="embedding --base-url <URL>",
    )
    embedding_api_key = _require_config(
        value=embedding_cfg.api_key,
        label="embedding.api_key",
        hint="embedding --api-key <KEY>",
    )
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=embedding_api_key,
            base_url=embedding_base_url,
            embedding_model=embedding_model,
            embedding_dim=embedding_cfg.dim,
        ),
    )

    reranker_cfg = settings.reranker
    reranker_base_url = _require_config(
        value=reranker_cfg.base_url,
        label="reranker.base_url",
        hint="reranker --base-url <URL>",
    )
    reranker_model = _require_config(
        value=reranker_cfg.model,
        label="reranker.model",
        hint="reranker --model <NAME>",
    )
    reranker_api_key = _require_config(
        value=reranker_cfg.api_key,
        label="reranker.api_key",
        hint="reranker --api-key <KEY>",
    )
    reranker_config = LLMConfig(
        api_key=reranker_api_key,
        base_url=reranker_base_url,
        model=reranker_model,
    )
    reranker = OpenAIRerankerClient(
        config=reranker_config,
        client=_build_openai_client(
            api_key=reranker_api_key,
            base_url=reranker_base_url,
        ),
    )

    # FalkorDB(Redis 协议, 默认端口 6379)
    falkor = settings.falkordb
    falkor_driver = FalkorDriver(
        host=falkor.host,
        port=falkor.port,
        username=falkor.username or None,
        password=falkor.password or None,
        database=falkor.database,
    )

    return Graphiti(
        graph_driver=falkor_driver,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=reranker,
    )
