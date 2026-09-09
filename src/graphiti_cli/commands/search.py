"""Hybrid search."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import typer
from graphiti_core.search.search_config_recipes import (
    COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
    COMBINED_HYBRID_SEARCH_MMR,
    COMBINED_HYBRID_SEARCH_RRF,
    COMMUNITY_HYBRID_SEARCH_CROSS_ENCODER,
    COMMUNITY_HYBRID_SEARCH_MMR,
    COMMUNITY_HYBRID_SEARCH_RRF,
    EDGE_HYBRID_SEARCH_CROSS_ENCODER,
    EDGE_HYBRID_SEARCH_EPISODE_MENTIONS,
    EDGE_HYBRID_SEARCH_MMR,
    EDGE_HYBRID_SEARCH_NODE_DISTANCE,
    EDGE_HYBRID_SEARCH_RRF,
    NODE_HYBRID_SEARCH_CROSS_ENCODER,
    NODE_HYBRID_SEARCH_EPISODE_MENTIONS,
    NODE_HYBRID_SEARCH_MMR,
    NODE_HYBRID_SEARCH_NODE_DISTANCE,
    NODE_HYBRID_SEARCH_RRF,
)
from graphiti_core.search.search_filters import (
    ComparisonOperator,
    DateFilter,
    SearchFilters,
)

from ._base import (
    driver_for,
    dump_models,
    echo_json,
    parse_attributes,
    parse_datetime,
    run_async,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from graphiti_core import Graphiti
    from graphiti_core.edges import EntityEdge
    from graphiti_core.nodes import EntityNode
    from graphiti_core.search.search_config import SearchConfig, SearchResults

__all__ = [
    "hybrid_search",
]


# ======================================================================================
# Helper Functions
# ======================================================================================
_CONFIGS = {
    "combined_rrf": COMBINED_HYBRID_SEARCH_RRF,
    "combined_mmr": COMBINED_HYBRID_SEARCH_MMR,
    "combined_cross_encoder": COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
    "edge_rrf": EDGE_HYBRID_SEARCH_RRF,
    "edge_mmr": EDGE_HYBRID_SEARCH_MMR,
    "edge_node_distance": EDGE_HYBRID_SEARCH_NODE_DISTANCE,
    "edge_episode_mentions": EDGE_HYBRID_SEARCH_EPISODE_MENTIONS,
    "edge_cross_encoder": EDGE_HYBRID_SEARCH_CROSS_ENCODER,
    "node_rrf": NODE_HYBRID_SEARCH_RRF,
    "node_mmr": NODE_HYBRID_SEARCH_MMR,
    "node_node_distance": NODE_HYBRID_SEARCH_NODE_DISTANCE,
    "node_episode_mentions": NODE_HYBRID_SEARCH_EPISODE_MENTIONS,
    "node_cross_encoder": NODE_HYBRID_SEARCH_CROSS_ENCODER,
    "community_rrf": COMMUNITY_HYBRID_SEARCH_RRF,
    "community_mmr": COMMUNITY_HYBRID_SEARCH_MMR,
    "community_cross_encoder": COMMUNITY_HYBRID_SEARCH_CROSS_ENCODER,
}


def _load_config(
    *,
    name: str,
) -> SearchConfig:
    try:
        return _CONFIGS[name.lower()]
    except KeyError as e:
        available = ", ".join(_CONFIGS.keys())
        raise typer.BadParameter(
            f"Found no search config named {name!r}, available options: {available}."
        ) from e


def _filter_by_attributes(
    *,
    models: Sequence[EntityNode] | Sequence[EntityEdge],
    attributes: dict[str, Any],
) -> list[EntityNode | EntityEdge]:
    if not attributes:
        return list(models)
    # NOTE: `KEY=null` parses to None; the membership check ensures records
    # missing the key entirely are not matched as a false "null" value.
    return [
        model
        for model in models
        if all(
            key in model.attributes and model.attributes[key] == value
            for key, value in attributes.items()
        )
    ]


def _build_date_filters(
    *,
    after: str | None,
    before: str | None,
    label_prefix: str,
) -> list[list[DateFilter]]:
    and_filters: list[DateFilter] = []
    if after is not None:
        and_filters.append(
            DateFilter(
                date=parse_datetime(value=after, label=f"--{label_prefix}-after"),
                comparison_operator=ComparisonOperator.greater_than_equal,
            )
        )
    if before is not None:
        and_filters.append(
            DateFilter(
                date=parse_datetime(value=before, label=f"--{label_prefix}-before"),
                comparison_operator=ComparisonOperator.less_than_equal,
            )
        )
    return [and_filters] if and_filters else []


# ======================================================================================
# CLI: ``graphiti-cli search ...``
# ======================================================================================
def hybrid_search(  # noqa: PLR0913
    *,
    content: str = typer.Option(
        ...,
        "--content",
        help="Search content.",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        min=1,
        help="Maximum number of results to return.",
    ),
    attribute: list[str] | None = typer.Option(
        None,
        "--attribute",
        help=(
            "filter nodes and edges by attributes(KEY=VALUE format), "
            "VALUE is parsed as JSON; "
            "post-filter on search results, "
            "--limit is applied before this filter"
        ),
    ),
    config_name: str = typer.Option(
        "combined_rrf",
        "--config",
        case_sensitive=False,
        help=f"search config, available options: {', '.join(_CONFIGS.keys())}",
    ),
    center_node_uuid: str | None = typer.Option(
        None,
        "--center-node-uuid",
        help="Re-rank with this node as the center.",
    ),
    bfs_origin_node_uuid: list[str] | None = typer.Option(
        None,
        "--bfs-origin-node-uuid",
        help=(
            "BFS origin node UUID; "
            "used for BFS search method and episode mentions re-ranking"
        ),
    ),
    valid_at_after: str | None = typer.Option(
        None,
        "--valid-at-after",
        help="ISO8601, only search record that are valid after this time.",
    ),
    valid_at_before: str | None = typer.Option(
        None,
        "--valid-at-before",
        help="ISO8601, only search record that are valid before this time.",
    ),
    invalid_at_after: str | None = typer.Option(
        None,
        "--invalid-at-after",
        help="ISO8601, only search record that are invalid after this time.",
    ),
    invalid_at_before: str | None = typer.Option(
        None,
        "--invalid-at-before",
        help="ISO8601, only search record that are invalid before this time.",
    ),
    created_at_after: str | None = typer.Option(
        None,
        "--created-at-after",
        help="ISO8601, only search record that are created after this time.",
    ),
    created_at_before: str | None = typer.Option(
        None,
        "--created-at-before",
        help="ISO8601, only search record that are created before this time.",
    ),
    expired_at_after: str | None = typer.Option(
        None,
        "--expired-at-after",
        help="ISO8601, only search record that are expired after this time.",
    ),
    expired_at_before: str | None = typer.Option(
        None,
        "--expired-at-before",
        help="ISO8601, only search record that are expired before this time.",
    ),
    only_node: bool = typer.Option(
        False,  # noqa: FBT003
        "--only-node",
        help="Only return nodes, ignore edges.",
    ),
    only_edge: bool = typer.Option(
        False,  # noqa: FBT003
        "--only-edge",
        help="Only return edges, ignore nodes.",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="Graph partition ID, null for default partition.",
    ),
) -> None:
    """Hybrid search with support for attribute and time range filters."""
    if all((only_node, only_edge)):
        raise typer.BadParameter(
            "`--only-node` and `--only-edge` cannot be used together."
        )

    search_config = _load_config(name=config_name).model_copy(update={"limit": limit})
    attribute_pairs = parse_attributes(pairs=attribute or [])
    filters = SearchFilters(
        valid_at=_build_date_filters(
            after=valid_at_after,
            before=valid_at_before,
            label_prefix="valid-at",
        )
        or None,
        invalid_at=_build_date_filters(
            after=invalid_at_after,
            before=invalid_at_before,
            label_prefix="invalid-at",
        )
        or None,
        created_at=_build_date_filters(
            after=created_at_after,
            before=created_at_before,
            label_prefix="created-at",
        )
        or None,
        expired_at=_build_date_filters(
            after=expired_at_after,
            before=expired_at_before,
            label_prefix="expired-at",
        )
        or None,
    )

    async def _action(graphiti: Graphiti) -> SearchResults:
        return await graphiti.search_(
            content,
            config=search_config,
            group_ids=[group_id] if group_id else None,
            center_node_uuid=center_node_uuid,
            bfs_origin_node_uuids=(
                list(bfs_origin_node_uuid) if bfs_origin_node_uuid else None
            ),
            search_filter=filters,
            driver=await driver_for(graphiti=graphiti, group_id=group_id),
        )

    result = run_async(action=_action)
    nodes = _filter_by_attributes(models=result.nodes, attributes=attribute_pairs)
    edges = _filter_by_attributes(models=result.edges, attributes=attribute_pairs)

    if only_node:
        echo_json(data={"nodes": dump_models(models=nodes)})
    elif only_edge:
        echo_json(data={"edges": dump_models(models=edges)})
    else:
        echo_json(
            data={
                "nodes": dump_models(models=nodes),
                "edges": dump_models(models=edges),
            }
        )
