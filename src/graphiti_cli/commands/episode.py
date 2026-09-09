"""About `EpisodeNode`."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import typer
from graphiti_core.nodes import EpisodeType, EpisodicNode
from graphiti_core.utils.datetime_utils import utc_now

from ._base import (
    delete_model,
    dump_model,
    dump_models,
    echo_json,
    get_model,
    list_model,
    parse_datetime,
    run_async,
)

if TYPE_CHECKING:
    from datetime import datetime

    from graphiti_core import Graphiti
    from graphiti_core.graphiti import AddEpisodeResults


__all__ = [
    "episode_add",
    "episode_delete",
    "episode_get",
    "episode_list",
]


# ======================================================================================
# Helper Functions
# ======================================================================================
def _read_stdin_or_value(
    *,
    value: str,
    label: str,
) -> str:
    if value != "-":
        return value
    content = sys.stdin.read()
    if not content.strip():
        msg = f"{label} read empty content from stdin"
        raise typer.BadParameter(msg)
    return content


# ======================================================================================
# CLI: ``graphiti-cli episode add ...``
# ======================================================================================
def episode_add(  # noqa: PLR0913
    *,
    content: str = typer.Option(
        ...,
        "--content",
        help="`EpisodeNode` episode body, pass '-' to read from stdin",
    ),
    uuid: str | None = typer.Option(
        None,
        "--uuid",
        help="custom `EpisodeNode` uuid",
    ),
    name: str = typer.Argument(
        ...,
        help="`EpisodeNode` name",
    ),
    source: EpisodeType = typer.Option(
        EpisodeType.text,
        "--source",
        case_sensitive=False,
        help="`EpisodeNode` source: text/json/message",
    ),
    source_description: str = typer.Option(
        "",
        "--source-description",
        help="`EpisodeNode` source description",
    ),
    reference_time: str | None = typer.Option(
        None,
        "--reference-time",
        help="ISO8601, defaults to current UTC time",
    ),
    update_communities: bool = typer.Option(
        False,  # noqa: FBT003
        "--update-communities",
        help="Should update community summaries after writing",
    ),
    instructions: str | None = typer.Option(
        None,
        "--instructions",
        help="Custom extraction instructions, guiding entity/relationship extraction",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Add an `EpisodeNode`.

    Will trigger entity/relationship extraction for `--content`.
    """
    body = _read_stdin_or_value(value=content, label="--content")
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
# CLI: ``graphiti-cli episode get ...``
# ======================================================================================
def episode_get(
    *,
    uuid: str = typer.Argument(
        ...,
        help="`EpisodeNode` uuid",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Get a single `EpisodeNode` by `--uuid`."""

    async def _action(graphiti: Graphiti) -> EpisodicNode:
        return await get_model(
            graphiti=graphiti,
            model_cls=EpisodicNode,
            group_id=group_id,
            uuid=uuid,
            label="EpisodeNode",
        )

    episode = run_async(action=_action)
    echo_json(data=dump_model(model=episode))


# ======================================================================================
# CLI: ``graphiti-cli episode list ...``
# ======================================================================================
def episode_list(
    *,
    limit: int = typer.Option(
        10,
        "--limit",
        min=1,
        help="maximum number to list per partition",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """List `EpisodeNode` by `--group-id`."""

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
# CLI: ``graphiti-cli episode delete ...``
# ======================================================================================
def episode_delete(
    *,
    uuid: str = typer.Argument(
        ...,
        help="`EpisodeNode` uuid",
    ),
    group_id: str | None = typer.Option(
        None,
        "--group-id",
        help="graph partition ID, null for default partition",
    ),
) -> None:
    """Delete an `EpisodeNode` by `--uuid`.

    Will cascade delete its produced edges and entities only mentioned by it.
    """

    async def _action(graphiti: Graphiti) -> str:
        return await delete_model(
            graphiti=graphiti,
            model_cls=EpisodicNode,
            group_id=group_id,
            uuid=uuid,
            label="EpisodeNode",
            delete=lambda graphiti, episode: graphiti.remove_episode(episode.uuid),
        )

    deleted = run_async(action=_action)
    typer.echo(f"Deleted `EpisodeNode`: {deleted}")
