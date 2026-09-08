"""CLI: ``graphiti-cli {config|edge|episode|node|search|triplet}``."""

import typer

from .config import app as config_cmd
from .edge import app as edge_cmd
from .episode import app as episode_cmd
from .node import app as node_cmd
from .search import hybrid_search
from .triplet import app as triplet_cmd

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
# CLI: ``graphiti-cli search``(单命令, 直接注册以支持 ``search QUERY``)
app.command(name="search", help="混合检索实体节点与关系边(事实).")(hybrid_search)
# CLI: ``graphiti-cli triplet``
app.add_typer(triplet_cmd, name="triplet")
