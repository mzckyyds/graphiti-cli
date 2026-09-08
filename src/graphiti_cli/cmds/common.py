"""episode/node/edge/triplet 各命令共用的工具函数.

约定: 每个命令用 ``run_async`` 执行一段接收 Graphiti 实例的协程,
结果统一以 JSON 输出(与 ``config show`` 风格一致).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import typer
from graphiti_core.edges import EntityEdge
from graphiti_core.errors import NodeNotFoundError
from graphiti_core.helpers import get_default_group_id
from graphiti_core.nodes import EntityNode, EpisodicNode
from graphiti_core.search.search_filters import ComparisonOperator, DateFilter

from graphiti_cli.client import build_graphiti

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from graphiti_core import Graphiti
    from graphiti_core.driver.driver import GraphDriver
    from pydantic import BaseModel

__all__ = [
    "build_date_filters",
    "delete_model",
    "driver_for",
    "echo_json",
    "effective_group_id",
    "get_model",
    "list_model",
    "parse_attributes",
    "parse_datetime",
    "patch_model",
    "read_stdin_or_value",
    "run_async",
]


logger = logging.getLogger(__name__)

# 输出时剔除的向量字段, 避免刷屏
_EMBEDDING_FIELDS = ("name_embedding", "fact_embedding")


# ======================================================================================
# 执行与输出
# ======================================================================================
def run_async[T](
    *,
    action: Callable[[Graphiti], Awaitable[T]],
) -> T:
    """构建 Graphiti 实例并执行异步操作, 失败时输出错误并以非零码退出.

    Args:
        action: 接收 Graphiti 实例并返回 awaitable 的回调.

    Returns:
        action 的执行结果.

    Raises:
        typer.Exit: 执行出错时以退出码 1 结束.

    """

    async def _run() -> T:
        graphiti = build_graphiti()
        try:
            return await action(graphiti)
        finally:
            await graphiti.close()

    try:
        return asyncio.run(_run())
    except typer.Exit:
        # 协程内已输出过错误信息, 原样透传退出码
        raise
    except Exception as exc:
        logger.debug("命令执行失败", exc_info=True)
        typer.secho(f"错误: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None


def echo_json(
    *,
    data: Any,  # noqa: ANN401
) -> None:
    """以 JSON 形式输出结果.

    Args:
        data: 待输出的数据.

    """
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def dump_model(
    *,
    model: BaseModel,
) -> dict[str, Any]:
    """把 pydantic 模型序列化为 dict, 剔除向量字段.

    Args:
        model: 待序列化的模型.

    Returns:
        不含 name_embedding/fact_embedding 的字段字典.

    """
    data = model.model_dump(mode="json")
    for field in _EMBEDDING_FIELDS:
        data.pop(field, None)
    return data


def dump_models(
    *,
    models: Sequence[BaseModel],
) -> list[dict[str, Any]]:
    """批量序列化 pydantic 模型, 剔除向量字段.

    Args:
        models: 待序列化的模型序列.

    Returns:
        字段字典列表.

    """
    return [dump_model(model=model) for model in models]


# ======================================================================================
# 参数解析
# ======================================================================================
def parse_datetime(
    *,
    value: str,
    label: str,
) -> datetime:
    """把 ISO8601 字符串解析为 datetime, 无时区时按 UTC 处理.

    Args:
        value: ISO8601 时间字符串.
        label: 选项名, 用于报错.

    Returns:
        解析后的 datetime.

    Raises:
        typer.BadParameter: 字符串不是合法的 ISO8601 时间时.

    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        msg = f"{label} 不是合法的 ISO8601 时间: {value!r}"
        raise typer.BadParameter(msg) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def build_date_filters(
    *,
    after: str | None,
    before: str | None,
    label_prefix: str,
) -> list[list[DateFilter]]:
    """构造 DNF 形式的日期区间过滤(内层 AND, 外层 OR).

    SearchFilters 的日期字段语义为: 外层列表各元素之间 OR, 单个元素
    内部的多个 DateFilter 之间 AND. 上下界同传时必须落在同一内层列表,
    才能表达区间(AND), 否则会退化成恒真的 OR.

    Args:
        after: ISO8601 下界, None 表示不限.
        before: ISO8601 上界, None 表示不限.
        label_prefix: 选项名前缀, 用于报错.

    Returns:
        可赋给 SearchFilters.valid_at/created_at 等字段的过滤条件.

    """
    and_filters: list[DateFilter] = []
    if after is not None:
        and_filters.append(
            DateFilter(
                date=parse_datetime(value=after, label=f"--{label_prefix}-after"),
                comparison_operator=ComparisonOperator.greater_than_equal,
            )
        )
    if before is not None:
        and_filters.append(
            DateFilter(
                date=parse_datetime(value=before, label=f"--{label_prefix}-before"),
                comparison_operator=ComparisonOperator.less_than_equal,
            )
        )
    return [and_filters] if and_filters else []


