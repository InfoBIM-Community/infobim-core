(async function () {
  const statusDot = document.getElementById("pyodide-status-dot");
  const statusLabel = document.getElementById("pyodide-status-label");
  const consoleElement = document.getElementById("pyodide-console");
  const projectPayload = window.infoBimProjectDashboard || {};

  function writeStatus(message, cssClass) {
    if (statusLabel) {
      statusLabel.textContent = message;
    }
    if (statusDot) {
      statusDot.classList.remove("is-ready", "is-error");
      if (cssClass) {
        statusDot.classList.add(cssClass);
      }
    }
  }

  function writeConsole(message) {
    if (consoleElement) {
      consoleElement.textContent = message;
    }
  }

  writeStatus("Loading Pyodide runtime...", "");
  writeConsole("Preparing browser Python runtime...");

  if (typeof loadPyodide !== "function") {
    writeStatus("Pyodide loader unavailable", "is-error");
    writeConsole(
      [
        "The page loaded, but the Pyodide loader was not found.",
        "Check internet connectivity or host the Pyodide distribution locally.",
      ].join("\n"),
    );
    return;
  }

  try {
    const pyodide = await loadPyodide();
    pyodide.globals.set("project_payload_json", JSON.stringify(projectPayload));
    const runtimeReport = await pyodide.runPythonAsync(`
import json
import platform

payload = json.loads(project_payload_json)
lines = [
    f"Python runtime: {platform.python_version()}",
    f"Project ID: {payload.get('projectId', '')}",
    f"Name: {payload.get('name', '')}",
    f"Path: {payload.get('path', '')}",
]
"\\n".join(lines)
`);

    writeStatus("Pyodide runtime ready", "is-ready");
    writeConsole(String(runtimeReport));
  } catch (error) {
    writeStatus("Pyodide initialization failed", "is-error");
    writeConsole(String(error));
  }
}());
