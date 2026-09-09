"""About `EntityEdge`."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import typer
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode
from graphiti_core.utils.datetime_utils import utc_now

from ._base import (
    EDGE_RESERVED_ATTRIBUTE_KEYS,
    delete_model,
    driver_for,
    dump_model,
    dump_models,
    echo_json,
    effective_gid_for,
    get_model,
    list_model,
    parse_attributes,
    parse_datetime,
    patch_model,
    run_async,
)

if TYPE_CHECKING:
    from graphiti_core import Graphiti

__all__ = [
    "edge_add",
    "edge_delete",
    "edge_get",
    "edge_list",
    "edge_patch",
]


# ======================================================================================
# CLI: ``graphiti-cli edge add ...``
# ======================================================================================
def edge_add(  # noqa: PLR0913
    *,
    uuid: str | None = typer.Option(
        None,
        "--uuid",
        help="Custom `EntityEdge` uuid",
    ),
    name: str = typer.Option(
        ...,
        "--name",
        help="`EntityEdge` name",
    ),
    fact: str = typer.Option(
        ...,
        "--fact",
        help="`EntityEdge` fact",
    ),
    valid_at: str | None = typer.Option(
        None,
        "--valid-at",
        help="ISO8601, `EntityEdge` valid start time",
    ),
    invalid_at: str | None = typer.Option(
        None,
        "--invalid-at",
        help="ISO8601, `EntityEdge` valid end time",
    ),
    expired_at: str | None = typer.Option(
        None,
        "--expired-at",
        help="ISO8601, `EntityEdge` expiration time",
    ),
    attribute: list[str] | None = typer.Option(
        None,
        "--attribute",
        help="`EntityEdge` attributes; KEY=VALUE format, VALUE is parsed as JSON",
    ),
    source_uuid: str = typer.Option(
        ...,
        "--source-uuid",
        help="`EntityEdge` source node uuid",
    ),
    target_uuid: str = typer.Option(
        ...,
        "--target-uuid",
        help="`EntityEdge` target node uuid",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Add an `EntityEdge` between two existing nodes(`EntityNode`).

    Will generate embeddings for `--fact`.
    """
    attributes = parse_attributes(
        pairs=attribute or [],
        reserved=EDGE_RESERVED_ATTRIBUTE_KEYS,
        label="`EntityEdge`",
    )

    async def _action(graphiti: Graphiti) -> EntityEdge:
        driver = await driver_for(graphiti=graphiti, group_id=group_id)
        effective_gid = effective_gid_for(graphiti=graphiti, group_id=group_id)
        source = await EntityNode.get_by_uuid(driver, source_uuid)
        target = await EntityNode.get_by_uuid(driver, target_uuid)
        edge = EntityEdge(
            uuid=uuid or str(uuid4()),
            group_id=effective_gid,
            source_node_uuid=source.uuid,
            target_node_uuid=target.uuid,
            name=name,
            fact=fact,
            attributes=attributes,
            created_at=utc_now(),
            valid_at=parse_datetime(value=valid_at, label="--valid-at")
            if valid_at is not None
            else None,
            invalid_at=parse_datetime(value=invalid_at, label="--invalid-at")
            if invalid_at is not None
            else None,
            expired_at=parse_datetime(value=expired_at, label="--expired-at")
            if expired_at is not None
            else None,
        )
        await edge.generate_embedding(graphiti.embedder)
        await edge.save(driver)
        return edge

    edge = run_async(action=_action)
    echo_json(data=dump_model(model=edge))


