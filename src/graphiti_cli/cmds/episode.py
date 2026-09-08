"""CLI: ``graphiti-cli episode {add|get|list|delete}``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from graphiti_core.nodes import EpisodeType, EpisodicNode
from graphiti_core.utils.datetime_utils import utc_now

from graphiti_cli.cmds.common import (
    delete_model,
    dump_model,
    dump_models,
    echo_json,
    get_model,
    list_model,
    parse_datetime,
    read_stdin_or_value,
    run_async,
)

if TYPE_CHECKING:
    from datetime import datetime

    from graphiti_core import Graphiti
    from graphiti_core.graphiti import AddEpisodeResults

__all__ = [
    "app",
]


app = typer.Typer(
    help="管理 episodes: 添加(触发实体/关系抽取)/查询/删除.",
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
# CLI: ``graphiti-cli episode get``
# ======================================================================================
@app.command(name="get")
def get_episode(
    *,
    uuid: str = typer.Argument(
        ...,
        help="episode UUID",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认分区",
    ),
) -> None:
    """按 UUID 查看单个 episode."""

    async def _action(graphiti: Graphiti) -> EpisodicNode:
        return await get_model(
            graphiti=graphiti,
            model_cls=EpisodicNode,
            group_id=group_id,
            uuid=uuid,
            label="episode",
        )

    episode = run_async(action=_action)
    echo_json(data=dump_model(model=episode))


# ======================================================================================
# CLI: ``graphiti-cli episode list``
# ======================================================================================
@app.command(name="list")
def list_episodes(
    *,
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认分区",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        min=1,
        help="单分区的最大条数",
    ),
) -> None:
    """按分区列出 episodes."""

    async def _action(graphiti: Graphiti) -> list[EpisodicNode]:
        return await list_model(
            graphiti=graphiti,
            model_cls=EpisodicNode,
            group_id=group_id,
            limit=limit,
        )

    episodes = run_async(action=_action)
    echo_json(data=dump_models(models=episodes))


# ======================================================================================
# CLI: ``graphiti-cli episode delete``
# ======================================================================================
@app.command(name="delete")
def delete_episode(
    *,
    uuid: str = typer.Argument(
        ...,
        help="episode UUID",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="图分区 ID, 缺省为默认分区",
    ),
) -> None:
    """按 UUID 删除 episode, 仅其独有的实体与关系会被级联删除."""

    async def _action(graphiti: Graphiti) -> str:
        return await delete_model(
            graphiti=graphiti,
            model_cls=EpisodicNode,
            group_id=group_id,
            uuid=uuid,
            label="episode",
            delete=lambda graphiti, episode: graphiti.remove_episode(episode.uuid),
        )

    deleted = run_async(action=_action)
    typer.echo(f"已删除 episode: {deleted}")
