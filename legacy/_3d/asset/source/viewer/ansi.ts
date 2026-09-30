// Render CLI output the way a real terminal would: apply the same SGR
// (truecolor) escape codes the CLI already emits for its own colored
// panels, instead of stripping them down to plain text.

type AnsiStyle = {
    foreground?: string;
    background?: string;
    bold?: boolean;
};

const SGR_PATTERN: RegExp = /\[([0-9;]*)m/g;

export class AnsiRenderer {
    private style: AnsiStyle = {};
    // an SGR sequence split across two SSE messages (the escape starts in
    // one chunk and its 'm' terminator arrives in the next) is held here
    // instead of being flushed as literal, broken escape text.
    private pending: string = "";

    write(output: HTMLElement, chunk: string): void {
        const text: string = this.pending + chunk;
        this.pending = "";
        const incomplete: number = text.lastIndexOf("");
        const usable: string = incomplete === -1 || text.indexOf("m", incomplete) !== -1
            ? text
            : text.slice(0, incomplete);
        if (usable !== text) {
            this.pending = text.slice(usable.length);
        }

        SGR_PATTERN.lastIndex = 0;
        let lastIndex: number = 0;
        let match: RegExpExecArray | null;
        while ((match = SGR_PATTERN.exec(usable)) !== null) {
            this.appendSegment(output, usable.slice(lastIndex, match.index));
            this.applyCodes(match[1]);
            lastIndex = SGR_PATTERN.lastIndex;
        }
        this.appendSegment(output, usable.slice(lastIndex));
    }

    private appendSegment(output: HTMLElement, segment: string): void {
        if (segment === "") {
            return;
        }
        if (!this.style.foreground && !this.style.background && !this.style.bold) {
            output.appendChild(document.createTextNode(segment));
            return;
        }
        const span: HTMLSpanElement = document.createElement("span");
        if (this.style.foreground) {
            span.style.color = this.style.foreground;
        }
        if (this.style.background) {
            span.style.backgroundColor = this.style.background;
        }
        if (this.style.bold) {
            span.style.fontWeight = "bold";
        }
        span.appendChild(document.createTextNode(segment));
        output.appendChild(span);
    }

    private static readonly PALETTE_3BIT: string[] = [
        "rgb(0,0,0)",
        "rgb(205,0,0)",
        "rgb(0,205,0)",
        "rgb(205,205,0)",
        "rgb(0,0,238)",
        "rgb(205,0,205)",
        "rgb(0,205,205)",
        "rgb(229,229,229)",
    ];

    private static readonly PALETTE_BRIGHT: string[] = [
        "rgb(127,127,127)",
        "rgb(255,0,0)",
        "rgb(0,255,0)",
        "rgb(255,255,0)",
        "rgb(92,92,255)",
        "rgb(255,0,255)",
        "rgb(0,255,255)",
        "rgb(255,255,255)",
    ];

    private applyCodes(raw: string): void {
        const codes: number[] = raw.split(";").filter((code) => code !== "").map(Number);
        if (codes.length === 0) {
            codes.push(0);
        }
        for (let index: number = 0; index < codes.length; index++) {
            const code: number = codes[index];
            if (code === 0) {
                this.style = {};
            } else if (code === 1) {
                this.style.bold = true;
            } else if (code === 22) {
                this.style.bold = false;
            } else if (code === 39) {
                delete this.style.foreground;
            } else if (code === 49) {
                delete this.style.background;
            } else if (code >= 30 && code <= 37) {
                this.style.foreground = AnsiRenderer.PALETTE_3BIT[code - 30];
            } else if (code >= 40 && code <= 47) {
                this.style.background = AnsiRenderer.PALETTE_3BIT[code - 40];
            } else if (code >= 90 && code <= 97) {
                this.style.foreground = AnsiRenderer.PALETTE_BRIGHT[code - 90];
            } else if (code >= 100 && code <= 107) {
                this.style.background = AnsiRenderer.PALETTE_BRIGHT[code - 100];
            } else if (code === 38 && codes[index + 1] === 2) {
                this.style.foreground = `rgb(${codes[index + 2]}, ${codes[index + 3]}, ${codes[index + 4]})`;
                index += 4;
            } else if (code === 48 && codes[index + 1] === 2) {
                this.style.background = `rgb(${codes[index + 2]}, ${codes[index + 3]}, ${codes[index + 4]})`;
                index += 4;
            }
        }
    }
}
