import { AnsiRenderer } from "./ansi";
import { TerminalI18n, TerminalMessages } from "./terminal-i18n";

// Plain module constants, not class fields: esbuild's lowering of a
// private static class field on a class whose own static method builds
// an instance of itself (TerminalPanel.start() -> new TerminalPanel(...))
// emits a self-reference to the class's internal name outside the scope
// where that name is valid, which throws "_TerminalPanel is not defined"
// on load and takes down every listener this script would otherwise wire
// up. Module-level constants need no such lowering.
// The 16-color ANSI yellows (dim 33, bright 93) are both a colder,
// purer yellow than the ⚠️ glyph itself renders in an emoji font (a
// warm gold/amber) -- truecolor names the exact shade instead of the
// nearest of 16 fixed options, so the text reads as the same color as
// the icon beside it rather than a mismatched near-yellow.
const YELLOW_FG: string = "\x1b[1;38;2;255;204;77m";
const RED_FG: string = "\x1b[31m";
const RESET: string = "\x1b[0m";
const WARN_ICON: string = "\u26a0\ufe0f ";
const ERROR_ICON: string = "\u274c ";

const STATUS_CLASSES: readonly string[] = [
    "terminal-status-connecting",
    "terminal-status-connected",
    "terminal-status-offline",
];

export class TerminalPanel {
    private token: string | null = null;
    private busy: boolean = false;
    private readonly stream: EventSource;
    private readonly errorBox: HTMLElement;
    private readonly status: HTMLElement;
    private readonly output: HTMLElement;
    private readonly screen: HTMLElement;
    private readonly ansi: AnsiRenderer = new AnsiRenderer();

