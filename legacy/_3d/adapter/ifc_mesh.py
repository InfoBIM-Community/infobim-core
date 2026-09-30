"""Convert the geometry of a Project's IFC elements into IFCX meshes."""

import json
from typing import Any, ClassVar, Dict, List, Tuple
from uuid import NAMESPACE_URL, uuid5
from pathlib import Path

from ontobdc.storage.adapter.crate import ContainerRoCrate

from infobim.drawing.model import IfcxDocument
from infobim.drawing.adapter.transformation_payload import TransformationPayloadPath
from infobim.ifc.adapter.schema_identifier import IfcSchemaIdentifier
from infobim._3d.adapter.ifc_ifcx_linkset import IfcIfcxLinksetWriter


class IfcElementMeshConverter:
    """
    Turns every IFC element that has geometry into an IFCX mesh of its own.

    The viewer draws IFCX, and a Project's geometry lives in its IFC
    models, so something has to say the same shapes in the other format.
    That is this: one mesh file per element, written the way a drawing's
    IFCX is written, so the viewer needs to know nothing about where a
    node came from.

    Which IFC models are read is what the Project's RO-Crate declares,
    and only that. A file the crate does not state is not a model of the
    Project even when it sits in the directory, and a walk of the
    directory would find both without being able to tell them apart.

    Each mesh is named after the element's own GlobalId, in the format
    directory of the schema its model is written in, and is declared
    beside its model by a linkset. The element is the unit throughout:
    the file, the linkset and the identity inside the document all say
    the same GlobalId, so a mesh can always be traced back to the
    element it draws.

    Geometry comes out of the reader in world coordinates: a mesh of one
    element travels alone, and a shape placed relative to something that
    did not travel with it would be drawn in the wrong place.
    """

    MODEL_SUFFIX: ClassVar[str] = ".ifc"
    TARGET_FORMAT: ClassVar[str] = "ifcx"
    TARGET_SUFFIX: ClassVar[str] = ".ifcx"
    SOURCE_FORMAT_PREFIX: ClassVar[str] = "ifc"

    NODE_PREFIX: ClassVar[str] = "element_"
    MESH_ATTRIBUTE: ClassVar[str] = "usd::usdgeom::mesh"
    NAME_ATTRIBUTE: ClassVar[str] = "infobim::name"
    GLOBAL_ID_ATTRIBUTE: ClassVar[str] = "infobim::globalId"
    TITLE_HEADER_KEY: ClassVar[str] = "title"

    GLOBAL_ID_KEY: ClassVar[str] = "global_id"
    NAME_KEY: ClassVar[str] = "name"
    PATH_KEY: ClassVar[str] = "path"
    LINKSET_KEY: ClassVar[str] = "linkset_path"

    @classmethod
    def convert(cls, container_path: Path) -> List[Dict[str, str]]:
        """
        Convert every element with geometry and return what was written.
        """
        converted: List[Dict[str, str]] = []
        for model_path in cls.declared_models(container_path):
            converted.extend(cls._convert_model(container_path, model_path))

        return converted

    @classmethod
    def declared_models(cls, container_path: Path) -> List[Path]:
        """
        Return the IFC models the Project's RO-Crate states and holds.

        A file the crate states and the Project no longer has is skipped
        rather than reported: the crate is then behind the Project, and
        the manifest that syncs it is what answers that, not the reading
        of geometry.
        """
        return sorted(
            model_path
            for relative in ContainerRoCrate.file_paths(container_path)
            if relative.lower().endswith(cls.MODEL_SUFFIX)
            for model_path in [container_path / relative]
            if model_path.is_file()
        )

    @classmethod
    def _convert_model(
        cls,
        container_path: Path,
        model_path: Path,
    ) -> List[Dict[str, str]]:
        """
        Convert one IFC model's elements, in the format its schema names.
        """
        import ifcopenshell

        model: Any = ifcopenshell.open(str(model_path))
        source_format: str = cls._source_format(model)

        converted: List[Dict[str, str]] = []
        for global_id, name, points, indices in cls._meshes(model):
            document: Dict[str, Any] = cls._document(
                global_id,
                name,
                points,
                indices,
            )
            ifcx_path: Path = TransformationPayloadPath.resolve(
                container_path,
                source_format,
                cls.TARGET_FORMAT,
                global_id,
                cls.TARGET_SUFFIX,
            )
            ifcx_path.parent.mkdir(parents=True, exist_ok=True)
            ifcx_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            linkset_path: Path = IfcIfcxLinksetWriter.write(
                container_path,
                model_path,
                ifcx_path,
                global_id,
                name,
            )
            converted.append({
                cls.GLOBAL_ID_KEY: global_id,
                cls.NAME_KEY: name,
                cls.PATH_KEY: str(ifcx_path),
                cls.LINKSET_KEY: str(linkset_path),
            })

        return converted

    @classmethod
    def _source_format(cls, model: Any) -> str:
        """
        Return the format directory the meshes of this model are filed in.

        The schema family, not the addendum the file was authored
        against: an addendum is a revision of one schema, and IFC 4.3 is
        one format however many of them it has had.
        """
        identifier: Any = getattr(model, "schema_identifier", None)
        if identifier is None:
            identifier = getattr(model, "schema", None)

        family: Any = IfcSchemaIdentifier.family_of(str(identifier))
        if not isinstance(family, str) or not family.strip():
            raise ValueError(
                f"The IFC model states no schema its meshes can be filed "
                f"under: {identifier!r}."
            )

        return family.strip().lower()

    @classmethod
    def _meshes(
        cls,
        model: Any,
    ) -> List[Tuple[str, str, List[List[float]], List[int]]]:
        """
        Return one triangulated mesh per element that has geometry.

        An element with no shape is not reported as a failure: a product
        the reader builds nothing for is a product with nothing to draw,
        which is an ordinary thing for a model to carry.
        """
        import ifcopenshell.geom

        settings: Any = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)

        iterator: Any = ifcopenshell.geom.iterator(settings, model)
        meshes: List[Tuple[str, str, List[List[float]], List[int]]] = []
        if not iterator.initialize():
            return meshes

        while True:
            shape: Any = iterator.get()
            element: Any = model.by_guid(shape.guid)
            vertices: List[float] = list(shape.geometry.verts)
            meshes.append((
                str(shape.guid),
                cls._name_of(element),
                [
                    [vertices[index], vertices[index + 1], vertices[index + 2]]
                    for index in range(0, len(vertices), 3)
                ],
                [int(value) for value in shape.geometry.faces],
            ))
            if not iterator.next():
                return meshes

    @staticmethod
    def _name_of(element: Any) -> str:
        """
        Return what the element is called, or what it is when unnamed.
        """
        name: Any = getattr(element, "Name", None)
        if isinstance(name, str) and name.strip():
            return name.strip()

        return str(element.is_a())

    @classmethod
    def _document(
        cls,
        global_id: str,
        name: str,
        points: List[List[float]],
        indices: List[int],
    ) -> Dict[str, Any]:
        """
        Return the IFCX document of one element's mesh.

        It is a drawing's document in every respect but its geometry: the
        same header, the same declared attributes, one node carrying what
        the node is called and what it is. The node is addressed by a
        name derived from the GlobalId rather than by the GlobalId
        itself, because a composition path is not the place for the
        characters an IFC identity is allowed to contain.
        """
        document: Dict[str, Any] = IfcxDocument.create(
            global_id,
            [{
                "path": f"{cls.NODE_PREFIX}{uuid5(NAMESPACE_URL, global_id).hex}",
                "attributes": {
                    cls.NAME_ATTRIBUTE: name,
                    cls.GLOBAL_ID_ATTRIBUTE: global_id,
                    cls.MESH_ATTRIBUTE: {
                        "points": points,
                        "faceVertexIndices": indices,
                    },
                },
            }],
        )
        document["header"][cls.TITLE_HEADER_KEY] = name
        document["header"][cls.GLOBAL_ID_ATTRIBUTE] = global_id

        return document