def parse_attributes(
    *,
    pairs: Sequence[str],
) -> dict[str, Any]:
    """把 KEY=VALUE 形式的选项解析为属性字典.

    VALUE 优先按 JSON 解析(支持数字/布尔/嵌套结构), 失败时保留原始字符串.

    Args:
        pairs: KEY=VALUE 字符串列表.

    Returns:
        解析后的属性字典.

    Raises:
        typer.BadParameter: 某项不含 '=' 或 KEY 为空时.

    """
    attributes: dict[str, Any] = {}
    for pair in pairs:
        key, sep, raw = pair.partition("=")
        if not sep or not key:
            msg = f"属性需为 KEY=VALUE 格式: {pair!r}"
            raise typer.BadParameter(msg)
        try:
            attributes[key] = json.loads(raw)
        except json.JSONDecodeError:
            attributes[key] = raw
    return attributes


def read_stdin_or_value(
    *,
    value: str,
    label: str,
) -> str:
    """读取选项值, 传 '-' 时改为从 stdin 读取.

    Args:
        value: 选项原始值.
        label: 选项名, 用于报错.

    Returns:
        最终的内容字符串.

    Raises:
        typer.BadParameter: 从 stdin 读到空内容时.

    """
    if value != "-":
        return value
    content = sys.stdin.read()
    if not content.strip():
        msg = f"{label} 从 stdin 读到了空内容"
        raise typer.BadParameter(msg)
    return content


# ======================================================================================
# 查询辅助
# ======================================================================================
def driver_for(
    *,
    graphiti: Graphiti,
    group_id: str | None,
) -> GraphDriver:
    """返回指向指定图分区的 driver.

    FalkorDB 下每个 group_id 对应一张同名图, 直写与按 UUID 直读都必须
    落在对的图上; 其他 provider 的 group_id 只是节点属性, 原 driver 即可.

    Args:
        graphiti: Graphiti 实例.
        group_id: 图分区 ID, None 表示使用当前默认图.

    Returns:
        指向目标分区的 GraphDriver.

    """
    if not group_id:
        return graphiti.driver
    return graphiti.driver.clone(database=group_id)


