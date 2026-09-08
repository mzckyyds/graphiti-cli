"""CLI: ``graphiti-cli episode {add|show|delete|nodes|edges}``."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import typer
from graphiti_core.errors import NodeNotFoundError
from graphiti_core.helpers import get_default_group_id
from graphiti_core.nodes import EpisodeType, EpisodicNode
from graphiti_core.utils.datetime_utils import utc_now

from graphiti_cli.cmds.common import (
    driver_for,
    dump_model,
    dump_models,
    echo_json,
    parse_datetime,
    read_stdin_or_value,
    run_async,
)

if TYPE_CHECKING:
    from datetime import datetime

    from graphiti_core import Graphiti
    from graphiti_core.edges import EntityEdge
    from graphiti_core.graphiti import AddEpisodeResults
    from graphiti_core.nodes import EntityNode

__all__ = [
    "app",
]


logger = logging.getLogger(__name__)

app = typer.Typer(
    help="管理 episodes: 添加(触发实体/关系抽取)/查询/删除.",
    no_args_is_help=True,
)


# ======================================================================================
# 内部工具
# ======================================================================================
def _warn_missing_uuid(
    *,
    uuid: str,
) -> None:
    """对批量操作中未找到的 UUID 输出警告, 不中断其余条目的处理."""
    typer.secho(
        f"警告: 未找到 episode: {uuid}",
        fg=typer.colors.YELLOW,
        err=True,
    )


def _effective_group_id(
    *,
    graphiti: Graphiti,
    gid: str | None,
) -> str:
    """把默认图占位 None 解析为 provider 的默认 group_id.

    FalkorDB 的默认 group_id 为 '_', 其他 provider 为空串.

    Args:
        graphiti: Graphiti 实例.
        gid: 图分区 ID, None 表示默认分区.

    Returns:
        有效的 group_id 字符串.

    """
    return gid if gid is not None else get_default_group_id(graphiti.driver.provider)


async def _select_episodes(
    *,
    graphiti: Graphiti,
    group_ids: list[str | None],
    uuids: list[str] | None,
    limit: int | None = None,
) -> list[EpisodicNode]:
    """遍历图分区收集目标 episodes, 按来源分区去重并保持遍历顺序.

    缺省(未传分区)时使用默认 group_id; 每个分区下按 UUID 逐一获取,
    未传 UUID 时拉取分区内全部. FalkorDB 下不同分区可存在 uuid 相同
    的节点, 去重需带上分区维度.

    Args:
        graphiti: Graphiti 实例.
        group_ids: 图分区 ID 列表, None 表示默认分区.
        uuids: 待获取的 episode UUID 列表, None 表示获取分区内全部.
        limit: 整组拉取时单分区的最大条数, None 表示不限制.

    Returns:
        去重后的 episode 列表, 每个 episode 均携带其所属分区 group_id.

    """
    selected: list[EpisodicNode] = []
    seen: set[tuple[str, str]] = set()
    for gid in group_ids:
        driver = driver_for(graphiti=graphiti, group_id=gid)
        effective_gid = _effective_group_id(graphiti=graphiti, gid=gid)
        if uuids is not None:
            found: list[EpisodicNode] = []
            for single_uuid in uuids:
                try:
                    found.append(await EpisodicNode.get_by_uuid(driver, single_uuid))
                except NodeNotFoundError:
                    continue
        else:
            found = await EpisodicNode.get_by_group_ids(
                driver, [effective_gid], limit=limit
            )
        for episode in found:
            key = (effective_gid, episode.uuid)
            if key in seen:
                continue
            seen.add(key)
            selected.append(episode)
    return selected


async def _collect_nodes_and_edges(
    *,
    graphiti: Graphiti,
    group_ids: list[str | None],
    uuids: list[str],
) -> tuple[list[EntityNode], list[EntityEdge]]:
    """遍历图分区汇总 episode 产出的实体节点与关系边, 按 UUID 去重.

    Args:
        graphiti: Graphiti 实例.
        group_ids: 图分区 ID 列表, None 表示默认分区.
        uuids: episode UUID 列表.

    Returns:
        (实体节点列表, 关系边列表) 元组.

    """
    nodes: list[EntityNode] = []
    edges: list[EntityEdge] = []
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()
    for gid in group_ids:
        graphiti.driver = driver_for(graphiti=graphiti, group_id=gid)
        result = await graphiti.get_nodes_and_edges_by_episode(uuids)
        for node in result.nodes:
            if node.uuid not in seen_nodes:
                seen_nodes.add(node.uuid)
                nodes.append(node)
        for edge in result.edges:
            if edge.uuid not in seen_edges:
                seen_edges.add(edge.uuid)
                edges.append(edge)
    return nodes, edges


# ======================================================================================
# CLI: ``graphiti-cli episode add``
# ======================================================================================
@app.command(name="add")
def add_episode(  # noqa: PLR0913
    *,
    name: str = typer.Argument(
        ...,
        help="episode 名称",
    ),
    content: str = typer.Option(
        ...,
        "--content",
        help="episode 正文, 传 '-' 时从 stdin 读取",
    ),
    source: EpisodeType = typer.Option(
        EpisodeType.text,
        "--source",
        case_sensitive=False,
        help="内容类型: text/json/message",
    ),
    source_description: str = typer.Option(
        "",
        "--source-description",
        help="数据来源描述",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认图",
    ),
    uuid: str | None = typer.Option(
        None,
        "--uuid",
        help="自定义 episode UUID",
    ),
    reference_time: str | None = typer.Option(
        None,
        "--reference-time",
        help="ISO8601 参考时间, 缺省为当前 UTC 时间",
    ),
    update_communities: bool = typer.Option(
        False,  # noqa: FBT003
        "--update-communities",
        help="写入后同步更新社区摘要",
    ),
    instructions: str | None = typer.Option(
        None,
        "--instructions",
        help="自定义抽取指令, 引导实体/关系抽取",
    ),
) -> None:
    """添加 episode 并触发实体/关系抽取, 是向图谱写入信息的主要入口."""
    body = read_stdin_or_value(value=content, label="--content")
    reference_dt: datetime = (
        parse_datetime(value=reference_time, label="--reference-time")
        if reference_time
        else utc_now()
    )

    async def _action(graphiti: Graphiti) -> AddEpisodeResults:
        return await graphiti.add_episode(
            name=name,
            episode_body=body,
            source=source,
            source_description=source_description,
            reference_time=reference_dt,
            group_id=group_id,
            uuid=uuid,
            update_communities=update_communities,
            custom_extraction_instructions=instructions,
        )

    result = run_async(action=_action)
    echo_json(
        data={
            "episode": dump_model(model=result.episode),
            "nodes": [node.uuid for node in result.nodes],
            "edges": [edge.uuid for edge in result.edges],
        }
    )


# ======================================================================================
# CLI: ``graphiti-cli episode show``
# ======================================================================================
@app.command(name="show")
def show_episodes(
    *,
    uuid: list[str] | None = typer.Argument(
        None,
        help="episode UUID, 可传多个; 省略时列出 episodes",
    ),
    group_id: list[str] | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 可传多个; 缺省为默认分区",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        min=1,
        help="列出时单分区的最大条数",
    ),
) -> None:
    """查看 episode(可传多个 UUID)或按分区列出 episodes(省略 UUID)."""
    uuids: list[str] | None = uuid
    group_ids: list[str | None] = list(group_id) if group_id else [None]

    async def _action(graphiti: Graphiti) -> list[EpisodicNode]:
        return await _select_episodes(
            graphiti=graphiti, group_ids=group_ids, uuids=uuids, limit=limit
        )

    episodes = run_async(action=_action)
    if uuids:
        found = {episode.uuid for episode in episodes}
        for single_uuid in uuids:
            if single_uuid not in found:
                _warn_missing_uuid(uuid=single_uuid)
    echo_json(data=dump_models(models=episodes))


# ======================================================================================
# CLI: ``graphiti-cli episode delete``
# ======================================================================================
@app.command(name="delete")
def delete_episodes(
    *,
    uuid: list[str] | None = typer.Argument(
        None,
        help="episode UUID, 可传多个; 省略时删除分区下的全部 episodes",
    ),
    group_id: list[str] | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 可传多个; 缺省为默认分区",
    ),
) -> None:
    """删除 episode, 仅其独有的实体与关系会被级联删除."""
    uuids: list[str] | None = uuid
    group_ids: list[str | None] = list(group_id) if group_id else [None]

    async def _action(graphiti: Graphiti) -> list[str]:
        episodes = await _select_episodes(
            graphiti=graphiti, group_ids=group_ids, uuids=uuids
        )
        deleted: list[str] = []
        for episode in episodes:
            # episode 自带所属分区, 在其来源图上执行级联删除
            graphiti.driver = driver_for(graphiti=graphiti, group_id=episode.group_id)
            await graphiti.remove_episode(episode.uuid)
            deleted.append(episode.uuid)
        return deleted

    deleted = run_async(action=_action)
    if uuids:
        found = set(deleted)
        for single_uuid in uuids:
            if single_uuid not in found:
                _warn_missing_uuid(uuid=single_uuid)
    if deleted:
        typer.echo(f"已删除 episode: {', '.join(deleted)}")
    else:
        typer.echo("没有可删除的 episode")


# ======================================================================================
# CLI: ``graphiti-cli episode nodes``
# ======================================================================================
@app.command(name="nodes")
def show_episode_nodes(
    *,
    uuid: list[str] = typer.Argument(
        ...,
        help="episode UUID, 可传多个",
    ),
    group_id: list[str] | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 可传多个; 缺省为默认分区",
    ),
) -> None:
    """查看 episode 产出的实体节点."""
    group_ids: list[str | None] = list(group_id) if group_id else [None]

    async def _action(graphiti: Graphiti) -> list[EntityNode]:
        found_nodes, _ = await _collect_nodes_and_edges(
            graphiti=graphiti, group_ids=group_ids, uuids=list(uuid)
        )
        return found_nodes

    found_nodes = run_async(action=_action)
    echo_json(data={"nodes": dump_models(models=found_nodes)})


# ======================================================================================
# CLI: ``graphiti-cli episode edges``
# ======================================================================================
@app.command(name="edges")
def show_episode_edges(
    *,
    uuid: list[str] = typer.Argument(
        ...,
        help="episode UUID, 可传多个",
    ),
    group_id: list[str] | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 可传多个; 缺省为默认分区",
    ),
) -> None:
    """查看 episode 产出的关系边."""
    group_ids: list[str | None] = list(group_id) if group_id else [None]

    async def _action(graphiti: Graphiti) -> list[EntityEdge]:
        _, found_edges = await _collect_nodes_and_edges(
            graphiti=graphiti, group_ids=group_ids, uuids=list(uuid)
        )
        return found_edges

    found_edges = run_async(action=_action)
    echo_json(data={"edges": dump_models(models=found_edges)})
