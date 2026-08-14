# ADR 002: CLI Output Strategy via Inversion of Control (IoC) with export_*

## Status
Accepted

## Context
The CLI outputs for capabilities were implemented with ad-hoc `if/else` blocks inside each strategy, duplicating logic and making it harder to introduce new formats consistently (e.g., JSON, Rich, Markdown, HTML, PDF). We need a unified, extensible mechanism to route output formatting without coupling business logic and presentation.

## Decision
Introduce an IoC-based output dispatch in the Capability CLI Strategy base class:
- Add `render(console, args, capability, result)` in `CapabilityCliStrategy` to centralize format selection using `args.export`.
- Implement default exporters:
  - `export_json`: standard JSON rendering using `json.dumps`.
  - `export_rich`: default rich printing (capabilities can override).
- Each capability strategy may override `export_rich` (and future exporters) to provide structured tables or domain-specific visualization, while keeping JSON as a safe fallback.
- The runner remains responsible for parsing `--export` and passing it to strategies; strategies do not declare their own `--export` to avoid argparse conflicts.

## Rationale
- Removes repeated conditionals across strategies.
- Enables new output formats by adding `export_<format>` methods with minimal touch-points.
- Keeps capability logic isolated from presentation concerns.
- Preserves backward compatibility: default format is `rich`; fallback is `json` if a specific exporter is absent.

## Alternatives Considered
- Per-capability `if/else` blocks for output selection: leads to duplication and drift.
- External formatter service: adds indirection and coupling for small, self-contained CLI outputs.
- Hooks-only approach without standardized method names: lacks discoverability and consistency.

## Consequences
### Positive
- Consistent output behavior across capabilities.
- Clear extension path for formats (`md`, `html`, `pdf`).
- Easier testing; JSON output validated in CLI tests.
### Negative / Trade-offs
- Requires strategies to follow the `export_*` naming convention.
- Minor refactor to remove local `--export` arguments from strategies to avoid conflicts with the runner.

## Implementation
- Core dispatch:
  - File: `stack/src/bib/core/capability/cli_strategy.py`
  - Methods: `render`, `export_json`, `export_rich`
- Strategies updated to use `render` and override `export_rich`:
  - `stack/src/plugin/capability/base/list_project_units.py`
  - `stack/src/plugin/capability/distribution/list_pipes.py`
  - `stack/src/plugin/capability/distribution/list_sewage_pipes.py`
  - `stack/src/plugin/capability/base/list_materials.py`
- Runner flag:
  - `stack/run.py` adds `--export {rich|json}` and delegates to strategies.

## Testing
- CLI export JSON tests ensure the stdout is valid JSON for:
  - Project Units, List Pipes, List Sewage Pipes
  - File: `test/suites/plugin/capability/base/test_cli_export.py`
  - Command examples:
    - `./infobim run org.infobim.base.capability.list_project_units <ifc> --export json`
    - `./infobim run org.infobim.base.capability.list_pipes <ifc> --export json`
    - `./infobim run org.infobim.base.capability.list_sewage_pipes <ifc> --export json`

## Future Work
- Add `export_md`, `export_html`, `export_pdf` with standardized structure and i18n.
- Consider a shared formatter toolkit for table/data layout across formats to reduce duplication.
