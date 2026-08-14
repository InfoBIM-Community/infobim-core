import os
import datetime
from typing import Optional, Dict, Any


class NarrativeMarkdownRepositoryAdapter:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or "data/outgoing"

    def save_block(self, slug: str, content: str) -> str:
        os.makedirs(self.base_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_slug = slug.replace(" ", "_").lower()
        path = os.path.join(self.base_dir, f"{ts}_{safe_slug}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def render_and_save(self, template_path: str, context: Dict[str, Any], slug: str) -> str:
        from jinja2 import Environment, FileSystemLoader
        base_dir = os.path.dirname(template_path)
        template_name = os.path.basename(template_path)
        env = Environment(
            loader=FileSystemLoader(base_dir),
            autoescape=False,
        )
        tpl = env.get_template(template_name)
        content = tpl.render(**context)
        return self.save_block(slug, content)
