from typing import Any, ClassVar, Dict, List
from pathlib import Path

from ontobdc.shared.adapter.loader import ResolverLoader
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException

from infobim.project.adapter.contract import ProjectGuard
from infobim.drawing.plugin.capability.transformation.dxf_to_ifcx import (
    DxfToIfcxCapability,
)
from infobim.drawing.plugin.capability.transformation.dxf_ifcx_linkset import (
    DxfIfcxLinksetCapability,
)


class DxfToIfcxCommand(CliCommandPort):
    """Convert a DXF file into a cached IFCX payload for the current Project."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="drawing_dxf_to_ifcx",
        logical_component="drawing",
        description="Convert a DXF file into a cached IFCX payload.",
        arguments=[
            {
                "accepts": ["--dxf-to-ifcx"],
                "valued": True,
                "parameter": "dxf_path",
                "description": "Path to the DXF file to convert.",
                "usage": "infobim drawing --dxf-to-ifcx <path/to/file.dxf>",
            },
            {
                "accepts": [],
                "valued": True,
                "parameter": "container",
                "description": "The Project this payload is cached under.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "drawing"
    FLAG: ClassVar[str] = "--dxf-to-ifcx"
    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    DXF_PATH_KEY: ClassVar[str] = "dxf_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 3
            and args[0] == DxfToIfcxCommand.COMPONENT
            and args[1] == DxfToIfcxCommand.FLAG
            and bool(str(args[2]).strip())
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        if not (
            len(command_args) == 2
            and command_args[0] == self.FLAG
            and bool(str(command_args[1]).strip())
        ):
            return False

        container_value: Any = self._request.context.get_parameter_value(
            self.CONTAINER_PATH_KEY
        )
        if not isinstance(container_value, str) or not container_value.strip():
            raise CliCommandArgumentException(
                "No InfoBIM Project was resolved. Run this command inside one."
            )
        container_path: Path = Path(container_value).expanduser().resolve()
        ProjectGuard.guard(container_path, self._request.context.root_path)

        source_path: Path = Path(command_args[1]).expanduser().resolve()
        if not source_path.is_file():
            raise CliCommandArgumentException(f"DXF file not found: {source_path}")
        if source_path.suffix.lower() != ".dxf":
            raise CliCommandArgumentException(f"Not a DXF file: {source_path}")

        self._request.context.set_parameter_value(
            self.DXF_PATH_KEY, str(source_path)
        )

        return True

    def run(self) -> CommandResponse:
        conversion: Dict[str, Any] = CapabilityExecutor.execute(
            DxfToIfcxCapability(),
            self._request.context,
            StrategyParamResolver(ResolverLoader()),
        )
        self._request.context.set_parameter_value(
            DxfIfcxLinksetCapability.IFCX_PATH_KEY, conversion["ifcx_path"]
        )
        linkset: Dict[str, Any] = CapabilityExecutor.execute(
            DxfIfcxLinksetCapability(),
            self._request.context,
            StrategyParamResolver(ResolverLoader()),
        )

        return CommandResponse(
            title="InfoBIM Drawing: DXF to IFCX",
            description=(
                "Converted the DXF file into a cached IFCX payload and "
                "declared its ISO 21597 linkset."
            ),
            content={**conversion, **linkset},
        )
