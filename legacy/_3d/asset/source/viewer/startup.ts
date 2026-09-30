import { InspectControls } from "./inspect-controls";
import { TerminalPanel } from "./terminal";
import { IfcxFile } from "../ifcx-core/schema/schema-helper";
import {
    ViewerModels,
    activateAttributesTab,
    activateModelTab,
    activateProjectInspectTab,
    activateThreeDInspectTab,
    collapseTree,
    expandTree,
    renderProjectInspectTree,
    renderThreeDInspectTree,
    setDarkTheme,
    setProjectName,
} from "./render";
import { SceneGeometry, SceneSummary } from "./scene-geometry";

type ProjectBootstrap = {
    // The Project's IfcProject, exactly as ifc_project.ttl declares it,
    // serialized as JSON-LD in expanded form (one node object per
    // subject, full predicate URIs as keys) -- not a convenience shape
    // built for this page, so it stays correct if a future feature needs
    // more of it than just the name.
    ifcProject: unknown[] | null;
    language?: string | null;
    // The tree `infobim project --inspect` renders for this same Project,
    // shown in the Project inspect panel. Untyped here (and narrowed by
    // renderProjectInspectTree itself) for the same reason ifcProject is:
    // this page trusts its own shape, not a convenience projection of it.
    projectTree?: unknown | null;
    // The tree `infobim 3d --inspect` renders for this same Project,
    // shown in the 3D inspect panel. Each IFCX leaf also carries its own
    // parsed document (see ThreeDElementDiscovery.with_documents on the
    // Python side), so clicking it can load it into the scene without
    // this page ever needing to fetch anything.
    threeDElementTree?: unknown | null;
};

const IFC_PROJECT_NAME_PREDICATE: string =
    "https://standards.buildingsmart.org/IFC/DEV/IFC4_3/OWL#name_IfcRoot";

function ifcProjectName(ifcProject: unknown[] | null | undefined): string | null {
    if (!Array.isArray(ifcProject) || ifcProject.length !== 1) {
        return null;
    }
    const node: unknown = ifcProject[0];
    if (typeof node !== "object" || node === null) {
        return null;
    }
    const values: unknown = (node as Record<string, unknown>)[IFC_PROJECT_NAME_PREDICATE];
    if (!Array.isArray(values) || values.length === 0) {
        return null;
    }
    const first: unknown = values[0];
    if (typeof first !== "object" || first === null) {
        return null;
    }
    const value: unknown = (first as Record<string, unknown>)["@value"];
    return typeof value === "string" ? value : null;
}

class ProjectViewer {
    static async start(): Promise<void> {
        InspectControls.bind();
        const themeToggle: HTMLButtonElement = document.querySelector("#theme-toggle")!;
        themeToggle.addEventListener("click", (): void => {
            const dark: boolean = themeToggle.getAttribute("aria-pressed") !== "true";
            themeToggle.setAttribute("aria-pressed", String(dark));
            themeToggle.textContent = dark ? "Light theme" : "Dark theme";
            setDarkTheme(dark);
        });
        const collapseAll: HTMLButtonElement = document.querySelector("#tree-collapse-all")!;
        collapseAll.addEventListener("click", collapseTree);
        const expandAll: HTMLButtonElement = document.querySelector("#tree-expand-all")!;
        expandAll.addEventListener("click", expandTree);
        document.querySelectorAll<HTMLButtonElement>("[data-tree-tab]").forEach((tab): void => {
            tab.addEventListener("click", (): void => {
                if (tab.dataset.treeTab === "attributes") {
                    activateAttributesTab();
                } else {
                    activateModelTab();
                }
            });
        });
        document.querySelectorAll<HTMLButtonElement>("[data-inspect-tab]").forEach((tab): void => {
            tab.addEventListener("click", (): void => {
                if (tab.dataset.inspectTab === "three_d") {
                    activateThreeDInspectTab();
                } else {
                    activateProjectInspectTab();
                }
            });
        });

        const form: HTMLFormElement = document.querySelector("#fileForm")!;
        form.addEventListener("submit", (event: SubmitEvent): void => {
            event.preventDefault();
            ProjectViewer.openFiles().catch(ProjectViewer.fail);
        });
        const bootstrapElement: HTMLElement = document.getElementById("infobim-project")!;
        const bootstrap: ProjectBootstrap | null = JSON.parse(bootstrapElement.textContent!);
        TerminalPanel.start(bootstrap?.language ?? navigator.language);
        const projectName: string | null = ifcProjectName(bootstrap?.ifcProject);
        setProjectName(projectName);
        renderProjectInspectTree(bootstrap?.projectTree ?? null);
        renderThreeDInspectTree(bootstrap?.threeDElementTree ?? null);
        if (projectName !== null) {
            document.title = `${projectName} — InfoBIM 3D`;
            document.getElementById("project-title")!.textContent = projectName;
        }
        ProjectViewer.status("Open local IFCX files to view a model.");
    }

    private static async openFiles(): Promise<void> {
        const input: HTMLInputElement = document.querySelector("#fileInput")!;
        if (input.files === null || input.files.length === 0) {
            throw new Error("Choose at least one local IFCX file.");
        }
        const models: [string, IfcxFile][] = [];
        for (const file of Array.from(input.files)) {
            models.push([file.name, JSON.parse(await file.text())]);
        }
        const summary: SceneSummary = await ViewerModels.add(models);
        ProjectViewer.status(SceneGeometry.describe(summary));
    }

    private static status(message: string): void {
        document.getElementById("status")!.textContent = message;
    }

    static fail(error: unknown): void {
        const message: string = error instanceof Error ? error.message : String(error);
        document.querySelector<HTMLElement>(".error-modal .message")!.textContent = message;
        document.querySelector<HTMLElement>(".error-modal")!.style.display = "block";
        ProjectViewer.status("Project could not be loaded.");
        console.error(error);
    }
}

ProjectViewer.start().catch(ProjectViewer.fail);
