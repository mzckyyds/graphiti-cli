"""``node`` 子命令: 管理实体节点.

对应 MCP 的 search_nodes, add/show/patch/delete 为 CLI 扩展
(基于 ``EntityNode.save``/``delete``, 直写不经过 LLM 抽取).

注意: FalkorDB 下每个 group_id 对应一张同名图, 按 UUID 直读/改删时
需用 ``--group-id`` 指明分区(与写入时一致).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

import typer
from graphiti_core.nodes import EntityNode
from graphiti_core.search.search_config_recipes import (
    NODE_HYBRID_SEARCH_NODE_DISTANCE,
    NODE_HYBRID_SEARCH_RRF,
)
from graphiti_core.search.search_filters import SearchFilters

from graphiti_cli.cmds.common import (
    driver_for,
    dump_model,
    dump_models,
    echo_json,
    parse_attributes,
    run_async,
)

if TYPE_CHECKING:
    from graphiti_core import Graphiti

__all__ = [
    "app",
]


logger = logging.getLogger(__name__)

app = typer.Typer(
    help="管理实体节点: 语义检索与直写增删改.",
    no_args_is_help=True,
)


@app.command(name="search")
def search(
    query: str = typer.Argument(..., help="查询文本"),
    *,
    group_id: list[str] | None = typer.Option(
        None, "--group-id", help="图分区 ID, 可多次传入"
    ),
    limit: int = typer.Option(10, "--limit", min=1, help="最大返回条数"),
    center_node_uuid: str | None = typer.Option(
        None, "--center-node-uuid", help="以该节点为中心重排序"
    ),
    entity_type: list[str] | None = typer.Option(
        None, "--entity-type", help="按节点 label 过滤, 可多次传入"
    ),
) -> None:
    """对实体节点做混合检索(语义 + 关键词), 可按 label 过滤并围绕中心节点重排序."""
    config = (
        NODE_HYBRID_SEARCH_NODE_DISTANCE if center_node_uuid else NODE_HYBRID_SEARCH_RRF
    ).model_copy(deep=True)
    config.limit = limit
    filters = SearchFilters(node_labels=list(entity_type) if entity_type else None)

    async def _action(graphiti: Graphiti) -> list[EntityNode]:
        result = await graphiti.search_(
            query,
            config=config,
            group_ids=list(group_id) if group_id else None,
            center_node_uuid=center_node_uuid,
            search_filter=filters,
        )
        return result.nodes

    nodes = run_async(action=_action)
    echo_json(data=dump_models(models=nodes))


@app.command(name="add")
def add(
    name: str = typer.Argument(..., help="节点名称"),
    *,
    summary: str = typer.Option("", "--summary", help="节点摘要"),
    group_id: str = typer.Option("", "--group-id", help="图分区 ID, 缺省为默认分区"),
    uuid_: str | None = typer.Option(None, "--uuid", help="自定义节点 UUID"),
    attribute: list[str] | None = typer.Option(
        None, "--attribute", help="附加属性 KEY=VALUE, VALUE 按 JSON 解析, 可多次传入"
    ),
) -> None:
    """直写新增实体节点, 自动生成名称向量, 不经过 LLM 抽取."""
    attributes = parse_attributes(pairs=attribute or [])

    async def _action(graphiti: Graphiti) -> EntityNode:
        driver = driver_for(graphiti=graphiti, group_id=group_id or None)
        node = EntityNode(
            name=name,
            group_id=group_id,
            summary=summary,
            attributes=attributes,
            uuid=uuid_ or str(uuid4()),
        )
        await node.generate_name_embedding(graphiti.embedder)
        await node.save(driver)
        return node

    node = run_async(action=_action)
    echo_json(data=dump_model(model=node))


@app.command(name="show")
def show(
    uuid: str = typer.Argument(..., help="节点 UUID"),
    *,
    group_id: str | None = typer.Option(
        None, "--group-id", help="图分区 ID, 需与写入时一致"
    ),
) -> None:
    """按 UUID 查看实体节点."""

    async def _action(graphiti: Graphiti) -> EntityNode:
        driver = driver_for(graphiti=graphiti, group_id=group_id)
        return await EntityNode.get_by_uuid(driver, uuid)

    node = run_async(action=_action)
    echo_json(data=dump_model(model=node))


@app.command(name="patch")
def patch(
    uuid: str = typer.Argument(..., help="节点 UUID"),
    *,
    group_id: str | None = typer.Option(
        None, "--group-id", help="图分区 ID, 需与写入时一致"
    ),
    name: str | None = typer.Option(
        None, "--name", help="新名称, 修改后自动重建名称向量"
    ),
    summary: str | None = typer.Option(None, "--summary", help="新摘要"),
    attribute: list[str] | None = typer.Option(
        None, "--attribute", help="合并的附加属性 KEY=VALUE, 可多次传入"
    ),
) -> None:
    """增量修改实体节点的名称, 摘要与属性."""
    attributes = parse_attributes(pairs=attribute or [])

    async def _action(graphiti: Graphiti) -> EntityNode:
        driver = driver_for(graphiti=graphiti, group_id=group_id)
        node = await EntityNode.get_by_uuid(driver, uuid)
        if name is not None:
            node.name = name
            await node.generate_name_embedding(graphiti.embedder)
        if summary is not None:
            node.summary = summary
        if attributes:
            node.attributes.update(attributes)
        await node.save(driver)
        return node

    node = run_async(action=_action)
    echo_json(data=dump_model(model=node))


@app.command(name="delete")
def delete(
    uuid: str = typer.Argument(..., help="节点 UUID"),
    *,
    group_id: str | None = typer.Option(
        None, "--group-id", help="图分区 ID, 需与写入时一致"
    ),
) -> None:
    """按 UUID 删除实体节点(不级联删除关联的边)."""

    async def _action(graphiti: Graphiti) -> None:
        driver = driver_for(graphiti=graphiti, group_id=group_id)
        node = await EntityNode.get_by_uuid(driver, uuid)
        await node.delete(driver)

    run_async(action=_action)
    typer.echo(f"已删除节点: {uuid}")
