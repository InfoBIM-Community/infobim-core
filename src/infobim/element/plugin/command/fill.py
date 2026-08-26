from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import InteractiveCommandResponse

from infobim.element.adapter.facade_field import (
    ElementFacadeFieldResolver,
    ElementFieldResolution,
)
from infobim.element.adapter.fill_form import ElementFillFormAdapter
from infobim.element.plugin.command import support
from infobim.project.plugin.parameter.project import ProjectIdStrategy

_DEFAULT_IFC_SCHEMA: str = "IFC4"


class ElementFillCommand(CliCommandPort):
    """Open a branded Textual form to fill one Element instance's fields.

    ``infobim element --project <project_id> --dataset <dataset_id>
    --entity <entity_uri> --fill [--schema <ifc_schema>]``. Fields come
    entirely from the entity's declared Facade (the dataset's own
    materialized ``linkset/facade.ttl``); when none is declared and the
    entity looks like an IFC class, fields fall back to IfcOpenShell's
    official schema for ``--schema`` (default ``IFC4``) — see
    ``ElementFacadeFieldResolver``.
    """

    METADATA = CliCommandMetadata(
        id="element_fill",
        logical_component="element",
        description="Fill one Element instance's fields in a branded Textual form.",
        arguments=[
            support.argument(
                ["--project"],
                valued=True,
                description="Select the Project through ProjectIdStrategy.",
            ),
            support.argument(
                ["--dataset"],
                valued=True,
                description=(
                    "Select the dataset by its directory name inside the "
                    "project."
                ),
            ),
            support.argument(
                ["--entity"],
                valued=True,
                description="Select the entity type by URI.",
            ),
            support.argument(
                ["--fill"],
                valued=False,
                description="Open the field-fill form.",
            ),
            support.argument(
                ["--schema"],
                valued=True,
                description=(
                    "IFC schema used for the no-facade fallback field "
                    "source (default IFC4)."
                ),
            ),
        ],
    )

    def __init__(
        self,
        request: CliCommandRequest,
        field_resolver: Optional[ElementFacadeFieldResolver] = None,
        form_adapter: Optional[ElementFillFormAdapter] = None,
    ) -> None:
        self._request = request
        self._field_resolver: ElementFacadeFieldResolver = (
            field_resolver or ElementFacadeFieldResolver()
        )
        self._form_adapter: ElementFillFormAdapter = (
            form_adapter or ElementFillFormAdapter()
        )
        self._dataset_id: str = ""
        self._entity_uri: str = ""
        self._ifc_schema: str = _DEFAULT_IFC_SCHEMA
        self._dataset_path: Optional[Path] = None

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            bool(args)
            and args[0] == "element"
            and ElementFillCommand._shape(args[1:])
        )

    @staticmethod
    def _shape(args: List[str]) -> bool:
        if len(args) not in (7, 9):
            return False
        base_ok: bool = (
            args[0] == "--project"
            and bool(str(args[1]).strip())
            and args[2] == "--dataset"
            and bool(str(args[3]).strip())
            and args[4] == "--entity"
            and bool(str(args[5]).strip())
            and args[6] == "--fill"
        )
        if not base_ok:
            return False
        if len(args) == 7:
            return True
        return args[7] == "--schema" and bool(str(args[8]).strip())

    def check(self) -> bool:
        args: List[str] = list(self._request.command_args)
        if not self._shape(args):
            return False

        project_selector: str = args[1].strip()
        self._request.context.set_parameter_value("project", project_selector)
        ProjectIdStrategy().execute(self._request.context)
        project_path_value: str = str(
            self._request.context.get_parameter_value("project_path") or ""
        ).strip()
        if not project_path_value:
            raise CliCommandArgumentException(
                f"InfoBIM Project not found: {project_selector}"
            )

        self._dataset_id = args[3].strip()
        self._entity_uri = args[5].strip()
        if len(args) == 9:
            self._ifc_schema = args[8].strip() or _DEFAULT_IFC_SCHEMA

        dataset_path: Path = Path(project_path_value) / self._dataset_id
        if not dataset_path.is_dir():
            raise CliCommandArgumentException(
                f"Dataset not found in project: {self._dataset_id}"
            )
        self._dataset_path = dataset_path
        return True

    def run(self) -> InteractiveCommandResponse:
        assert self._dataset_path is not None
        resolution: ElementFieldResolution = self._field_resolver.resolve(
            dataset_path=self._dataset_path,
            entity_uri=self._entity_uri,
            ifc_schema=self._ifc_schema,
            ontology_root=Path(str(self._request.context.root_path)),
        )
        values: Dict[str, str] = self._form_adapter.open(
            entity_uri=self._entity_uri, resolution=resolution
        )
        filled_count: int = sum(1 for value in values.values() if value.strip())

        return InteractiveCommandResponse(
            title="Element Fill",
            description=(
                f"Filled {filled_count}/{resolution.field_count} "
                f"field(s) ({resolution.source.value}) on "
                f"{self._entity_uri}."
            ),
            content={
                "project_id": support.value(self._request, "project_id"),
                "dataset_id": self._dataset_id,
                "entity_uri": self._entity_uri,
                "source": resolution.source.value,
                "values": values,
            },
        )
