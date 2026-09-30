export class InspectControls {
    static bind(): void {
        const tree: HTMLElement | null = document.querySelector(".inspect-tree");
        const collapse: HTMLButtonElement | null = document.querySelector("#inspect-collapse-all");
        const expand: HTMLButtonElement | null = document.querySelector("#inspect-expand-all");
        if (tree === null || collapse === null || expand === null) {
            throw new Error("Project inspect tree controls are missing.");
        }
        collapse.addEventListener("click", (): void => InspectControls.setCollapsed(tree, true));
        expand.addEventListener("click", (): void => InspectControls.setCollapsed(tree, false));
    }

    private static setCollapsed(tree: HTMLElement, collapsed: boolean): void {
        tree.querySelectorAll<HTMLElement>(".tree-children").forEach((node: HTMLElement): void => {
            node.hidden = collapsed;
        });
        tree.querySelectorAll<HTMLElement>(".tree-toggle:not(.tree-toggle-empty)").forEach((toggle: HTMLElement): void => {
            toggle.textContent = collapsed ? "▸" : "▾";
        });
    }
}
