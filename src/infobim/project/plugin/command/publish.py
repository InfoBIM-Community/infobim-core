from typing import Dict, List

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class ProjectPublishCommand(CliCommandPort):
    """Stub command for publishing a project element as a navigable PDF."""

    USAGE = (
        "infobim project --project <project_id> --element <element_uri> "
        "--profile <profile_uri> --audience <audience_type> --output <file_path>"
    )

    METADATA = CliCommandMetadata(
        id="proj_publish",
        logical_component="project",
        description=(
            "Publish a selected project element as a filtered, navigable PDF "
            "for a declared profile and audience."
        ),
        arguments=[
            {
                "accepts": ["--project"],
                "valued": True,
                "description": "Select the source InfoBIM project.",
                "usage": USAGE,
            },
            {
                "accepts": ["--element"],
                "valued": True,
                "description": "Select the source element or WorkStream URI.",
                "usage": USAGE,
            },
            {
                "accepts": ["--profile"],
                "valued": True,
                "description": "Select the publication profile URI.",
                "usage": USAGE,
            },
            {
                "accepts": ["--audience"],
                "valued": True,
                "description": "Declare the target audience type.",
                "usage": USAGE,
            },
            {
                "accepts": ["--output"],
                "valued": True,
                "description": "Set the output PDF file path.",
                "usage": USAGE,
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 11
            and args[0] == "project"
            and all(
                flag in args
                for flag in (
                    "--project",
                    "--element",
                    "--profile",
                    "--audience",
                    "--output",
                )
            )
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        args: List[str] = list(self._request.command_args)
        if len(args) != 10:
            return False

        argument_pairs: Dict[str, str] = {
            args[index]: str(args[index + 1]).strip()
            for index in range(0, len(args), 2)
        }

        project_id: str = str(
            self._request.context.get_parameter_value("project_id")
            or argument_pairs.get("--project", "")
        ).strip()
        element_uri: str = argument_pairs.get("--element", "")
        profile_uri: str = argument_pairs.get("--profile", "")
        audience_type: str = argument_pairs.get("--audience", "")
        output_path: str = argument_pairs.get("--output", "")

        if not all(
            (project_id, element_uri, profile_uri, audience_type, output_path)
        ):
            raise CliCommandArgumentException(f"Usage: {self.USAGE}")

        self._request.context.set_parameter_value("project_id", project_id)
        self._request.context.set_parameter_value("element_uri", element_uri)
        self._request.context.set_parameter_value("publication_profile_uri", profile_uri)
        self._request.context.set_parameter_value("publication_audience_type", audience_type)
        self._request.context.set_parameter_value("publication_output_path", output_path)
        return True

    def run(self) -> CommandResponse:
        content: Dict[str, str] = {
            "status": "stub",
            "project_id": str(
                self._request.context.get_parameter_value("project_id")
            ),
            "element_uri": str(
                self._request.context.get_parameter_value("element_uri")
            ),
            "profile_uri": str(
                self._request.context.get_parameter_value("publication_profile_uri")
            ),
            "audience_type": str(
                self._request.context.get_parameter_value("publication_audience_type")
            ),
            "output_path": str(
                self._request.context.get_parameter_value("publication_output_path")
            ),
        }

        return CommandResponse(
            title="Navigable PDF Publication",
            description="Command stub. PDF publication implementation pending.",
            content=content,
        )
