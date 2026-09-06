"""``config [show|set]`` 子命令."""

import typer

from .set import app as set_cmd
from .show import show

__all__ = [
    "app",
]

app = typer.Typer(
    help="查看与写入 ~/.graphiti-cli/settings.json.",
    no_args_is_help=True,
)
app.command(name="show")(show)
app.add_typer(set_cmd, name="set")
