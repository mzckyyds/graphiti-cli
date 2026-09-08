"""CLI: ``graphiti-cli search``."""

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
from graphiti_core.search.search_filters import SearchFilters

from graphiti_cli.cmds.common import (
    build_date_filters,
    dump_models,
    echo_json,
    parse_attributes,
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
# 内部工具
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
        # BadParameter 让 typer 输出干净的 CLI 报错而非 traceback
        raise typer.BadParameter(
            f"未找到检索配置 {name!r}, 可选配置: {available}"
        ) from e


def _filter_by_attributes(
    *,
    models: Sequence[EntityNode] | Sequence[EntityEdge],
    attributes: dict[str, Any],
) -> list[EntityNode | EntityEdge]:
    """按属性键值对过滤节点/边, 条件之间为 AND.

    Args:
        models: 带 attributes 字典的节点或边.
        attributes: 期望的属性键值对, 空表示不过滤.

    Returns:
        属性全部命中的模型列表.

    """
    if not attributes:
        return list(models)
    return [
        model
        for model in models
        if all(model.attributes.get(key) == value for key, value in attributes.items())
    ]


# ======================================================================================
# CLI: ``graphiti-cli search``
# ======================================================================================
def hybrid_search(  # noqa: PLR0913
    *,
    content: str = typer.Argument(
        ...,
        help="检索内容",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认分区",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        min=1,
        help="最大返回条数",
    ),
    attribute: list[str] | None = typer.Option(
        None,
        "--attribute",
        help=(
            "按属性过滤节点与边, 格式 KEY=VALUE, VALUE 按 JSON 解析, 可传多个, "
            "条件之间为 AND; 在检索结果上后置过滤, --limit 先于本过滤生效"
        ),
    ),
    config_name: str = typer.Option(
        "combined_rrf",
        "--config",
        case_sensitive=False,
        help=f"检索配置, 可选: {', '.join(_CONFIGS.keys())}",
    ),
    center_node_uuid: str | None = typer.Option(
        None,
        "--center-node-uuid",
        help="以该节点为中心重排序",
    ),
    bfs_origin_node_uuid: list[str] | None = typer.Option(
        None,
        "--bfs-origin-node-uuid",
        help="BFS 起点节点 UUID, 可传多个; 供 BFS 检索方法与 episode mentions 重排使用",
    ),
    valid_at_after: str | None = typer.Option(
        None,
        "--valid-at-after",
        help="ISO8601, 只返回该时间后生效的事实",
    ),
    valid_at_before: str | None = typer.Option(
        None,
        "--valid-at-before",
        help="ISO8601, 只返回该时间前生效的事实",
    ),
    invalid_at_after: str | None = typer.Option(
        None,
        "--invalid-at-after",
        help="ISO8601, 只返回该时间后失效的事实",
    ),
    invalid_at_before: str | None = typer.Option(
        None,
        "--invalid-at-before",
        help="ISO8601, 只返回该时间前失效的事实",
    ),
    created_at_after: str | None = typer.Option(
        None,
        "--created-at-after",
        help="ISO8601, 只返回该时间后写入的事实",
    ),
    created_at_before: str | None = typer.Option(
        None,
        "--created-at-before",
        help="ISO8601, 只返回该时间前写入的事实",
    ),
    expired_at_after: str | None = typer.Option(
        None,
        "--expired-at-after",
        help="ISO8601, 只返回该时间后被新事实取代的边",
    ),
    expired_at_before: str | None = typer.Option(
        None,
        "--expired-at-before",
        help="ISO8601, 只返回该时间前被新事实取代的边",
    ),
    only_node: bool = typer.Option(
        False,  # noqa: FBT003
        "--only-node",
        help="仅返回节点, 忽略关系边",
    ),
    only_edge: bool = typer.Option(
        False,  # noqa: FBT003
        "--only-edge",
        help="仅返回关系边, 忽略节点",
    ),
) -> None:
    """对实体节点与关系边(事实)做混合检索, 支持属性与时间区间过滤."""
    if all((only_node, only_edge)):
        raise typer.BadParameter(
            "只能选择仅返回节点或仅返回关系边中的一个, 不能同时选择."
        )

    # 复制 recipe 后再改 limit, 避免改写模块级共享的配置实例
    search_config = _load_config(name=config_name).model_copy(update={"limit": limit})
    attribute_pairs = parse_attributes(pairs=attribute or [])
    filters = SearchFilters(
        valid_at=build_date_filters(
            after=valid_at_after,
            before=valid_at_before,
            label_prefix="valid-at",
        )
        or None,
        invalid_at=build_date_filters(
            after=invalid_at_after,
            before=invalid_at_before,
            label_prefix="invalid-at",
        )
        or None,
        created_at=build_date_filters(
            after=created_at_after,
            before=created_at_before,
            label_prefix="created-at",
        )
        or None,
        expired_at=build_date_filters(
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
        )

    result = run_async(action=_action)
    nodes = _filter_by_attributes(models=result.nodes, attributes=attribute_pairs)
    edges = _filter_by_attributes(models=result.edges, attributes=attribute_pairs)

    if only_node:
        echo_json(data=dump_models(models=nodes))
    elif only_edge:
        echo_json(data=dump_models(models=edges))
    else:
        echo_json(
            data={
                "nodes": dump_models(models=nodes),
                "edges": dump_models(models=edges),
            }
        )
