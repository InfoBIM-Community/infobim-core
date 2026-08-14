
from typing import Any, Dict
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.plugin.command.init import CliInitCommand as OntoBDCCliInitCommand


class CliInitCommand(OntoBDCCliInitCommand):
    """
    InfoBIM wrapper command for the shared bootstrap init flow.
    """
    METADATA = CliCommandMetadata(
        id="init",
        logical_component="cli",
        description="Initialize InfoBIM in the current directory.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "init",
                ],
                "description": "Initialize InfoBIM in the current directory.",
            },
        ],
    )

    def run(self) -> CommandResponse:
        """
        Execute the command to initialize the InfoBIM environment.
        """
        response: CommandResponse = super().run()
        response.title = "InfoBIM Init"
        response.description = "Bootstrap initialization executed successfully for InfoBIM."
        response.content = self._update_response_content(response.content)

        return response

    def _update_response_content(
        self,
        content: Dict[str, Any],
    ) -> Dict[str, Any]:
        updated_content: Dict[str, Any] = dict(content)

        root_path: Any = updated_content.pop("root_path", None)
        if isinstance(root_path, str) and root_path.strip():
            updated_content["project_root"] = root_path

        ontobdc_directory: Any = updated_content.get("ontobdc_directory")
        if isinstance(ontobdc_directory, str) and ontobdc_directory.strip():
            updated_content["infobim_bootstrap_directory"] = ontobdc_directory

        return updated_content
