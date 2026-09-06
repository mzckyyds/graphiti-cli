"""``config show`` 子命令.

展示当前配置, 默认掩码 api_key/password.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from graphiti_cli.settings import SETTINGS_PATH, load_settings

from ._base import mask_secret

__all__ = [
    "show",
]


def show(
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
        for name in ("llm", "embedder", "reranker"):
            data[name]["api_key"] = mask_secret(value=data[name]["api_key"])
        data["falkordb"]["password"] = mask_secret(value=data["falkordb"]["password"])
    typer.echo(f"# settings path: {SETTINGS_PATH}")
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
