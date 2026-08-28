# InfoBIM

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

> **If you just landed**: InfoBIM is an **OpenBIM application of OntoBDC** for
> transforming ordinary project information into an executable semantic mesh,
> while keeping files in the formats and environments where they already live.
>
> InfoBIM is implemented on top of the OntoBDC generic semantic runtime —
> install the sibling `ontobdc/` package first, then this one.
>
> Everything below is about InfoBIM itself: its CLI, its domain contracts,
> its tiles and its v0.5 rebuild status.

---

## 3-minute Quickstart

```bash
# 1. Install prerequisites (install the sibling ontobdc package first)
pip install infobim

# 3. Initialize a shared workspace
mkdir -p ~/bim-workspace && cd ~/bim-workspace
infobim init

# 4. Create a new empty InfoBIM Project
infobim project --create ~/bim-workspace/demo-hospital

# 5. Drop IFC files / PDFs / spreadsheets into the Project folder and reprocess:
cd ~/bim-workspace/demo-hospital
infobim project --update

# 6. Generate the Project Surface HTML and open it in the default browser
infobim view
```

> **`--create <path>` takes a literal filesystem path, not a project name.**
> It is resolved and used directly — InfoBIM never nests a new subfolder
> underneath it on your behalf. This matters in two ways:
>
> - **Pointing it at an existing folder adopts that folder in place.** Every
>   internal folder-creation step is idempotent (`mkdir(..., exist_ok=True)`),
>   so re-running `--create` against a folder that's already a Project (or
>   partway there) is safe and simply resumes/completes it — it will not fail
>   or duplicate anything. To use the folder you're already standing in:
>   ```bash
>   infobim project --create .
>   ```
> - **A bare relative name is still a path**, resolved against your current
>   directory — it is *not* a display name. Running
>   `infobim project --create "My Project"` while already inside
>   `.../Some Existing Folder/` creates a **new subfolder**
>   `.../Some Existing Folder/My Project/`, one level deeper than you're
>   probably expecting, instead of using the folder you're in. If that's not
>   what you want, pass `.` (see above) or an absolute path to the exact
>   folder you mean.
>
> The Project's display name is derived from the **target folder's own
> basename** — there is currently no separate `--name`/title argument
> independent of the path. If you want a specific display name, name (or
> rename) the folder accordingly before running `--create`.

---

## Core InfoBIM concepts

### 1. InfoBIM Project

An InfoBIM Project is a data folder that carries:

- a **reserved IfcProject dataset** (with a stable and unique IFC GlobalId);
- zero or more IFC payload datasets (`.ifc` files with elements, materials,
  properties);
- zero or more supplementary documents (PDFs, photos, schedules, etc);
- metadata, semantic bindings and presentation facades inside the
  `.__ontobdc__/` folder.

The **IfcProject GlobalId** is InfoBIM's natural user-facing identifier.
Operators never have to memorize technical container UUIDs — they refer to
projects by GlobalId, by name, by path, or simply by being `cd`'d inside the
project folder.

### 2. ProjectIdStrategy

`ProjectIdStrategy` is InfoBIM's parameter-translation layer. Before any
command runs it normalizes *any* of these user inputs:

- an explicit `--project-id <IfcGlobalId>`;
- a `--project "project name"` or `--project /path/to/project`;
- no flag at all, when the current working directory is already a Project.

into a consistent resolved triple:

```
project_id (IfcGlobalId)  +  container_id (stable UUID)  +  project_path
```

If resolution fails it raises a `CliCommandArgumentException` telling the user
exactly what to do next: list projects with `infobim project --list`, `cd`
into the project folder, or retry with the right `--project-id`.

### 3. IFC datasets and their facades

When `infobim project --update` runs, InfoBIM processes the IFC payload
datasets in the Project. Each dataset may expose IFC classes through its
semantic facade, while the actual entity instances remain in the dataset and
are read through the OntoBDC dataset repository.

Across the Project, InfoBIM can therefore build:

- a deduplicated IFC class catalog;
- per-class element lists across all matching datasets;
- per-element GlobalId lookup across the Project.

