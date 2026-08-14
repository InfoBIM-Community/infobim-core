from typing import Dict, List, Optional

from ontobdc.shared.facade.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.shared.facade.response.command import CommandResponse


class ProjectLocateElementCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="proj_locate_element",
        logical_component="project",
        description="Register a project element class and its geolocation in the project container metadata.",
        arguments=[
            {
                "accepts": [
                    "--project",
                    "--project-id",
                    "--element",
                    "--locate-at",
                ],
                "valued": True,
                "description": "Boilerplate command to locate an element class at a latitude/longitude for a project.",
                "usage": "infobim project --project <project_id> --element <class_uri> --locate-at <latitude,longitude>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if len(args) < 2:
            return False

        return (
            args[0] == "project"
            and any(flag in args for flag in ("--project", "--project-id"))
            and "--element" in args
            and "--locate-at" in args
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        project_id_value: object = self._request.context.get_parameter_value("project_id")
        project_id: Optional[str] = (
            str(project_id_value).strip() if project_id_value is not None else None
        )
        element_class_uri: Optional[str] = self._get_flag_value("--element")
        located_at: Optional[str] = self._get_flag_value("--locate-at")

        if not project_id or not element_class_uri or not located_at:
            return False

        self._request.context.set_parameter_value("project_id", project_id)
        self._request.context.set_parameter_value("element_class_uri", element_class_uri)
        self._request.context.set_parameter_value("located_at", located_at)
        return True

    def run(self) -> CommandResponse:
        project_id: str = str(self._request.context.get_parameter_value("project_id"))
        element_class_uri: str = str(self._request.context.get_parameter_value("element_class_uri"))
        located_at: str = str(self._request.context.get_parameter_value("located_at"))

        content: Dict[str, str] = {
            "project_id": project_id,
            "element_class_uri": element_class_uri,
            "located_at": located_at,
        }

        return CommandResponse(
            title="Project Element Location",
            description="Boilerplate command stub. Implementation pending.",
            content=content,
        )

    def _get_flag_value(self, flag_name: str) -> Optional[str]:
        args: List[str] = list(self._request.command_args)
        if flag_name in args:
            index: int = args.index(flag_name)
            if index + 1 >= len(args):
                return None

            value: str = str(args[index + 1]).strip()
            if not value:
                return None

            return value

        context_parameter_name_by_flag: Dict[str, str] = {
            "--project": "project_id",
            "--project-id": "project_id",
            "--element": "element_class_uri",
            "--locate-at": "located_at",
        }
        context_parameter_name: Optional[str] = context_parameter_name_by_flag.get(flag_name)
        if not context_parameter_name:
            return None

        context_value: object = self._request.context.get_parameter_value(context_parameter_name)
        if context_value is None:
            return None

        resolved_value: str = str(context_value).strip()
        if not resolved_value:
            return None

        return resolved_value
