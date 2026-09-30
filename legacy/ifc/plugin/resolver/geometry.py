from typing import Any, ClassVar

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.resolver import ParamResolverStrategyPort

from infobim.ifc.domain.model.geometry import GeometryDefinition


class GeometryParamResolverStrategy(ParamResolverStrategyPort):
    """
    Hands a capability the run's geometry as the object it declared.

    A geometry command produces a ``GeometryDefinition``; a capability
    declares an object. Turning one into the other is resolution, not
    something each capability should carry a conversion for, so it happens
    here, before the input is checked.

    A value that is neither is left as it is, and the capability's own
    input check reports it — this normalizes the forms the definition
    legitimately arrives in, it does not invent one.
    """

    GEOMETRY_URI: ClassVar[str] = "org.infobim.ifc.geometry"

    def supports(self, parameter_uri: str) -> bool:
        return parameter_uri.strip() == self.GEOMETRY_URI

    def resolve(
        self,
        context: CliContextPort,
        parameter_uri: str,
        parameter_name: str,
    ) -> None:
        if not context.has_parameter(parameter_name):
            return

        value: Any = context.get_parameter_value(parameter_name)
        if not isinstance(value, GeometryDefinition):
            return

        context.set_parameter_value(parameter_name, value.to_dict())
