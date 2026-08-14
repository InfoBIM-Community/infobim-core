from __future__ import annotations

from typing import List, Optional

from infobim.context.service import ContextEntityCreateService
from infobim.project.plugin.parameter.project import ProjectIdStrategy
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class InfoBIMContextEntityCommand(CliCommandPort):
    """Proxy OntoBDC context/entity operations through an InfoBIM Project."""

    METADATA = CliCommandMetadata(
        id="context_entity",
        logical_component="context",
        description="Operate OntoBDC context entities through an InfoBIM Project.",
        arguments=[
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": "Look up an entity catalog, instance list, or single entity by URI/CURIE.",
                "usage": (
                    "infobim context --entity --all | "
                    "infobim context --entity <entity_uri|EntityName> "
                    "[--project-id <GlobalId>|--project <selector>] | "
                    "infobim context --create <instance_name> --entity <EntityName> "
                    "[--project-id <GlobalId>|--project <selector>]"
                ),
            },
            {"accepts": ["--all"], "valued": False, "description": "List the full entity catalog."},
            {"accepts": ["--create"], "valued": True, "description": "Create a new entity instance."},
            {
                "accepts": ["--project-id", "--project"],
                "valued": True,
                "description": "Select the InfoBIM Project an instance operation applies to.",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "context":
            return False
        body = args[1:]
        if body == ["--entity", "--all"]:
            return True
        if len(body) == 2 and body[0] == "--entity":
            return True
        if "--entity" not in body:
            return False
        if "--create" in body:
            return len(body) in (4, 6)
        return len(body) in (2, 4)

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        args = list(self._request.command_args)
        if args == ["--entity", "--all"]:
            return True
        if "--entity" not in args:
            return False

        self._bind_explicit_values(args)

        entity_value = self._value_after(args, "--entity")
        if not entity_value:
            return False

        # A URI/CURIE lookup and the catalog listing are global context operations;
        # instance list/create operations require a Project resolution.
        if ":" in entity_value and "--create" not in args and not self._has_project_selector(args):
            return True

        ProjectIdStrategy().execute(self._request.context)
        project_id = str(self._request.context.get_parameter_value("project_id") or "").strip()
        container_id = str(self._request.context.get_parameter_value("container_id") or "").strip()
        container_path = str(self._request.context.get_parameter_value("container_path") or "").strip()
        return bool(project_id and container_id and container_path)

    def run(self) -> CommandResponse:
        if self._is_infobim_context_create():
            result = ContextEntityCreateService().create(
                project_id=self._context_value("project_id"),
                project_path=self._context_value("project_path"),
                container_id=self._context_value("container_id"),
                entity=self._value_after(
                    list(self._request.command_args), "--entity"
                )
                or "",
                instance_name=self._value_after(
                    list(self._request.command_args), "--create"
                )
                or "",
                context=self._request.context,
            )
            return CommandResponse(
                title="Context Entity Created",
                description=(
                    "Created an ontology-declared InfoBIM entity context "
                    f"for '{result.entity_uri}'."
                ),
                content=result.to_dict(),
            )

        # Imported here, not at module level: a module-level import would
        # make CommandLoader's discovery (inspect.getmembers()) see this
        # class as a second candidate command for InfoBIM's own "context"
        # domain -- both share logical_component == "context" and both
        # accept the same argv, so every context --entity call would raise
        # a "Multiple commands match" ambiguity error. This command is used
        # here as an implementation detail, not re-exported as one of
        # InfoBIM's own top-level commands (contrast with
        # infobim/cli/plugin/command/init.py's deliberate re-export).
        from ontobdc.context.plugin.command.entity import ContextEntityCommand

        proxy_args = self._to_ontobdc_args(list(self._request.command_args))
        request = CliCommandRequest(
            logical_component="context",
            component_action="entity",
            command_args=proxy_args,
            context=self._request.context,
        )
        command = ContextEntityCommand(request)
        if not command.check():
            raise ValueError(f"Invalid InfoBIM context entity command: {self._request.command_args}")
        return command.run()

    def _is_infobim_context_create(self) -> bool:
        args = list(self._request.command_args)
        entity = self._value_after(args, "--entity") or ""
        local_name = entity.rstrip("/#").rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        return "--create" in args and local_name.lower() == "ifcworkschedule"

    def _context_value(self, name: str) -> str:
        return str(self._request.context.get_parameter_value(name) or "").strip()

    def _bind_explicit_values(self, args: List[str]) -> None:
        for flag, parameter in (
            ("--entity", "entity"),
            ("--create", "create"),
            ("--project-id", "project_id"),
            ("--project", "project"),
        ):
            value = self._value_after(args, flag)
            if value is not None:
                self._request.context.set_parameter_value(parameter, value)

    def _to_ontobdc_args(self, args: List[str]) -> List[str]:
        if args == ["--entity", "--all"]:
            return args

        entity_value = self._value_after(args, "--entity")
        create_value = self._value_after(args, "--create")
        container_id = str(self._request.context.get_parameter_value("container_id") or "").strip()

        if create_value is not None:
            if container_id:
                return ["--create", create_value, "--entity", entity_value or "", "--container", container_id]
            return ["--create", create_value, "--entity", entity_value or ""]

        if ":" in str(entity_value or "") and not container_id:
            return ["--entity", entity_value or ""]

        if container_id:
            return ["--container", container_id, "--entity", entity_value or ""]
        return ["--entity", entity_value or ""]

    @staticmethod
    def _value_after(args: List[str], flag: str) -> Optional[str]:
        try:
            index = args.index(flag)
        except ValueError:
            return None
        if index + 1 >= len(args):
            return None
        value = str(args[index + 1] or "").strip()
        return value or None

    @staticmethod
    def _has_project_selector(args: List[str]) -> bool:
        return "--project-id" in args or "--project" in args
