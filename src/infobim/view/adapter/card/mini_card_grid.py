from typing import Iterable


class MiniCardGridCardAdapter:
    def render(self, items: Iterable[dict[str, str]] | None = None) -> str:
        mini_cards = list(items or [])
        if not mini_cards:
            mini_cards = [{"label": "-", "value": ""} for _ in range(6)]

        item_html: list[str] = []
        for item in mini_cards[:6]:
            label: str = str(item.get("label", "")).strip()
            value: str = str(item.get("value", "")).strip()
            item_html.append(
                f"""
        <div class="view-badge">
          <span class="view-badge-label">{label}</span>
          <span class="view-badge-value">{value}</span>
        </div>
""".rstrip()
            )

        return f"""
      <aside class="view-hero-meta" data-card="mini-card-grid">
{"".join(item_html)}
      </aside>
""".strip()
