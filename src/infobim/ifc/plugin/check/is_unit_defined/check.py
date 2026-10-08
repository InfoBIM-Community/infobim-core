from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Standalone check. It imports no sibling check/hotfix and mutates nothing.
#
# UNIT_DEFINED means the sole IfcProject carries a complete global physical
# unit assignment:
#   - every standard IfcUnitEnum physical type (except USERDEFINED);
#   - every standard IfcDerivedUnitEnum type (except USERDEFINED);
# restricted to the types the model's own schema defines (IFC2X3 lacks some
# derived types IFC4 added).
#
# Existing project units remain authoritative. The matching hotfix only fills
# gaps. This check validates uniqueness and dimensional consistency, but it
# does not force existing units to SI or rewrite an existing scale.
#
# Missing units are created by the hotfix in coherent SI at 10^0. MASSUNIT is
# kilogram (IfcSIUnit GRAM + KILO) because kg is the SI base unit of mass.
# PLANEANGLEUNIT is the deliberate exception: missing plane-angle units are
# defined in degrees rather than radians.

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
            return None
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


def _unit_findings(
    project: Any,
    expected_named: Dict[str, Dimensions],
    expected_derived: Dict[str, Recipe],
) -> List[str]:
    """
    The units of the global assignment that are missing, repeated or
    dimensionally wrong, one sentence each. None when it is complete.
    """
    units = _assignment_units(project)
    if units is None:
        return ["The IfcProject has no unit assignment (UnitsInContext)."]

    indexed = _indexed_units(units)
    if indexed is None:
        return ["The units of the assignment could not be read."]
    named, derived = indexed

    missing: List[str] = []
    repeated: List[str] = []
    wrong: List[str] = []
    for unit_type, expected_dimensions in expected_named.items():
        candidates = named.get(unit_type, [])
        if not candidates:
            missing.append(unit_type)
        elif len(candidates) != 1:
            repeated.append(f"{unit_type} ({len(candidates)}x)")
        elif not _valid_named_unit(candidates[0], expected_dimensions):
            wrong.append(unit_type)

    for unit_type, recipe in expected_derived.items():
        candidates = derived.get(unit_type, [])
        if not candidates:
            missing.append(unit_type)
        elif len(candidates) != 1:
            repeated.append(f"{unit_type} ({len(candidates)}x)")
        elif not _valid_derived_unit(candidates[0], _recipe_dimensions(recipe)):
            wrong.append(unit_type)

    findings: List[str] = []
    if missing:
        findings.append(f"{len(missing)} units are not defined: {', '.join(missing)}.")
    if repeated:
        findings.append(f"Units defined more than once: {', '.join(repeated)}.")
    if wrong:
        findings.append(f"Units with the wrong dimensions: {', '.join(wrong)}.")
    return findings


def _is_complete(
    project: Any,
    expected_named: Dict[str, Dimensions],
    expected_derived: Dict[str, Recipe],
) -> bool:
    return not _unit_findings(project, expected_named, expected_derived)


def diagnose(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> List[str]:
    """
    Why the global unit assignment of the model is not complete: which units
    are missing, repeated or dimensionally wrong. None when it is complete.
    """
    del project_path, container_path

    model_path = _resolve_path(ifc_model_path)
    if model_path is None or not model_path.is_file():
        return ["The IFC model was not given or does not exist."]

    try:
        import ifcopenshell

        model = ifcopenshell.open(str(model_path))
    except Exception as error:
        return [f"The file does not read as an IFC STEP model: {error}"]

    projects = _projects(model)
    if len(projects) != 1:
        return [f"The model has {len(projects)} IfcProject entities; exactly one is required."]

    expected = _expected_units(model)
    if expected is None:
        return ["The units the model's schema defines could not be determined."]
    expected_named, expected_derived = expected

    return _unit_findings(projects[0], expected_named, expected_derived)


def main(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> int:
    return 1 if diagnose(project_path, ifc_model_path, container_path) else 0


if __name__ == "__main__":
    raise SystemExit(main())