# ======================================================================================
# CLI: ``graphiti-cli edge get ...``
# ======================================================================================
def edge_get(
    *,
    uuid: str = typer.Option(
        ...,
        "--uuid",
        help="`EntityEdge` uuid",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Get a single `EntityEdge` by `--uuid`."""

    async def _action(graphiti: Graphiti) -> EntityEdge:
        return await get_model(
            graphiti=graphiti,
            model_cls=EntityEdge,
            group_id=group_id,
            uuid=uuid,
            label="EntityEdge",
        )

    edge = run_async(action=_action)
    echo_json(data=dump_model(model=edge))


# ======================================================================================
# CLI: ``graphiti-cli edge list ...``
# ======================================================================================
def edge_list(
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
            "if provided, only returns edges produced by it, "
            "--limit is ignored"
        ),
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """List `EntityEdge` by `--group-id` and optionally `--episode-uuid`."""

    async def _action(graphiti: Graphiti) -> list[EntityEdge]:
        if episode_uuid:
            graphiti.driver = await driver_for(graphiti=graphiti, group_id=group_id)
            result = await graphiti.get_nodes_and_edges_by_episode([episode_uuid])
            return list(result.edges)
        return await list_model(
            graphiti=graphiti,
            model_cls=EntityEdge,
            group_id=group_id,
            limit=limit,
        )

    edges = run_async(action=_action)
    echo_json(data=dump_models(models=edges))


# ======================================================================================
# CLI: ``graphiti-cli edge patch ...``
# ======================================================================================
def edge_patch(  # noqa: PLR0913
    *,
    uuid: str = typer.Option(
        ...,
        "--uuid",
        help="`EntityEdge` uuid",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="new `EntityEdge` name",
    ),
    fact: str | None = typer.Option(
        None,
        "--fact",
        help=(
            "new `EntityEdge` fact, "
            "automatically rebuilds fact vector after modification"
        ),
    ),
    valid_at: str | None = typer.Option(
        None,
        "--valid-at",
        help="ISO8601, `EntityEdge` valid start time",
    ),
    invalid_at: str | None = typer.Option(
        None,
        "--invalid-at",
        help="ISO8601, `EntityEdge` valid end time",
    ),
    expired_at: str | None = typer.Option(
        None,
        "--expired-at",
        help="ISO8601, `EntityEdge` expiration time",
    ),
    attribute: list[str] | None = typer.Option(
        None,
        "--attribute",
        help="`EntityEdge` attributes; KEY=VALUE format, VALUE is parsed as JSON",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Patch `EntityEdge` by `--uuid`."""
    attributes = parse_attributes(
        pairs=attribute or [],
        reserved=EDGE_RESERVED_ATTRIBUTE_KEYS,
        label="`EntityEdge`",
    )

    async def _action(graphiti: Graphiti) -> EntityEdge:
        async def _patch(edge: EntityEdge) -> None:
            if name is not None:
                edge.name = name
            if fact is not None:
                edge.fact = fact
                await edge.generate_embedding(graphiti.embedder)
            if valid_at is not None:
                edge.valid_at = parse_datetime(value=valid_at, label="--valid-at")
            if invalid_at is not None:
                edge.invalid_at = parse_datetime(value=invalid_at, label="--invalid-at")
            if expired_at is not None:
                edge.expired_at = parse_datetime(value=expired_at, label="--expired-at")
            if attributes:
                edge.attributes.update(attributes)

        return await patch_model(
            graphiti=graphiti,
            model_cls=EntityEdge,
            group_id=group_id,
            uuid=uuid,
            label="EntityEdge",
            patch=_patch,
        )

    edge = run_async(action=_action)
    echo_json(data=dump_model(model=edge))


# ======================================================================================
# CLI: ``graphiti-cli edge delete ...``
# ======================================================================================
def edge_delete(
    *,
    uuid: str = typer.Option(
        ...,
        "--uuid",
        help="`EntityEdge` uuid",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Delete `EntityEdge` by `--uuid`."""

    async def _action(graphiti: Graphiti) -> str:
        return await delete_model(
            graphiti=graphiti,
            model_cls=EntityEdge,
            group_id=group_id,
            uuid=uuid,
            label="EntityEdge",
        )

    deleted = run_async(action=_action)
    typer.echo(f"Deleted `EntityEdge`: {deleted}")
