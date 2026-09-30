from typing import Any, ClassVar, List, Optional
from pathlib import Path

from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort

from infobim.ifc.plugin.parameter.ifc_model_path import IfcModelPathStrategy
from infobim.ifc.domain.exception.creation import (
    IfcClassNotConcreteProductError,
    IfcClassNotDeclaredError,
)


class IfcClassStrategy(CliContextStrategyPort):
    """
    Resolves the IFC class an IFC creation command will instantiate.

    The class is validated against the schema of the target model itself,
    through the reader's own schema introspection: the declaration has to
    exist, it has to be concrete, and it has to be an ``IfcProduct``.
    There is no allow-list of classes to maintain, because the schema
    already knows which classes it has, and a list would go stale the
    first time a schema did not.

    A class the schema does not declare fails. It is never quietly
    replaced by the default: the default answers the absence of a choice,
    never a wrong one.
    """

    SELECTOR_FLAG: ClassVar[str] = "--ifc-class"
    PARAMETER_KEY: ClassVar[str] = "ifc_class"
    DEFAULT_IFC_CLASS: ClassVar[str] = "IfcBuildingElementProxy"
    PRODUCT_SUPERTYPE: ClassVar[str] = "IfcProduct"

    METADATA: ParameterMetadata = ParameterMetadata(
        id="org.infobim.ifc.plugin.parameter.ifc_class",
        version="1.0.0",
        name="ifc_class",
        description=(
            "Resolve the IFC class of the object an IFC creation command "
            "creates, validated against the schema of the target model."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
        tags=["infobim", "ifc", "class"],
        supported_languages=["en", "pt-br"],
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        """
        Bind the IFC class the command will create, or fail saying why not.

        Only a class this invocation actually named counts. The context
        outlives a command, so a class chosen in an earlier run would
        otherwise silently decide what this one creates.
        """
        supplied: Any = (
            context.get_parameter_value(self.PARAMETER_KEY)
            if self.SELECTOR_FLAG in context.raw_args
            else None
        )
        ifc_class: str = (
            supplied.strip()
            if isinstance(supplied, str) and supplied.strip()
            else self.DEFAULT_IFC_CLASS
        )

        self._validate(self._model_path(context), ifc_class)
        context.set_parameter_value(self.PARAMETER_KEY, ifc_class)

        return context

    @staticmethod
    def _model_path(context: CliContextPort) -> Path:
        """
        Return the target model, resolving it when it is not bound yet.

        The class is validated against the schema of the model it will be
        created in, so the model has to be known first. Which strategy the
        parameter stage happens to run first is not something this can
        depend on, and a value left in the context by an earlier run is
        not an answer for this one, so the resolution is asked for rather
        than read back.
        """
        IfcModelPathStrategy().execute(context)
        bound: Any = context.get_parameter_value(
            IfcModelPathStrategy.PARAMETER_KEY
        )

        return Path(str(bound)).expanduser().resolve()

    @classmethod
    def _validate(cls, model_path: Path, ifc_class: str) -> None:
        """
        Fail unless the model's schema declares this concrete IfcProduct.
        """
        import ifcopenshell
        from ifcopenshell import ifcopenshell_wrapper

        model: Any = ifcopenshell.open(str(model_path))
        schema: Any = ifcopenshell_wrapper.schema_by_name(model.schema_identifier)

        try:
            declaration: Any = schema.declaration_by_name(ifc_class)
        except RuntimeError as error:
            raise IfcClassNotDeclaredError(
                f"The schema {model.schema_identifier} of {model_path} "
                f"declares no {ifc_class}."
            ) from error

        entity: Any = declaration.as_entity()
        if entity is None:
            raise IfcClassNotConcreteProductError(
                f"{ifc_class} is not an entity of the schema "
                f"{model.schema_identifier}, so nothing can be created as one."
            )

        if entity.is_abstract():
            raise IfcClassNotConcreteProductError(
                f"{ifc_class} is abstract in the schema "
                f"{model.schema_identifier}; name a concrete class."
            )

        if cls.PRODUCT_SUPERTYPE not in cls._supertypes(entity):
            raise IfcClassNotConcreteProductError(
                f"{ifc_class} is not an {cls.PRODUCT_SUPERTYPE} in the "
                f"schema {model.schema_identifier}."
            )

    @staticmethod
    def _supertypes(entity: Any) -> List[str]:
        """
        Return the entity's own name and the names of every supertype.
        """
        names: List[str] = []
        current: Optional[Any] = entity
        while current is not None:
            names.append(current.name())
            current = current.supertype()

        return names
