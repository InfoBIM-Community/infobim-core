from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.container.adapter.entity_facade import EntityFacadeLocator
from ontobdc.container.adapter.entity_rules import EntityFieldRules

from infobim.ifc.adapter.element_triples import IfcElementTriples
from infobim.project.domain.model.contract import ProjectContract


class IfcElementEntity:
    """
    An IfcElement of an IFC model, in the shape the entities of a container
    are answered in: the element as one entity, and the model it is in as
    the dataset that keeps it.
    """

    ELEMENT_IRIS: ClassVar[Dict[str, str]] = {
        "IFC4": "https://standards.buildingsmart.org/IFC/DEV/IFC4/FINAL/OWL#IfcElement",
        "IFC4X3": "https://standards.buildingsmart.org/IFC/DEV/IFC4_3/OWL#IfcElement",
    }
    TYPE: ClassVar[str] = "IfcElement"
    #: The attribute of the element, by the field of the facade of IfcElement that shows it.
    FIELDS: ClassVar[Dict[str, str]] = {
        "global_id": "GlobalId",
        "name": "Name",
        "description": "Description",
        "object_type": "ObjectType",
        "tag": "Tag",
    }

    @staticmethod
    def dataset_path(project_path: Path) -> Path:
        """The reserved dataset of the project, where what the container keeps about its IFC elements is."""
        return project_path / ProjectContract.DATASET_NAME

    @classmethod
    def element_iri(cls, model: Any) -> str:
        """The IfcElement of the schema the model is written in."""
        schema: str = str(model.schema).upper()
        return cls.ELEMENT_IRIS["IFC4X3" if schema.startswith("IFC4X3") else "IFC4"]

    @classmethod
    def entity(cls, element: Any, stored: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        The element as an entity of the type IfcElement, whatever its class is: the class is the field
        ``ifc_class``, the ones the container keeps for it (``related_documents`` and ``tags``) come from
        ``stored``, and the others are the ones the facade of IfcElement declares.
        """
        values: Dict[str, str] = {
            field: str(getattr(element, attribute, None) or "")
            for field, attribute in cls.FIELDS.items()
        }
        values["ifc_class"] = element.is_a()
        return {
            "iri": f"urn:ifc:{values['global_id']}",
            "global_id": values["global_id"],
            "name": values["name"],
            "type": cls.TYPE,
            "fields": [
                {"name": field, "editable": False, "values": [value] if value else []}
                for field, value in values.items()
            ] + [{"name": field, "editable": False, "values": stored.get(field, [])} for field in IfcElementTriples.FIELDS],
        }

    @classmethod
    def dataset(cls, project_path: Path, model_path: Path, model: Any, elements: Any) -> Dict[str, Any]:
        """The model as the dataset that keeps the given elements."""
        try:
            relative: str = model_path.relative_to(project_path).as_posix()
        except ValueError:
            relative = str(model_path)

        triples: IfcElementTriples = IfcElementTriples(project_path)
        return {
            "title": model_path.name,
            "path": relative,
            "entity_types": [cls.element_iri(model)],
            "entities": [cls.entity(element, triples.read(element.is_a(), element.GlobalId)) for element in elements],
        }

    @classmethod
    def locate(cls, project_path: Path, guid: str, model_path: Optional[Path] = None) -> Optional[Tuple[Path, Any, Any]]:
        """
        The model that holds the entity with the GlobalId, and the entity, or None when no model holds one.
        The model is the one named, or else each of the models the project's RO-Crate declares.

        Raises:
            FileNotFoundError: the named model is not a file.
            LookupError: the project's RO-Crate cannot be read, or the GlobalId is the one of an entity that is not an IfcElement.
            RuntimeError: ifcopenshell, which reading an IFC model needs, is not installed.
        """
        try:
            import ifcopenshell
        except ImportError as error:
            raise RuntimeError("Reading IFC models needs ifcopenshell, which is not installed here.") from error

        from infobim.ifc.adapter.models import IfcProjectModels

        models: Optional[List[Path]] = [cls._model(project_path, model_path)] if model_path else IfcProjectModels.paths(project_path)
        if models is None:
            raise LookupError("The project's RO-Crate could not be read.")

        for path in sorted(models):
            model: Any = ifcopenshell.open(str(path))
            try:
                entity: Any = model.by_guid(guid)
            except RuntimeError:
                continue
            if not entity.is_a("IfcElement"):
                raise LookupError(f"The entity {guid} of the model {path.name} is an {entity.is_a()}, not an IfcElement.")
            return path, model, entity

        return None

    @classmethod
    def find(cls, project_path: Path, guid: str, model_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """
        The dataset of the model that holds the IfcElement with the GlobalId, with only that element in it,
        or None when no model holds an entity with it. Raises as ``locate`` does.
        """
        located: Optional[Tuple[Path, Any, Any]] = cls.locate(project_path, guid, model_path)
        if located is None:
            return None

        path, model, entity = located
        return cls.dataset(project_path, path, model, [entity])

    @classmethod
    def update(cls, project_path: Path, guid: str, changes: Dict[str, Any], model_path: Optional[Path] = None) -> Optional[List[str]]:
        """
        Change the fields of the IfcElement with the GlobalId and write the model back to its file; returns
        the fields that changed, or None when no model holds an entity with the GlobalId.

        The fields that can be changed are the ones the facade of IfcElement declares editable. Raises as
        ``locate`` does, and ValueError when a field cannot be changed or takes a structure.
        """
        located: Optional[Tuple[Path, Any, Any]] = cls.locate(project_path, guid, model_path)
        if located is None:
            return None

        path, model, entity = located
        facade: Any = EntityFacadeLocator.of(cls.element_iri(model))
        fields: Dict[str, Any] = {field.identifier: field for field in facade.fields}
        triples: IfcElementTriples = IfcElementTriples(project_path)
        stored: Dict[str, List[str]] = triples.read(entity.is_a(), entity.GlobalId)
        changed: Dict[str, str] = {}
        for name, value in changes.items():
            field: Any = fields.get(name)
            kept: bool = name in IfcElementTriples.FIELDS
            if field is None or not EntityFieldRules.is_editable(field) or (name not in cls.FIELDS and not kept):
                raise ValueError(f"The field {name} of the entity cannot be changed.")
            if isinstance(value, (dict, list)):
                raise ValueError(f"The field {name} takes a text, not a structure.")

            text: str = "" if value is None else str(value)
            if field.required and not text.strip():
                raise ValueError(f"The field {name} is required.")
            if kept:
                text = IfcElementTriples.SEPARATOR.join(IfcElementTriples.split(text))
                current: str = IfcElementTriples.SEPARATOR.join(stored[name])
            else:
                current = str(getattr(entity, cls.FIELDS[name], None) or "")
            if text != current:
                changed[name] = text

        attributes: Dict[str, str] = {name: text for name, text in changed.items() if name in cls.FIELDS}
        if attributes:
            for name, text in attributes.items():
                setattr(entity, cls.FIELDS[name], text or None)
            model.write(str(path))
        kept_changes: Dict[str, List[str]] = {name: IfcElementTriples.split(text) for name, text in changed.items() if name in IfcElementTriples.FIELDS}
        if kept_changes:
            namespace: str = cls.element_iri(model)[: -len(cls.TYPE)]
            triples.write(namespace, entity.is_a(), entity.GlobalId, kept_changes)

        return sorted(changed)

    @staticmethod
    def declared(project_path: Path) -> str:
        """What the project's RO-Crate says about its IFC models, for the message of an element that was not found."""
        from infobim.ifc.adapter.models import IfcProjectModels

        models: Optional[List[Path]] = IfcProjectModels.paths(project_path)
        if models is None:
            return "the RO-Crate of the project could not be read"
        if not models:
            return "the RO-Crate of the project declares no IFC model"

        names: str = ", ".join(sorted(path.relative_to(project_path).as_posix() for path in models))
        return f"the IFC models the RO-Crate of the project declares are {names}"

    @classmethod
    def absent(cls, project_path: Path, guid: str, error: Exception) -> LookupError:
        """The error of an entity no dataset keeps and no IFC model holds: the one of the datasets, and where the models were looked for."""
        return LookupError(f"{error} No IFC element has the GlobalId {guid} either: {cls.declared(project_path)}.")

    @staticmethod
    def _model(project_path: Path, requested: Path) -> Path:
        """The model file the request names, as a path or relative to the project."""
        for candidate in (requested.expanduser(), project_path / requested):
            if candidate.is_file():
                return candidate.resolve()
        raise FileNotFoundError(f"{requested} is not an IFC model file.")
