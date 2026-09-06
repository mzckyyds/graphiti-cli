"""graphiti-cli 各类子命令的统一存放处, 每类命令一个模块."""

from .config import app as config_cmd
from .edge import app as edge_cmd
from .episode import app as episode_cmd
from .node import app as node_cmd
from .triplet import app as triplet_cmd

__all__ = [
    "config_cmd",
    "edge_cmd",
    "episode_cmd",
    "node_cmd",
    "triplet_cmd",
]
