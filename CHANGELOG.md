# Changelog

- Packaged the InfoBIM PNG icon, SVG brand mark and SVG logotype inside the Python distribution. Surface generation now resolves and embeds these installed resources locally, so branding works from a wheel without the source repository or network access.

## v0.14.0

### Fixed

- The IFC models a project declares were read from its RO-Crate as if the `@id` of each part were the path of the file. A crate that names a file by an identifier, with the path in the `relativePath` of its `fileHistory`, which is what OntoBDC writes, declared no IFC model: `infobim ifc --health` said the crate did not declare the model, and an IFC element was found in none, so commenting on it, tagging it or saving it failed with "No entity the container keeps has the global id". The three places that read the crate now ask the crate reader of OntoBDC, which knows both ways of naming a file.
- A geometry responsibility answered by the measurements it was handed rather than by which primitive they measure, so a cylinder — measured by a radius, as a sphere is — was created as whichever of the two the chain reached first: `infobim ifc --create <title> --radius <r> --height <h> …` produced an `IfcSphere`. The kind now travels with the measurements and each responsibility answers for its own.

### Added

- `infobim comment`, the project name of OntoBDC's comment commands: `--guid <id> --create|--list`, `--update <comment>` and `--delete <comment>`, with `--global-id` as the project selector. The entity may be an IFC element, which no dataset keeps: its thread is kept in the reserved dataset of the project, `payload/triple/comment_<GlobalId>.ttl`, where `--update` and `--delete` find it as they find any other.

- What the container says about an IFC element that the IFC model does not: its related documents and its tags (`related_documents` and `tags`, read and changed by `infobim ifc --guid <GlobalId> --inspect|--update` and by `infobim project --entity <id> --inspect|--update`). They are not kept in the IFC model but in the reserved dataset of the project, in `payload/triple/<ifc_class>.ttl` — `IfcWall` in `ifc_wall.ttl` — as the subject `urn:infobim:ifcwall/<GlobalId>`, typed with its class in the ifcOWL namespace of the schema of its model, with its GlobalId, the documents as `dcterms:relation` and the tags as `schema:keywords`. An element with none is not in the file, and a file with no element is removed.

- `infobim ifc --guid <GlobalId> --update <source> [--global-id <project>] [--ifc-model-path <model.ifc>]` changes the fields of one IFC element and writes the IFC model back to its file. The values come from `--update` as they do for an entity of a container (a JSON object, `key=value` assignments, or a `.json`/`.csv` file), and the fields that can be changed are the ones the facade of `IfcElement` declares editable: the name, the description and the tag. An empty value clears the attribute. `infobim project --entity <id> --update <source>` hands an id no dataset keeps to it, the way `--inspect` does. Saving rewrites the whole IFC file through `ifcopenshell`, so its text can differ from what the file had before, beyond the field changed.

- `infobim project --entity <id> --inspect`, the project name of OntoBDC's `container --entity <id> --inspect`. The entities of the datasets are OntoBDC's to answer; an id no dataset keeps may be an element of an IFC model of the project, which InfoBIM answers the way `infobim ifc --guid <id> --inspect` does.

- `infobim ifc --guid <GlobalId> --inspect [--global-id <project>]` inspects one IFC element of a project: the models its RO-Crate declares are searched for the `IfcElement` with that GlobalId, and the answer has the shape of the container entity listing, with the model that holds the element as the one dataset and the element as the one entity. `--ifc-model-path <model.ifc>` names the model that holds the element, which need not be one the RO-Crate declares; without it the declared models are searched. It needs `ifcopenshell`. The listing of `IfcElement` (`project --entity IfcElement --list`) answers its elements in the same shape.

- `infobim project --entity <type> --list` and `infobim project --entity <type> --tree`, the project names of OntoBDC's own entity listing and tree. `IfcElement` is the one type no dataset keeps, so listing it runs a machine of InfoBIM's own — it finds the IFC models the RO-Crate declares and reads their `IfcElement` instances (it needs `ifcopenshell`) — and answers in the shape of the container listing; any other type is handed to OntoBDC unchanged.

