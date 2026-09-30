class IfcCreationError(Exception):
    """
    Base of every failure the IFC creation flow reports by itself.

    Resolving a target model, validating a class against its schema and
    driving a product through its states each fail for a reason a caller
    can act on, so each raises its own error instead of a bare
    ``ValueError`` that says nothing about which step gave up.
    """


class IfcModelNotResolvedError(IfcCreationError):
    """
    The project states more than one IFC model and none was chosen.

    One model is selected automatically and no model at all means a basic
    one is created; several is the case only the caller can settle, with
    ``--ifc-model-path``.
    """


class IfcModelNotUsableError(IfcCreationError):
    """
    The supplied ``--ifc-model-path`` cannot be used as a target.
    """


class IfcModelUnhealthyError(IfcCreationError):
    """
    The target IFC model is not in a state where it may be modified.

    Health is a precondition, not a repair: a model whose schema disagrees
    with the schema the project declares, or whose IfcProject is not the
    project's own, is reported rather than reconciled.
    """


class IfcClassNotDeclaredError(IfcCreationError):
    """
    The requested IFC class is not declared by the target model's schema.
    """


class IfcClassNotConcreteProductError(IfcCreationError):
    """
    The requested IFC class is abstract, or is not an ``IfcProduct``.
    """


class IfcSchemaIdentifierNotRegisteredError(IfcCreationError):
    """
    No IfcOpenShell schema identifier is registered for the project's schema.

    The project declares its schema as a buildingSMART release URI and the
    reader names schemas its own way. The two are related by a declared
    pair, so a release URI with no registered identifier is unsupported
    rather than guessed from the spelling of either one.
    """


class GeometryDefinitionInvalidError(IfcCreationError):
    """
    The geometry inputs do not describe the primitive they claim to.

    A dimension that is not positive, or a null extrusion direction, is
    not a geometry this flow rounds off into a usable one.
    """


class PositionDefinitionInvalidError(IfcCreationError):
    """
    A coordinate this run stated is not a real number a position can use.

    A coordinate that does not read as a number, and one that reads as
    NaN or as an infinity, are both reported: a placement cannot be made
    of them, and quietly turning either into zero would put the product
    at the origin while the caller believed it was somewhere else.

    An axis nobody stated is a different matter. It is not an error at
    all, because the contract says what an unstated axis means: the
    origin, on that axis.
    """


class DisplacementDefinitionInvalidError(IfcCreationError):
    """
    The axis or amount this run stated does not describe a displacement.

    An axis has to be one this flow moves an element along, and an amount
    has to be a real, finite, non-zero number: zero would move nothing,
    which is not what a move was asked for.
    """


class IfcElementNotFoundError(IfcCreationError):
    """
    The GlobalId this run resolved names no element the target model carries.

    A title identifies an element deterministically, but only an element
    the model already federates can be moved: one that was never created,
    or was created in another model, is reported rather than moved into
    existing by this flow.
    """


class ObjectPlacementNotMovableError(IfcCreationError):
    """
    The element's own placement is not shaped the way this flow moves it.

    Every element this flow creates carries an ``IfcLocalPlacement`` whose
    ``RelativePlacement`` is an ``IfcAxis2Placement3D`` located by an
    ``IfcCartesianPoint`` — the same shape ``IfcProductAssembler`` gives
    every product it assembles. An element placed some other way was not
    assembled by this flow, and this flow does not guess how to move it.
    """
