import json
from typing import Any, ClassVar, List


class IfcValueText:
    """The text of a value of an IFC attribute or property, as the fields of an entity carry it."""

    DECIMALS: ClassVar[int] = 4

    @classmethod
    def of(cls, value: Any) -> List[str]:
        """
        None for an empty value, one for a single, each for a list. What is none of those (the properties of a
        complex property, an entity) is the text it has, never left out.
        """
        if value is None:
            return []
        if isinstance(value, bool):
            return ["true" if value else "false"]
        if isinstance(value, float):
            return [f"{value:.{cls.DECIMALS}f}".rstrip("0").rstrip(".")]
        if isinstance(value, (str, int)):
            return [str(value)]
        if isinstance(value, (list, tuple)):
            return [text for item in value for text in cls.of(item)]
        if isinstance(value, dict):
            return [json.dumps(value, ensure_ascii=False, default=str)]
        return [str(value)]
