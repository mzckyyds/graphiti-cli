"""CLI: ``graphiti-cli episode {add|show|patch|delete|nodes|edges}``.

注意: FalkorDB 下每个 group_id 对应一张同名图, 按 UUID 直读/改删时
需用 ``--group-id`` 指明分区(与写入时一致).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import typer
from graphiti_core.nodes import EpisodeType, EpisodicNode
from graphiti_core.utils.datetime_utils import utc_now

from graphiti_cli.cmds.common import (
    driver_for,
    dump_model,
    dump_models,
    echo_json,
    parse_datetime,
    read_stdin_or_value,
    resolve_group_ids,
    run_async,
)

if TYPE_CHECKING:
    from datetime import datetime

    from graphiti_core import Graphiti
    from graphiti_core.graphiti import AddEpisodeResults
    from graphiti_core.search.search_config import SearchResults

__all__ = [
    "app",
]


logger = logging.getLogger(__name__)

app = typer.Typer(
    help="管理 episodes: 添加(触发实体/关系抽取), 查询, 修改与删除.",
    no_args_is_help=True,
)


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
        help="图分区 ID, 缺省为默认分区",
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
def show(
    *,
    uuid: str | None = typer.Argument(
        None,
        help="episode UUID, 省略时列出 episodes",
    ),
    group_id: list[str] | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 可多次传入; 单查 UUID 时取第一个",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        min=1,
        help="列出时的最大条数",
    ),
) -> None:
    """查看单个 episode(传 UUID)或按分区列出 episodes(省略 UUID)."""
    if uuid is not None:

        async def _get_one(graphiti: Graphiti) -> EpisodicNode:
            driver = driver_for(
                graphiti=graphiti, group_id=group_id[0] if group_id else None
            )
            return await EpisodicNode.get_by_uuid(driver, uuid)

        episode = run_async(action=_get_one)
        echo_json(data=dump_model(model=episode))
        return

    async def _get_list(graphiti: Graphiti) -> list[EpisodicNode]:
        effective_ids = await resolve_group_ids(
            graphiti=graphiti, group_ids=group_id or []
        )
        episodes: list[EpisodicNode] = []
        for gid in effective_ids:
            driver = driver_for(graphiti=graphiti, group_id=gid)
            found = await EpisodicNode.get_by_group_ids(driver, [gid], limit=limit)
            episodes.extend(found)
        episodes.sort(key=lambda ep: ep.uuid, reverse=True)
        return episodes[:limit]

    episodes = run_async(action=_get_list)
    echo_json(data=dump_models(models=episodes))


# ======================================================================================
# CLI: ``graphiti-cli episode patch``
# ======================================================================================
@app.command(name="patch")
def patch(  # noqa: PLR0913
    *,
    uuid: str = typer.Argument(
        ...,
        help="episode UUID",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 需与写入时一致",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="新名称",
    ),
    content: str | None = typer.Option(
        None,
        "--content",
        help="新正文, 传 '-' 时从 stdin 读取",
    ),
    source_description: str | None = typer.Option(
        None,
        "--source-description",
        help="新数据来源描述",
    ),
    valid_at: str | None = typer.Option(
        None,
        "--valid-at",
        help="ISO8601, 事实发生时间",
    ),
) -> None:
    """增量修改 episode 的描述字段.

    注意: 修改 content 只更新原始数据, 不会触发重新抽取实体/关系;
    如需按新内容重建图谱, 请删除后重新添加.
    """

    async def _action(graphiti: Graphiti) -> EpisodicNode:
        driver = driver_for(graphiti=graphiti, group_id=group_id)
        episode = await EpisodicNode.get_by_uuid(driver, uuid)
        if name is not None:
            episode.name = name
        if content is not None:
            episode.content = read_stdin_or_value(value=content, label="--content")
        if source_description is not None:
            episode.source_description = source_description
        if valid_at is not None:
            episode.valid_at = parse_datetime(value=valid_at, label="--valid-at")
        await episode.save(driver)
        return episode

    episode = run_async(action=_action)
    echo_json(data=dump_model(model=episode))


# ======================================================================================
# CLI: ``graphiti-cli episode delete``
# ======================================================================================
@app.command(name="delete")
def delete(
    *,
    uuid: str = typer.Argument(
        ...,
        help="episode UUID",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 需与写入时一致",
    ),
) -> None:
    """删除 episode, 仅其独有的实体与关系会被级联删除."""

    async def _action(graphiti: Graphiti) -> None:
        graphiti.driver = driver_for(graphiti=graphiti, group_id=group_id)
        await graphiti.remove_episode(uuid)

    run_async(action=_action)
    typer.echo(f"已删除 episode: {uuid}")


# ======================================================================================
# CLI: ``graphiti-cli episode nodes``
# ======================================================================================
@app.command(name="nodes")
def nodes(
    *,
    uuids: list[str] = typer.Argument(
        ...,
        help="episode UUID, 可传多个",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 需与写入时一致",
    ),
) -> None:
    """查看 episode 产出的实体节点(溯源查询)."""

    async def _action(graphiti: Graphiti) -> SearchResults:
        graphiti.driver = driver_for(graphiti=graphiti, group_id=group_id)
        return await graphiti.get_nodes_and_edges_by_episode(list(uuids))

    result = run_async(action=_action)
    echo_json(data={"nodes": dump_models(models=result.nodes)})


# ======================================================================================
# CLI: ``graphiti-cli episode edges``
# ======================================================================================
@app.command(name="edges")
def edges(
    *,
    uuids: list[str] = typer.Argument(
        ...,
        help="episode UUID, 可传多个",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 需与写入时一致",
    ),
) -> None:
    """查看 episode 产出的关系边(溯源查询)."""

    async def _action(graphiti: Graphiti) -> SearchResults:
        graphiti.driver = driver_for(graphiti=graphiti, group_id=group_id)
        return await graphiti.get_nodes_and_edges_by_episode(list(uuids))

    result = run_async(action=_action)
    echo_json(data={"edges": dump_models(models=result.edges)})
