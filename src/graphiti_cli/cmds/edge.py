"""``edge`` 子命令: 管理关系边(事实).

对应 MCP 的 search_memory_facts/get_entity_edge/delete_entity_edge,
add/patch 为 CLI 扩展(基于 ``EntityEdge.save``, 直写不经过 LLM 抽取).

注意: FalkorDB 下每个 group_id 对应一张同名图, 按 UUID 直读/改删时
需用 ``--group-id`` 指明分区(与写入时一致).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

import typer
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode
from graphiti_core.search.search_filters import (
    ComparisonOperator,
    DateFilter,
    SearchFilters,
)
from graphiti_core.utils.datetime_utils import utc_now

from graphiti_cli.cmds.common import (
    driver_for,
    dump_model,
    dump_models,
    echo_json,
    parse_attributes,
    parse_datetime,
    run_async,
)

if TYPE_CHECKING:
    from graphiti_core import Graphiti

__all__ = [
    "app",
]


logger = logging.getLogger(__name__)

app = typer.Typer(
    help="管理关系边(事实): 混合检索与直写增删改.",
    no_args_is_help=True,
)


def _build_date_filters(
    *,
    after: str | None,
    before: str | None,
    label_prefix: str,
) -> list[list[DateFilter]]:
    """构造 DNF 形式的日期区间过滤(内层 OR, 外层 AND).

    Args:
        after: ISO8601 下界, None 表示不限.
        before: ISO8601 上界, None 表示不限.
        label_prefix: 选项名前缀, 用于报错.

    Returns:
        可赋给 SearchFilters.valid_at/invalid_at 的过滤条件.

    """
    filters: list[list[DateFilter]] = []
    if after is not None:
        filters.append(
            [
                DateFilter(
                    date=parse_datetime(value=after, label=f"--{label_prefix}-after"),
                    comparison_operator=ComparisonOperator.greater_than_equal,
                )
            ]
        )
    if before is not None:
        filters.append(
            [
                DateFilter(
                    date=parse_datetime(value=before, label=f"--{label_prefix}-before"),
                    comparison_operator=ComparisonOperator.less_than_equal,
                )
            ]
        )
    return filters


@app.command(name="search")
def search(  # noqa: PLR0913
    query: str = typer.Argument(..., help="查询文本"),
    *,
    group_id: list[str] | None = typer.Option(
        None, "--group-id", help="图分区 ID, 可多次传入"
    ),
    limit: int = typer.Option(10, "--limit", min=1, help="最大返回条数"),
    center_node_uuid: str | None = typer.Option(
        None, "--center-node-uuid", help="以该节点为中心重排序"
    ),
    edge_type: list[str] | None = typer.Option(
        None, "--edge-type", help="按关系类型过滤, 可多次传入"
    ),
    valid_at_after: str | None = typer.Option(
        None, "--valid-at-after", help="ISO8601, 只返回该时间后生效的事实"
    ),
    valid_at_before: str | None = typer.Option(
        None, "--valid-at-before", help="ISO8601, 只返回该时间前生效的事实"
    ),
    invalid_at_after: str | None = typer.Option(
        None, "--invalid-at-after", help="ISO8601, 只返回该时间后失效的事实"
    ),
    invalid_at_before: str | None = typer.Option(
        None, "--invalid-at-before", help="ISO8601, 只返回该时间前失效的事实"
    ),
) -> None:
    """对关系边(事实)做混合检索, 支持关系类型与生效/失效时间区间过滤."""
    filters = SearchFilters(
        edge_types=list(edge_type) if edge_type else None,
        valid_at=_build_date_filters(
            after=valid_at_after, before=valid_at_before, label_prefix="valid-at"
        )
        or None,
        invalid_at=_build_date_filters(
            after=invalid_at_after, before=invalid_at_before, label_prefix="invalid-at"
        )
        or None,
    )

    async def _action(graphiti: Graphiti) -> list[EntityEdge]:
        return await graphiti.search(
            query,
            center_node_uuid=center_node_uuid,
            group_ids=list(group_id) if group_id else None,
            num_results=limit,
            search_filter=filters,
        )

    edges = run_async(action=_action)
    echo_json(data=dump_models(models=edges))


@app.command(name="add")
def add(  # noqa: PLR0913
    source_node_uuid: str = typer.Argument(..., help="源节点 UUID"),
    target_node_uuid: str = typer.Argument(..., help="目标节点 UUID"),
    *,
    name: str = typer.Option(..., "--name", help="关系名称"),
    fact: str = typer.Option(..., "--fact", help="事实描述"),
    group_id: str | None = typer.Option(
        None, "--group-id", help="图分区 ID, 缺省沿用源节点所在分区"
    ),
    uuid_: str | None = typer.Option(None, "--uuid", help="自定义边 UUID"),
    attribute: list[str] | None = typer.Option(
        None, "--attribute", help="附加属性 KEY=VALUE, VALUE 按 JSON 解析, 可多次传入"
    ),
) -> None:
    """在两个已有节点间直写一条关系边, 自动生成事实向量, 不经过 LLM 抽取."""
    attributes = parse_attributes(pairs=attribute or [])

    async def _action(graphiti: Graphiti) -> EntityEdge:
        driver = driver_for(graphiti=graphiti, group_id=group_id)
        source = await EntityNode.get_by_uuid(driver, source_node_uuid)
        target = await EntityNode.get_by_uuid(driver, target_node_uuid)
        edge = EntityEdge(
            uuid=uuid_ or str(uuid4()),
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


@app.command(name="show")
def show(
    uuid: str = typer.Argument(..., help="边 UUID"),
    *,
    group_id: str | None = typer.Option(
        None, "--group-id", help="图分区 ID, 需与写入时一致"
    ),
) -> None:
    """按 UUID 查看关系边."""

    async def _action(graphiti: Graphiti) -> EntityEdge:
        driver = driver_for(graphiti=graphiti, group_id=group_id)
        return await EntityEdge.get_by_uuid(driver, uuid)

    edge = run_async(action=_action)
    echo_json(data=dump_model(model=edge))


@app.command(name="patch")
def patch(  # noqa: PLR0913
    uuid: str = typer.Argument(..., help="边 UUID"),
    *,
    group_id: str | None = typer.Option(
        None, "--group-id", help="图分区 ID, 需与写入时一致"
    ),
    name: str | None = typer.Option(None, "--name", help="新关系名称"),
    fact: str | None = typer.Option(
        None, "--fact", help="新事实描述, 修改后自动重建事实向量"
    ),
    valid_at: str | None = typer.Option(
        None, "--valid-at", help="ISO8601, 事实开始生效时间"
    ),
    invalid_at: str | None = typer.Option(
        None, "--invalid-at", help="ISO8601, 事实停止生效时间"
    ),
    expired_at: str | None = typer.Option(
        None, "--expired-at", help="ISO8601, 边失效(被新事实取代)时间"
    ),
    attribute: list[str] | None = typer.Option(
        None, "--attribute", help="合并的附加属性 KEY=VALUE, 可多次传入"
    ),
) -> None:
    """增量修改关系边的关系名, 事实描述与时间字段."""
    attributes = parse_attributes(pairs=attribute or [])

    async def _action(graphiti: Graphiti) -> EntityEdge:
        driver = driver_for(graphiti=graphiti, group_id=group_id)
        edge = await EntityEdge.get_by_uuid(driver, uuid)
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
        await edge.save(driver)
        return edge

    edge = run_async(action=_action)
    echo_json(data=dump_model(model=edge))


@app.command(name="delete")
def delete(
    uuid: str = typer.Argument(..., help="边 UUID"),
    *,
    group_id: str | None = typer.Option(
        None, "--group-id", help="图分区 ID, 需与写入时一致"
    ),
) -> None:
    """按 UUID 删除关系边."""

    async def _action(graphiti: Graphiti) -> None:
        driver = driver_for(graphiti=graphiti, group_id=group_id)
        edge = await EntityEdge.get_by_uuid(driver, uuid)
        await edge.delete(driver)

    run_async(action=_action)
    typer.echo(f"已删除关系边: {uuid}")
