from html import escape
from typing import Any, Dict


class HeroCardAdapter:
    def render(self, project: Dict[str, Any], page_description: str, asset_root: str) -> str:
        project_name: str = escape(str(project.get("name", "")).strip())
        project_id: str = escape(str(project.get("projectId", "")).strip())
        description: str = escape(page_description.strip()) if page_description.strip() else ""
        return f"""
      <article class="view-hero-card" data-card="hero-card">
        <div class="view-brand">
          <img class="view-brand-logo" src="{escape(asset_root)}/logo.png" alt="InfoBIM logo">
          <div class="view-brand-copy">
            <span class="view-eyebrow">InfoBIM Dashboard</span>
            <span class="view-eyebrow-meta">{project_id}</span>
          </div>
        </div>
        <h1>{project_name}</h1>
        {f"<p>{description}</p>" if description else ""}
      </article>
""".strip()
