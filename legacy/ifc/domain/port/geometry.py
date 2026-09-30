from abc import ABC, abstractmethod

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.chain import ChainResponsibilityPort

from infobim.ifc.domain.model.geometry import GeometryDefinition


class GeometryProducerPort(ABC):
    """
    Produces one primitive geometry from the inputs its own form declares.

    A producer answers with a ``GeometryDefinition`` and nothing else: no
    IFC entity, no placement, and no opinion about which IFC class the
    geometry will end up representing. Each form — a box from three
    orthogonal dimensions, a cylinder from a radius, a length and an
    extrusion direction, a sphere from a radius — declares its own inputs,
    which is what keeps one command per form instead of one command that
    guesses the form from the arguments it was handed.
    """

    GEOMETRY_KEY: str = "geometry"

    @abstractmethod
    def geometry(self, context: CliContextPort) -> GeometryDefinition:
        """
        Return the geometry the context's inputs define.
        """
        ...


class GeometryCreateResponsibilityPort(ChainResponsibilityPort):
    """
    Contract implemented by capabilities that can materialize one primitive
    geometry definition as IFC representation items.

    The inherited ``can_handle`` method is the only selection contract the
    chain needs. Concrete responsibilities own both recognition and creation
    of their primitive; the state machine does not dispatch on geometry kind.
    """

    pass
