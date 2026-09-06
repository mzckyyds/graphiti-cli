"""``triplet`` 子命令: 直写单条事实三元组.

对应 MCP 的 add_triplet: 绕过抽取流程直接写入
``source 节点 -> 关系 -> target 节点``, 节点自动去重解析并生成向量.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

import typer
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode
from graphiti_core.utils.datetime_utils import utc_now

from graphiti_cli.cmds.common import driver_for, dump_models, echo_json, run_async

if TYPE_CHECKING:
    from graphiti_core import Graphiti
    from graphiti_core.graphiti import AddTripletResults

__all__ = [
    "app",
]


logger = logging.getLogger(__name__)

app = typer.Typer(
    help="直写事实三元组: source 节点 -> 关系 -> target 节点.",
    no_args_is_help=True,
)


@app.command(name="add")
def add(  # noqa: PLR0913
    source_node_name: str = typer.Argument(..., help="源节点名称"),
    edge_name: str = typer.Argument(..., help="关系名称"),
    fact: str = typer.Argument(..., help="事实描述"),
    target_node_name: str = typer.Argument(..., help="目标节点名称"),
    *,
    group_id: str = typer.Option("", "--group-id", help="图分区 ID, 缺省为默认分区"),
    source_node_uuid: str | None = typer.Option(
        None, "--source-uuid", help="指定源节点 UUID, 与已有节点合并时使用"
    ),
    target_node_uuid: str | None = typer.Option(
        None, "--target-uuid", help="指定目标节点 UUID, 与已有节点合并时使用"
    ),
) -> None:
    """直写单条事实三元组, 节点不存在时经 LLM 解析合并, 不抽取 episode."""

    async def _action(graphiti: Graphiti) -> AddTripletResults:
        graphiti.driver = driver_for(graphiti=graphiti, group_id=group_id or None)
        source = EntityNode(
            name=source_node_name,
            group_id=group_id,
            uuid=source_node_uuid or str(uuid4()),
        )
        target = EntityNode(
            name=target_node_name,
            group_id=group_id,
            uuid=target_node_uuid or str(uuid4()),
        )
        edge = EntityEdge(
            source_node_uuid=source.uuid,
            target_node_uuid=target.uuid,
            name=edge_name,
            fact=fact,
            group_id=group_id,
            created_at=utc_now(),
        )
        return await graphiti.add_triplet(source, edge, target)

    result = run_async(action=_action)
    echo_json(
        data={
            "nodes": dump_models(models=result.nodes),
            "edges": dump_models(models=result.edges),
        }
    )
