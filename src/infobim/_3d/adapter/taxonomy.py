from typing import ClassVar, Tuple


class IfcMimeTaxonomy:
    PART21: ClassVar[str] = "application/p21"
    SUPPORTED: ClassVar[Tuple[str, ...]] = (PART21, "application/vnd.ifc")
