# Capability: List Pipes

- ID: org.infobim.base.capability.list_pipes
- Name: List Pipes
- Version: 0.1.0
- File: [list_pipes.py](../../src/plugin/capability/distribution/list_pipes.py)
- Category: Distribution / Flow
- Owner: Elias M. P. Junior

## Purpose
- Extract and list pipe segments with key geometric and property data: DN, length, and start/end elevations (Z).
- Works with IFC4 (IfcPipeSegment) and IFC2X3 (IfcFlowSegment).
- Optionally suggests sizing using the UHC/NBR8160 method when enabled.

## IFC Compatibility
- IFC4: IfcPipeSegment
- IFC2X3: IfcFlowSegment
- Automatic unit detection for DN (mm vs m) and computation of length/elevations from Axis/Body representations.

## Inputs
- ifc_path (string, required): Absolute path to the IFC file
- materials (boolean, optional, default=false): Include material information in listing
- uhc-sizing-suggest (boolean, optional, default=false): Enable UHC sizing suggestion (read-only)
- org.ontobdc.common.lang.code (string, enum: en, pt_BR, default: en): Language for messages and columns

Schema reference: [ListPipesCapability.METADATA.input_schema](../../src/plugin/capability/distribution/list_pipes.py)

## Outputs
- org.ontobdc.aeco.distribution.flow.pipe.list.count (integer): Total number of pipes found
- org.ontobdc.aeco.distribution.flow.pipe.list (collection): Items with:
  - guid (string)
  - name (string)
  - dn (number, in mm)
  - material (string)
  - z_start (number, in meters)
  - z_end (number, in meters)
  - length (number, in meters)

When uhc-sizing-suggest=true, also includes:
- org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.suggestions (array): per-segment suggestions (guid, name, suggested_dn, suggested_slope, accumulated_uhc)
- events: ["org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.suggested"]

Schema reference: [ListPipesCapability.METADATA.output_schema](../../src/plugin/capability/distribution/list_pipes.py)

## Events
- Success:
  - org.infobim.base.capability.list_pipes.empty
  - org.infobim.base.capability.list_pipes.all
  - org.infobim.base.capability.list_pipes.many
  - org.infobim.base.capability.list_pipes.paginated
- Failure:
  - org.infobim.base.capability.list_pipes.error
- UHC sizing (when suggested):
  - org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.suggested

Reference: [ListPipesCapability.METADATA.events](../../src/plugin/capability/distribution/list_pipes.py)

## Internal Requests
- Materials (conditional: materials=true):
  - id: org.infobim.base.capability.list_material
  - type: collection
- UHC sizing (conditional: uhc-sizing-suggest=true):
  - id: org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc
  - type: process

Reference: [ListPipesCapability.METADATA.request](../../src/plugin/capability/distribution/list_pipes.py)

## Behavior
- IFC read via ifcopenshell; unit detection for conversions.
- DN extraction via common Psets and unit heuristic (m → mm).
- Geometry: Axis (Polyline) preferred, Body (ExtrudedAreaSolid) fallback for length and Z start/end.
- Output sorting: DN desc, Name asc.
- UHC mode: triggers UHCSizingCapability to analyze the network and generate per-segment sizing suggestions.

## CLI
- ID: org.infobim.base.capability.list_pipes
- CLI Strategy: ListPipesCliStrategy (supports conditional columns and i18n)

### Basic run
```bash
./infobim run org.infobim.base.capability.list_pipes ./test/data/ifc/rede_esgoto_projeto_existente.ifc --lang en
```

### Include materials
```bash
./infobim run org.infobim.base.capability.list_pipes ./test/data/ifc/rede_esgoto_projeto_existente.ifc --materials --lang en
```

### UHC sizing suggestions
```bash
./infobim run org.infobim.base.capability.list_pipes ./test/data/ifc/rede_esgoto_projeto_existente.ifc --uhc-sizing-suggest --lang en
```

## UHC Integration
- UHCSizingCapability (package distribution/uhc_sizing) loads NBR8160 tables from its own data package and analyzes the network to suggest minimal DN and slope.
- Suggestions include guid, name, suggested_dn, suggested_slope, accumulated_uhc.
- Event org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.suggested is emitted on success.

## Common Issues
- IFC file not found: verify absolute path in ifc_path.
- IFC without usable Axis/Body: the capability falls back where possible and may return partial length/elevation data.
- Missing UHC tables: UHCSizingCapability uses packaged data under distribution/uhc_sizing/data.

## Code References
- Capability: [list_pipes.py](../../src/plugin/capability/distribution/list_pipes.py)
- UHC sizing: [uhc_sizing/__init__.py](../../src/plugin/capability/distribution/uhc_sizing/__init__.py), [analyzer.py](../../src/plugin/capability/distribution/uhc_sizing/analyzer.py), [tables.py](../../src/plugin/capability/distribution/uhc_sizing/tables.py)
