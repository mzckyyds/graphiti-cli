"""graphiti-cli 常量定义."""

from pathlib import Path

__all__ = [
    "RUNS_DIR",
]


RUNS_DIR = Path.home() / ".graphiti-cli"
