from html import escape
from typing import Any, Dict, Iterable


class DynamicMenubarCardAdapter:
    def render(self, project: Dict[str, Any], items: Iterable[Dict[str, Any]] | None = None) -> str:
        menu_items = list(items or [])
        if not menu_items:
            menu_items = [{"label": "", "value": ""}]

        item_html: list[str] = []
        for item in menu_items:
            label: str = escape(str(item.get("label", "")).strip())
            value: str = escape(str(item.get("value", "")).strip())
            item_html.append(
                f"""
          <div class="menubar-item">
            <span class="menubar-item-label">{label}</span>
            <span class="menubar-item-value">{value}</span>
          </div>
""".rstrip()
            )

        return f"""
      <article class="view-menubar-card" data-card="dynamic-menubar-card">
        <div class="view-menubar-track">
{"".join(item_html)}
        </div>
      </article>
""".strip()