    constructor(root: HTMLElement, language: string) {
        const endpoint: string | undefined = root.dataset.eventsUrl;
        const errorBox: HTMLElement | null = root.querySelector(".terminal-error");
        const status: HTMLElement | null = root.querySelector(".terminal-status");
        const output: HTMLElement | null = root.querySelector(".terminal-output");
        const screen: HTMLElement | null = root.querySelector(".terminal-screen");
        if (!endpoint || !errorBox || !status || !output || !screen) {
            throw new Error("Terminal connection configuration or markup is missing.");
        }
        const messages: TerminalMessages = TerminalI18n.messages(language);
        root.lang = language.replace(/_/g, "-");
        root.querySelector<HTMLElement>(".terminal-error-title")!.textContent = messages.error;
        root.querySelector<HTMLElement>(".terminal-unavailable")!.textContent = messages.unavailable;
        root.querySelector<HTMLElement>(".terminal-instruction")!.textContent = messages.instruction;
        output.setAttribute("aria-label", messages.output);
        this.errorBox = errorBox;
        this.status = status;
        this.output = output;
        this.screen = screen;
        this._setStatus(messages.connecting, "connecting");
        const input: HTMLInputElement | null = root.querySelector(".terminal-input");
        if (input === null) {
            throw new Error("Terminal command input is missing.");
        }
        input.setAttribute("aria-label", messages.command);
        document.addEventListener("infobim:element-requested", (event: Event): void => {
            if (!(event instanceof CustomEvent)) {
                return;
            }
            const globalId: unknown = event.detail.globalId;
            if (typeof globalId !== "string" || !/^[A-Za-z0-9_$-]+$/.test(globalId)) {
                this._writeWarningToOutput(messages.missingId);
                return;
            }
            input.value = `--element ${globalId}`;
            if (!this.screen.hidden) {
                input.focus();
                input.setSelectionRange(input.value.length, input.value.length);
            }
        });
        document.addEventListener("infobim:point-picked", (event: Event): void => {
            if (!(event instanceof CustomEvent)) {
                return;
            }
            const point: string | null = TerminalPanel._coordinates(event.detail);
            if (point === null) {
                this._writeWarningToOutput(messages.missingPoint);
                return;
            }
            // The command being typed is kept: a point is picked to tell a
            // command where, and a command that lost its own arguments to
            // the answer would have to be typed again. Coordinates already
            // there are replaced, because the last place clicked is the
            // place meant.
            input.value = TerminalPanel._withPoint(input.value, point);
            if (!this.screen.hidden) {
                input.focus();
                input.setSelectionRange(input.value.length, input.value.length);
            }
        });
        root.addEventListener("click", (event: MouseEvent): void => {
            if (this.screen.hidden || !(event.target instanceof Element)) {
                return;
            }
            if (event.target.closest(".terminal-output")) {
                return;
            }
            input.focus();
        });
        input.addEventListener("keydown", (event: KeyboardEvent): void => {
            if (event.key !== "Enter" || event.isComposing) {
                return;
            }
            event.preventDefault();
            const command: string = input.value;
            if (this.busy || this.token === null || !command.trim()) {
                return;
            }
            this.busy = true;
            input.readOnly = true;
            this.output.append(document.createTextNode(`>_ ${command}\n`));
            fetch(new URL("/command", endpoint), {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${this.token}` },
                body: JSON.stringify({ command }),
            }).then(async (response: Response): Promise<void> => {
                if (!response.ok) {
                    throw new Error(`${messages.commandFailed} (HTTP ${response.status})`);
                }
                input.value = "";
            }).catch((error: unknown): void => {
                this._writeErrorToOutput(`${messages.commandFailed}: ${String(error)}`);
                this.busy = false;
                input.readOnly = false;
            });
        });
        this.stream = new EventSource(endpoint);
        this.stream.addEventListener("session", (event: MessageEvent<string>): void => {
            this.token = event.data;
        });
        this.stream.addEventListener("complete", (event: MessageEvent<string>): void => {
            this.busy = false;
            input.readOnly = false;
            if (event.data !== "0") {
                this.output.append(document.createTextNode(`${messages.exitCode}: ${event.data}\n`));
            }
            input.focus();
        });
        this.stream.onopen = (): void => {
            this.errorBox.hidden = true;
            this.screen.hidden = false;
            this._setStatus(messages.connected, "connected");
            if (document.activeElement === document.body || root.contains(document.activeElement)) {
                input.focus();
            }
        };
        this.stream.onerror = (): void => {
            this.token = null;
            this.busy = false;
            input.readOnly = false;
            this.errorBox.hidden = false;
            this.screen.hidden = true;
            this._setStatus(messages.reconnecting, "offline");
        };
        this.stream.onmessage = (event: MessageEvent<string>): void => {
            const text: unknown = JSON.parse(event.data);
            if (typeof text !== "string") {
                throw new Error("Invalid terminal output event");
            }
            this.ansi.write(this.output, text);
            while (this.output.childNodes.length > 1000) {
                this.output.firstChild!.remove();
            }
            this.output.scrollTop = this.output.scrollHeight;
        };
        window.addEventListener("pagehide", (): void => this.stream.close(), { once: true });
    }

    private _setStatus(text: string, state: "connecting" | "connected" | "offline"): void {
        this.status.textContent = text;
        this.status.classList.remove(...STATUS_CLASSES);
        this.status.classList.add(`terminal-status-${state}`);
    }

    // Warnings and errors that are not a command's own output (a
    // double-clicked element with no GlobalId, a failed request) are
    // appended to the same output history as everything else, in the
    // order they actually happened -- not pinned in a separate status
    // line above the scrollback, where they would sit out of sequence
    // with the commands run before and after them.
    private _writeWarningToOutput(message: string): void {
        const chunk: string = (
            YELLOW_FG +
            WARN_ICON +
            "WARNING" +
            RESET +
            " " +
            message +
            "\n"
        );
        this.ansi.write(this.output, chunk);
        this.output.scrollTop = this.output.scrollHeight;
    }

    private _writeErrorToOutput(message: string): void {
        const chunk: string = (
            RED_FG +
            ERROR_ICON +
            "ERROR" +
            RESET +
            " " +
            message +
            "\n"
        );
        this.ansi.write(this.output, chunk);
        this.output.scrollTop = this.output.scrollHeight;
    }

    // A point is written with millimetre resolution and no trailing
    // zeros: the model is measured in its own unit, and a picked point
    // is worth as much precision as a person can aim at, not as much as
    // a float carries.
    private static _coordinates(detail: unknown): string | null {
        if (detail === null || typeof detail !== "object") {
            return null;
        }

        const axes: string[] = [];
        for (const axis of ["x", "y", "z"]) {
            const value: unknown = (detail as Record<string, unknown>)[axis];
            if (typeof value !== "number" || !Number.isFinite(value)) {
                return null;
            }
            axes.push(`--${axis} ${String(Number(value.toFixed(3)))}`);
        }

        return axes.join(" ");
    }

    private static _withPoint(command: string, point: string): string {
        const kept: string = command
            .replace(/\s*--[xyz]\s+-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?/g, "")
            .trim();

        return kept === "" ? point : `${kept} ${point}`;
    }

    static start(language: string): void {
        const root: HTMLElement | null = document.querySelector(".terminal");
        if (root === null) {
            throw new Error("Terminal panel is missing.");
        }
        new TerminalPanel(root, language);
    }
}
