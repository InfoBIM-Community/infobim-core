class PyodideRuntimeCardAdapter:
    def render(self) -> str:
        return """
        <article class="view-panel" data-card="pyodide-runtime-card">
          <header class="view-panel-head">
            <h2 class="view-panel-title">Pyodide Runtime</h2>
            <p class="view-panel-copy">Bootstrap do ambiente Python no browser para as proximas etapas do dashboard.</p>
          </header>
          <div class="view-panel-body">
            <div class="runtime-status">
              <span class="runtime-dot" id="pyodide-status-dot"></span>
              <strong id="pyodide-status-label">Initializing Pyodide...</strong>
            </div>
            <pre class="runtime-console" id="pyodide-console">Waiting for runtime...</pre>
          </div>
        </article>
""".strip()
