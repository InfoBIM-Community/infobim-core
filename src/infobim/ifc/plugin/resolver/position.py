from typing import ClassVar

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.resolver import ParamResolverStrategyPort


class PositionParamResolverStrategy(ParamResolverStrategyPort):
    """
    Owns the position URI a geometric-product capability declares.

    The position a geometric operation is given is a fact of the run, so
    it reaches a capability the way every declared input does: by URI,
    through the resolver that answers for it. A URI no strategy answers
    for is a missing plugin, and resolution says so rather than leaving
    the capability to find out later — which is why this exists before
    the position contract does.

    What a position looks like is the contract of whoever defines it, and
    this invents nothing: the value is left exactly as it arrived, and the
    capability's own input check reports a value that is not the object it
    declared.
    """

    POSITION_URI: ClassVar[str] = "org.infobim.ifc.position"

    def supports(self, parameter_uri: str) -> bool:
        return parameter_uri.strip() == self.POSITION_URI

    def resolve(
        self,
        context: CliContextPort,
        parameter_uri: str,
        parameter_name: str,
    ) -> None:
        return None
