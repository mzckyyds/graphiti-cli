"""About `EntityNode`."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import typer
from graphiti_core.nodes import EntityNode
from graphiti_core.utils.datetime_utils import utc_now

from ._base import (
    delete_model,
    driver_for,
    dump_model,
    dump_models,
    echo_json,
    effective_gid_for,
    get_model,
    list_model,
    parse_attributes,
    patch_model,
    run_async,
)

if TYPE_CHECKING:
    from graphiti_core import Graphiti

__all__ = [
    "node_add",
    "node_delete",
    "node_get",
    "node_list",
    "node_patch",
]


# ======================================================================================
# CLI: ``graphiti-cli node add ...``
# ======================================================================================
def node_add(
    *,
    uuid: str | None = typer.Option(
        None,
        "--uuid",
        help="Custom `EntityNode` uuid",
    ),
    name: str = typer.Argument(
        ...,
        help="`EntityNode` name",
    ),
    summary: str = typer.Option(
        "",
        "--summary",
        help="`EntityNode` summary",
    ),
    attribute: list[str] | None = typer.Option(
        None,
        "--attribute",
        help="`EntityNode` attributes; KEY=VALUE format, VALUE is parsed as JSON",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Add an `EntityNode`.

    Will generate embeddings for `--name`.
    """
    attributes = parse_attributes(pairs=attribute or [])

    async def _action(graphiti: Graphiti) -> EntityNode:
        driver = driver_for(graphiti=graphiti, group_id=group_id)
        effective_gid = effective_gid_for(graphiti=graphiti, group_id=group_id)
        node = EntityNode(
            name=name,
            group_id=effective_gid,
            summary=summary,
            attributes=attributes,
            uuid=uuid or str(uuid4()),
            created_at=utc_now(),
        )
        await node.generate_name_embedding(graphiti.embedder)
        await node.save(driver)
        return node

    node = run_async(action=_action)
    echo_json(data=dump_model(model=node))


# ======================================================================================
# CLI: ``graphiti-cli node get ...``
# ======================================================================================
def node_get(
    *,
    uuid: str = typer.Argument(
        ...,
        help="`EntityNode` uuid",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Get a single `EntityNode` by `--uuid`."""

    async def _action(graphiti: Graphiti) -> EntityNode:
        return await get_model(
            graphiti=graphiti,
            model_cls=EntityNode,
            group_id=group_id,
            uuid=uuid,
            label="EntityNode",
        )

    node = run_async(action=_action)
    echo_json(data=dump_model(model=node))


# ======================================================================================
# CLI: ``graphiti-cli node list ...``
# ======================================================================================
def node_list(
    *,
    limit: int = typer.Option(
        10,
        "--limit",
        min=1,
        help="maximum number to list per partition",
    ),
    episode_uuid: str | None = typer.Option(
        None,
        "--episode-uuid",
        help=(
            "`EpisodeNode` uuid; "
            "if provided, only returns nodes produced by it, "
            "--limit is ignored"
        ),
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """List `EntityNode` by `--group-id` and optionally `--episode-uuid`."""

    async def _action(graphiti: Graphiti) -> list[EntityNode]:
        if episode_uuid:
            graphiti.driver = driver_for(graphiti=graphiti, group_id=group_id)
            result = await graphiti.get_nodes_and_edges_by_episode([episode_uuid])
            return list(result.nodes)
        return await list_model(
            graphiti=graphiti,
            model_cls=EntityNode,
            group_id=group_id,
            limit=limit,
        )

    nodes = run_async(action=_action)
    echo_json(data=dump_models(models=nodes))


# ======================================================================================
# CLI: ``graphiti-cli node patch ...``
# ======================================================================================
def node_patch(
    *,
    uuid: str = typer.Argument(
        ...,
        help="`EntityNode` uuid",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="new `EntityNode` name",
    ),
    summary: str | None = typer.Option(
        None,
        "--summary",
        help=(
            "new `EntityNode` summary, "
            "automatically rebuilds summary vector after modification"
        ),
    ),
    attribute: list[str] | None = typer.Option(
        None,
        "--attribute",
        help="`EntityNode` attributes; KEY=VALUE format, VALUE is parsed as JSON",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Patch `EntityNode` by `--uuid`."""
    attributes = parse_attributes(pairs=attribute or [])

    async def _action(graphiti: Graphiti) -> EntityNode:
        async def _patch(node: EntityNode) -> None:
            if name is not None:
                node.name = name
                await node.generate_name_embedding(graphiti.embedder)
            if summary is not None:
                node.summary = summary
            if attributes:
                node.attributes.update(attributes)

        return await patch_model(
            graphiti=graphiti,
            model_cls=EntityNode,
            group_id=group_id,
            uuid=uuid,
            label="EntityNode",
            patch=_patch,
        )

    node = run_async(action=_action)
    echo_json(data=dump_model(model=node))


# ======================================================================================
# CLI: ``graphiti-cli node delete ...``
# ======================================================================================
def node_delete(
    *,
    uuid: str = typer.Argument(
        ...,
        help="`EntityNode` uuid",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Delete `EntityNode` by `--uuid`.

    Will also delete all edges connected to this node.
    """

    async def _action(graphiti: Graphiti) -> str:
        return await delete_model(
            graphiti=graphiti,
            model_cls=EntityNode,
            group_id=group_id,
            uuid=uuid,
            label="EntityNode",
        )

    deleted = run_async(action=_action)
    typer.echo(f"Deleted `EntityNode`: {deleted}")
