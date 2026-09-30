from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Standalone hotfix. It imports no sibling check/hotfix.
#
# The project unit assignment is completed, never normalized destructively.
# Existing valid units are authoritative and are preserved exactly as they are.
# Every missing standard named or derived physical unit the model's own schema
# defines is added (IFC2X3 lacks some derived types IFC4 added).
#
# Missing units use coherent SI at 10^0:
#   - metre, square metre, cubic metre, second, kelvin, ampere, mole, candela,
#     and the corresponding derived SI names;
#   - kilogram is represented as IfcSIUnit(GRAM, Prefix=KILO), which is the SI
#     base unit of mass;
#   - plane angle is the deliberate exception and is created as degree.
#
# Derived units are built from 10^0 SI support units. Angle-bearing derived
# units use degree as well. Supporting named units used inside a derived unit
# are not added to IfcProject.UnitsInContext unless that named project unit was
# itself missing.

Dimensions = Tuple[int, int, int, int, int, int, int]
Recipe = Tuple[Tuple[str, int], ...]

_EXPECTED_NAMED_DIMENSIONS: Dict[str, Dimensions] = {
    "ABSORBEDDOSEUNIT": (2, 0, -2, 0, 0, 0, 0),
    "AMOUNTOFSUBSTANCEUNIT": (0, 0, 0, 0, 0, 1, 0),
    "AREAUNIT": (2, 0, 0, 0, 0, 0, 0),
    "DOSEEQUIVALENTUNIT": (2, 0, -2, 0, 0, 0, 0),
    "ELECTRICCAPACITANCEUNIT": (-2, -1, 4, 2, 0, 0, 0),
    "ELECTRICCHARGEUNIT": (0, 0, 1, 1, 0, 0, 0),
    "ELECTRICCONDUCTANCEUNIT": (-2, -1, 3, 2, 0, 0, 0),
    "ELECTRICCURRENTUNIT": (0, 0, 0, 1, 0, 0, 0),
    "ELECTRICRESISTANCEUNIT": (2, 1, -3, -2, 0, 0, 0),
    "ELECTRICVOLTAGEUNIT": (2, 1, -3, -1, 0, 0, 0),
    "ENERGYUNIT": (2, 1, -2, 0, 0, 0, 0),
    "FORCEUNIT": (1, 1, -2, 0, 0, 0, 0),
    "FREQUENCYUNIT": (0, 0, -1, 0, 0, 0, 0),
    "ILLUMINANCEUNIT": (-2, 0, 0, 0, 0, 0, 1),
    "INDUCTANCEUNIT": (2, 1, -2, -2, 0, 0, 0),
    "LENGTHUNIT": (1, 0, 0, 0, 0, 0, 0),
    "LUMINOUSFLUXUNIT": (0, 0, 0, 0, 0, 0, 1),
    "LUMINOUSINTENSITYUNIT": (0, 0, 0, 0, 0, 0, 1),
    "MAGNETICFLUXDENSITYUNIT": (0, 1, -2, -1, 0, 0, 0),
    "MAGNETICFLUXUNIT": (2, 1, -2, -1, 0, 0, 0),
    "MASSUNIT": (0, 1, 0, 0, 0, 0, 0),
    "PLANEANGLEUNIT": (0, 0, 0, 0, 0, 0, 0),
    "POWERUNIT": (2, 1, -3, 0, 0, 0, 0),
    "PRESSUREUNIT": (-1, 1, -2, 0, 0, 0, 0),
    "RADIOACTIVITYUNIT": (0, 0, -1, 0, 0, 0, 0),
    "SOLIDANGLEUNIT": (0, 0, 0, 0, 0, 0, 0),
    "THERMODYNAMICTEMPERATUREUNIT": (0, 0, 0, 0, 1, 0, 0),
    "TIMEUNIT": (0, 0, 1, 0, 0, 0, 0),
    "VOLUMEUNIT": (3, 0, 0, 0, 0, 0, 0),
}