The **datasets are the source of truth** consumed by the IFC commands and
presentation layer. Dataset facades describe which IFC entity classes a
dataset exposes and are used to discover the relevant datasets and classes.

### 4. BIM tiles on the Presentation Surface

When `infobim view` runs it injects InfoBIM domain-specific web components
into the static Surface HTML. The default Surface includes:

- a **Project header tile** — semantic IfcProject header (GlobalId, name,
  description, IFC schema, project-level metrics);
- a **Work schedule tile** — browser for `IfcWorkSchedule` context instances
  attached to the project.

The **Distributed IFC** component remains implemented and available for
explicit use, but is not selected by the default InfoBIM Surface.

The set of InfoBIM tiles is extensible; the README does not treat the current
number of components as part of the architectural contract.

The tiles are injected as JS strings and loaded client-side; the Surface
itself is fully static and opens offline via `file://`.

### 5. IfcWorkSchedule workbook service

"Creating one schedule instance" means more than one sheet. An
`IfcWorkSchedule` semantically relates to `IfcTask` rows and each `IfcTask`
points to an `IfcTaskTime` row — a 3-entity workbook, not a 1-entity sheet.

That is why InfoBIM provides a dedicated service that intercepts:

```bash
infobim context --create "Executive Schedule" --entity IfcWorkSchedule --project-id <GlobalId>
```

and produces a single XLSX workbook with three sheets:

```
ifc_work_schedule.xlsx
├── IfcWorkSchedule   ← PredefinedType: PLANNED default; ACTUAL / BASELINE / USERDEFINED / NOTDEFINED allowed
├── IfcTask           ← tasks; TaskTime column keeps reference to IfcTaskTime rows
└── IfcTaskTime       ← time data for each task
```

The mapping (`IfcWorkSchedule → IfcTask → IfcTaskTime`) is driven by the
`ibim:assignsRelatedClass` predicate declared in the InfoBIM ontology so
future multi-entity workbooks follow the exact same pattern.

---

## v0.5 status — selective rebuild instead of a blind port

InfoBIM 0.5 is a deliberate rebuild against the current generic OntoBDC
architecture. The previous v0.4 monolithic implementation is **not** deleted:
the full v0.4 source tree is preserved under `src/old/` while the active 0.5
implementation lives exclusively under `src/infobim/`.

### The rebuild decision rule

Code is brought back from `src/old` only when:

1. its responsibility still genuinely belongs to InfoBIM, and
2. it fits the current contracts.

The decision tree per legacy piece:

- is this already provided by the generic runtime? → drop;
- is this already provided by the generic view layer? → drop;
- is this genuinely BIM/InfoBIM-specific and still valuable? → cherry-pick or
  reimplement cleanly;
- is this obsolete? → leave frozen in `src/old` as evidence only.

`src/old` is **not** part of the distributed `infobim` Python package, is
**not** discoverable by the active command loader, and is **not** imported at
runtime. It is a frozen reference library.

---

## CLI — cheat-sheet (top commands)

Full user-centric reference with guards, response shapes and detailed examples
is cataloged in
[`../ontobdc/docs/2026-08-14-infobim-cli-command-reference.md`](../ontobdc/docs/2026-08-14-infobim-cli-command-reference.md).

