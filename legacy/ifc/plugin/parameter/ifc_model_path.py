from typing import Any, ClassVar, List, Optional
from pathlib import Path

from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort

from ontobdc.storage.adapter.crate import ContainerRoCrate

from infobim.ifc.adapter.model import IfcModelBootstrap
from infobim.ifc.domain.port.model import IfcModelBootstrapPort
from infobim.ifc.domain.exception.creation import (
    IfcModelNotResolvedError,
    IfcModelNotUsableError,
)


class IfcModelPathStrategy(CliContextStrategyPort):
    """
    Resolves which IFC model an IFC command writes into.

    Supplied explicitly, the path is used, and a path that is not a usable
    model of this project fails. Left out, the project's own models
    decide:

    ``0`` models
        a basic model is created and its path bound — carrying no model
        yet is a project's normal starting point, not an error;
    ``1`` model
        it is the target, because there is nothing to choose between;
    more than one
        the command fails asking for ``--ifc-model-path``, because picking
        one of several models to modify is the caller's decision.

    The search is the project's own, never the configured root that may
    hold several projects: a model belonging to a neighbouring project is
    not a target this one may write into.

    However it ends, the model is stated in the project's RO-Crate, which
    is what lets the IFC → IFCX pipeline find elements in it later.
    """

    SELECTOR_FLAG: ClassVar[str] = "--ifc-model-path"
    PARAMETER_KEY: ClassVar[str] = "ifc_model_path"
    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"

    METADATA: ParameterMetadata = ParameterMetadata(
        id="org.infobim.ifc.plugin.parameter.ifc_model_path",
        version="1.0.0",
        name="ifc_model_path",
        description=(
            "Resolve the IFC model an IFC command targets, selecting the "
            "project's only model or creating a basic one when it has none."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
        tags=["infobim", "ifc", "model"],
        supported_languages=["en", "pt-br"],
    )

    MODEL_SUFFIX: ClassVar[str] = ".ifc"

    def __init__(
        self,
        bootstrap: Optional[IfcModelBootstrapPort] = None,
    ) -> None:
        self._bootstrap: IfcModelBootstrapPort = bootstrap or IfcModelBootstrap()

    def execute(self, context: CliContextPort) -> CliContextPort:
        """
        Bind the IFC model the command targets, or fail saying why not.

        Only a flag this invocation actually carries counts as a choice.
        The context outlives a command, so a model resolved for an earlier
        run — in another project, even — is still sitting there, and
        reading it back would let one project's model be handed to the
        next one as if the caller had named it.
        """
        project_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_PATH_KEY)
        ).expanduser().resolve()

        supplied: Any = (
            context.get_parameter_value(self.PARAMETER_KEY)
            if self.SELECTOR_FLAG in context.raw_args
            else None
        )
        if isinstance(supplied, str) and supplied.strip():
            model_path: Path = self._supplied(project_path, supplied)
        else:
            model_path = self._resolved(project_path)

        context.set_parameter_value(self.PARAMETER_KEY, str(model_path))

        return context

    def _supplied(self, project_path: Path, supplied: str) -> Path:
        """
        Return the model the caller named, or fail saying why it cannot serve.
        """
        model_path: Path = Path(supplied.strip()).expanduser()
        if not model_path.is_absolute():
            model_path = project_path / model_path

        model_path = model_path.resolve()
        if not model_path.is_file():
            raise IfcModelNotUsableError(
                f"The supplied IFC model does not exist: {model_path}."
            )

        if not model_path.is_relative_to(project_path):
            raise IfcModelNotUsableError(
                f"The supplied IFC model is outside the project at "
                f"{project_path}: {model_path}."
            )

        if model_path not in self._declared_models(project_path):
            raise IfcModelNotUsableError(
                f"The project at {project_path} states no IFC model at "
                f"{model_path}. A file the project does not declare is not "
                f"a target a product may be created in."
            )

        return model_path

    def _resolved(self, project_path: Path) -> Path:
        """
        Return the project's own model, creating a basic one if it has none.
        """
        models: List[Path] = self._declared_models(project_path)
        if not models:
            return self._bootstrap.create(project_path)

        if len(models) > 1:
            raise IfcModelNotResolvedError(
                f"The project at {project_path} states "
                f"{len(models)} IFC models "
                f"({', '.join(model.name for model in models)}); name the "
                f"target with {self.SELECTOR_FLAG}."
            )

        return models[0]

    @classmethod
    def _declared_models(cls, project_path: Path) -> List[Path]:
        """
        Return the IFC models the project's RO-Crate states and still holds.

        What a project holds is what it declares, not what a walk of the
        directory turns up: a payload this tooling cached for itself and a
        file nobody declared are both on the disk, and neither is a model
        of the project. The IFC → IFCX pipeline reads the same crate to
        find elements, so this and it always agree about what exists.

        A file the crate states and the project no longer has is not a
        model either. The crate is then behind the project rather than
        wrong about it, and what answers that is creating the model
        again, not handing a path that is not there to whoever opens it
        next. The manifest the command syncs before the machine runs
        brings the crate back in line with what the project holds.
        """
        return sorted(
            model_path
            for relative in ContainerRoCrate.file_paths(project_path)
            if relative.lower().endswith(cls.MODEL_SUFFIX)
            for model_path in [project_path / relative]
            if model_path.is_file()
        )