# Dimensions an older schema derives differently for an IfcSIUnit. IFC2X3's
# IfcDimensionsForSiUnit gives FARAD an electric-current exponent of 1 instead
# of 2 (fixed in IFC4), so no IFC2X3 FARAD can ever carry the physical value.
_SCHEMA_NAMED_DIMENSION_ERRATA: Dict[str, Dict[str, Dimensions]] = {
    "IFC2X3": {
        "ELECTRICCAPACITANCEUNIT": (-2, -1, 4, 1, 0, 0, 0),
    },
}

_DERIVED_RECIPES: Dict[str, Recipe] = {
    "ACCELERATIONUNIT": (("LENGTHUNIT", 1), ("TIMEUNIT", -2)),
    "ANGULARVELOCITYUNIT": (("PLANEANGLEUNIT", 1), ("TIMEUNIT", -1)),
    "AREADENSITYUNIT": (("MASSUNIT", 1), ("AREAUNIT", -1)),
    "COMPOUNDPLANEANGLEUNIT": (
        ("PLANEANGLEUNIT", 1),
        ("LENGTHUNIT", 1),
        ("LENGTHUNIT", -1),
    ),
    "CURVATUREUNIT": (("PLANEANGLEUNIT", 1), ("LENGTHUNIT", -1)),
    "DYNAMICVISCOSITYUNIT": (("PRESSUREUNIT", 1), ("TIMEUNIT", 1)),
    "HEATFLUXDENSITYUNIT": (("POWERUNIT", 1), ("AREAUNIT", -1)),
    "HEATINGVALUEUNIT": (("ENERGYUNIT", 1), ("MASSUNIT", -1)),
    "INTEGERCOUNTRATEUNIT": (("TIMEUNIT", -1),),
    "IONCONCENTRATIONUNIT": (("MASSUNIT", 1), ("VOLUMEUNIT", -1)),
    "ISOTHERMALMOISTURECAPACITYUNIT": (
        ("VOLUMEUNIT", 1),
        ("MASSUNIT", -1),
    ),
    "KINEMATICVISCOSITYUNIT": (("AREAUNIT", 1), ("TIMEUNIT", -1)),
    "LINEARFORCEUNIT": (("FORCEUNIT", 1), ("LENGTHUNIT", -1)),
    "LINEARMOMENTUNIT": (
        ("FORCEUNIT", 1),
        ("LENGTHUNIT", 1),
        ("LENGTHUNIT", -1),
    ),
    "LINEARSTIFFNESSUNIT": (("FORCEUNIT", 1), ("LENGTHUNIT", -1)),
    "LINEARVELOCITYUNIT": (("LENGTHUNIT", 1), ("TIMEUNIT", -1)),
    "LUMINOUSINTENSITYDISTRIBUTIONUNIT": (
        ("LUMINOUSINTENSITYUNIT", 1),
        ("LUMINOUSFLUXUNIT", -1),
    ),
    "MASSDENSITYUNIT": (("MASSUNIT", 1), ("VOLUMEUNIT", -1)),
    "MASSFLOWRATEUNIT": (("MASSUNIT", 1), ("TIMEUNIT", -1)),
    "MASSPERLENGTHUNIT": (("MASSUNIT", 1), ("LENGTHUNIT", -1)),
    "MODULUSOFELASTICITYUNIT": (("FORCEUNIT", 1), ("AREAUNIT", -1)),
    "MODULUSOFLINEARSUBGRADEREACTIONUNIT": (
        ("FORCEUNIT", 1),
        ("AREAUNIT", -1),
    ),
    "MODULUSOFROTATIONALSUBGRADEREACTIONUNIT": (
        ("FORCEUNIT", 1),
        ("LENGTHUNIT", 1),
        ("LENGTHUNIT", -1),
        ("PLANEANGLEUNIT", -1),
    ),
    "MODULUSOFSUBGRADEREACTIONUNIT": (
        ("FORCEUNIT", 1),
        ("VOLUMEUNIT", -1),
    ),
    "MOISTUREDIFFUSIVITYUNIT": (("VOLUMEUNIT", 1), ("TIMEUNIT", -1)),
    "MOLECULARWEIGHTUNIT": (
        ("MASSUNIT", 1),
        ("AMOUNTOFSUBSTANCEUNIT", -1),
    ),
    "MOMENTOFINERTIAUNIT": (("LENGTHUNIT", 4),),
    "PHUNIT": (
        ("AMOUNTOFSUBSTANCEUNIT", 1),
        ("VOLUMEUNIT", -1),
    ),
    "PLANARFORCEUNIT": (("FORCEUNIT", 1), ("AREAUNIT", -1)),
    "ROTATIONALFREQUENCYUNIT": (("TIMEUNIT", -1),),
    "ROTATIONALMASSUNIT": (("MASSUNIT", 1), ("AREAUNIT", 1)),
    "ROTATIONALSTIFFNESSUNIT": (
        ("FORCEUNIT", 1),
        ("LENGTHUNIT", 1),
        ("PLANEANGLEUNIT", -1),
    ),
    "SECTIONAREAINTEGRALUNIT": (("LENGTHUNIT", 5),),
    "SECTIONMODULUSUNIT": (("LENGTHUNIT", 3),),
    "SHEARMODULUSUNIT": (("FORCEUNIT", 1), ("AREAUNIT", -1)),
    "SOUNDPOWERLEVELUNIT": (("POWERUNIT", 1), ("POWERUNIT", -1)),
    "SOUNDPOWERUNIT": (("ENERGYUNIT", 1), ("TIMEUNIT", -1)),
    "SOUNDPRESSURELEVELUNIT": (
        ("PRESSUREUNIT", 1),
        ("PRESSUREUNIT", -1),
    ),
    "SOUNDPRESSUREUNIT": (("FORCEUNIT", 1), ("AREAUNIT", -1)),
    "SPECIFICHEATCAPACITYUNIT": (
        ("ENERGYUNIT", 1),
        ("MASSUNIT", -1),
        ("THERMODYNAMICTEMPERATUREUNIT", -1),
    ),
    "TEMPERATUREGRADIENTUNIT": (
        ("THERMODYNAMICTEMPERATUREUNIT", 1),
        ("LENGTHUNIT", -1),
    ),
    "TEMPERATURERATEOFCHANGEUNIT": (
        ("THERMODYNAMICTEMPERATUREUNIT", 1),
        ("TIMEUNIT", -1),
    ),
    "THERMALADMITTANCEUNIT": (
        ("POWERUNIT", 1),
        ("AREAUNIT", -1),
        ("THERMODYNAMICTEMPERATUREUNIT", -1),
    ),
    "THERMALCONDUCTANCEUNIT": (
        ("POWERUNIT", 1),
        ("LENGTHUNIT", -1),
        ("THERMODYNAMICTEMPERATUREUNIT", -1),
    ),
    "THERMALEXPANSIONCOEFFICIENTUNIT": (
        ("THERMODYNAMICTEMPERATUREUNIT", -1),
    ),
    "THERMALRESISTANCEUNIT": (
        ("AREAUNIT", 1),
        ("THERMODYNAMICTEMPERATUREUNIT", 1),
        ("POWERUNIT", -1),
    ),
    "THERMALTRANSMITTANCEUNIT": (
        ("POWERUNIT", 1),
        ("AREAUNIT", -1),
        ("THERMODYNAMICTEMPERATUREUNIT", -1),
    ),
    "TORQUEUNIT": (("FORCEUNIT", 1), ("LENGTHUNIT", 1)),
    "VAPORPERMEABILITYUNIT": (
        ("MASSUNIT", 1),
        ("TIMEUNIT", -1),
        ("LENGTHUNIT", -1),
        ("PRESSUREUNIT", -1),
    ),
    "VOLUMETRICFLOWRATEUNIT": (("VOLUMEUNIT", 1), ("TIMEUNIT", -1)),
    "WARPINGCONSTANTUNIT": (("LENGTHUNIT", 6),),
    "WARPINGMOMENTUNIT": (("FORCEUNIT", 1), ("LENGTHUNIT", 2)),
}


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    return Path(path_value).expanduser().resolve()


