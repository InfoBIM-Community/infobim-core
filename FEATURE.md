---
feature: Navigable PDF WorkStream Publication
feature_id: navigable-pdf-publication
repository: InfoBIM-Community/infobim-core
component_role: WorkStream publication command, engineering selection profiles and navigable PDF presentation
source_version: 0.3.0
source_branch: master
source_commit: 77a901dc985ae7574faffc3d05d40fe1f60ae4d6
feature_branch: feat/navigable-pdf-publication
target_version: TBD
status: planning
created_at: 2026-07-31
related_repository: OntoBDC/ontobdc-core
related_source_version: 0.11.0
related_feature_branch: feat/navigable-pdf-publication
---

# Navigable PDF WorkStream Publication

## 1. Summary

This feature introduces a publication layer that transforms a live InfoBIM WorkStream, backed by an OntoBDC container, into a filtered, navigable, portable and verifiable PDF snapshot.

The PDF is not the source of truth and does not replace the live WorkStream. It is a derived publication artifact created for a specific audience, purpose and point in time.

The central flow is:

```text
Live WorkStream container
        ↓
Publication profile + audience + source revision
        ↓
Content selection, rendering and provenance capture
        ↓
Navigable PDF publication
```

The result must be usable without granting the recipient access to the engineering OneDrive, internal project folder, InfoBIM runtime or live WorkStream.

## 2. Problem and motivation

The immediate operational need is to share WorkStream information with recipients who cannot access the internal engineering information environment:

- a contractor outside the organization;
- a client user inside the organization but without access to the engineering OneDrive;
- another external recipient who needs a controlled deliverable but must not receive the complete internal WorkStream.

The usual alternatives create friction or information loss:

- requesting external accounts and permissions;
- exposing internal folder structures;
- sending isolated drawings, photos and reports without context;
- manually assembling delivery packages;
- duplicating and reorganizing information outside the source container;
- requiring installation, login, server access or training.

PDF is already accepted as a normal engineering deliverable. A navigable PDF allows the structured intelligence of the WorkStream to cross organizational boundaries disguised as a familiar document rather than a new platform.

## 3. Primary use cases

### 3.1 Executive project publication for the contractor

Generate a controlled PDF containing only what is required for execution, such as:

- current executive drawings and details;
- applicable scope;
- released areas;
- execution-relevant constraints and pending items;
- approved instructions;
- selected photos and evidence;
- links between locations, activities, drawings and documents.

Internal discussions, costs, private annotations, commercial information and unauthorized files must remain excluded.

Conceptual command:

```bash
infobim publish workstream infrastructure \
  --profile executive-project \
  --audience contractor \
  --output project-executive-r07.pdf
```

### 3.2 Databook publication for the client

Generate a navigable databook containing the approved project record, such as:

- final documents and drawings;
- revisions and approvals;
- inspections and checklists;
- photographic records;
- certificates;
- as-built information;
- activity and evidence timelines;
- traceability between location, activity, document and evidence.

Conceptual command:

```bash
infobim publish workstream infrastructure \
  --profile databook \
  --audience client \
  --output databook-infrastructure-r03.pdf
```

### 3.3 Periodic publication

The publication command may be executed automatically at defined intervals, for example:

- daily during a critical execution phase;
- weekly for contractor coordination;
- monthly for client reporting;
- at each formal revision or milestone;
- after a WorkStream reaches a publishable state.

The MVP should expose a deterministic, non-interactive command that can be called by Windows Task Scheduler, cron, CI or another external scheduler. A permanent InfoBIM daemon or cloud service is not required.

## 4. Product concept

The PDF is the publication interface of the WorkStream.

The architecture separates:

- **live operational source:** the InfoBIM/OntoBDC container;
- **publication rules:** profile, audience, filters and template;
- **published deliverable:** the generated navigable PDF;
- **publication event:** who generated it, when, from which source state and for which purpose.

This creates a clean distinction between internal operation and external delivery.

```text
WorkStream revision X
    ├── contractor executive-project PDF
    ├── client databook PDF
    ├── internal coordination PDF
    └── management summary PDF
```

## 5. Core principles

### 5.1 WorkStream remains the source of truth

The PDF is always derived. Corrections are made in the WorkStream and followed by a new publication. The PDF must never become the authoritative editable source.

### 5.2 Audience-specific publication

Every output must be filtered for its recipient and purpose. The feature must not expose the complete WorkStream merely because all resources are reachable from the source graph.

### 5.3 Static and portable by default

The baseline PDF must work offline and without scripts, plugins, logins, servers or application-specific runtime behavior.

### 5.4 Verifiable snapshot

A PDF is not intrinsically impossible to modify. The feature must therefore produce a tamper-evident and traceable publication.

