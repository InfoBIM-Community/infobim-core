# Technical Specification: Narrative TUI (`SPEC-003`)

## 1. Overview
- Provides a terminal UI to browse IFC files and select narrative chapters.
- Delegates rendering and translations to template-provided UI adapters.
- Persists narrative output blocks as Markdown via a repository adapter.

## 2. Components
- Global configuration: [config.yaml](../../src/tui/config.yaml)
- Selected template: relative path in `template.path` (from config)
- Template UI adapter: [screen.py](../../src/tui/terminal/template/infobim-community-tui/adapter/ui/screen.py)
- Template translations: [translation](../../src/tui/terminal/template/infobim-community-tui/translation)
- Narrative runner: [narrative.py](../../src/tui/terminal/narrative.py)

## 3. Execution Flow
1. Load config (language, `template.path`).
2. Resolve absolute template directory.
3. Load template module class `TerminalScreenAdapter`.
4. Instantiate IFC repository:
   - Local default: `./data/incoming`
   - Docker when `engine.ifc == docker`
5. Build IFC file tree via `IfcFileTreeAdapter`.
6. If `TerminalScreenTreeContentAdapter` exists, render tree/list through it; else use adapter default rendering.
7. Collect available IFC files and allow user selection.
8. Load chapter list from template translation:
   - `translation/<lang>.yaml` → `narrative.chapters`
   - Fallback to `en.yaml` if specific language is missing.
9. Display chapter menu; on choice, proceed with chapter workflow.

## 4. Cover Template (pt_BR)
- Location: [cover.jinja](../../src/plugin/template/infobim-community-tui/pt_br/cover.jinja)
- Variables:
  - `title` or `project_name`
  - `subtitle` (optional)
  - `author_name`, `author_org` (optional)
  - `version`, `release_name` (optional)
  - `date` (string)
  - `tags` (list)
  - `logo_text` (optional)

## 5. Markdown Output Repository
- A repository adapter persists narrative blocks as Markdown.
- Output directory: `data/outgoing` (relative to repository root)
- Write policy:
  - One `.md` file per content block (cover, chapter, annexes).
  - Filename recommendation: `<timestamp>_<block_slug>.md`
  - UTF-8 content; no binary metadata.
  - Adapter must create the directory if missing.

## 6. Translation Rules
- UI adapter loads template translations based on config language.
- Minimum keys:
  - `exit.label`
  - `exception.message.ifc_engine_not_found`
  - `narrative.chapters` (string labels or objects with `label`/`value`)

## 7. Extensibility
- New templates can provide:
  - Custom UI adapters
  - Translation files `translation/<lang>.yaml`
  - Jinja partials for cover/sections (e.g., `cover.jinja`, `chapter.jinja`)
- Alternative repositories may be used if they implement writing to `data/outgoing`.

## 8. Considerations
- Safe fallbacks when translations/files are missing.
- Maintain strict separation of ports (contracts) and adapters (implementations) in TUI.
