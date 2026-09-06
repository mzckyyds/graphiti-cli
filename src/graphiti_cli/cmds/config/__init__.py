"""CLI: ``config {show|set}``."""

import typer

from .set import set_embedder, set_falkordb, set_llm, set_reranker
from .show import show_config

__all__ = [
    "app",
]

app = typer.Typer(
    help="查看与写入 ~/.graphiti-cli/settings.json.",
    no_args_is_help=True,
)

# ======================================================================================
# config show
# ======================================================================================
app.command(name="show")(show_config)

# ======================================================================================
# config set
# ======================================================================================
set_cmd = typer.Typer(help="写入单项配置, 未传入的选项保持不变.")
set_cmd.command(name="llm")(set_llm)
set_cmd.command(name="embedder")(set_embedder)
set_cmd.command(name="reranker")(set_reranker)
set_cmd.command(name="falkordb")(set_falkordb)
app.add_typer(set_cmd, name="set")