Each publication must record at least:

- publication identifier;
- WorkStream identifier;
- source container identifier;
- source snapshot or revision;
- source container hash;
- publication profile and version;
- audience;
- generation timestamp;
- generator name and version;
- included-resource manifest;
- final PDF hash stored in an external publication record.

Optional later capabilities may include digital signatures, trusted timestamps and content-addressed storage.

### 5.5 Conservative PDF compatibility

The dependable baseline uses:

- bookmarks;
- internal page links;
- clickable table of contents;
- standard HTTP/HTTPS links;
- searchable text;
- static images and vector content;
- visible navigation controls.

JavaScript, automatic local-file execution, 3D, complex forms and multimedia must not be required.

## 6. Expected navigation model

A publication may contain:

1. Cover and publication metadata.
2. Executive dashboard or summary.
3. Navigation by area or physical location.
4. Navigation by subject or discipline.
5. Navigation by date or timeline.
6. Navigation by person or responsible party.
7. Drawings or plans with clickable hotspots.
8. WorkStream item, annotation or occurrence pages.
9. Evidence pages.
10. Documents and references.
11. Traceability and publication manifest.

Detailed pages should provide consistent controls where applicable:

```text
Home | Back to plan | Previous | Next | Open evidence
```

The PDF may simulate prepared filters by generating separate indexed sections. It is not expected to support arbitrary semantic queries after publication.

## 7. WorkStream content model for publication

The publication model should be able to represent and connect:

- WorkStream 5W2H data;
- areas and physical locations;
- subjects and disciplines;
- people, organizations and responsibilities;
- timeline events and status changes;
- annotations;
- drawings and sheets;
- documents and document revisions;
- photos and other evidence;
- activities and deliverables;
- IFC elements or model references when available;
- source identifiers and provenance links.

The renderer should operate on an intermediate publication model rather than directly coupling every page to raw Turtle, YAML, JSON or filesystem structures.

## 8. Publication profiles

A publication profile defines what is selected and how it is rendered.

Conceptual profile:

```yaml
id: executive-project
name: Executive Project for Contractor
audience: contractor
workstream_selector: infrastructure
include:
  entity_types: []
  states: []
  relationships: []
  document_categories: []
  evidence_categories: []
exclude:
  visibility: [internal, confidential]
  document_categories: [commercial, cost, internal_discussion]
navigation:
  by_area: true
  by_subject: true
  by_date: true
  by_person: false
  plan_hotspots: true
rendering:
  template: executive-project
  include_manifest: true
  include_qr_codes: false
```

Profiles must be declarative, validated and versionable.

Initial profiles:

- `executive-project` for contractor delivery;
- `databook` for client delivery.

Future profiles may include internal coordination, management summary, handover package, inspection record or discipline-specific publications.

## 9. InfoBIM responsibilities

This repository owns the user-facing and engineering-domain implementation.

### 9.1 WorkStream resolution

- resolve a WorkStream by ID, name or path;
- read its 5W2H structure and linked resources;
- preserve the relationship between source entities and publication sections;
- report missing or ambiguous links before rendering.

### 9.2 Engineering selection profiles

- define the initial `executive-project` and `databook` profiles;
- map audience rules to document, annotation, evidence and visibility categories;
- provide restrictive defaults for external publication;
- expose dry-run selection summaries.

### 9.3 Publication views

The renderer should support prepared views such as:

- by area;
- by subject;
- by person;
- by date;
- by WorkStream item or status;
- by document or evidence type.

The view set may grow later without changing the core idea of a static publication.

### 9.4 Plans and hotspots

When coordinates or visual references are available, InfoBIM should:

- render a plan, drawing or image;
- place clickable regions over areas, elements or annotations;
- route each hotspot to the relevant detail page;
- provide textual indexes as an alternative to purely visual navigation;
- provide a reliable route back to the plan.

### 9.5 Page templates

Initial template families:

- cover and publication metadata;
- dashboard/summary;
- area index;
- subject index;
- timeline;
- people/responsibility index;
- plan with hotspots;
- WorkStream item/occurrence sheet;
- evidence sheet;
- document/revision sheet;
- traceability and manifest.

### 9.6 CLI command

The exact syntax remains open, but the feature should expose a command equivalent to:

```bash
infobim publish workstream <workstream-id> \
  --profile <profile-id-or-file> \
  --audience <audience> \
  --output <publication.pdf>
```

Expected supporting options may include:

```text
--source-revision
--publication-revision
--template
--dry-run
--overwrite
--output-package
--include-attachments
--generated-at
--non-interactive
```

The MVP must not require every option. Defaults must remain safe and explicit.

### 9.7 Automation compatibility