def _schema_unit_types(model: Any) -> Optional[Tuple[Set[str], Set[str]]]:
    """Return the named and derived unit types the model's own schema defines."""
    try:
        import ifcopenshell.ifcopenshell_wrapper as wrapper

        schema: Any = wrapper.schema_by_name(model.schema_identifier)
        named: Set[str] = set(
            schema.declaration_by_name("IfcUnitEnum").enumeration_items()
        )
        derived: Set[str] = set(
            schema.declaration_by_name("IfcDerivedUnitEnum").enumeration_items()
        )
    except Exception:
        return None
    return named, derived


def _expected_units(
    model: Any,
) -> Optional[Tuple[Dict[str, Dimensions], Dict[str, Recipe]]]:
    """
    Return the named and derived units required for this model.

    Only unit types the model's schema defines can be required: IFC2X3 has
    no AREADENSITYUNIT, SOUNDPOWERLEVELUNIT, SOUNDPRESSURELEVELUNIT or
    TEMPERATURERATEOFCHANGEUNIT, so an IFC2X3 model can never carry them.
    Named units are expected with the dimensions the schema itself derives.
    """
    unit_types = _schema_unit_types(model)
    if unit_types is None:
        return None
    named_types, derived_types = unit_types
    errata: Dict[str, Dimensions] = _SCHEMA_NAMED_DIMENSION_ERRATA.get(
        str(model.schema_identifier),
        {},
    )
    return (
        {
            unit_type: errata[unit_type] if unit_type in errata else dimensions
            for unit_type, dimensions in _EXPECTED_NAMED_DIMENSIONS.items()
            if unit_type in named_types
        },
        {
            unit_type: recipe
            for unit_type, recipe in _DERIVED_RECIPES.items()
            if unit_type in derived_types
        },
    )


