from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.storage.plugin.machine.open_file.port import OpenFileChainSupport

from infobim.drawing.plugin.machine.dwg_to_dxf.machine import DwgToDxfStateTransitionHandler


class DwgToDxfOpenFileConversion:
    """
    Convert the requested DWG into DXF and point the open-file path at it.

    The DWG path is handed to the DWG to DXF machine, which must report the
    converted DXF path; the open-file path is then replaced by it.
    """

    DWG_PATH_KEY: ClassVar[str] = "dwg_path"
    CONVERTED_DXF_PATH_KEY: ClassVar[str] = "dxf_path"

    @classmethod
    def convert(cls, context: CliContextPort) -> str:
        context.set_parameter_value(
            cls.DWG_PATH_KEY,
            RequiredParameter.of(context, OpenFileChainSupport.PATH_KEY),
        )
        conversion: Dict[str, Any] = DwgToDxfStateTransitionHandler(context).execute()
        if cls.CONVERTED_DXF_PATH_KEY not in conversion:
            raise RuntimeError("DWG to DXF conversion returned no DXF path.")

        dxf_path: str = conversion[cls.CONVERTED_DXF_PATH_KEY]
        context.set_parameter_value(OpenFileChainSupport.PATH_KEY, dxf_path)
        return dxf_path
