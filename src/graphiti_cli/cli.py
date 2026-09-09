"""CLI: ``graphiti-cli {config|edge|episode|node|search|triplet} ...``."""

import typer

from .commands import (
    append_triplet,
    config_set_embedder,
    config_set_falkordb,
    config_set_llm,
    config_set_reranker,
    config_show,
    edge_add,
    edge_delete,
    edge_get,
    edge_list,
    edge_patch,
    episode_add,
    episode_delete,
    episode_get,
    episode_list,
    hybrid_search,
    node_add,
    node_delete,
    node_get,
    node_list,
    node_patch,
)

__all__ = [
    "app",
]


app = typer.Typer(
    help="CLI for Graphiti.",
    no_args_is_help=True,
)


# ======================================================================================
# CLI: ``graphiti-cli config...``
# ======================================================================================
config_cli = typer.Typer(
    help="Read and write configuration file (~/.graphiti-cli/settings.json).",
    no_args_is_help=True,
)

# show
config_cli.command(name="show")(config_show)

# set
config_set_cli = typer.Typer(
    help="Write individual configuration items; options not passed remain unchanged."
)
config_set_cli.command(name="llm")(config_set_llm)
config_set_cli.command(name="embedder")(config_set_embedder)
config_set_cli.command(name="reranker")(config_set_reranker)
config_set_cli.command(name="falkordb")(config_set_falkordb)
config_cli.add_typer(config_set_cli, name="set")

app.add_typer(config_cli, name="config")

# ======================================================================================
# CLI: ``graphiti-cli episode ...``
# ======================================================================================
episode_cli = typer.Typer(
    help="Manage `EpisodeNode`: add/get/list/delete.",
    no_args_is_help=True,
)

episode_cli.command(name="add")(episode_add)
episode_cli.command(name="delete")(episode_delete)
episode_cli.command(name="get")(episode_get)
episode_cli.command(name="list")(episode_list)

app.add_typer(episode_cli, name="episode")

# ======================================================================================
# CLI: ``graphiti-cli node ...``
# ======================================================================================
node_cli = typer.Typer(
    help="Manage `EntityNode`: add/get/list/patch/delete.",
    no_args_is_help=True,
)

node_cli.command(name="add")(node_add)
node_cli.command(name="delete")(node_delete)
node_cli.command(name="get")(node_get)
node_cli.command(name="list")(node_list)
node_cli.command(name="patch")(node_patch)

app.add_typer(node_cli, name="node")

# ======================================================================================
# CLI: ``graphiti-cli edge ...``
# ======================================================================================
edge_cli = typer.Typer(
    help="Manage `EntityEdge`: add/get/list/patch/delete.",
    no_args_is_help=True,
)

edge_cli.command(name="add")(edge_add)
edge_cli.command(name="delete")(edge_delete)
edge_cli.command(name="get")(edge_get)
edge_cli.command(name="list")(edge_list)
edge_cli.command(name="patch")(edge_patch)

app.add_typer(edge_cli, name="edge")


# ======================================================================================
# CLI: ``graphiti-cli search ...``
# ======================================================================================
app.command(name="search")(hybrid_search)


# ======================================================================================
# CLI: ``graphiti-cli triplet ...``
# ======================================================================================
app.command(name="triplet")(append_triplet)
