"""Build `Graphiti` instance according to the configuration.

All models use OpenAI-compatible endpoints.
The configuration is uniformly read from ``~/.graphiti-cli/settings.json``:
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


def _validate_config(
    *,
    value: str,
    label: str,
    hint: str,
) -> None:
    if len(value.strip()) == 0:
        raise ValueError(
            f"Missing configuration: {label!r}, "
            f"please `run graphiti-cli config set {hint}`"
        )


def _build_openai_client(
    *,
    api_key: str,
    base_url: str,
    extra_body: dict[str, Any],
) -> AsyncOpenAI:
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
    """Build a Graphiti instance according to the configuration.

    Args:
        settings: global configuration, loaded from the configuration file if `None`

    Returns:
        A ready-to-use Graphiti instance.

    Raises:
        ValueError: Raised when any required configuration section is missing.

    """
    cfg = settings or load_settings()

    # validate base_url/model/api_key
    _validate_config(
        value=cfg.llm.base_url,
        label="llm.base_url",
        hint="llm --base-url <URL>",
    )
    _validate_config(
        value=cfg.llm.model_name,
        label="llm.model",
        hint="llm --model <NAME>",
    )
    _validate_config(
        value=cfg.llm.api_key,
        label="llm.api_key",
        hint="llm --api-key <KEY>",
    )
    _validate_config(
        value=cfg.embedder.base_url,
        label="embedder.base_url",
        hint="embedder --base-url <URL>",
    )
    _validate_config(
        value=cfg.embedder.model_name,
        label="embedder.model",
        hint="embedder --model <NAME>",
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
        value=cfg.reranker.model_name,
        label="reranker.model",
        hint="reranker --model <NAME>",
    )
    _validate_config(
        value=cfg.reranker.api_key,
        label="reranker.api_key",
        hint="reranker --api-key <KEY>",
    )

    # Driver/LLM/Embedder/Reranker clients
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
            model=cfg.llm.model_name,
            small_model=cfg.llm.model_name,
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
            embedding_model=cfg.embedder.model_name,
            embedding_dim=cfg.embedder.dim,
        ),
    )
    reranker = OpenAIRerankerClient(
        config=LLMConfig(
            api_key=cfg.reranker.api_key,
            base_url=cfg.reranker.base_url,
            model=cfg.reranker.model_name,
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
