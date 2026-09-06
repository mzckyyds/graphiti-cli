"""episode/node/edge/triplet 各命令共用的工具函数.

约定: 每个命令用 ``run_async`` 执行一段接收 Graphiti 实例的协程,
结果统一以 JSON 输出(与 ``set show`` 风格一致).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import typer

from graphiti_cli.client import build_graphiti

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from graphiti_core import Graphiti
    from graphiti_core.driver.driver import GraphDriver
    from pydantic import BaseModel

__all__ = [
    "driver_for",
    "echo_json",
    "parse_attributes",
    "parse_datetime",
    "read_stdin_or_value",
    "resolve_group_ids",
    "run_async",
]


logger = logging.getLogger(__name__)

# 输出时剔除的向量字段, 避免刷屏
_EMBEDDING_FIELDS = ("name_embedding", "fact_embedding")


# ======================================================================================
# 执行与输出
# ======================================================================================
def run_async[T](*, action: Callable[[Graphiti], Awaitable[T]]) -> T:
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
    except Exception as exc:
        logger.debug("命令执行失败", exc_info=True)
        typer.secho(f"错误: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None


def echo_json(*, data: Any) -> None:  # noqa: ANN401
    """以 JSON 形式输出结果.

    Args:
        data: 待输出的数据.

    """
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def dump_model(*, model: BaseModel) -> dict[str, Any]:
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


def dump_models(*, models: Sequence[BaseModel]) -> list[dict[str, Any]]:
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
def parse_datetime(*, value: str, label: str) -> datetime:
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


def parse_attributes(*, pairs: Sequence[str]) -> dict[str, Any]:
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


def read_stdin_or_value(*, value: str, label: str) -> str:
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
def driver_for(*, graphiti: Graphiti, group_id: str | None) -> GraphDriver:
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


async def resolve_group_ids(
    *,
    graphiti: Graphiti,
    group_ids: Sequence[str],
) -> list[str]:
    """解析有效的图分区 ID 列表, 未显式传入时从当前图中收集现存分区.

    注意: 只扫描当前默认图, FalkorDB 下其他分区的 group_id 不会出现在结果里.

    Args:
        graphiti: Graphiti 实例.
        group_ids: 显式传入的分区 ID 列表.

    Returns:
        去重后的分区 ID 列表, 图为空时返回空列表.

    """
    if group_ids:
        return list(dict.fromkeys(group_ids))
    query = (
        "MATCH (n) WHERE n.group_id IS NOT NULL RETURN DISTINCT n.group_id AS group_id"
    )
    result = cast(
        "tuple[list[dict[str, Any]], Any, Any]",
        await graphiti.driver.execute_query(  # pyright: ignore[reportUnknownMemberType]
            query,
            routing_="r",
        ),
    )
    records = result[0]
    return [str(record["group_id"]) for record in records if record.get("group_id")]
