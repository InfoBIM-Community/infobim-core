# Implement IfcWorkSchedule Gantt HTML — Sprint 007

Implement the complete `IfcWorkSchedule` Gantt HTML feature in `EliasMPJunior/infobim-wip`.

Start from branch `s007/v0.8` and create a dedicated implementation branch for this feature. Do not implement directly on `s007/v0.8`.

The objective is to give `IfcWorkSchedule` its own standalone/static/offline HTML presentation, using Gantt as a project-management framework applied to the schedule. The implementation must follow the architectural precedent already established by WorkStream and 5W2H: the underlying entity remains independent from the project-management framework used to organize/present it.

Do not invent a new schedule model. Use the existing semantic model and facades.

The canonical ontology source is `Brasidata/brasidatacenter`. For the new Gantt framework semantics, use branch `feat/gantt-framework` as the current reference. That branch contains `ontology/infobim/domain/gantt.ttl`, where `ibim:Gantt` is an `owl:Class` and `rdfs:subClassOf obdc:ProjectManagementFramework`, with identifier `gantt`. It also generalizes `obdc:usesProjectManagementFramework` so the property applies to the OWL union of `ws:WorkStream` and `ibim:IfcWorkSchedule`. This is intentionally the same generic relationship already used by WorkStream. Do not create `usesGantt`, `hasGantt`, or another parallel property.

The semantic pattern to preserve is:

`WorkStream -> obdc:usesProjectManagementFramework -> FiveWTwoH`

and equivalently:

`IfcWorkSchedule -> obdc:usesProjectManagementFramework -> Gantt`

The property remains non-functional so future frameworks such as Kanban can coexist without redefining `IfcWorkSchedule`.

The BrasiDataCenter already defines the schedule-control model. Reuse it; do not mint a second dimension taxonomy. Existing concepts include `ibim:WorkScheduleDimension`, `ibim:WorkScheduleDimensionKind`, `ibim:WorkScheduleAspect`, and `ibim:WorkScheduleState`. Existing aspects include Scope, Time, Progress, Labor, Equipment, Material, and Cost. Existing states include Planned, Actual, and Forecast. Existing kinds combine these concepts, such as TimePlanned, TimeActual, TimeForecast, ProgressPlanned, ProgressActual, ProgressForecast, CostPlanned, CostActual, CostForecast, etc.

The schedule is also already connected to WorkStream through `ibim:schedulesDimension` / `ibim:scheduledBy`, intended to connect an `IfcWorkSchedule` to the `When` dimension of a WorkStream. Preserve this semantic relationship; do not replace it with a presentation-specific shortcut.

Use the existing IFC/InfoBIM facades as the source of presentation data. The schedule-level facade exposes metadata such as GlobalId, Name, Description, ObjectType, Identification, CreationDate, Creators, Purpose, Duration, TotalFloat, StartTime, FinishTime, and PredefinedType. Task data is represented through `IfcTask`; task-time data through `IfcTaskTime`; predecessor/successor relationships through `IfcRelSequence` facades. The existing tabular schedule facade already projects Work Breakdown Structure / Identification and task Name to `IfcTask`, and exposes schedule duration/start/finish, planned progress, executed progress, deviation, and completion for `IfcTaskTime`. The broader InfoBIM view ontology already includes task status, work method, milestone flag, priority, early/late dates, free/total float, critical flag, actual duration/start/finish, remaining time, and completion. Reuse what is already available before adding anything new.

The Gantt renderer must produce a view visually and behaviorally familiar to engineers who use Microsoft Project. Do not produce a dashboard/card layout. Do not attempt a pixel-perfect clone and do not copy proprietary Microsoft assets, but use the conventional Microsoft Project-style visual grammar so an engineer understands the screen immediately.

The first version must include a left-side task table/tree aligned row-for-row with a right-side time grid. At minimum show WBS/Identification, task name, schedule start, schedule finish, schedule duration, and completion/progress when available. Render milestones when applicable. On the right, render a readable timeline/calendar header and grid, with horizontal task bars positioned according to `ScheduleStart` and `ScheduleFinish` and aligned exactly with the corresponding task rows.

Dependency arrows are mandatory in this implementation. Use the existing `IfcRelSequence` predecessor/successor relationships to draw visible directional arrows between the relevant task bars or milestones. Do not satisfy this requirement by merely showing predecessor/successor IDs in a table column. The arrows must be visibly drawn on the Gantt timeline, show direction, and connect the related activities. Common finish-to-start sequencing must be visually clear. Preserve richer sequence semantics if the existing IFC data/model provides them and they can be supported without inventing semantics that are not present.

Treat the IFC Worksheet as the editable working representation and point of alteration. The generated Gantt must consume the current schedule/context/worksheet state. If a user edits schedule values in the worksheet, regenerating the presentation must reflect those edits. Do not create or maintain an independent competing copy of schedule data. Do not silently overwrite worksheet edits during rendering or regeneration.

The generated page must be a standalone/static/offline-capable InfoBIM Surface consistent with the existing OntoBDC/InfoBIM local HTML philosophy.

Study the existing WorkStream/5W2H presentation implementation in OntoBDC/InfoBIM and reuse its architectural pattern where applicable, especially the existing transformation/state-machine approach used to assemble WorkStream-specific scripts and presentations. Do not introduce an unrelated monolithic Gantt pipeline if the current plugin/capability architecture already provides the appropriate extension points. Follow current capability, adapter, component, statechart, logging, metadata, packaging, and testing conventions in the repositories rather than copying old v0.4 code blindly.

The old InfoBIM timetable implementation may be used as historical evidence for behavior and mappings, especially its specific `IfcWorkSchedule` tabular strategy and the older schedule extraction/transformation flow, but the implementation must be adapted to the current architecture.

Implement this feature end-to-end. Add or update the necessary ontology integration, strategy/framework discovery, adapters/capabilities, HTML/template/script/component assets, and tests required by the current architecture. Keep Gantt-specific behavior in the Gantt framework/presentation layer rather than hard-coding it into the base `IfcWorkSchedule` semantic contract.

Acceptance is end-to-end, not only unit-level. Demonstrate at least one schedule instance using Gantt that generates the HTML successfully. Verify that task bars align with dates, milestones appear when present, progress/completion appears when present, and predecessor/successor relationships render as visible arrows. Verify that changing schedule data through the worksheet/current context and regenerating the HTML changes the rendered Gantt. Verify the resulting HTML works standalone/offline under the InfoBIM Surface model.

The architecture must remain extensible: a future Kanban framework should be addable as another `ProjectManagementFramework` for the same `IfcWorkSchedule`, without redefining the schedule entity, duplicating its data, or rewriting the Gantt implementation into the base schedule model.

When finished, report the exact branch used, files changed, tests executed and results, and the concrete end-to-end command/path used to generate and inspect the Gantt HTML. Do not claim completion unless the generated result and dependency arrows were actually verified.
