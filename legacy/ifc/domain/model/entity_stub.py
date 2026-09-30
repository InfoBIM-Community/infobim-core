from typing import ClassVar


class IfcEntityStub:
    """Minimal declarative stub for an IFC schema class.

    These stubs intentionally carry no creation, persistence, geometry, or
    validation behavior. They only give the IFC work a stable Python symbol
    while the creation workflow is implemented.
    """

    IFC_CLASS: ClassVar[str]

    @classmethod
    def ifc_class(cls) -> str:
        return cls.IFC_CLASS


class IfcProjectStub(IfcEntityStub):
    IFC_CLASS = "IfcProject"


class IfcSiteStub(IfcEntityStub):
    IFC_CLASS = "IfcSite"


class IfcBuildingStub(IfcEntityStub):
    IFC_CLASS = "IfcBuilding"


class IfcBuildingStoreyStub(IfcEntityStub):
    IFC_CLASS = "IfcBuildingStorey"


class IfcPipeSegmentStub(IfcEntityStub):
    IFC_CLASS = "IfcPipeSegment"


class IfcSanitaryTerminalStub(IfcEntityStub):
    IFC_CLASS = "IfcSanitaryTerminal"


class IfcTankStub(IfcEntityStub):
    IFC_CLASS = "IfcTank"


class IfcPumpStub(IfcEntityStub):
    IFC_CLASS = "IfcPump"
