from __future__ import annotations

from typing import Any

from ontobdc.cli.domain.exception.command import CliCommandArgumentException

from infobim.project.plugin.parameter.project import ProjectIdStrategy


def argument(accepts: list[str], *, valued: bool, description: str) -> dict[str, Any]:
    return {
        "accepts": accepts,
        "valued": valued,
        "description": description,
    }


def bind_context(request: Any, args: list[str]) -> None:
    project = args[1]
    global_id = args[3]
    request.context.set_parameter_value("project", project)
    request.context.set_parameter_value("global_id", global_id)
    if "--parameter" in args:
        request.context.set_parameter_value(
            "parameter_uri",
            args[args.index("--parameter") + 1],
        )
    if "--set" in args:
        request.context.set_parameter_value(
            "set_value",
            args[args.index("--set") + 1],
        )
    ProjectIdStrategy().execute(request.context)
    if not str(request.context.get_parameter_value("project_path") or "").strip():
        raise CliCommandArgumentException(f"InfoBIM Project not found: {project}")


def value(request: Any, name: str) -> str:
    return str(request.context.get_parameter_value(name) or "").strip()


def public_args(args: list[str]) -> list[str]:
    return ["element", *args]
