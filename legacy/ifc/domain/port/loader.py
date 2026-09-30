from abc import ABC, abstractmethod
from typing import List, Type

from ontobdc.shared.domain.port.capability import CapabilityPort


class IfcCapabilityPackageLoaderPort(ABC):
    """
    Discovers IFC child capabilities inside one designated package.

    Discovery is restricted on purpose: a source loader is resolved only
    from the IFC loader package and a writer only from the IFC writer
    package, so a capability shipped elsewhere never answers for a pair it
    was not put there to answer for.

    Every candidate found is returned, including two capabilities that
    declare the same ``METADATA.id``. The generic capability loader drops
    the second of those silently, which would hide exactly the duplicate
    registration this family has to report.
    """

    @abstractmethod
    def get_all(self) -> List[Type[CapabilityPort]]:
        """
        Return every IFC capability declared inside the designated package.
        """
        ...

    @abstractmethod
    def resolve(self, schema_uri: str, ifc_class: str) -> Type[CapabilityPort]:
        """
        Return the single capability declaring the given pair.

        :raises IfcConversionError: when no capability declares the pair, or
            when more than one does.
        """
        ...
