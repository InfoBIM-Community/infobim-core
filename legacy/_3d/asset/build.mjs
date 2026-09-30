import { fileURLToPath } from "node:url";
import { readFile, writeFile } from "node:fs/promises";

import { build } from "esbuild";

class OfflineViewerBuild {
    static async run() {
        const root = new URL("./", import.meta.url);
        const result = await build({
            absWorkingDir: fileURLToPath(root),
            entryPoints: ["source/viewer/startup.ts"],
            bundle: true,
            platform: "browser",
            format: "iife",
            write: false,
            legalComments: "inline",
        });
        const template = await readFile(new URL("source/index.html", root), "utf8");
        const marker = "<!-- INFOBIM_VIEWER_SCRIPT -->";
        if (template.split(marker).length !== 2 || result.outputFiles.length !== 1) {
            throw new Error("Expected one viewer script marker and one bundle.");
        }
        const script = result.outputFiles[0].text.replace(/<\/script/gi, "<\\/script");
        const html = template.replace(marker, () => `<script>\n${script}\n</script>`);
        if (/<(?:script|link)[^>]+(?:src|href)=["']https?:/i.test(html)) {
            throw new Error("The offline viewer still references remote assets.");
        }
        const output = new URL("ifcx-viewer-offline.html", root);
        await writeFile(output, html, "utf8");
        console.log(`Built ${fileURLToPath(output)}`);
    }
}

await OfflineViewerBuild.run();
