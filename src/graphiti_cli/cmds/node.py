"""CLI: ``graphiti-cli node {add|get|list|patch|delete}``."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import typer
from graphiti_core.nodes import EntityNode

from graphiti_cli.cmds.common import (
    delete_model,
    driver_for,
    dump_model,
    dump_models,
    echo_json,
    effective_group_id,
    get_model,
    list_model,
    parse_attributes,
    patch_model,
    run_async,
)

if TYPE_CHECKING:
    from graphiti_core import Graphiti

__all__ = [
    "app",
]


app = typer.Typer(
    help="管理 EntityNode: 添加/查询/修改/删除.",
    no_args_is_help=True,
)


# ======================================================================================
# CLI: ``graphiti-cli node add``
# ======================================================================================
@app.command(name="add")
def add_node(
    *,
    name: str = typer.Argument(
        ...,
        help="EntityNode 名称",
    ),
    summary: str = typer.Option(
        "",
        "--summary",
        help="EntityNode 摘要",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认分区",
    ),
    uuid: str | None = typer.Option(
        None,
        "--uuid",
        help="自定义 EntityNode UUID",
    ),
    attribute: list[str] | None = typer.Option(
        None,
        "--attribute",
        help="附加属性 KEY=VALUE, VALUE 按 JSON 解析, 可传多个",
    ),
) -> None:
    """添加 EntityNode 并生成名称向量(不经过 LLM 抽取)."""
    attributes = parse_attributes(pairs=attribute or [])

    async def _action(graphiti: Graphiti) -> EntityNode:
        effective_gid = effective_group_id(graphiti=graphiti, gid=group_id)
        driver = driver_for(graphiti=graphiti, group_id=group_id)
        node = EntityNode(
            name=name,
            group_id=effective_gid,
            summary=summary,
            attributes=attributes,
            uuid=uuid or str(uuid4()),
        )
        await node.generate_name_embedding(graphiti.embedder)
        await node.save(driver)
        return node

    node = run_async(action=_action)
    echo_json(data=dump_model(model=node))


# ======================================================================================
# CLI: ``graphiti-cli node get``
# ======================================================================================
@app.command(name="get")
def get_node(
    *,
    uuid: str = typer.Argument(
        ...,
        help="EntityNode UUID",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认分区",
    ),
) -> None:
    """按 UUID 查看单个 EntityNode."""

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
# CLI: ``graphiti-cli node list``
# ======================================================================================
@app.command(name="list")
def list_nodes(
    *,
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认分区",
    ),
    episode_uuid: str | None = typer.Option(
        None,
        "--episode-uuid",
        help="episode UUID; 传入时只返回该 episode 产出的节点",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        min=1,
        help="列出时单分区的最大条数",
    ),
) -> None:
    """按分区列出 EntityNode, 可按 episode 过滤(替代原 ``episode nodes``)."""

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
# CLI: ``graphiti-cli node patch``
# ======================================================================================
@app.command(name="patch")
def patch_node(
    *,
    uuid: str = typer.Argument(
        ...,
        help="EntityNode UUID",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 需与写入时一致",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="新名称, 修改后自动重建名称向量",
    ),
    summary: str | None = typer.Option(
        None,
        "--summary",
        help="新摘要",
    ),
    attribute: list[str] | None = typer.Option(
        None,
        "--attribute",
        help="合并的附加属性 KEY=VALUE, 可传多个",
    ),
) -> None:
    """增量修改实体节点的名称(修改后自动重建名称向量), 摘要与属性."""
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
# CLI: ``graphiti-cli node delete``
# ======================================================================================
@app.command(name="delete")
def delete_node(
    *,
    uuid: str = typer.Argument(
        ...,
        help="EntityNode UUID",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认分区",
    ),
) -> None:
    """按 UUID 删除实体节点(不级联删除关联的边)."""

    async def _action(graphiti: Graphiti) -> str:
        return await delete_model(
            graphiti=graphiti,
            model_cls=EntityNode,
            group_id=group_id,
            uuid=uuid,
            label="EntityNode",
        )

    deleted = run_async(action=_action)
    typer.echo(f"已删除节点: {deleted}")
