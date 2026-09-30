import shutil
from typing import Any, ClassVar
from pathlib import Path

from ontobdc.shared.adapter.etl import EtlDirectoryContract
from ontobdc.shared.adapter.slug import TitleSlug
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

from infobim.ifc.domain.exception.creation import IfcCreationError


class GeometricProductState:
    """
    Holds the geometry a run creates, outside the project's own IFC model.

    A geometric product is assembled before anything of it belongs in the
    model the project federates: the primitive is created, its shape
    representation wraps it, and only a product carrying that
    representation is worth publishing. Writing each of those steps
    straight into the federated model leaves the model carrying geometry
    nothing references — a block no product owns cannot even be found
    again, because a representation item is not rooted and has nothing to
    be addressed by.

    So the steps write here instead: one STEP file per product, under the
    project's ETL state directory, in the schema the target model is
    written in, so what is assembled can be merged into the model
    unchanged. It is a state file and it reads as one — the same layout
    every other persisted state of this codebase uses,
    ``.__ontobdc__/etl/<module>/<phase>/<entity>/<element>/``, with the
    slug of the product's title as the element.

    Assembling the same product again replaces its file rather than
    adding to it: what a run creates is that run's product, and a second
    block beside the first would be geometry belonging to nobody, which
    is the thing this exists to avoid.
    """

    ETL_MODULE_NAME: ClassVar[str] = "ifc"
    ETL_PHASE_NAME: ClassVar[str] = "geometric_product_create"
    ETL_ENTITY_NAME: ClassVar[str] = "product"
    GEOMETRY_FILE_NAME: ClassVar[str] = "__geometric_product__.ifc"
    ELEMENT_FILE_NAME: ClassVar[str] = "__geometric_product_element__.ifc"

    @classmethod
    def path_of(cls, container_path: Path, title: str, file_name: str) -> Path:
        """
        Return one state file of the product the title names.

        A product is assembled in two files, because the two are worth
        telling apart: the geometry and its representation, and the
        element that carries them. Both live under the same element
        directory, which is what makes them one product's state.
        """
        return cls.directory_of(container_path, title) / file_name

    @classmethod
    def directory_of(cls, container_path: Path, title: str) -> Path:
        """
        Return the directory a product is assembled in.

        While it is being assembled a product has a title and no
        identity, so the title names its directory. What it is named
        once it has one is settled by ``identified_as``.
        """
        slug: str = TitleSlug.of(title)
        if not slug:
            raise IfcCreationError(
                f"The product title '{title}' has no character a state file "
                f"can be named after."
            )

        return cls.root_of(container_path) / slug

    @classmethod
    def root_of(cls, container_path: Path) -> Path:
        """
        Return where the project keeps the products it assembles.
        """
        return StorageBootstrap.get_ontobdc_directory(container_path).joinpath(
            EtlDirectoryContract.DIRECTORY_NAME,
            cls.ETL_MODULE_NAME,
            cls.ETL_PHASE_NAME,
            cls.ETL_ENTITY_NAME,
        )

    @classmethod
    def identified_as(
        cls,
        container_path: Path,
        title: str,
        global_id: str,
    ) -> Path:
        """
        File a product's state under the identity it was given.

        A title is what a product is called and an identity is what it
        is: two products may be renamed into each other's titles, and
        the state of one is still not the state of the other. So the
        directory a product was assembled in is named after its GlobalId
        once it has one, and every later run of the same product
        replaces that state rather than leaving one directory per name
        it has ever had.

        A product assembled again arrives at the same identity, so the
        state already filed under it is the same product's and is
        replaced by what this run assembled.
        """
        assembled: Path = cls.directory_of(container_path, title)
        identified: Path = cls.root_of(container_path) / global_id.strip()
        if not global_id.strip():
            raise IfcCreationError(
                "A product with no identity cannot have its state filed "
                "under one."
            )

        if identified == assembled or not assembled.is_dir():
            return identified

        if identified.exists():
            shutil.rmtree(identified)

        assembled.replace(identified)

        return identified

    @classmethod
    def read(cls, state_path: Path) -> Any:
        """
        Return the product being assembled, or fail saying it is not there.
        """
        import ifcopenshell

        if not state_path.is_file():
            raise IfcCreationError(
                f"The geometric product state file does not exist: "
                f"{state_path}. The geometry of this run was not created."
            )

        try:
            return ifcopenshell.open(str(state_path))
        except Exception as error:
            raise IfcCreationError(
                f"The geometric product state file does not open with the "
                f"STEP reader: {state_path} ({error})."
            ) from error

    @classmethod
    def write(cls, model: Any, state_path: Path) -> Path:
        """
        Persist the product being assembled and return where it was written.
        """
        state_path.parent.mkdir(parents=True, exist_ok=True)
        model.write(str(state_path))

        return state_path
