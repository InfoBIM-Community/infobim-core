from __future__ import annotations

import re
from typing import ClassVar, Dict, List, Optional, Tuple

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Label, Static
from textual_datepicker import DateSelect

from infobim.element.adapter.facade_field import ElementField, ElementFieldResolution

_UNSAFE_ID_CHARACTERS: re.Pattern[str] = re.compile(r"[^a-zA-Z0-9_-]")

# facade:fieldDatatype / IfcOpenShell attribute types that get a calendar
# picker instead of a free-text Input — matched by local name, lowercased
# (covers xsd:date, xsd:dateTime, and IFC's own IfcDate/IfcDateTime/
# IfcCalendarDate style local names alike).
_DATE_DATATYPES: frozenset[str] = frozenset({"date", "datetime"})


def _widget_id(identifier: str) -> str:
    sanitized: str = _UNSAFE_ID_CHARACTERS.sub("_", identifier).strip("_") or "field"
    return f"field-{sanitized}"


def _is_date_field(element_field: ElementField) -> bool:
    return element_field.datatype.strip().lower() in _DATE_DATATYPES


class ElementFillFormApp(App[Dict[str, str]]):
    """Standalone Textual form to fill one entity's field values.

    Same brand chrome (Header/Footer, cyan-on-dark theme) as
    ``StorageElementExplorerApp``/``StorageElementLazyExplorerApp`` in
    ontobdc, so every "open a Textual view" command in this toolchain
    reads as one consistent product.
    """

    TITLE: ClassVar[str] = "OntoBDC"
    SUB_TITLE: ClassVar[str] = "Element Fill"
    CSS: ClassVar[str] = """
    Screen {
        background: #071820;
        color: #f4fbfd;
    }

    Header {
        background: #00b4d8;
        color: #001219;
    }

    #fill-form {
        background: #071820;
        color: #f4fbfd;
        scrollbar-color: #00b4d8;
        scrollbar-color-hover: #48cae4;
        scrollbar-color-active: #90e0ef;
    }

    #summary {
        color: #90e0ef;
        padding: 1 1 1 1;
    }

    .field-label {
        color: #caf0f8;
        padding: 1 0 0 1;
    }

    Input {
        background: #0b2630;
        color: #f4fbfd;
        border: solid #00b4d8;
        margin: 0 1;
    }

    DateSelect {
        background: #0b2630;
        color: #f4fbfd;
        border: solid #00b4d8;
        margin: 0 1;
    }

    DateSelect:focus {
        border: solid #90e0ef;
    }

    DatePickerDialog {
        background: #0b2630;
        border: tall #00b4d8;
    }

    DatePicker WeekdayLabel {
        color: #90e0ef;
    }

    DatePicker DayLabel.--today {
        color: #48cae4;
    }

    DatePicker DayLabel.--day:hover {
        background: #071820;
    }

    Button {
        background: #00b4d8;
        color: #001219;
        margin: 1;
    }

    Footer {
        background: #0b2630;
        color: #caf0f8;
    }
    """
    BINDINGS: ClassVar[List[Tuple[str, str, str]]] = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
    ]

    def __init__(self, *, entity_uri: str, resolution: ElementFieldResolution) -> None:
        super().__init__()
        self._entity_uri: str = entity_uri
        self._resolution: ElementFieldResolution = resolution

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        body: List[Static] = [
            Static(
                f"{self._entity_uri}  ·  source: {self._resolution.source.value}"
                f"  ·  {self._resolution.field_count} field(s)",
                id="summary",
            )
        ]
        if not self._resolution.fields:
            body.append(
                Static(
                    "_No fields could be resolved for this entity — no "
                    "facade is declared for it, and it either isn't an IFC "
                    "class or IfcOpenShell doesn't know it in this schema._"
                )
            )
        for element_field in self._resolution.fields:
            required_marker: str = " *" if element_field.required else ""
            body.append(
                Label(
                    f"{element_field.label}{required_marker} "
                    f"({element_field.datatype})",
                    classes="field-label",
                )
            )
            if _is_date_field(element_field):
                body.append(
                    DateSelect(
                        picker_mount="#fill-form",
                        placeholder=element_field.identifier,
                        id=_widget_id(element_field.identifier),
                    )
                )
            else:
                body.append(
                    Input(
                        placeholder=element_field.identifier,
                        id=_widget_id(element_field.identifier),
                    )
                )
        if self._resolution.fields:
            body.append(Button("Submit", id="submit", variant="primary"))
        yield VerticalScroll(*body, id="fill-form")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "submit":
            return
        values: Dict[str, str] = {
            element_field.identifier: self._read_value(element_field)
            for element_field in self._resolution.fields
        }
        self.exit(values)

    def _read_value(self, element_field: ElementField) -> str:
        widget_selector: str = f"#{_widget_id(element_field.identifier)}"
        if _is_date_field(element_field):
            date_select: DateSelect = self.query_one(widget_selector, DateSelect)
            picked_date = date_select.date
            return picked_date.to_iso8601_string() if picked_date else ""
        return self.query_one(widget_selector, Input).value


class ElementFillFormAdapter:
    """Open the standalone Textual element-fill form."""

    def open(
        self,
        *,
        entity_uri: str,
        resolution: ElementFieldResolution,
    ) -> Dict[str, str]:
        app: ElementFillFormApp = ElementFillFormApp(
            entity_uri=entity_uri,
            resolution=resolution,
        )
        result: Optional[Dict[str, str]] = app.run()
        return dict(result or {})
