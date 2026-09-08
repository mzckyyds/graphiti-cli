"""CLI: ``graphiti-cli {config|episode|node|edge|triplet}``."""

from __future__ import annotations

import typer

from graphiti_cli.cmds import config_cmd, edge_cmd, episode_cmd, node_cmd, triplet_cmd

__all__ = [
    "app",
]


app = typer.Typer(
    help="Graphiti 时序知识图谱 CLI 工具.",
    no_args_is_help=True,
)
# CLI: ``graphiti-cli config``
app.add_typer(config_cmd, name="config")
# CLI: ``graphiti-cli episode``
app.add_typer(episode_cmd, name="episode")
# CLI: ``graphiti-cli node``
app.add_typer(node_cmd, name="node")
# CLI: ``graphiti-cli edge``
app.add_typer(edge_cmd, name="edge")
# CLI: ``graphiti-cli triplet``
app.add_typer(triplet_cmd, name="triplet")
