from html import escape
from typing import Any, Dict


class ProjectInformationCardAdapter:
    def render(self, project: Dict[str, Any], caption: str) -> str:
        project_name: str = escape(str(project.get("name", "")).strip())
        project_path: str = escape(str(project.get("path", "")).strip())
        caption_html: str = escape(caption.strip())
        return f"""
        <article class="view-panel" data-card="project-information-card">
          <header class="view-panel-head">
            <h2 class="view-panel-title">Project Information</h2>
            <p class="view-panel-copy"><span class="view-panel-copy-diamond">◆</span>{caption_html}</p>
          </header>
          <div class="view-panel-body">
            <dl class="metadata-list">
              <div class="metadata-row">
                <dt>Name</dt>
                <dd>{project_name}</dd>
              </div>
              <div class="metadata-row">
                <dt>Path</dt>
                <dd>{project_path}</dd>
              </div>
            </dl>
          </div>
        </article>
""".strip()
