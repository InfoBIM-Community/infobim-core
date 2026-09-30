import json
from pathlib import Path
from typing import Any, ClassVar

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.resolver import ParamResolverStrategyPort


class JsonLdParamResolverStrategy(ParamResolverStrategyPort):
    """
    Hands a Writer Capability its JSON-LD as an object, however it arrived.

    The handoff between the loader side and the writer side is JSON-LD, and
    it reaches the Writer either as the object a Loader Capability just
    returned or as the path of a ``.jsonld`` file someone points at from the
    command line. A Writer declares one input, ``json_ld``, of type
    ``object``: it is not the Writer's job to know that the same parameter
    sometimes arrives as a path and to carry a file-reading fallback for it.

    Resolution runs before the input is validated, so by the time the Writer
    is checked the parameter is an object in both cases. A value that is
    neither is left as it is, and the Writer's own input check reports it.
    """

    JSON_LD_URI: ClassVar[str] = "org.infobim.ifc.json_ld"

    def supports(self, parameter_uri: str) -> bool:
        return parameter_uri.strip() == self.JSON_LD_URI

    def resolve(
        self,
        context: CliContextPort,
        parameter_uri: str,
        parameter_name: str,
    ) -> None:
        if not context.has_parameter(parameter_name):
            return

        value: Any = context.get_parameter_value(parameter_name)
        if isinstance(value, dict):
            return

        if not isinstance(value, str) or not value.strip():
            return

        document_path: Path = Path(value.strip()).expanduser().resolve()
        if not document_path.is_file():
            raise ValueError(
                f"The JSON-LD document does not exist: {document_path}."
            )

        loaded: Any = json.loads(document_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(
                f"The JSON-LD document must be an object: {document_path}."
            )

        context.set_parameter_value(parameter_name, loaded)
