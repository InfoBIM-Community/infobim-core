import json
from io import StringIO
import re
import shutil
import textwrap
from typing import Any, Dict, List, Optional, Type

from ontobdc.cli.domain.port.machine import CliInitProcessStatePort
from rich.console import Console
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from infobim.cli.adapter.logo import LogoRenderAdapter
from infobim.cli.domain.port.response import ResponseAnsiInformationAdapterPort
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
    HelpCommandResponse,
    ListCommandResponse,
    WelcomeCommandResponse,
)
from ontobdc.view.adapter.response import ExceptionCommandResponseMessageBoxAdapter
from ontobdc.view.plugin.render.rich.layout import RichMessageBoxLayout


class BaseResponseAnsiInformationAdapter(ResponseAnsiInformationAdapterPort):
    response_type: Type[CommandResponse] = CommandResponse
    _MARKDOWN_HORIZONTAL_MARGIN: int = 4

    def __init__(
        self,
        logo_adapter: LogoRenderAdapter | None = None,
    ) -> None:
        self._logo_adapter = logo_adapter or LogoRenderAdapter()

    def accepts(self, response: CommandResponse) -> bool:
        return isinstance(response, self.response_type)

    def render(self, response: CommandResponse) -> str:
        logo_content: str = self._logo_adapter.render()
        markdown_content: str = self._render_markdown(self._markdown_content(response))
        if not markdown_content:
            return logo_content

        return f"{logo_content}\n\n{markdown_content}"

    def _markdown_content(self, response: CommandResponse) -> str:
        sections: List[str] = []
        title: str = str(getattr(response, "title", "")).strip()
        description: str = str(getattr(response, "description", "")).strip()

        if title:
            sections.append(f"# {title}")

        if description:
            sections.append(description)

        sections.append("## Content")
        sections.append(
            "```json\n"
            f"{self._serialize_content_as_json(getattr(response, 'content', {}))}\n"
            "```"
        )

        return "\n\n".join(section for section in sections if section)

    def _render_markdown(self, content: str) -> str:
        available_width: int = max(
            self._console_width() - (self._MARKDOWN_HORIZONTAL_MARGIN * 2),
            20,
        )
        indentation: str = " " * self._MARKDOWN_HORIZONTAL_MARGIN
        rendered_lines: List[str] = []
        paragraph_buffer: List[str] = []
        code_block_lines: List[str] = []
        inside_code_block: bool = False

        def flush_paragraph() -> None:
            if not paragraph_buffer:
                return

            normalized_paragraph: str = " ".join(
                line.strip() for line in paragraph_buffer
            ).strip()
            paragraph_buffer.clear()
            if not normalized_paragraph:
                return

            heading_match = re.match(r"^(#{1,6})\s+(.*)$", normalized_paragraph)
            if heading_match:
                rendered_lines.append(
                    f"{indentation}{self._normalize_inline_markdown(heading_match.group(2).strip())}"
                )
                return

            normalized_paragraph = self._normalize_inline_markdown(normalized_paragraph)
            wrapped_lines: List[str] = textwrap.wrap(
                normalized_paragraph,
                width=available_width,
                break_long_words=False,
                break_on_hyphens=False,
            )
            rendered_lines.extend(f"{indentation}{line}" for line in wrapped_lines)

        def flush_code_block() -> None:
            if not code_block_lines:
                return

            rendered_lines.append(f"{indentation}```json")
            rendered_lines.extend(f"{indentation}{line}" for line in code_block_lines)
            rendered_lines.append(f"{indentation}```")
            code_block_lines.clear()

        raw_line: str
        for raw_line in content.splitlines():
            stripped_line: str = raw_line.strip()

            if stripped_line.startswith("```"):
                flush_paragraph()
                if inside_code_block:
                    flush_code_block()
                    inside_code_block = False
                else:
                    inside_code_block = True
                continue

            if inside_code_block:
                code_block_lines.append(raw_line.rstrip())
                continue

            if not stripped_line:
                flush_paragraph()
                if rendered_lines and rendered_lines[-1] != "":
                    rendered_lines.append("")
                continue

            paragraph_buffer.append(raw_line)

        flush_paragraph()
        if inside_code_block:
            flush_code_block()

        return "\n".join(rendered_lines).rstrip()

    def _serialize_content_as_json(self, content: Any) -> str:
        serialized_content: Any = self._serialize_json_value(content)
        return json.dumps(
            serialized_content,
            indent=2,
            ensure_ascii=False,
        )

    def _serialize_json_value(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, dict):
            return {
                str(key): self._serialize_json_value(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [self._serialize_json_value(item) for item in value]

        if hasattr(value, "to_dict") and callable(value.to_dict):
            return self._serialize_json_value(value.to_dict())

        return str(value)

    def _console_width(self) -> int:
        return shutil.get_terminal_size(fallback=(120, 40)).columns

    def _normalize_inline_markdown(self, content: str) -> str:
        normalized_content: str = re.sub(r"\*\*(.*?)\*\*", r"\1", content)
        normalized_content = re.sub(r"`([^`]+)`", r"\1", normalized_content)
        return normalized_content.strip()


class LogoResponseAnsiInformationAdapter(BaseResponseAnsiInformationAdapter):
    response_type: Type[CommandResponse] = CommandResponse


class ExceptionResponseAnsiInformationAdapter(
    ExceptionCommandResponseMessageBoxAdapter,
    ResponseAnsiInformationAdapterPort,
):
    def render(self, response: CommandResponse) -> str:
        return super().render(response, RichMessageBoxLayout())


class HelpResponseAnsiInformationAdapter(BaseResponseAnsiInformationAdapter):
    response_type: Type[CommandResponse] = HelpCommandResponse


class ListResponseAnsiInformationAdapter(BaseResponseAnsiInformationAdapter):
    response_type: Type[CommandResponse] = ListCommandResponse

    def render(self, response: CommandResponse) -> str:
        content: Any = getattr(response, "content", [])
        rows: List[Dict[str, str]] = self._extract_label_value_rows(content)
        items: List[Dict[str, Any]] = self._extract_list_items(content)
        if not rows and not self._is_project_card_list(items):
            return super().render(response)

        logo_content: str = self._logo_adapter.render()
        markdown_content: str = self._render_markdown(self._list_intro_markdown(response))
        table_content: str = self._render_project_table_from_rows(rows)
        if not table_content:
            table_content = self._render_project_table(items)

        sections: List[str] = [logo_content]
        if markdown_content:
            sections.append(markdown_content)
        if table_content:
            sections.append(table_content)

        return "\n\n".join(section for section in sections if section)

    def _extract_list_items(self, content: Any) -> List[Dict[str, Any]]:
        if isinstance(content, list):
            return [item for item in content if isinstance(item, dict)]

        if isinstance(content, dict):
            for key in ("projects", "items", "containers"):
                candidate: Any = content.get(key)
                if isinstance(candidate, list):
                    return [item for item in candidate if isinstance(item, dict)]

        return []

    def _extract_label_value_rows(self, content: Any) -> List[Dict[str, str]]:
        if not isinstance(content, dict):
            return []

        rows_candidate: Any = content.get("rows")
        if not isinstance(rows_candidate, list):
            return []

        rows: List[Dict[str, str]] = []
        row: Any
        for row in rows_candidate:
            if not isinstance(row, dict):
                continue

            label: str = str(row.get("label", "")).strip()
            value: str = str(row.get("value", "")).strip()
            if not label:
                continue

            rows.append({"label": label, "value": value})

        return rows

    def _is_project_card_list(self, items: List[Dict[str, Any]]) -> bool:
        if not items:
            return True

        return all(
            isinstance(item.get("name"), str) and isinstance(item.get("path"), str)
            for item in items
        )

    def _list_intro_markdown(self, response: CommandResponse) -> str:
        sections: List[str] = []
        title: str = str(getattr(response, "title", "")).strip()
        description: str = str(getattr(response, "description", "")).strip()

        if title:
            sections.append(f"# {title}")

        if description:
            sections.append(description)

        return "\n\n".join(section for section in sections if section)

    def _render_project_table(self, items: List[Dict[str, Any]]) -> str:
        if not items:
            return self._render_markdown("No active projects found.")

        rows: List[Dict[str, str]] = []
        item: Dict[str, Any]
        for index, item in enumerate(items):
            project_id: str = str(item.get("project_id", "")).strip()
            name: str = str(item.get("name", "")).strip()
            path: str = str(item.get("path", "")).strip()
            if project_id:
                rows.append({"label": "Project ID", "value": project_id})
            rows.append({"label": "Name", "value": name})
            rows.append({"label": "Path", "value": path})
            if index < len(items) - 1:
                rows.append({"label": "", "value": ""})

        return self._render_project_table_from_rows(rows)

    def _render_project_table_from_rows(self, rows: List[Dict[str, str]]) -> str:
        if not rows:
            return ""

        label_style: str = self._rgb_to_hex(self._logo_adapter.bim_rgb())
        buffer: StringIO = StringIO()
        console: Console = Console(
            file=buffer,
            force_terminal=True,
            color_system="truecolor",
            width=self._console_width(),
            soft_wrap=True,
            legacy_windows=False,
        )
        table: Table = Table.grid(padding=(0, 2))
        table.add_column(style=label_style, no_wrap=True)
        table.add_column(no_wrap=False, overflow="fold")

        row: Dict[str, str]
        for row in rows:
            label: str = str(row.get("label", "")).strip()
            value: str = str(row.get("value", "")).strip()
            if not label and not value:
                table.add_row(Text(""), Text(""))
                continue

            table.add_row(
                Text(label, style=label_style),
                Text(value, no_wrap=False, overflow="fold"),
            )

        console.print(Padding(table, (0, self._MARKDOWN_HORIZONTAL_MARGIN)))
        return "\n".join(line.rstrip() for line in buffer.getvalue().splitlines()).rstrip()

    def _rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


class MarkdownResponseAnsiInformationAdapter(BaseResponseAnsiInformationAdapter):
    response_type: Type[CommandResponse] = WelcomeCommandResponse
    _MARKDOWN_HORIZONTAL_MARGIN: int = 4
    _TABLE_VALUE_STYLE: str = "#949494"
    _STATUS_LABEL_STYLE: str = "#949494"
    _CREDITS_STYLE: str = "#949494"
    _CREDITS_NAME: str = "Elias Magalhães"
    _CREDITS_EMAIL: str = "elias@brasidata.com"

    def render(self, response: CommandResponse) -> str:
        logo_content: str = self._logo_adapter.render()
        markdown_content: str = self._render_markdown(self._markdown_content(response))
        overview_content: str = self._render_overview(self._overview_rows(response))
        system_status_content: str = self._render_system_status(self._system_status(response))
        footer_content: str = self._render_footer()

        if overview_content:
            return (
                f"{logo_content}\n\n{markdown_content}\n\n\n"
                f"{overview_content}\n\n\n{system_status_content}\n\n{footer_content}"
            )

        return f"{logo_content}\n\n{markdown_content}\n\n{footer_content}"

    def _markdown_content(self, response: CommandResponse) -> str:
        content: object = getattr(response, "content", {})
        if isinstance(content, dict):
            hero: object = content.get("hero", "")
            if isinstance(hero, str):
                return hero

        return ""

    def _render_markdown(self, content: str) -> str:
        available_width: int = max(self._console_width() - (self._MARKDOWN_HORIZONTAL_MARGIN * 2), 20)
        indentation: str = " " * self._MARKDOWN_HORIZONTAL_MARGIN
        rendered_lines: List[str] = []
        paragraph: str

        for paragraph in content.split("\n\n"):
            normalized_paragraph: str = " ".join(line.strip() for line in paragraph.splitlines()).strip()
            if not normalized_paragraph:
                rendered_lines.append("")
                continue

            wrapped_lines: List[str] = textwrap.wrap(
                normalized_paragraph,
                width=available_width,
                break_long_words=False,
                break_on_hyphens=False,
            )
            rendered_lines.extend(f"{indentation}{line}" for line in wrapped_lines)
            rendered_lines.append("")

        return "\n".join(rendered_lines).rstrip()

    def _overview_rows(self, response: CommandResponse) -> List[Dict[str, str]]:
        content: object = getattr(response, "content", {})
        if not isinstance(content, dict):
            return []

        overview: object = content.get("overview", [])
        if not isinstance(overview, list):
            return []

        valid_rows: List[Dict[str, str]] = []
        row: object
        for row in overview:
            if not isinstance(row, dict):
                continue

            label: object = row.get("label", "")
            value: object = row.get("value", "")
            if isinstance(label, str) and isinstance(value, str) and label and value:
                valid_rows.append(
                    {
                        "label": label,
                        "value": value,
                    }
                )

        return valid_rows

    def _system_status(self, response: CommandResponse) -> Optional[CliInitProcessStatePort]:
        content: object = getattr(response, "content", {})
        if not isinstance(content, dict):
            return None

        system_status: object = content.get("system_status", "")
        if isinstance(system_status, CliInitProcessStatePort):
            return system_status

        return None

    def _render_overview(self, rows: List[Dict[str, str]]) -> str:
        if not rows:
            return ""

        label_style: str = self._rgb_to_hex(self._logo_adapter.bim_rgb())
        buffer: StringIO = StringIO()
        console: Console = Console(
            file=buffer,
            force_terminal=True,
            color_system="truecolor",
            width=self._console_width(),
            soft_wrap=True,
            legacy_windows=False,
        )
        table: Table = Table.grid(padding=(0, 3))
        table.add_column(style=label_style, no_wrap=True)
        table.add_column(style=self._TABLE_VALUE_STYLE)

        row: Dict[str, str]
        for row in rows:
            label_text: Text = Text(f"{row['label']}:", style=label_style)
            value_text: Text = Text.from_markup(row["value"], style=self._TABLE_VALUE_STYLE)
            table.add_row(label_text, value_text)

        console.print(Padding(table, (0, self._MARKDOWN_HORIZONTAL_MARGIN)))
        return "\n".join(line.rstrip() for line in buffer.getvalue().splitlines()).rstrip()

    def _render_system_status(self, system_status: Optional[CliInitProcessStatePort]) -> str:
        if system_status is None:
            return ""

        bim_rgb: tuple[int, int, int] = self._logo_adapter.bim_rgb()
        status_style: str = f"\x1b[38;2;{bim_rgb[0]};{bim_rgb[1]};{bim_rgb[2]}m"
        indentation: str = " " * self._MARKDOWN_HORIZONTAL_MARGIN
        diamond: str = (
            f"\x1b[38;2;{bim_rgb[0]};{bim_rgb[1]};{bim_rgb[2]}m◆\x1b[0m"
        )
        return (
            f"{indentation}{diamond} "
            f"{status_style}System Status:\x1b[0m "
            f"{system_status.label()}"
            f"\n\n{indentation}\x1b[38;2;148;148;148m{system_status.description()}\x1b[0m"
        )

    def _render_footer(self) -> str:
        terminal_width: int = self._console_width()
        separator_width: int = self._logo_adapter.logo_width()
        separator_padding: int = max((terminal_width - separator_width) // 2, 0)
        credits_text: str = f"Developed by {self._CREDITS_NAME} <{self._CREDITS_EMAIL}>"
        credits_padding: int = max((terminal_width - len(credits_text)) // 2, 0)
        separator: str = (
            f"{' ' * separator_padding}"
            f"\x1b[38;2;{self._logo_adapter.bim_rgb()[0]};{self._logo_adapter.bim_rgb()[1]};{self._logo_adapter.bim_rgb()[2]}m"
            f"{'─' * separator_width}\x1b[0m"
        )
        credits: str = (
            f"{' ' * credits_padding}"
            f"\x1b[38;2;148;148;148m{credits_text}\x1b[0m"
        )
        return f"{separator}\n{credits}\n\n"

    def _console_width(self) -> int:
        return shutil.get_terminal_size(fallback=(120, 40)).columns

    def _rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
