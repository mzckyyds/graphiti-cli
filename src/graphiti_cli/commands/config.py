"""About Configuration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import typer

from graphiti_cli.settings import (
    SETTINGS_PATH,
    Settings,
    load_settings,
    save_settings,
)

if TYPE_CHECKING:
    from graphiti_cli.settings import (
        EmbedderSettings,
        FalkorDBSettings,
        LLMSettings,
        RerankerSettings,
    )

    # The common field types for the three model service configuration sections:
    # - base_url
    # - model_name
    # - api_key
    ProviderSettings = LLMSettings | EmbedderSettings | RerankerSettings

__all__ = [
    "config_set_embedder",
    "config_set_falkordb",
    "config_set_llm",
    "config_set_reranker",
    "config_show",
]


# ======================================================================================
# Helper Functions
# ======================================================================================
def _load_settings_or_exit() -> Settings:
    try:
        return load_settings()
    except ValueError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None


def _mask_secret(
    *,
    value: str,
) -> str:
    if not value:
        return ""
    return f"{value[:4]}***"


def _parse_extra_body(
    *,
    raw: str,
) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"--extra-body is not valid JSON: {e}") from e
    if not isinstance(value, dict):
        raise typer.BadParameter("--extra-body must be a JSON object")
    return cast("dict[str, Any]", value)


def _update_model_provider(
    *,
    section: ProviderSettings,
    base_url: str | None,
    model_name: str | None,
    api_key: str | None,
) -> None:
    if base_url is not None:
        section.base_url = base_url.rstrip("/")
    if model_name is not None:
        section.model_name = model_name
    if api_key is not None:
        section.api_key = api_key


def _echo_provider(
    *,
    section: ProviderSettings,
    name: str,
    extra_body: dict[str, Any] | None = None,
) -> None:
    suffix = "" if extra_body is None else f", extra_body={extra_body!r}"
    typer.echo(
        f"{name}: base_url={section.base_url!r}, "
        f"model={section.model_name!r}, "
        f"api_key={_mask_secret(value=section.api_key)!r}"
        f"{suffix}",
    )


def _echo_falkordb(
    *,
    section: FalkorDBSettings,
) -> None:
    typer.echo(
        f"falkordb: host={section.host!r}, port={section.port!r}, "
        f"username={section.username!r}, "
        f"password={_mask_secret(value=section.password)!r}, "
        f"database={section.database!r}",
    )


# ======================================================================================
# CLI: ``graphiti-cli config set llm``
# ======================================================================================
def config_set_llm(
    *,
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="OpenAI compatible endpoint URL",
    ),
    model_name: str | None = typer.Option(
        None,
        "--model-name",
        help="LLM model name",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="API key",
    ),
    extra_body: str | None = typer.Option(
        None,
        "--extra-body",
        help=(
            "Extra request body fields (JSON object), "
            "e.g., '{\"enable_thinking\": false}'"
        ),
    ),
) -> None:
    """Update LLM service configuration.

    Options not provided will remain unchanged.
    """
    settings = _load_settings_or_exit()
    _update_model_provider(
        section=settings.llm,
        base_url=base_url,
        model_name=model_name,
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
# CLI: ``graphiti-cli config set embedder``
# ======================================================================================
def config_set_embedder(
    *,
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="OpenAI compatible endpoint URL",
    ),
    model_name: str | None = typer.Option(
        None,
        "--model-name",
        help="Embedder model name",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="API key",
    ),
    dim: int | None = typer.Option(
        None,
        "--dim",
        help="Dimensionality of the embedding vectors, default is 1024",
    ),
) -> None:
    """Update Embedder service configuration.

    Options not provided will remain unchanged.
    """
    settings = _load_settings_or_exit()
    _update_model_provider(
        section=settings.embedder,
        base_url=base_url,
        model_name=model_name,
        api_key=api_key,
    )
    if dim is not None:
        settings.embedder.dim = dim
    save_settings(settings=settings)
    _echo_provider(section=settings.embedder, name="embedder")


# ======================================================================================
# CLI: ``graphiti-cli config set reranker``
# ======================================================================================
def config_set_reranker(
    *,
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="OpenAI compatible endpoint URL",
    ),
    model_name: str | None = typer.Option(
        None,
        "--model",
        help="Reranker model name",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="API key",
    ),
    extra_body: str | None = typer.Option(
        None,
        "--extra-body",
        help=(
            "Extra request body fields (JSON object), "
            "e.g., '{\"enable_thinking\": false}'"
        ),
    ),
) -> None:
    """Update Reranker service configuration.

    Options not provided will remain unchanged.
    """
    settings = _load_settings_or_exit()
    _update_model_provider(
        section=settings.reranker,
        base_url=base_url,
        model_name=model_name,
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
# CLI: ``graphiti-cli config set falkordb``
# ======================================================================================
def config_set_falkordb(
    *,
    host: str | None = typer.Option(
        None,
        "--host",
        help="FalkorDB host",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        help="FalkorDB port",
    ),
    username: str | None = typer.Option(
        None,
        "--username",
        help="Username, pass an empty string if no authentication is required",
    ),
    password: str | None = typer.Option(
        None,
        "--password",
        help="Password, pass an empty string if no authentication is required",
    ),
    database: str | None = typer.Option(
        None,
        "--database",
        help=(
            "Graph name (default graph for the connection); "
            "note that it is different from the --group-id in various commands. "
            "--group-id is the data partition ID, "
            "and when a non-default partition is passed, "
            "the data falls into the graph with the same name."
        ),
    ),
) -> None:
    """Configure FalkorDB connection.

    Options not provided will remain unchanged.
    """
    settings = _load_settings_or_exit()
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


# ======================================================================================
# CLI: ``graphiti-cli config show``
# ======================================================================================
def config_show(
    *,
    reveal: bool = typer.Option(
        False,  # noqa: FBT003
        "--reveal",
        help="Show full api_key/password",
    ),
) -> None:
    """Show current configuration, masking api_key/password by default."""
    settings = _load_settings_or_exit()
    data: dict[str, Any] = settings.model_dump()
    if not reveal:
        for name in ("llm", "embedder", "reranker"):
            data[name]["api_key"] = _mask_secret(value=data[name]["api_key"])
        data["falkordb"]["password"] = _mask_secret(value=data["falkordb"]["password"])
    typer.echo(f"# settings path: {SETTINGS_PATH}")
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
