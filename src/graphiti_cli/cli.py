"""graphiti-cli 根命令行.

结构: ``set`` 子命令负责写配置, 其余命令从配置读取后执行.
"""

from __future__ import annotations

import typer

from graphiti_cli.cmds import edge_cmd, episode_cmd, node_cmd, set_cmd, triplet_cmd

__all__ = [
    "app",
]


app = typer.Typer(
    help="Graphiti 时序知识图谱 CLI, 配置文件: ~/.graphiti-cli/settings.json.",
    no_args_is_help=True,
)

app.add_typer(
    set_cmd,
    name="set",
    help="配置 LLM/Embedding/Reranker 与 FalkorDB.",
)
app.add_typer(
    episode_cmd,
    name="episode",
    help="管理 episodes(写入信息与溯源查询).",
)
app.add_typer(
    node_cmd,
    name="node",
    help="管理实体节点(检索与直写增删改).",
)
app.add_typer(
    edge_cmd,
    name="edge",
    help="管理关系边/事实(检索与直写增删改).",
)
app.add_typer(
    triplet_cmd,
    name="triplet",
    help="直写事实三元组(绕过抽取流程).",
)
