# InfoBIM offline 3D viewer

InfoBIM owns the viewer source, build configuration, embedded standard layers,
environment map and generated HTML in this directory. Building, packaging and
running InfoBIM do not require an IFCX checkout. The initial buildingSMART
Three.js/IFCX source snapshot was copied from local commit `5e30af9`; its MIT
notice and the Three.js license are retained here.

## Build and install

From the InfoBIM repository:

```sh
npm ci --prefix src/infobim/3d/asset
python -m infobim.3d.vendor
python -m pip wheel --no-deps --wheel-dir dist .
python -m pip install --force-reinstall --no-deps dist/infobim-0.11.0-py3-none-any.whl
```

The initial npm dependency installation uses the package registry. Subsequent
viewer builds use only the sources and dependencies in this directory.
The installed Python package includes the standalone HTML, sources, build files,
licenses and the mixed-geometry IFCX fixture. Node.js is a development dependency;
opening the installed viewer requires only a WebGL-capable browser.
Reinstalling with `--no-deps` assumes the InfoBIM runtime dependencies are already
installed. `--force-reinstall` replaces an older build with the same version.

Edit `source/` and rebuild. Do not edit `ifcx-viewer-offline.html` directly.

## Project loading

```sh
infobim 3d
infobim 3d --global-id '<GlobalId>'
```

The first form resolves the current Project through the container strategy.
The second resolves a registered Project through its IfcProject GlobalId.

The Project's RO-Crate is authoritative: only declared File entries ending in
`.ifcx`, `.dxf` or `.dwg` are loaded. Paths must stay inside the Project, including after
symlink resolution. Missing files, malformed IFCX and invalid DXF units are errors.
Local IFCX layers are embedded together so references to their header IDs can
resolve offline; standard schema layers are bundled. Other unresolved imports
are errors and are never downloaded.

Python creates a private temporary `infobim-3d-*.html` file, embeds the Project's
JSON, then asks the default browser to open it. The HTML is self-contained and
needs no local web server, file fetch, external font or CDN. Its content security
policy blocks HTTP requests. Temporary launch pages persist so the browser can
finish opening them; they can be removed after closing the viewer.

The Project supplies the title and GlobalId; it is **not** an IFCX layer. Each
CAD drawing produces its own IFCX document, listed with an `.ifcx` filename.
Neither the original DWG nor the intermediate DXF is sent to the browser.
Projects with no eligible drawings fail before browser launch. After composition,
the viewer rejects scenes without visible geometry instead of reporting success.
Successful loads report actual rendered curve, mesh and point-cloud counts.

## DWG conversion

DWG input requires an installed [ODA File Converter](https://www.opendesign.com/guestfiles/teighafileConverter).
InfoBIM resolves the executable through `INFOBIM_ODA_FILE_CONVERTER`, then `PATH`,
or the macOS application registry. An explicitly configured invalid executable
fails; it is not silently replaced by another converter. No fixed installation
path or IFCX checkout is required.

Each source is copied to a private temporary directory and converted to DXF
with auditing disabled. That DXF is read by ezdxf and converted into the same
IFCX geometry used for DXF inputs. Source files and Project metadata are never
modified. Intermediate DWG copies and DXFs are removed when conversion finishes;
the resulting IFCX documents are embedded in the offline launch HTML.

## CAD geometry and placement

Supported modelspace entities: LINE, LWPOLYLINE, 2D/3D POLYLINE, ARC and CIRCLE.
Polyline bulges and OCS/elevation are handled by ezdxf's path conversion.
Curves are tessellated with a 1 mm flattening tolerance in drawing scale.
Each entity remains a separate BasisCurves node. A node containing multiple
`curveVertexCounts` is rendered as independent lines, without joining gaps.

Points remain in the drawing's local coordinates. The drawing parent carries
the complete `usd::xformop::transform`, including the conversion from DXF
`$INSUNITS` to metres. Placement defaults to identity by contract.

Optional Project settings live at `.__infobim__/3d.json`:

```json
{
  "drawings": {
    "drawings/plan.dxf": {
      "meters_per_unit": 0.001,
      "transform": [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [12, 4, 2, 1]
      ]
    }
  }
}
```

Keys are decoded, normalized paths relative to the Project and must name DWGs or DXFs
in its RO-Crate. The USD matrix uses row vectors: translation is in its last
row, measured in metres. Unit scaling is applied before this placement.
`meters_per_unit` explicitly overrides the DXF unit declaration and is required
for unitless DXFs; no guessed unit is substituted. Omitted transforms mean
identity. Invalid matrices, non-finite values and non-positive scales fail.

TEXT/MTEXT, DIMENSION, HATCH, INSERT/block expansion, SPLINE and complex linetypes
remain outside the geometry converter. This is not a complete CAD visual
reproduction. Unsupported entity counts are available under the viewer's
conversion-warning summary; a drawing with no supported paths fails explicitly.

## Verification

`fixture/mixed-geometry.ifcx` contains one mesh, two BasisCurves nodes (one with
two separate paths), and a parent translated by `[12, 4, 2]`. Expected world
bounds are `[12, 4, 2]` to `[20, 10, 2]`, with one mesh and three independent
line objects. See `../CODEX_HANDOFF.md` for executed checks and pending visual
acceptance.

Conversion APIs follow the [ezdxf path documentation](https://ezdxf.readthedocs.io/en/stable/path.html)
and [unit conversion contract](https://ezdxf.readthedocs.io/en/stable/concepts/units.html).

## Local terminal connection

Run `infobim 3d connect` in a PC terminal to serve the viewer's SSE endpoint
at `http://127.0.0.1:8765/events`. Keep the command running; Ctrl+C stops it.
An open viewer reconnects automatically. The server binds only to loopback
and uses Python's standard library. An occupied port produces an explicit error.

The terminal submits commands with Enter using authenticated HTTP POST requests.
Each SSE connection receives its own random session token and output stream.
Commands run in the directory where `infobim 3d connect` started, with the
server's Python environment available on PATH. Output and exit codes return via
SSE. Each command starts a fresh shell; interactive programs and persistent `cd`
are not supported. Closing the connection terminates its running command.
