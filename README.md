# InfoBIM

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

InfoBIM is the OpenBIM command line of the **OntoBDC** ecosystem. It turns an
ordinary folder of building information into an **InfoBIM project**: IFC models,
DXF/DWG drawings, PDFs, images and spreadsheets are described in a semantic
graph. The files stay where they are, in their own formats.

InfoBIM is a thin domain layer on top of [OntoBDC](https://github.com/EliasMPJunior/ontobdc-wip),
the generic semantic runtime:

- **OntoBDC** owns containers, datasets, the storage index, the RO-Crate and
  Data Package manifests, health checks and state machines.
- **InfoBIM** adds only what depends on IFC and buildingSMART semantics.

The ontologies both use, such as AECO kinds, file encodings and facades, come
from the [brasidatacenter](https://github.com/EliasMPJunior/brasidatacenter)
package. They are looked up by the IRI they are published at.

The same CLI runs in the browser in [databim.tech](https://github.com/EliasMPJunior/databim.tech),
through Pyodide.

## Install

InfoBIM needs **Python 3.11 or later**, which `brasidatacenter` requires.
Install its two sibling packages first, then InfoBIM:

```bash
pip install brasidatacenter ontobdc infobim
```

To work on the code, install the three repositories in editable mode in one
virtual environment (`reinstall.sh` does it for InfoBIM):

```bash
pip install -e ../brasidatacenter -e ../ontobdc-wip -e .
```

Optional extras:

| Extra | What it adds |
|---|---|
| `infobim[2d]` | The 2D drawing viewer (PySide6), used to pick points on a drawing. `infobim 2d --enable` installs it into the running environment. |
| `infobim[3d]` | The 3D viewer (PySide6). |
| `infobim[all]` | Both. |

To read **DWG** drawings, install the ODA File Converter. InfoBIM finds it on
the `PATH`, or at the executable named by `INFOBIM_ODA_FILE_CONVERTER`.

## Quickstart

```bash
mkdir ~/obras && cd ~/obras
infobim init                              # makes this folder a storage root

infobim project --create "Hospital Norte"   # creates and registers ./hospital-norte
cd hospital-norte

cp ~/Downloads/estrutura.ifc ~/Downloads/planta.dxf .
infobim project --refresh                 # registers the new files in the project

infobim project --inspect                 # what the project holds, from its IfcProject down
infobim project --entity                  # the entities the project holds, by dataset
infobim project --health                  # every check the project must pass
infobim project --list                    # (from anywhere under the root) every project
```

Every command answers in JSON with `--json`. This is how databim.tech reads
the answers.

## Concepts

### Storage root

`infobim init` makes a folder a **storage root** by creating a
`.__ontobdc__/` directory in it:

- `config.yaml` is the marker that identifies the root.
- `storage.ttl` is the index of the projects registered under the root.

Commands find the root by walking up from the current directory to that
marker. A root can be moved, or created in one file system and opened in
another (for example, created in the browser and opened on disk): the
locations recorded in the index are read relative to where the root is now.
A recorded location outside the root is an error, not something silently
tolerated.

### Project

A project is an **OntoBDC container**, a folder registered in the root's index,
that carries InfoBIM's **reserved dataset**, `.__infobim__/`. That dataset
holds the IfcProject declaration. The IfcProject's GlobalId is the project's
identity.

```text
hospital-norte/
├── .__ontobdc__/
│   ├── container.ttl             the container's metadata and its datasets
│   ├── ro-crate-metadata.json    every file of the project, with its media type
│   └── datapackage.json          the tabular files, for frictionless
├── .__infobim__/                 the reserved InfoBIM dataset
│   ├── .__ontobdc__/dataset.ttl
│   └── payload/
│       ├── triple/ifc_project.ttl    the IfcProject (GlobalId, name)
│       └── linkset/dataset_facade.ttl
├── estrutura.ifc
└── planta.dxf
```

`--create <name>` takes a **name**. The project goes into a subfolder named
after its slug (`"Hospital Norte"` → `hospital-norte/`) under the current
storage root. Creating a project also refreshes it, so a new project already
passes `project --health`.

### Choosing the project a command acts on

Every project command acts on:

- the project of the **current directory**, or
- the project whose IfcProject GlobalId is given with `--global-id <GlobalId>`.

### Refresh

`infobim project --refresh` brings a project in line with its folder, in two
stages:

1. **OntoBDC's container refresh.** It checks the container and each of its
   datasets, repairing what fails. It removes stray files. It rewrites the
   Data Package and the RO-Crate, so files added, changed or removed are
   recorded. A dataset still unhealthy after its repair **fails the refresh**,
   naming the dataset and the checks it fails.
2. **InfoBIM's project refresh.** It reconciles the reserved dataset and the
   IfcProject on top of the refreshed container.

Each file is recorded in the RO-Crate with a media type (`encodingFormat`):

- For the domain's own formats, it is the one the AECO ontology declares:
  `application/x-step` for IFC, `image/vnd.dxf` for DXF.
- For any other file, it is the type built into Python.
- An extension that neither knows gets no media type.

The result is the same on every machine.

## Commands

| What | Command |
|---|---|
| Make the current folder a storage root | `infobim init` |
| Show the version | `infobim --version` |
| Create a project under the current root | `infobim project --create "<name>"` |
| List the registered projects | `infobim project --list` |
| Show what a project holds | `infobim project --inspect` |
| The same, in an interactive tree (Textual) | `infobim project --inspect --interactive` |
| Check a project's health | `infobim project --health` |
| Register a project's files after they change | `infobim project --refresh` |
| Write metadata from a source | `infobim project --update <file.csv \| file.json \| key=value,…>` |
| Create a dataset inside a project | `infobim project --create-dataset "<title>"` |
| Register a project copied from elsewhere | `infobim project --project-path <path> --attach` |
| Unregister a project (its files stay) | `infobim project --delete <GlobalId>` |
| Look a term up in the ontology dictionary | `infobim context --term "<term>" --inspect` |
| Create IFC elements of the kind a term names, at points picked on a drawing | `infobim ifc --term "<term>" --point <drawing.dxf\|.dwg> [--ifc-model-path <model.ifc>]` |
| Install the 2D extra | `infobim 2d --enable` |
| Run the development tools (tests, …) of `ontobdc-dev` | `infobim dev …` |

Every project command also accepts `--global-id <GlobalId>` instead of the
current directory, and `--json` for a machine-readable answer. `infobim --help`
lists every command with its flags.

`infobim ifc --point` opens the drawing in the 2D viewer to pick the points. It
creates the elements in the model `--ifc-model-path` names. Without it, they
go into the project's own model, named after its IfcProject GlobalId; that
model is created and declared in the project if it does not exist yet.

## Source layout

```text
src/infobim/
├── cli/        entry point, init, --version, the welcome screen
├── project/    project lifecycle: create, list, inspect, health, refresh, update, attach, delete
├── ifc/        IFC elements: creation from points, IFC model bootstrap
├── drawing/    drawings: DXF reading, DWG → DXF through the ODA File Converter
├── context/    the ontology dictionary command
├── 2d/, _2d/   the 2D viewer (optional PySide6 extra) and its proxy
├── _3d/        the 3D viewer (optional PySide6 extra)
├── dev/        proxy to the ontobdc-dev tools
└── shared/     configuration shared by the components
legacy/         earlier implementation and its test suite, kept for reference; not packaged
```

Each component follows OntoBDC's plugin layout: `plugin/command/`,
`plugin/parameter/`, `plugin/check/` (with a `check.py` and its `hotfix.py`),
`plugin/capability/`, `plugin/machine/` (state machines in YAML), `adapter/` and
`domain/`. The CLI discovers commands from these folders.

## Tests

Tests run through the `ontobdc-dev` tools:

```bash
infobim dev test          # the InfoBIM test suite
infobim dev test --e2e    # the end-to-end tests, which run the real infobim executable
```

The previous end-to-end suite now lives under `legacy/test/` with the earlier
implementation. The active suite under `test/` is being rebuilt.

## License

[Apache License 2.0](LICENSE).