def _projects(model: Any) -> List[Any]:
    try:
        return list(model.by_type("IfcProject"))
    except Exception:
        return []


def _dimensions(value: Any) -> Optional[Dimensions]:
    try:
        dimensions = value.Dimensions
        return (
            int(dimensions.LengthExponent),
            int(dimensions.MassExponent),
            int(dimensions.TimeExponent),
            int(dimensions.ElectricCurrentExponent),
            int(dimensions.ThermodynamicTemperatureExponent),
            int(dimensions.AmountOfSubstanceExponent),
            int(dimensions.LuminousIntensityExponent),
        )
    except Exception:
        return None


def _recipe_dimensions(recipe: Recipe) -> Dimensions:
    result = [0, 0, 0, 0, 0, 0, 0]
    for unit_type, exponent in recipe:
        base = _EXPECTED_NAMED_DIMENSIONS[unit_type]
        for index, value in enumerate(base):
            result[index] += value * exponent
    return tuple(result)  # type: ignore[return-value]


def _assignment_units(project: Any) -> Optional[List[Any]]:
    try:
        assignment = project.UnitsInContext
        if assignment is None:
            return []
        return list(assignment.Units or [])
    except Exception:
        return None


def _indexed_units(
    units: List[Any],
) -> Optional[Tuple[Dict[str, List[Any]], Dict[str, List[Any]]]]:
    named: Dict[str, List[Any]] = {}
    derived: Dict[str, List[Any]] = {}

    for unit in units:
        try:
            unit_type = getattr(unit, "UnitType", None)
            if not isinstance(unit_type, str):
                continue
            if unit.is_a("IfcNamedUnit"):
                named.setdefault(unit_type, []).append(unit)
            elif unit.is_a("IfcDerivedUnit"):
                derived.setdefault(unit_type, []).append(unit)
        except Exception:
            return None

    return named, derived


def _valid_named_unit(unit: Any, expected: Dimensions) -> bool:
    try:
        if not unit.is_a("IfcNamedUnit"):
            return False
        entity_type = unit.is_a()
        if entity_type == "IfcSIUnit":
            if not getattr(unit, "Name", None):
                return False
        elif entity_type in {
            "IfcConversionBasedUnit",
            "IfcConversionBasedUnitWithOffset",
        }:
            if not getattr(unit, "Name", None):
                return False
            if getattr(unit, "ConversionFactor", None) is None:
                return False
        elif entity_type == "IfcContextDependentUnit":
            if not getattr(unit, "Name", None):
                return False
        else:
            return False
    except Exception:
        return False

    return _dimensions(unit) == expected


