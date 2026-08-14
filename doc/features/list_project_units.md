# Capability: Project Units

- ID: org.infobim.base.capability.list_project_units
- Name: Project Units
- Version: 0.1.0
- File: [list_project_units.py](../../src/plugin/capability/base/list_project_units.py)
- Category: Base / Project
- Owner: InfoBIM Team

## Purpose
- Detect IFC project units and provide a normalized scale factor for length to meters.
- List all units attached to IfcProject.UnitsInContext (SI, ConversionBased, Derived).

## Inputs
- ifc_path (string, required): Absolute path to the IFC file

## Outputs
- length_unit (string): Name of the length unit
- length_scale (number): Scale factor to meters
- schema (string): IFC schema version
- units (array): All units entries from UnitsInContext with:
  - unit_type
  - name
  - prefix
  - kind
  - elements_count (for IfcDerivedUnit)

## CLI
```bash
./infobim run org.infobim.base.capability.list_project_units ./test/data/ifc/rede_esgoto_projeto_existente.ifc
```

## Code References
- Implementation: [list_project_units.py](../../src/plugin/capability/base/list_project_units.py)