- command must run without prompts when required parameters are supplied;
- exit codes must distinguish validation, missing resource and rendering failures;
- output filenames may use profile, revision, date and WorkStream placeholders;
- scheduled executions must not silently overwrite formal revisions;
- generation logs and publication records must remain auditable;
- the command should be callable from Windows Task Scheduler in restricted corporate environments.

## 10. OntoBDC responsibilities

The coordinated OntoBDC feature branch owns generic runtime concerns:

- container and dataset resolution;
- RO-Crate-first resource discovery;
- publication-profile loading and generic validation;
- semantic resource selection and exclusion;
- source snapshot and provenance capture;
- source and output hashing;
- publication-record generation;
- generic rendering orchestration;
- non-interactive capability execution and exit codes.

InfoBIM should not duplicate generic container, provenance or hash logic when it can be provided by OntoBDC. OntoBDC should not embed InfoBIM-specific assumptions about WorkStreams, drawings, contractors or databooks.

## 11. Rendering pipeline

Conceptual stages:

```text
resolve WorkStream and source container
    ↓
load and validate publication profile
    ↓
select and exclude resources
    ↓
build intermediate publication model
    ↓
render sections and pages
    ↓
create links, destinations and bookmarks
    ↓
write provenance and manifest page
    ↓
finalize PDF
    ↓
calculate output hash
    ↓
register publication event
```

The rendering engine remains an open technical decision. Selection criteria include:

- internal links and destinations;
- bookmarks;
- image and vector support;
- page composition control;
- reliable Windows installation;
- offline operation;
- acceptable package size;
- licensing;
- compatibility with the current Python stack.

## 12. Publication record

Each output must have a structured publication record, conceptually:

```yaml
publication_id: <id>
workstream_id: <id>
source_container_id: <id>
source_snapshot_id: <id>
source_hash: <sha256>
profile_id: <id>
profile_version: <version>
audience: <audience>
generated_at: <timestamp>
generator:
  name: infobim
  version: <version>
  ontobdc_version: <version>
output:
  file: <name>
  media_type: application/pdf
  sha256: <hash>
included_resources: []
excluded_resource_summary: {}
```

The final PDF SHA-256 must be stored outside the PDF because the file cannot reliably contain its own final hash before completion.

## 13. Packaging strategies

### 13.1 Single self-contained PDF

Preferred for the first implementation.

Advantages:

- one familiar file;
- works offline;
- easy to email, archive, upload and protocol;
- no broken relative paths.

Disadvantages:

- may become large;
- embedded attachments are not consistently supported.

### 13.2 PDF plus controlled payload package

Possible package:

```text
publication-package/
├── index.pdf
├── manifest.json
├── evidence/
├── drawings/
└── documents/
```

The package may be distributed as a ZIP or container snapshot.

Advantages:

- native files remain available;
- lighter PDF;
- large evidence remains outside the document.

Disadvantages:

- relative links may be blocked or broken;
- the folder structure must remain intact;
- email, Teams or SharePoint may separate files.

External-payload packaging should be optional. The MVP should prioritize a self-contained navigable PDF.

## 14. Security and disclosure control

Publication is an explicit disclosure operation and must assume that the result can leave the internal organization.

Required safeguards:

- audience declared in the profile or command;
- default-deny treatment for internal and confidential information;
- dry-run or preview summary before formal release;
- manifest of included resources;
- warnings for unresolved visibility classifications;
- no implicit inclusion of every reachable file;
- no hidden internal notes in PDF layers, annotations or metadata;
- removal or control of sensitive PDF metadata;
- explicit handling of external URLs and attachments;
- future support for redaction rules where omission is insufficient.

## 15. Advantages

- no external OneDrive or internal-folder access is required;
- contractor and client receive only the intended publication;
- familiar PDF delivery avoids platform-adoption resistance;
- works offline;
- preserves navigation and context absent from ordinary document dumps;
- provides a formal snapshot for contractual, audit and handover purposes;
- different audiences can receive different outputs from one WorkStream state;
- periodic exports can be automated;
- source-to-deliverable traceability is preserved;
- printing remains possible;
- manual executive-project and databook assembly is reduced.

## 16. Disadvantages and limitations

- the PDF is static and must be regenerated after source changes;
- arbitrary live queries are unavailable inside the PDF;
- drawings, photos and evidence may produce very large files;
- viewer support varies;
- relative local links and attachments may be blocked;
- PDF is not suitable for concurrent collaboration or status updates;
- recipient comments create divergent copies;
- strong tamper resistance requires hashes, controlled storage or digital signatures;
- visual hotspots require textual alternatives and deliberate accessibility work;
- advanced JavaScript, 3D and multimedia are unreliable baseline dependencies;
- archival PDF standards may restrict active features.

