# Project CLI end-to-end tests

Run from the InfoBIM repository in the virtual environment containing pytest,
InfoBIM, OntoBDC, BrasidataCenter and their runtime dependencies:

```sh
PYTHONPATH="$PWD/src:$PWD" python -m pytest -q test/e2e/project
```

The suite follows the OntoBDC command-test structure: the installed executable
next to the current Python interpreter runs in a real subprocess, with JSON
output and a temporary working directory. The runners prepend this checkout
to PYTHONPATH and remove project-root environment overrides. Interactive
inspection uses a real pseudo-terminal, sends keys and checks process completion.

Coverage includes project help, creation, listing, attachment, deletion,
dataset creation, health, refresh, static and interactive inspection, metadata
update, IFC GlobalId and storage-ID selection, and relocation of the storage root.
Assertions verify response contracts, RDF and JSON metadata, index changes,
user-file preservation, repeatability and rejected arguments.

ProjectE2eWorkspace initializes the root through the real CLI and prepares a
project with existing standalone hotfixes, as ContainerE2eWorkspace does in
OntoBDC. Fixture setup is independent of project creation; creation has its own
command tests. Every tested operation invokes the executable, rather than calling
command classes or capabilities directly. No commands are mocked and no failures
are skipped or marked as expected failures.

These tests cover the project command. Opening files in external 2D/3D viewers
and processing large IFC model fixtures are outside this suite's scope.

## Validation on 2026-10-03

The full project suite collected 72 cases: 66 passed and 6 failed.
All six failures are successful-update contracts, across inline, JSON and CSV
sources. Updating from the project directory fails because OntoBDC requests
`ontology/tool/ontobdc/resource/data_container_facade.ttl`, which the installed
BrasidataCenter package does not contain. Updating with `--global-id` fails at
argument routing, although ProjectUpdateCommand declares that selector.
These failures remain active; this test-only change does not alter production
commands or ontology resources.

## Validation on 2026-10-04

After fixing the production update path, all 72 project command tests passed.
The existing OntoBDC update suite passed all 12 tests and BrasidataCenter passed
all 11 resource tests. The container update command now accepts its selector
and preserves the selection already resolved by the CLI when invoking persistence.
The editable title and description fields are declared in the canonical
`ontology/tool/ontobdc/abox/facade.ttl` resource shipped by BrasidataCenter.
The explicit-ID update cases run from the storage root, so their success cannot
come from implicitly selecting the project through the working directory.
