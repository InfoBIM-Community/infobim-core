from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from infobim.context.adapter.entity import IfcRuntimeEntityAdapter
from infobim.shared.adapter.path import CliPathAdapter
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.context.adapter.machine import EntityLearningStateTransitionHandler
from ontobdc.context.adapter.repository import EntityLearningStepRepository


class ContextLearnFromIfcElementCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="learn_from_ifc_element",
        logical_component="context",
        description="Learn an InfoBIM IFC element profile from a file or directory.",
        arguments=[
            {
                "accepts": ["--element"],
                "valued": True,
                "description": "IFC element name or URI to be resolved as a runtime entity.",
                "usage": "infobim context --element <element_uri> --learn-from <file_path>",
            },
            {
                "accepts": ["--learn-from"],
                "valued": True,
                "description": "Learn an IFC element profile from a file or directory.",
                "usage": "infobim context --element <element_uri> --learn-from <file_path>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) == 5 and args[0] == "context" and "--element" in args and "--learn-from" in args

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._entity_adapter = IfcRuntimeEntityAdapter()
        self._path_adapter: CliPathAdapter = CliPathAdapter()

    def check(self) -> bool:
        raw_element, learn_from_path = self._parse_arguments()
        resolved_entity: Dict[str, str] = self._entity_adapter.resolve(raw_element)

        resolved_path: Path = self._path_adapter.resolve(
            learn_from_path,
            root_path=self._request.context.root_path,
        )
        if not resolved_path.exists():
            raise CliCommandArgumentException(f"Invalid learn-from path: {learn_from_path}")

        source_files: List[Path] = self._collect_source_files(resolved_path)
        if not source_files:
            raise CliCommandArgumentException(f"No PDF files found in '{resolved_path}'.")

        self._request.context.set_parameter_value("element_name", resolved_entity["element_name"])
        self._request.context.set_parameter_value("element_uri", resolved_entity["element_uri"])
        self._request.context.set_parameter_value("entity_uri", resolved_entity["entity_uri"])
        self._request.context.set_parameter_value("learn_from_path", str(resolved_path))
        self._request.context.set_parameter_value(
            "learn_source_files",
            [str(source_file) for source_file in source_files],
        )
        return True

    def run(self) -> CommandResponse:
        element_name: str = str(self._request.context.get_parameter_value("element_name")).strip()
        element_uri: str = str(self._request.context.get_parameter_value("element_uri")).strip()
        entity_uri: str = str(self._request.context.get_parameter_value("entity_uri")).strip()
        source_files: List[str] = list(self._request.context.get_parameter_value("learn_source_files"))
        root_path: str = str(self._request.context.root_path).strip()
        results: List[Dict[str, object]] = []

        try:
            runtime_entity: Dict[str, str] = self._entity_adapter.register(root_path=root_path, raw_element=element_name)
            self._request.context.set_parameter_value("entity_uri", runtime_entity["entity_uri"])

            for source_file in source_files:
                step_repository = EntityLearningStepRepository(
                    root_path=root_path,
                    source_path=source_file,
                )
                self._request.context.set_parameter_value("step_repository", step_repository)
                self._request.context.set_parameter_value("learn_source_path", source_file)

                response: CommandResponse = EntityLearningStateTransitionHandler(
                    context=self._request.context,
                ).execute()
                if isinstance(response, ExceptionCommandResponse):
                    raise ValueError(str(response.description).strip() or "The entity learning pipeline failed.")

                published_payload: Optional[Dict[str, Any]] = self._extract_published_payload(response)
                if published_payload is None:
                    raise ValueError("The entity learning pipeline did not publish a valid learning record.")

                runtime_entity["context_file"] = self._entity_adapter.persist_learning_record(
                    root_path=root_path,
                    published_payload=published_payload,
                )
                results.append(
                    {
                        "source_file": source_file,
                        "response": response.content,
                    }
                )

            runtime_entity = self._entity_adapter.register(root_path=root_path, raw_element=element_name)

            return CommandResponse(
                title="IFC Element Learned",
                description=(
                    f"Processed {len(results)} learning source file(s) for IFC element '{element_name}'."
                ),
                content={
                    "element_name": element_name,
                    "element_uri": element_uri,
                    "entity_uri": entity_uri,
                    "processed_files": len(results),
                    "context_file": runtime_entity["context_file"],
                    "results": results,
                },
            )
        except Exception as exc:
            return ExceptionCommandResponse(
                title="IFC Element Learning Failed",
                description=f"Could not learn IFC element '{element_name}' from the provided source path.",
                content={
                    "element_name": element_name,
                    "element_uri": element_uri,
                    "entity_uri": entity_uri,
                    "source_files": source_files,
                    "error": str(exc),
                },
            )

    def _parse_arguments(self) -> Tuple[str, str]:
        command_args: List[str] = list(self._request.command_args)
        if len(command_args) != 4:
            raise CliCommandArgumentException(
                "Usage: infobim context --element <element_uri> --learn-from <file_path>"
            )

        argument_pairs = {
            command_args[index]: command_args[index + 1]
            for index in range(0, len(command_args), 2)
        }
        raw_element: str = str(argument_pairs.get("--element", "")).strip()
        learn_from_path: str = str(argument_pairs.get("--learn-from", "")).strip()
        if not raw_element or not learn_from_path:
            raise CliCommandArgumentException(
                "Usage: infobim context --element <element_uri> --learn-from <file_path>"
            )

        return raw_element, learn_from_path

    def _collect_source_files(self, resolved_path: Path) -> List[Path]:
        if resolved_path.is_file():
            return [resolved_path] if resolved_path.suffix.lower() == ".pdf" else []

        return sorted(
            file_path
            for file_path in resolved_path.rglob("*.pdf")
            if file_path.is_file()
        )

    def _extract_published_payload(self, response: CommandResponse) -> Optional[Dict[str, Any]]:
        content: Any = getattr(response, "content", {})
        if not isinstance(content, dict):
            return None

        published: Any = content.get("published")
        if not isinstance(published, dict):
            return None

        return published