| Intent | Command |
|---|---|
| Initialize workspace | `infobim init` |
| Check which version is active | `infobim --version` \| `-v` |
| Create a new empty Project — `<path>` is a literal filesystem path, not a name; `.` adopts the current directory (see Quickstart note above) | `infobim project --create <abs/or/rel/path>` |
| List every registered Project (filtered to real IfcProject-bearing containers only) | `infobim project --list` |
| Attach a Project received via external drive / shared folder | `infobim project --project-path <path> --attach` |
| Refresh Project datasets after dropping new IFCs/docs | `infobim project --update` (inside folder) or `--project-id <GlobalId>` |
| Rename a Project in-place | `infobim project --project-id <id> --update --project "New Name"` |
| Deregister a Project from the workspace index (by GlobalId) | `infobim project --delete <GlobalId>` |
| Inventory all IFC classes + counts in a Project | `infobim ifc --project-id <id> --class --all` |
| List all elements of one IFC class | `infobim ifc --project-id <id> --class IfcWall --all` |
| Drill into a single element by GlobalId | `infobim ifc --project-id <id> --element <ElemGlobalId>` |
| Browse the full entity catalog | `infobim context --entity --all` |
| Create a full workbook-backed `IfcWorkSchedule` | `infobim context --create "Name" --entity IfcWorkSchedule --project-id <id>` |
| Record 4D tasks and progress in the mapped workbook | `infobim 4d --task [--container <path>]` |
| Export the mapped 4D Gantt as a paginated PDF | `infobim 4d --pdf [--container <path>] [--out <file.pdf>]` |
| Generate + open Project Surface | `infobim view` (inside project) or `--project-id <id>` |

---

## Active source layout

```text
infobim/ (this package)
├── src/
│   ├── infobim/             # active v0.5 distribution package (discovered by CLI loader)
│   │   ├── cli/             entry-point (welcome / --version / init)
│   │   ├── 4d/              task entry and Gantt PDF capabilities
│   │   ├── project/         full lifecycle + ProjectIdStrategy
│   │   ├── ifc/             IFC operational commands and catalog access
│   │   ├── context/         entity command + IfcWorkSchedule workbook service
│   │   └── view/            presentation repository, InfoBIM tile assets, Surface state machine
│   └── old/                 # frozen v0.4 reference (NOT shipped, NOT imported, NOT discoverable)
│       ├── cli/
│       ├── project/         legacy create / detail / import / locate / update / create_element
│       ├── context/         legacy learn-from-ifc-element flow
│       └── view/            legacy dashboard / element / 5W2H surfaces
├── tests/                   mirrors src/infobim/ structure
├── docs/                    v0.5-plan, view-architecture, ADRs
├── demo/annotation-workstream/  sample JSON payloads
└── README.md                # this file
```

---

### Mandatory JS syntax check before trusting any tile change

Because InfoBIM tiles are injected as strings into the Surface, always
validate JS syntax before shipping a modified view:

```bash
node --check src/infobim/view/plugin/asset/js/*.js
```

---

## Boundaries: what InfoBIM deliberately does NOT reimplement

To keep InfoBIM a thin domain layer, the following responsibilities are
explicitly delegated to the generic OntoBDC runtime:

- container / dataset / storage-index mechanics;
- the 5-category strict annotation contract (Note / Issue / Classification /
  Location / Record);
- WorkStream machinery (Related / Suggested / Found tabs, linkset persistence
  into `.__ontobdc__/linkset/`, Proposed/Rejected audit trail);
- Subject Page and annotation workspace filters;
- Surface HTML layout, tile compositor, routing and browser opening;
- dBriefcase / dDock / dWorker product concepts and the event model.

If in doubt: default to generic code, only add InfoBIM-specific code when the
behavior genuinely depends on IFC / buildingSMART semantics.

---

## Related documentation

| Title | Path |
|---|---|
| Full audited CLI reference | [../ontobdc/docs/2026-08-14-infobim-cli-command-reference.md](../ontobdc/docs/2026-08-14-infobim-cli-command-reference.md) |
| InfoBIM v0.5 rebuild plan | [docs/v0.5-plan.md](docs/v0.5-plan.md) |
| InfoBIM View architecture & extension points | [docs/infobim-view-architecture.md](docs/infobim-view-architecture.md) |
| ADR — visual representation parameter | [docs/adr/ADR-visual-representation-parameter.md](docs/adr/ADR-visual-representation-parameter.md) |
| OntoBDC generic CLI reference (for the delegated commands) | [../ontobdc/docs/2026-08-14-cli-command-reference.md](../ontobdc/docs/2026-08-14-cli-command-reference.md) |
| AI agent rules (shared agent contract) | [../ontobdc/docs/AGENTS.md](../ontobdc/docs/AGENTS.md) |

---

## License

[Apache License 2.0](LICENSE).
