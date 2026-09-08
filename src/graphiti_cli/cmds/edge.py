"""CLI: ``graphiti-cli edge {add|get|list|patch|delete}``."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import typer
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode
from graphiti_core.utils.datetime_utils import utc_now

from graphiti_cli.cmds.common import (
    delete_model,
    driver_for,
    dump_model,
    dump_models,
    echo_json,
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
    "app",
]


app = typer.Typer(
    help="管理关系边(事实): 添加/查询/修改/删除.",
    no_args_is_help=True,
)


# ======================================================================================
# CLI: ``graphiti-cli edge add``
# ======================================================================================
@app.command(name="add")
def add_edge(  # noqa: PLR0913
    *,
    source_node_uuid: str = typer.Argument(
        ...,
        help="源节点 UUID",
    ),
    target_node_uuid: str = typer.Argument(
        ...,
        help="目标节点 UUID",
    ),
    name: str = typer.Option(
        ...,
        "--name",
        help="关系名称",
    ),
    fact: str = typer.Option(
        ...,
        "--fact",
        help="事实描述",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省沿用源节点所在分区",
    ),
    uuid: str | None = typer.Option(
        None,
        "--uuid",
        help="自定义边 UUID",
    ),
    attribute: list[str] | None = typer.Option(
        None,
        "--attribute",
        help="附加属性 KEY=VALUE, VALUE 按 JSON 解析, 可传多个",
    ),
) -> None:
    """在两个已有节点间直写一条关系边, 自动生成事实向量, 不经过 LLM 抽取."""
    attributes = parse_attributes(pairs=attribute or [])

    async def _action(graphiti: Graphiti) -> EntityEdge:
        driver = driver_for(graphiti=graphiti, group_id=group_id)
        source = await EntityNode.get_by_uuid(driver, source_node_uuid)
        target = await EntityNode.get_by_uuid(driver, target_node_uuid)
        edge = EntityEdge(
            uuid=uuid or str(uuid4()),
            group_id=group_id if group_id is not None else source.group_id,
            source_node_uuid=source.uuid,
            target_node_uuid=target.uuid,
            name=name,
            fact=fact,
            attributes=attributes,
            created_at=utc_now(),
        )
        await edge.generate_embedding(graphiti.embedder)
        await edge.save(driver)
        return edge

    edge = run_async(action=_action)
    echo_json(data=dump_model(model=edge))


# ======================================================================================
# CLI: ``graphiti-cli edge get``
# ======================================================================================
@app.command(name="get")
def get_edge(
    *,
    uuid: str = typer.Argument(
        ...,
        help="边 UUID",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认分区",
    ),
) -> None:
    """按 UUID 查看单条关系边."""

    async def _action(graphiti: Graphiti) -> EntityEdge:
        return await get_model(
            graphiti=graphiti,
            model_cls=EntityEdge,
            group_id=group_id,
            uuid=uuid,
            label="关系边",
        )

    edge = run_async(action=_action)
    echo_json(data=dump_model(model=edge))


# ======================================================================================
# CLI: ``graphiti-cli edge list``
# ======================================================================================
@app.command(name="list")
def list_edges(
    *,
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认分区",
    ),
    episode_uuid: str | None = typer.Option(
        None,
        "--episode-uuid",
        help="episode UUID; 传入时只返回该 episode 产出的关系边",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        min=1,
        help="列出时单分区的最大条数",
    ),
) -> None:
    """按分区列出关系边, 可按 episode 过滤(替代原 ``episode edges``)."""

    async def _action(graphiti: Graphiti) -> list[EntityEdge]:
        if episode_uuid:
            graphiti.driver = driver_for(graphiti=graphiti, group_id=group_id)
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
# CLI: ``graphiti-cli edge patch``
# ======================================================================================
@app.command(name="patch")
def patch_edge(  # noqa: PLR0913
    *,
    uuid: str = typer.Argument(
        ...,
        help="边 UUID",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 需与写入时一致",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="新关系名称",
    ),
    fact: str | None = typer.Option(
        None,
        "--fact",
        help="新事实描述, 修改后自动重建事实向量",
    ),
    valid_at: str | None = typer.Option(
        None,
        "--valid-at",
        help="ISO8601, 事实开始生效时间",
    ),
    invalid_at: str | None = typer.Option(
        None,
        "--invalid-at",
        help="ISO8601, 事实停止生效时间",
    ),
    expired_at: str | None = typer.Option(
        None,
        "--expired-at",
        help="ISO8601, 边失效(被新事实取代)时间",
    ),
    attribute: list[str] | None = typer.Option(
        None,
        "--attribute",
        help="合并的附加属性 KEY=VALUE, 可传多个",
    ),
) -> None:
    """增量修改关系边的关系名, 事实描述与时间字段."""
    attributes = parse_attributes(pairs=attribute or [])

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
            label="关系边",
            patch=_patch,
        )

    edge = run_async(action=_action)
    echo_json(data=dump_model(model=edge))


# ======================================================================================
# CLI: ``graphiti-cli edge delete``
# ======================================================================================
@app.command(name="delete")
def delete_edge(
    *,
    uuid: str = typer.Argument(
        ...,
        help="边 UUID",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认分区",
    ),
) -> None:
    """按 UUID 删除关系边."""

    async def _action(graphiti: Graphiti) -> str:
        return await delete_model(
            graphiti=graphiti,
            model_cls=EntityEdge,
            group_id=group_id,
            uuid=uuid,
            label="关系边",
        )

    deleted = run_async(action=_action)
    typer.echo(f"已删除关系边: {deleted}")
