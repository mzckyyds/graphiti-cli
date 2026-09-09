"""Append triplets: (`EntityNode`, `EntityEdge`, `EntityNode`)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import typer
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode
from graphiti_core.utils.datetime_utils import utc_now

from ._base import (
    EDGE_RESERVED_ATTRIBUTE_KEYS,
    NODE_RESERVED_ATTRIBUTE_KEYS,
    driver_for,
    dump_models,
    echo_json,
    effective_gid_for,
    parse_attributes,
    parse_datetime,
    run_async,
)

if TYPE_CHECKING:
    from graphiti_core import Graphiti
    from graphiti_core.graphiti import AddTripletResults

__all__ = [
    "append_triplet",
]


def append_triplet(  # noqa: PLR0913
    *,
    source_uuid: str | None = typer.Option(
        None,
        "--source-uuid",
        help="custom source `EntityNode` uuid.",
    ),
    source_name: str = typer.Option(
        ...,
        "--source-name",
        help="source `EntityNode` name.",
    ),
    source_summary: str | None = typer.Option(
        None,
        "--source-summary",
        help="source `EntityNode` summary.",
    ),
    source_attribute: list[str] | None = typer.Option(
        None,
        "--source-attribute",
        help=(
            "source `EntityNode` attributes; KEY=VALUE format, VALUE is parsed as JSON"
        ),
    ),
    target_uuid: str | None = typer.Option(
        None,
        "--target-uuid",
        help="custom target `EntityNode` uuid.",
    ),
    target_name: str = typer.Option(
        ...,
        "--target-name",
        help="target `EntityNode` name.",
    ),
    target_summary: str | None = typer.Option(
        None,
        "--target-summary",
        help="target `EntityNode` summary.",
    ),
    target_attribute: list[str] | None = typer.Option(
        None,
        "--target-attribute",
        help=(
            "target `EntityNode` attributes; KEY=VALUE format, VALUE is parsed as JSON"
        ),
    ),
    edge_uuid: str | None = typer.Option(
        None,
        "--edge-uuid",
        help="custom `EntityEdge` uuid.",
    ),
    edge_name: str = typer.Option(
        ...,
        "--edge-name",
        help="`EntityEdge` name.",
    ),
    edge_fact: str = typer.Option(
        ...,
        "--edge-fact",
        help="`EntityEdge` fact.",
    ),
    edge_valid_at: str | None = typer.Option(
        None,
        "--edge-valid-at",
        help="ISO8601, `EntityEdge` valid start time",
    ),
    edge_invalid_at: str | None = typer.Option(
        None,
        "--edge-invalid-at",
        help="ISO8601, `EntityEdge` valid end time",
    ),
    edge_expired_at: str | None = typer.Option(
        None,
        "--edge-expired-at",
        help="ISO8601, `EntityEdge` expiration time",
    ),
    edge_attribute: list[str] | None = typer.Option(
        None,
        "--edge-attribute",
        help="`EntityEdge` attributes; KEY=VALUE format, VALUE is parsed as JSON",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Append triplets: (`EntityNode`, `EntityEdge`, `EntityNode`)."""
    source_attributes = parse_attributes(
        pairs=source_attribute or [],
        reserved=NODE_RESERVED_ATTRIBUTE_KEYS,
        label="`EntityNode`",
    )
    target_attributes = parse_attributes(
        pairs=target_attribute or [],
        reserved=NODE_RESERVED_ATTRIBUTE_KEYS,
        label="`EntityNode`",
    )
    edge_attributes = parse_attributes(
        pairs=edge_attribute or [],
        reserved=EDGE_RESERVED_ATTRIBUTE_KEYS,
        label="`EntityEdge`",
    )

    async def _action(graphiti: Graphiti) -> AddTripletResults:
        graphiti.driver = await driver_for(graphiti=graphiti, group_id=group_id)
        effective_gid = effective_gid_for(graphiti=graphiti, group_id=group_id)
        graphiti.clients.driver = graphiti.driver
        source = EntityNode(
            name=source_name,
            group_id=effective_gid,
            summary=source_summary or "",
            attributes=source_attributes,
            uuid=source_uuid or str(uuid4()),
            created_at=utc_now(),
        )
        target = EntityNode(
            name=target_name,
            group_id=effective_gid,
            summary=target_summary or "",
            attributes=target_attributes,
            uuid=target_uuid or str(uuid4()),
            created_at=utc_now(),
        )
        edge = EntityEdge(
            source_node_uuid=source.uuid,
            target_node_uuid=target.uuid,
            name=edge_name,
            fact=edge_fact,
            attributes=edge_attributes,
            group_id=effective_gid,
            uuid=edge_uuid or str(uuid4()),
            created_at=utc_now(),
            valid_at=parse_datetime(value=edge_valid_at, label="--edge-valid-at")
            if edge_valid_at is not None
            else None,
            invalid_at=parse_datetime(value=edge_invalid_at, label="--edge-invalid-at")
            if edge_invalid_at is not None
            else None,
            expired_at=parse_datetime(value=edge_expired_at, label="--edge-expired-at")
            if edge_expired_at is not None
            else None,
        )
        return await graphiti.add_triplet(source, edge, target)

    result = run_async(action=_action)
    echo_json(
        data={
            "nodes": dump_models(models=result.nodes),
            "edges": dump_models(models=result.edges),
        }
    )
