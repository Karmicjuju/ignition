from __future__ import annotations

import typer

from ignition import __version__
from ignition.app import IgnitionApp

app = typer.Typer(
    name="ignition",
    help="Terminal-native developer onboarding and workspace command centre.",
    add_completion=False,
    no_args_is_help=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ignition {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    demo: bool = typer.Option(False, "--demo", help="Launch with seeded demo state."),
    operator: bool = typer.Option(
        False, "--operator", help="Enable operator mode (privileged debug features).", hidden=True
    ),
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    # operator mode is wired through but no-op in v0.1; flag is reserved for future use.
    _ = operator
    IgnitionApp(demo_mode=demo).run()


if __name__ == "__main__":
    app()