- `infobim dict --create <title> --uri <entry> [--global-id <GlobalId>] [--x --y --z]` defines an element of the project from a dictionary entry. It is the sibling of `infobim ifc --create`, and the difference is what decides what the element is: neither geometry nor IFC class is resolved from the invocation — the dictionary the URI names is what states them, and the command goes there, brings the entry back and reads it. `--global-id` is this executable's Project selector here as everywhere else, and the element being defined is identified by the machine, from the Project and the title, by the same rule the IFC creation flow derives a product's identity by.

  `--uri` takes the entry named in full — a URL or a path — or the prefix it is already called by everywhere else in this stack, which `UriStrategy` expands into the document the prefix is short for, through the same central ontology adapter every tool resolves prefixes with. A prefix nobody declared is refused rather than turned into a path by substituting its characters into a layout. What the expansion binds is where the entry is read from, the packaged copy of the ontology tree, with the namespace the prefix names kept beside it.

  The entry is stored in the project's own ETL state, under that element identity, so an element can still be explained after the dictionary it was defined from has been edited, moved or taken down. A code-hosting page is translated to the raw location of the same revision, so the link a human was given can be pasted as it is. What is read out of the entry is what the entry declares and nothing more: the IFC class it maps onto, the predefined type an OWL restriction pins that class to, and the other classes the definition belongs to; a reasoner is a different tool with different guarantees.

  What the entry says is then built. The shape it describes — an X3D primitive with the values pinned to that primitive's own properties, reached through the element's geometry and that geometry's description — becomes this run's geometry, and the IFC class and predefined type it states become the element the project's model carries, placed where the run put it and contained in its storey. From the shape onwards the states are the IFC creation flow's own, reached through its own capabilities rather than mirrored here: a shape defined, an IFC item carrying it, a representation wrapping the item, an element carrying the representation and a model carrying the element are the same facts whether the measurements came from a command or from a dictionary.

- `infobim 4d --task` opens a local screen for recording tasks and progress into the container's schedule workbook — the same workbook the Gantt Surface reads. One logical task is three rows across `IfcTask`, `IfcTaskTime` and `IfcRelSequence`, tied together by GlobalIds; typing those by hand is where a schedule loses data silently, because a mistyped id raises nothing, it just makes the task stop appearing in the Gantt. The command generates the ids and the `FINISH_START` sequence row, so nobody types one.

  The workbook and each sheet name come from the container's own `.__ontobdc__/datapackage.json`, never from a search: writing to a file the Surface does not read would be invisible until someone noticed the Gantt was stale. Rows are appended, and columns are matched by header name rather than position, so a workbook authored elsewhere keeps its shape; a column the entry needs but the sheet lacks (`ActualStart` in a schedule that only ever recorded the plan) is added rather than demanded. Progress entry records a finish date at 100% and an actual start on first movement, since a percentage with no dates cannot be compared against the plan.

- `infobim 4d --pdf` exports the datapackage-mapped `IfcWorkSchedule` workbook as a paginated A4 landscape PDF with a task table and matching Gantt chart. It supports both datapackage shapes used by InfoBIM: one resource per worksheet and one `IfcWorkSchedule` resource whose related entities are sheets in the same declared workbook. The output defaults beside the workbook and can be selected with `--out`.

## v0.6.0

### Changed

- `infobim`'s terminal output no longer hand-rolls its own rendering (title/description as plain text, content as raw `json.dumps`). It now reuses OntoBDC's terminal presentation Surface stack wholesale — `TerminalSurface`, the `Widget` port and its implementations, and `ResponseWidgetAdapterPort`/`ResponseWidgetAdapterLoader` (requires `ontobdc>=0.16.4`, already the floor) — the same architecture OntoBDC's own CLI was rebuilt on. Every InfoBIM command already returns one of OntoBDC's own `CommandResponse` types, so OntoBDC's existing widget adapters (record/table detection, recursive section decomposition, error rendering via `ErrorWidget`) apply with no InfoBIM-specific adapter code needed. Added `infobim.cli.adapter.logo.InfoBIMLogoComponent`, a thin subclass of OntoBDC's `LogoComponent` swapping only the brand text ("InfoBIM") and version lookup — everything else (ANSI coloring, the compact one-line default vs. the large pyfiglet banner, terminal-width centering) is inherited unchanged. `infobim`'s CLI now also honors `--large-logo`, `--silent`/`-s`, and a properly wired `--json` (previously parsed but silently ignored); uncaught command errors now render through `ExceptionCommandResponse`/`ErrorWidget` instead of a raw Python traceback.

## v0.5.3

### Fixed

- `infobim view`'s v0.5.2 retry-with-backoff fix for `PermissionError: [WinError 5]` still failed for some setups with `"still in use after 5 attempts"` — five identical failures in a row is the signature of a permanent condition (a read-only attribute OneDrive marks on synced files), not a transient lock, which retrying alone never fixes. Now uses ontobdc's improved `remove_directory_tree()`/new `remove_file()` (requires `ontobdc>=0.16.4`), which clear the read-only attribute and retry the specific failing operation before falling back to the sleep/retry loop for genuine transient locks. Also applies the same treatment to the stale surface-file removal (`surface_path.unlink()`), which had the identical unprotected-delete vulnerability.

