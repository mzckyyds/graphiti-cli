from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import typer
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.edges import EntityEdge
from graphiti_core.errors import (
    EdgeNotFoundError,
    GroupsEdgesNotFoundError,
    NodeNotFoundError,
)
from graphiti_core.helpers import get_default_group_id
from graphiti_core.nodes import EntityNode, EpisodicNode

from graphiti_cli.client import build_graphiti

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from graphiti_core import Graphiti
    from graphiti_core.driver.driver import GraphDriver
    from graphiti_core.search.search_config import SearchResults
    from pydantic import BaseModel

__all__ = [
    "EDGE_RESERVED_ATTRIBUTE_KEYS",
    "NODE_RESERVED_ATTRIBUTE_KEYS",
    "delete_model",
    "driver_for",
    "dump_model",
    "dump_models",
    "echo_json",
    "effective_gid_for",
    "get_episode_nodes_and_edges",
    "get_model",
    "list_model",
    "parse_attributes",
    "parse_datetime",
    "patch_model",
    "run_async",
]


logger = logging.getLogger(__name__)


# ======================================================================================
# Execution & Output
# ======================================================================================
def run_async[T](
    *,
    action: Callable[[Graphiti], Awaitable[T]],
) -> T:
    """Build instance of `Graphiti` and execute the asynchronous action.

    Args:
        action: A callable that takes a `Graphiti` instance and returns an awaitable.

    Returns:
        The result of the action.

    Raises:
        typer.Exit: If an error occurs during execution, exits with code 1.

    """

    async def _reap_index_tasks() -> None:
        """Await FalkorDB index-building tasks spawned by cloned drivers.

        Every `FalkorDriver` (including each `clone()`) schedules
        `build_indices_and_constraints` as a background task on creation.
        Cloned drivers that end up unreferenced leave these tasks dangling,
        and `Graphiti.close()` cancels - rather than awaits - the pending
        init task of the driver it closes. So before closing, await any
        task that is still building indices and log its failure.
        """
        current = asyncio.current_task()
        strays = [
            task
            for task in asyncio.all_tasks()
            if task is not current
            and (coro := task.get_coro()) is not None
            and getattr(coro, "__name__", "") == "build_indices_and_constraints"
        ]
        if not strays:
            return
        results = await asyncio.gather(*strays, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.debug("Index building task failed", exc_info=result)

    async def _run() -> T:
        graphiti = build_graphiti()
        try:
            return await action(graphiti)
        finally:
            await _reap_index_tasks()
            await graphiti.close()

    try:
        return asyncio.run(_run())
    except (typer.Exit, typer.BadParameter):
        # `typer.Exit` is the control flow of inner helpers; `typer.BadParameter`
        # must bubble up so click renders it as a standard usage error (exit 2).
        raise
    except Exception as exc:
        logger.debug("Failed to execute action", exc_info=True)
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None


def echo_json(
    *,
    data: Any,  # noqa: ANN401
) -> None:
    """Output the result in JSON format.

    Args:
        data: The data to be output.

    """
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def dump_model(
    *,
    model: BaseModel,
) -> dict[str, Any]:
    """Serialize a pydantic model to a dict with embedding fields removed.

    Args:
        model: The model to be serialized.

    Returns:
        A dict of fields excluding name_embedding and fact_embedding.

    """
    data = model.model_dump(mode="json")
    for field in ("name_embedding", "fact_embedding"):
        data.pop(field, None)
    return data


def dump_models(
    *,
    models: Sequence[BaseModel],
) -> list[dict[str, Any]]:
    """Serialize a sequence of pydantic models with embedding fields removed.

    Args:
        models: The sequence of models to be serialized.

    Returns:
        A list of dicts of fields excluding name_embedding and fact_embedding.

    """
    return [dump_model(model=model) for model in models]


# ======================================================================================
# Parsing Utilities
# ======================================================================================
NODE_RESERVED_ATTRIBUTE_KEYS = frozenset(
    {
        "uuid",
        "name",
        "name_embedding",
        "group_id",
        "summary",
        "created_at",
        "labels",
    }
)
EDGE_RESERVED_ATTRIBUTE_KEYS = frozenset(
    {
        "uuid",
        "name",
        "group_id",
        "fact",
        "fact_embedding",
        "episodes",
        "created_at",
        "expired_at",
        "valid_at",
        "invalid_at",
        "reference_time",
        "source_uuid",
        "source_node_uuid",
        "target_uuid",
        "target_node_uuid",
    }
)


def parse_datetime(
    *,
    value: str,
    label: str,
) -> datetime:
    """Parse an ISO8601 string into a datetime, using UTC if no timezone is provided.

    Args:
        value: The ISO8601 datetime string.
        label: The option name, used for error reporting.

    Returns:
        The parsed datetime.

    Raises:
        typer.BadParameter: If the string is not a valid ISO8601 datetime.

    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(
            f"Expected ISO8601 datetime for {label!r}, got {value!r}"
        ) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_attributes(
    *,
    pairs: Sequence[str],
    reserved: frozenset[str] = frozenset(),
    label: str | None = None,
) -> dict[str, Any]:
    """Parse string with KEY=VALUE format into an attribute dictionary.

    Parse VALUE as JSON first and fall back to the raw string if failed.

    Args:
        pairs: A list of KEY=VALUE strings.
        reserved: Attribute keys reserved by the model persistence layer;
            collisions are rejected because they would be silently dropped
            (or corrupt the record) when the model is saved.
        label: The model name, used for error reporting.

    Returns:
        A dictionary of parsed attributes.

    Raises:
        typer.BadParameter: If any item does not contain '=', if the KEY is
            empty, or if a KEY collides with a reserved key.

    """
    attributes: dict[str, Any] = {}
    for pair in pairs:
        key, sep, raw = pair.partition("=")
        if not sep or not key:
            raise typer.BadParameter(f"Expected KEY=VALUE format, got {pair!r}")
        try:
            attributes[key] = json.loads(raw)
        except json.JSONDecodeError:
            attributes[key] = raw
    conflicts = sorted(reserved & attributes.keys())
    if conflicts:
        keys = ", ".join(repr(key) for key in conflicts)
        raise typer.BadParameter(
            f"Reserved attribute key(s) {keys} conflict with built-in "
            f"{label or 'model'} fields, please use different keys"
        )
    return attributes


# ======================================================================================
# Get Graph Driver/Effective Group ID
# ======================================================================================
async def driver_for(
    *,
    graphiti: Graphiti,
    group_id: str | None,
) -> GraphDriver:
    """Return the `GraphDriver` pointing to the target partition.

    In FalkorDB, each `group_id` corresponds to a graph with the same name.
    So direct writes and UUID-based reads must target the correct graph.

    The default partition always maps to the configured database, even when it
    is passed explicitly (e.g. `--group-id _` for FalkorDB): `FalkorDriver.clone('_')`
    hard-codes a fallback to `default_db` and would silently bypass a user-configured
    custom database, so the original driver is returned instead.

    A non-default partition must already exist as a graph (i.e. data has been
    written into it via `episode add --group-id`); `clone()` would otherwise
    silently create an empty graph with indexes on first query.

    Args:
        graphiti: `Graphiti` instance.
        group_id: Graph partition ID, `None` means using the current default graph.

    Returns:
        The `GraphDriver` pointing to the target partition.

    Raises:
        typer.BadParameter: If the target graph does not exist on FalkorDB.

    """
    driver = graphiti.driver
    if not group_id or group_id == get_default_group_id(driver.provider):
        return driver
    if isinstance(driver, FalkorDriver):
        # NOTE: falkordb's sync-looking `list_graphs()` wraps redis.asyncio
        # internally and returns a coroutine.
        graphs = await driver.client.list_graphs()
        if group_id not in graphs:
            raise typer.BadParameter(
                f"Graph partition {group_id!r} does not exist on FalkorDB, "
                "write data into it first via `graphiti-cli episode add --group-id`"
            )
    return driver.clone(database=group_id)


def effective_gid_for(
    *,
    graphiti: Graphiti,
    group_id: str | None,
) -> str:
    """Return the effective group id.

    Return `group_id` if it is not `None`.
    Otherwise, return the default group id for the provider.

    For FalkorDB, the default group_id is '_'.
    For other providers, the default group_id is an empty string.

    Args:
        graphiti: `Graphiti` instance.
        group_id: Graph partition ID, `None` means using the current default graph.

    Returns:
        The effective group id.

    """
    return (
        group_id
        if group_id is not None
        else get_default_group_id(graphiti.driver.provider)
    )


# ======================================================================================
# Episode Result
# ======================================================================================
async def get_episode_nodes_and_edges(
    *,
    graphiti: Graphiti,
    group_id: str | None,
    episode_uuid: str,
) -> SearchResults:
    """Return the nodes/edges produced by an episode within a single graph partition.

    `Graphiti.get_nodes_and_edges_by_episode` silently returns an empty result
    when the episode does not exist in the target partition, which is
    indistinguishable from "the episode produced nothing". So the episode is
    explicitly fetched first to report a clear error.

    Args:
        graphiti: `Graphiti` instance.
        group_id: Graph partition ID, `None` means using the current default graph.
        episode_uuid: The uuid of the `EpisodeNode`.

    Returns:
        The `SearchResults` containing the nodes and edges produced by the episode.

    Raises:
        typer.Exit: Exits(code=1) if the episode is not found in the partition.

    """
    graphiti.driver = await driver_for(graphiti=graphiti, group_id=group_id)
    effective_gid = effective_gid_for(graphiti=graphiti, group_id=group_id)
    try:
        await EpisodicNode.get_by_uuid(graphiti.driver, episode_uuid)
    except NodeNotFoundError as exc:
        msg = (
            f"EpisodeNode not found in partition {effective_gid!r}: {episode_uuid}, "
            "please make sure --group-id matches the partition containing the episode"
        )
        typer.secho(f"Error: {msg}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    return await graphiti.get_nodes_and_edges_by_episode([episode_uuid])


# ======================================================================================
# Model Get/List/Patch/Delete
# ======================================================================================
def _require_single[ModelT](
    *,
    models: list[ModelT],
    uuid: str,
    label: str,
) -> ModelT:
    """Ensure that the result of a UUID-based query contains exactly one item.

    Args:
        models: result list of the query.
        uuid:   The requested UUID.
        label:  The name of the object, used for error messages.

    Returns:
        The single model that matches the UUID.

    Raises:
        typer.Exit: Exits(code=1) if no match is found or multiple matches are found.

    """
    if len(models) == 1:
        return models[0]
    msg = (
        f"{label} not found: {uuid}"
        if not models
        else f"{label} {uuid} matched multiple records"
    )
    typer.secho(f"Error: {msg}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


async def _select_models[ModelT: (EpisodicNode, EntityNode, EntityEdge)](
    *,
    graphiti: Graphiti,
    model_cls: type[ModelT],
    group_id: str | None,
    uuid: str | None,
    limit: int | None = None,
) -> list[ModelT]:
    """Select models within a single graph partition.

    If `uuid` is provided, fetch the model by UUID; if not found, return an empty list.
    If `uuid` is not provided, fetch all models within the partition.

    Args:
        graphiti:   Graphiti instance.
        model_cls:  Model class, must provide `get_by_uuid` and `get_by_group_ids`.
        group_id:   Graph partition ID, `None` means the default partition.
        uuid:       The UUID to fetch, `None` means fetch all models.
        limit:      The maximum number of models to fetch, `None` means no limit.

    Returns:
        A list of models that match the query (0 or 1 item if fetched by UUID).

    """
    driver = await driver_for(graphiti=graphiti, group_id=group_id)
    if uuid is not None:
        try:
            model = cast("ModelT", await model_cls.get_by_uuid(driver, uuid))
        except (NodeNotFoundError, EdgeNotFoundError):
            return []
        return [model]
    effective_gid = effective_gid_for(graphiti=graphiti, group_id=group_id)
    try:
        return cast(
            "list[ModelT]",
            await model_cls.get_by_group_ids(driver, [effective_gid], limit=limit),
        )
    except GroupsEdgesNotFoundError:
        return []


async def get_model[ModelT: (EpisodicNode, EntityNode, EntityEdge)](
    *,
    graphiti: Graphiti,
    model_cls: type[ModelT],
    group_id: str | None,
    uuid: str,
    label: str,
) -> ModelT:
    """Return a single model by UUID within a single graph partition.

    Args:
        graphiti:   Graphiti instance.
        model_cls:  Model class.
        group_id:   Graph partition ID, `None` means the default partition.
        uuid:       The UUID of the record to fetch.
        label:      For error messages.

    Returns:
        The model that matches the UUID.

    Raises:
        typer.Exit: Exits(code=1) if no match is found or multiple matches are found.

    """
    models = await _select_models(
        graphiti=graphiti, model_cls=model_cls, group_id=group_id, uuid=uuid
    )
    return _require_single(models=models, uuid=uuid, label=label)


async def list_model[ModelT: (EpisodicNode, EntityNode, EntityEdge)](
    *,
    graphiti: Graphiti,
    model_cls: type[ModelT],
    group_id: str | None,
    limit: int | None = None,
) -> list[ModelT]:
    """Return a list of models within a single graph partition.

    Args:
        graphiti:   Graphiti instance.
        model_cls:  Model class.
        group_id:   Graph partition ID, `None` means the default partition.
        limit:      The maximum number of models to fetch, `None` means no limit.

    Returns:
        The list of models that match the query.

    """
    return await _select_models(
        graphiti=graphiti,
        model_cls=model_cls,
        group_id=group_id,
        uuid=None,
        limit=limit,
    )


async def patch_model[ModelT: (EpisodicNode, EntityNode, EntityEdge)](  # noqa: PLR0913
    *,
    graphiti: Graphiti,
    model_cls: type[ModelT],
    group_id: str | None,
    uuid: str,
    label: str,
    patch: Callable[[ModelT], Awaitable[None]],
) -> ModelT:
    """Patch a single model by UUID within a single graph partition.

    Args:
        graphiti: Graphiti instance.
        model_cls:  Model class.
        group_id:   Graph partition ID, `None` means the default partition.
        uuid:       The UUID of the record to patch.
        label:      For error messages.
        patch:      A callback that receives the record and modifies it in place.

    Returns:
        The patched model.

    Raises:
        typer.Exit: Exits(code=1) if no match is found or multiple matches are found.

    """
    models = await _select_models(
        graphiti=graphiti, model_cls=model_cls, group_id=group_id, uuid=uuid
    )
    model = _require_single(models=models, uuid=uuid, label=label)
    await patch(model)
    await model.save(await driver_for(graphiti=graphiti, group_id=model.group_id))
    return model


async def delete_model[ModelT: (EpisodicNode, EntityNode, EntityEdge)](  # noqa: PLR0913
    *,
    graphiti: Graphiti,
    model_cls: type[ModelT],
    group_id: str | None,
    uuid: str,
    label: str,
    delete: Callable[[Graphiti, ModelT], Awaitable[None]] | None = None,
) -> str:
    """Delete a single model by UUID within a single graph partition.

    Args:
        graphiti: Graphiti instance.
        model_cls:  Model class.
        group_id:   Graph partition ID, `None` means the default partition.
        uuid:       The UUID of the record to delete.
        label:      For error messages.
        delete:     A callback that receives and performs the deletion.

    Returns:
        The UUID of the deleted model.

    Raises:
        typer.Exit: Exits(code=1) if no match is found or multiple matches are found.

    """
    models = await _select_models(
        graphiti=graphiti, model_cls=model_cls, group_id=group_id, uuid=uuid
    )
    model = _require_single(models=models, uuid=uuid, label=label)
    graphiti.driver = await driver_for(graphiti=graphiti, group_id=model.group_id)
    if delete is None:
        await model.delete(graphiti.driver)
    else:
        await delete(graphiti, model)
    return model.uuid