## 17. Compatibility tiers

### Tier 1 — Baseline portable publication

Required for MVP:

- internal links;
- bookmarks;
- clickable table of contents;
- searchable text;
- static drawings and images;
- standard URLs;
- provenance page;
- publication identifier and source-hash reference.

### Tier 2 — Enhanced controlled publication

Optional:

- QR codes;
- embedded attachments;
- external package links;
- layers where supported;
- digital signature;
- trusted timestamp.

### Tier 3 — Viewer-specific experiments

Not part of the dependable baseline:

- JavaScript;
- 3D PDF;
- multimedia;
- automatic external-file execution;
- complex interactive forms.

## 18. MVP scope

The first usable implementation should provide:

1. Publication of one selected WorkStream.
2. Two profiles: executive project and databook.
3. Audience-based inclusion and exclusion.
4. Clickable table of contents and bookmarks.
5. Internal navigation among summary, location, item and evidence pages.
6. Static plan or drawing with clickable hotspots when coordinates exist.
7. Publication metadata and traceability page.
8. Source snapshot/hash reference.
9. External publication record with final PDF hash and included-resource manifest.
10. Non-interactive CLI execution suitable for periodic scheduling.
11. No required JavaScript, online service or recipient installation.

## 19. Non-goals for the first iteration

- executing OntoBDC or InfoBIM inside the PDF;
- replacing the live InfoBIM interface;
- arbitrary user-defined queries inside the PDF;
- real-time synchronization after publication;
- collaborative task management in the PDF;
- universal support for every viewer feature;
- complete signing and trusted-timestamp infrastructure;
- embedding every source file by default;
- mandatory cloud publication;
- mandatory internal scheduling daemon.

## 20. Acceptance criteria

The feature is ready for an initial release when:

- a WorkStream can be published from a command without manual page assembly;
- the source remains authoritative and unchanged except for intentional publication records;
- output opens offline in Adobe Reader and a mainstream browser PDF viewer;
- table of contents, bookmarks and internal links work in supported viewers;
- a contractor publication excludes internal resources;
- a client databook produces a different selection from the same source WorkStream;
- the PDF identifies publication ID, source state, profile, audience and generation date;
- an external record stores the final PDF SHA-256;
- included items trace back to source identifiers;
- a scheduled non-interactive invocation generates revisioned output without prompts;
- failures return a non-zero exit code and intelligible log.

## 21. Testing strategy

### Unit tests

- profile validation;
- include/exclude rules;
- deterministic ordering of sections and items;
- publication ID and filename generation;
- template-model construction;
- safe handling of missing drawings, photos and documents;
- hotspot coordinate mapping;
- manifest and hash integration.

### Integration tests

- publish a sample WorkStream end to end;
- verify internal destinations, links and bookmarks;
- compare contractor and client selections;
- confirm excluded information is absent from extracted PDF text and metadata;
- validate source identifiers and publication-record linkage;
- run the command twice in scheduled mode;
- validate revision naming and overwrite behavior.

### Manual compatibility tests

- Adobe Acrobat Reader on Windows;
- browser PDF viewer on Windows;
- at least one mobile viewer;
- printing selected sections;
- operation without network access;
- opening a large drawing and navigating back to the related index.

## 22. Open decisions

- PDF rendering engine and dependencies;
- exact publication-profile schema or ontology;
- publication-record serialization: JSON-LD, Turtle, JSON or more than one;
- exact source-hash definition when external resources exist;
- attachment support in the initial release;
- QR-code destination strategy;
- digital-signature mechanism;
- handling of very large drawings and photo sets;
- publication revision and filename conventions;
- whether profiles live in the project container, InfoBIM package or both;
- target InfoBIM and OntoBDC release versions.

## 23. Initial implementation sequence

1. Define the shared publication-profile structure with OntoBDC.
2. Define publication record and provenance fields.
3. Implement executive-project and databook selectors.
4. Build the intermediate WorkStream publication model.
5. Select and validate the PDF rendering engine.
6. Implement baseline pages, links and bookmarks.
7. Implement drawing/plan hotspot navigation.
8. Add manifest and provenance pages.
9. Integrate final PDF hash registration through OntoBDC.
10. Add non-interactive CLI and scheduling behavior.
11. Validate both profiles against a real WorkStream and real external-delivery scenario.

## 24. Design statement

InfoBIM operates the live engineering WorkStream. OntoBDC preserves and executes the structured container. The navigable PDF is the controlled publication boundary: a familiar deliverable for contractor and client, a filtered disclosure of internal information, and a verifiable snapshot that can be regenerated or exported periodically without granting access to the underlying engineering environment.