def _valid_derived_unit(unit: Any, expected: Dimensions) -> bool:
    try:
        if not unit.is_a("IfcDerivedUnit"):
            return False
        elements = list(unit.Elements or [])
        if not elements:
            return False
        for element in elements:
            if getattr(element, "Unit", None) is None:
                return False
            int(element.Exponent)
    except Exception:
        return False

    return _dimensions(unit) == expected


def _is_complete(
    project: Any,
    expected_named: Dict[str, Dimensions],
    expected_derived: Dict[str, Recipe],
) -> bool:
    units = _assignment_units(project)
    if units is None:
        return False

    indexed = _indexed_units(units)
    if indexed is None:
        return False
    named, derived = indexed

    for unit_type, expected_dimensions in expected_named.items():
        candidates = named.get(unit_type, [])
        if len(candidates) != 1:
            return False
        if not _valid_named_unit(candidates[0], expected_dimensions):
            return False

    for unit_type, recipe in expected_derived.items():
        candidates = derived.get(unit_type, [])
        if len(candidates) != 1:
            return False
        if not _valid_derived_unit(
            candidates[0],
            _recipe_dimensions(recipe),
        ):
            return False

    return True


def _new_named_unit(model: Any, unit_type: str) -> Any:
    import ifcopenshell.api.unit as unit_api

    if unit_type == "PLANEANGLEUNIT":
        return unit_api.add_conversion_based_unit(model, name="degree")

    prefix = "KILO" if unit_type == "MASSUNIT" else None
    return unit_api.add_si_unit(
        model,
        unit_type=unit_type,
        prefix=prefix,
    )


def _new_derived_unit(model: Any, unit_type: str, recipe: Recipe) -> Any:
    elements: List[Any] = []
    for support_type, exponent in recipe:
        support_unit = _new_named_unit(model, support_type)
        elements.append(
            model.create_entity(
                "IfcDerivedUnitElement",
                Unit=support_unit,
                Exponent=exponent,
            )
        )

    return model.create_entity(
        "IfcDerivedUnit",
        Elements=tuple(elements),
        UnitType=unit_type,
    )


def main(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> int:
    del project_path, container_path

    model_path = _resolve_path(ifc_model_path)
    if model_path is None or not model_path.is_file():
        return 1

    try:
        import ifcopenshell

        model = ifcopenshell.open(str(model_path))
    except Exception:
        return 1

    projects = _projects(model)
    if len(projects) != 1:
        return 1
    project = projects[0]

    expected = _expected_units(model)
    if expected is None:
        return 1
    expected_named, expected_derived = expected

    assigned_units = _assignment_units(project)
    if assigned_units is None:
        return 1

    indexed = _indexed_units(assigned_units)
    if indexed is None:
        return 1
    named, derived = indexed

    for unit_type, expected_dimensions in expected_named.items():
        candidates = named.get(unit_type, [])
        if len(candidates) > 1:
            return 1
        if len(candidates) == 1 and not _valid_named_unit(
            candidates[0],
            expected_dimensions,
        ):
            return 1

    for unit_type, recipe in expected_derived.items():
        candidates = derived.get(unit_type, [])
        if len(candidates) > 1:
            return 1
        if len(candidates) == 1 and not _valid_derived_unit(
            candidates[0],
            _recipe_dimensions(recipe),
        ):
            return 1

    created_for_assignment: List[Any] = []
    try:
        for unit_type in expected_named:
            if not named.get(unit_type):
                created_for_assignment.append(_new_named_unit(model, unit_type))

        for unit_type, recipe in expected_derived.items():
            if not derived.get(unit_type):
                created_for_assignment.append(
                    _new_derived_unit(model, unit_type, recipe)
                )

        assignment = getattr(project, "UnitsInContext", None)
        if assignment is None:
            project.UnitsInContext = model.create_entity(
                "IfcUnitAssignment",
                Units=tuple(created_for_assignment),
            )
        else:
            assignment.Units = tuple(assigned_units + created_for_assignment)

        model.write(str(model_path))
        verified = ifcopenshell.open(str(model_path))
        verified_projects = _projects(verified)
    except Exception:
        return 1

    if len(verified_projects) != 1:
        return 1
    return (
        0
        if _is_complete(verified_projects[0], expected_named, expected_derived)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