## v0.5.2

### Fixed

- `infobim view` crashed with `PermissionError: [WinError 5] Access is denied` removing its ETL state directory (`.__ontobdc__/etl/view/surface`) on every run — the unprotected `shutil.rmtree()` call had no tolerance for a cloud-sync client (OneDrive, Dropbox, etc.) briefly holding an open handle on a file while indexing/uploading it, a lock that normally clears within a second. Now uses `ontobdc`'s `shared.adapter.filesystem.remove_directory_tree()` (requires `ontobdc>=0.16.3`), which retries with a short backoff before giving up instead of failing on the first transient lock.

## v0.5.1

### Fixed

- `pyproject.toml`'s `[tool.setuptools.package-data]` only listed `*.ttl` and `*.js` globs, so the published 0.5.0 wheel never shipped `project/domain/machine/standard_project_create.yaml`. Every `infobim project --create` run from a `pip install infobim` install failed with `FileNotFoundError` trying to load that statechart. Added a `**/*.yaml` glob so all packaged YAML — this file today, any future one automatically — ships with the wheel.

## Unreleased — v0.5

### Added

- `infobim/cli/plugin/command/{welcome,version}.py`: the bare `infobim` and `infobim --version` commands are now discovered the same declarative way as every other InfoBIM command, instead of being handled inline by `main()`. `init.py` re-exports OntoBDC's own `CliInitCommand` unmodified, the simplest possible proxy.
- `infobim/cli/adapter/help.py`: shared `discover_logical_components`/`build_command_table`/`build_domain_help_content` helpers, mirroring OntoBDC's own `StorageHelpCommand` pattern. All five help surfaces (`welcome`, `project --help`, `context --help`, `ifc --help`, `view --help`) now self-generate their Usage/Options content from `CommandLoader(<domain>, ..., root_package="infobim").get_all()` instead of hand-written text, so a new command's help never goes stale.

### Changed

- `infobim/cli/__init__.py`'s `main()` no longer hardcodes a flat if/elif dispatcher with a manually-maintained command list per domain. It now delegates to OntoBDC's own `CliCommandRunAdapter.make(args, logger, loader_class=functools.partial(CommandLoader, root_package="infobim"))`, reusing OntoBDC's health-check, command-resolution, and ambiguity-detection machinery unmodified (see `ontobdc`'s changelog for the `root_package` addition this relies on). Invalid/ambiguous argv now produces OntoBDC's standard "Invalid command arguments" error instead of InfoBIM's old generic message.
- `project --attach` and `project --update` now route through OntoBDC's own `StorageAttachCommand`/`StorageUpdateCommand` instead of calling the underlying state-transition handlers directly, picking up parameter-clearing behavior (`ATTACH_PLAN_PARAMETER` etc., stale `container`/`dataset_path` context) that was previously silently skipped. `project --list` now builds its container list via `StorageBaseCommand` instead of `ContainerIdStrategy._registered_containers`, keeping the existing IfcProject-presence filter on top. `project --delete`'s already-proxied `run()` gained response relabeling. All four commands now relabel OntoBDC vocabulary in their responses (`container_id` → `project_id`, "Storage Container ..." → "InfoBIM Project ...") so it never surfaces to InfoBIM users.
- Rebuilds InfoBIM from a clean `src/infobim` package against the current OntoBDC architecture.
- Preserves the complete v0.4 implementation under `src/old` as historical/source evidence for selective recovery.
- Resets the runtime baseline to `ontobdc>=0.14.0` and `ontobdc-view>=0.1.0`.
- Removes the assumption that v0.4 code should be ported wholesale; functionality returns only when it remains an InfoBIM/BIM responsibility.

## Frozen — v0.4 (never released)

v0.4 is intentionally frozen and will not be released. The OntoBDC architecture changed substantially while this line was under development, so v0.5 starts a selective reconstruction rather than attempting an in-place migration.

### Breaking changes

- Requires OntoBDC 0.12 and its strict annotation schema 2.
- Removes the temporary `InfoBIMSpatialAnnotations` and `infoBimWorkStreamView` aliases.
- Does not read or repair legacy annotations.

### Added

- Typed annotations inside WorkStream evidence views.
- Portuguese presentation labels and the InfoBIM visual theme over the OntoBDC runtime.
- BIM resource and people resolver specialization through the generic OntoBDC resolver contract.
- Embedded annotation workspace and Subject Page navigation.
- Anonymous WorkStream demonstration data and release-contract tests.