def effective_group_id(
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


# ======================================================================================
# 分区与选取
# ======================================================================================
def _require_single[ModelT](
    *,
    models: list[ModelT],
    uuid: str,
    label: str,
) -> ModelT:
    """校验按 UUID 查找的结果有且只有一条, 否则报错退出.

    Args:
        models: 查找结果列表.
        uuid: 请求的 UUID.
        label: 对象名称(如 episode/EntityNode/关系边), 用于报错文案.

    Returns:
        唯一命中的模型.

    Raises:
        typer.Exit: 未找到或命中多条时以退出码 1 结束.

    """
    if len(models) == 1:
        return models[0]
    msg = f"未找到 {label}: {uuid}" if not models else f"{label} {uuid} 命中了多条记录"
    typer.secho(f"错误: {msg}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


async def _select_models[ModelT: (EpisodicNode, EntityNode, EntityEdge)](
    *,
    graphiti: Graphiti,
    model_cls: type[ModelT],
    group_id: str | None,
    uuid: str | None,
    limit: int | None = None,
) -> list[ModelT]:
    """在单个图分区上获取节点/边.

    传入 uuid 时按 UUID 单个获取, 未找到返回空列表; 未传 uuid 时拉取
    分区内全部(受 limit 限制).

    Args:
        graphiti: Graphiti 实例.
        model_cls: 节点/边模型类, 需提供 get_by_uuid 与 get_by_group_ids.
        group_id: 图分区 ID, None 表示默认分区.
        uuid: 待获取的 UUID, None 表示获取分区内全部.
        limit: 整组拉取时的最大条数, None 表示不限制.

    Returns:
        命中的模型列表(按 UUID 获取时为 0 或 1 条).

    """
    driver = driver_for(graphiti=graphiti, group_id=group_id)
    if uuid is not None:
        try:
            # graphiti_core 的 get_by_uuid 返回未标注, 需显式收窄
            model = cast("ModelT", await model_cls.get_by_uuid(driver, uuid))
        except NodeNotFoundError:
            return []
        return [model]
    effective_gid = effective_group_id(graphiti=graphiti, gid=group_id)
    # graphiti_core 的 get_by_group_ids 返回未标注, 需显式收窄
    return cast(
        "list[ModelT]",
        await model_cls.get_by_group_ids(driver, [effective_gid], limit=limit),
    )


async def get_model[ModelT: (EpisodicNode, EntityNode, EntityEdge)](
    *,
    graphiti: Graphiti,
    model_cls: type[ModelT],
    group_id: str | None,
    uuid: str,
    label: str,
) -> ModelT:
    """按 UUID 在单个分区上获取节点/边, 目标必须存在且唯一.

    Args:
        graphiti: Graphiti 实例.
        model_cls: 节点/边模型类.
        group_id: 图分区 ID, None 表示默认分区.
        uuid: 待获取记录的 UUID.
        label: 对象名称, 用于报错文案.

    Returns:
        命中的模型.

    Raises:
        typer.Exit: 未找到或命中多条时以退出码 1 结束.

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
    """按分区列出节点/边.

    Args:
        graphiti: Graphiti 实例.
        model_cls: 节点/边模型类.
        group_id: 图分区 ID, None 表示默认分区.
        limit: 最大条数, None 表示不限制.

    Returns:
        命中的模型列表.

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
    """按 UUID 获取节点/边, 应用修改回调后保存回其来源分区, 目标必须存在且唯一.

    Args:
        graphiti: Graphiti 实例.
        model_cls: 节点/边模型类.
        group_id: 图分区 ID, None 表示默认分区.
        uuid: 待修改记录的 UUID.
        label: 对象名称, 用于报错文案.
        patch: 接收记录并原地修改的回调, 可为异步(如重建向量).

    Returns:
        修改后的模型.

    Raises:
        typer.Exit: 未找到或命中多条时以退出码 1 结束.

    """
    models = await _select_models(
        graphiti=graphiti, model_cls=model_cls, group_id=group_id, uuid=uuid
    )
    model = _require_single(models=models, uuid=uuid, label=label)
    await patch(model)
    # 记录自带所属分区, 在其来源图上保存
    await model.save(driver_for(graphiti=graphiti, group_id=model.group_id))
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
    """按 UUID 在单个分区上查找并删除节点/边, 目标必须存在且唯一.

    Args:
        graphiti: Graphiti 实例.
        model_cls: 节点/边模型类.
        group_id: 图分区 ID, None 表示默认分区.
        uuid: 待删除记录的 UUID.
        label: 对象名称, 用于报错文案.
        delete: 接收 (Graphiti 实例, 记录) 并执行删除的回调,
            缺省为 ``model.delete(graphiti.driver)``.

    Returns:
        已删除记录的 UUID.

    Raises:
        typer.Exit: 未找到或命中多条时以退出码 1 结束.

    """
    models = await _select_models(
        graphiti=graphiti, model_cls=model_cls, group_id=group_id, uuid=uuid
    )
    model = _require_single(models=models, uuid=uuid, label=label)
    # 记录自带所属分区, 在其来源图上执行删除
    graphiti.driver = driver_for(graphiti=graphiti, group_id=model.group_id)
    if delete is None:
        await model.delete(graphiti.driver)
    else:
        await delete(graphiti, model)
    return model.uuid
