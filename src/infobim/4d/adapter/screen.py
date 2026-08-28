"""The local screen that records a task into the container's schedule.

A person on site needs to add a task and move on. The screen is served from
localhost rather than published as a file so the write happens where the
container is, with the workbook opened and closed per submission -- nothing
is held open, so Excel and this can take turns on the same file.

The palette mirrors the Surface's own theme tokens, and follows the
operating system's light/dark setting, so this does not look like a
different product from the Gantt page it feeds.
"""
from __future__ import annotations

import datetime as dt
import html
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs

from openpyxl.workbook.workbook import Workbook

from .workbook import (
    ScheduleWorkbookAdapter,
    ScheduleWorkbookError,
    parse_date,
    parse_percent,
    today_at_midnight,
)

# Every visible string, in one place: translating this screen later is one
# edit here rather than a hunt through the markup.
LABELS: Dict[str, str] = {
    "title": "Lançar tarefa",
    "wbs": "WBS",
    "task": "Tarefa",
    "start": "Início previsto",
    "finish": "Fim previsto",
    "actual_start": "Início real",
    "actual_finish": "Fim real",
    "percent": "Avanço %",
    "after": "Depende de",
    "none": "— nenhuma —",
    "milestone": "Marco",
    "critical": "Caminho crítico",
    "submit": "Gravar na planilha",
    "empty": "Nenhuma tarefa na planilha ainda.",
    "col_finish": "Fim prev.",
    "col_actual_finish": "Fim real",
    "col_progress": "Avanço",
}

PAGE: str = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
  :root {
    color-scheme: light dark;
    --background:#ffffff; --foreground:#0f172a; --accent:#0284c7;
    --line:rgba(15,23,42,.14); --soft:rgba(15,23,42,.04);
  }
  @media (prefers-color-scheme: dark) {
    :root { --background:#000; --foreground:#f8fafc; --accent:#38bdf8;
            --line:rgba(248,250,252,.16); --soft:rgba(248,250,252,.05); }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--background); color:var(--foreground);
         font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }
  .page { max-width:1080px; margin:0 auto; padding:clamp(16px,4vw,32px);
          display:flex; flex-direction:column; gap:20px; min-width:0; }
  header { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap;
           min-width:0; }
  h1 { font-size:20px; margin:0; letter-spacing:-.01em; }
  /* The workbook path is monospaced and has no natural break point: at
     448px on a 430px phone it gave the whole page a horizontal scrollbar.
     Breaking a file path anywhere is acceptable; losing the rest of the
     screen on site is not. */
  .target { font-size:12px; opacity:.6; font-family:ui-monospace,monospace;
            overflow-wrap:anywhere; min-width:0; }
  .card { border:1px solid var(--line); border-radius:14px;
          padding:clamp(14px,2.5vw,22px); background:var(--soft);
          min-width:0; }
  .fields { display:grid; gap:12px;
            grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); }
  label { display:flex; flex-direction:column; gap:5px; font-size:12px;
          font-weight:700; letter-spacing:.05em; text-transform:uppercase;
          opacity:.75; }
  input, select { font:inherit; font-size:15px; padding:9px 11px;
    border:1px solid var(--line); border-radius:9px;
    background:var(--background); color:var(--foreground); min-width:0; }
  input:focus, select:focus { outline:2px solid var(--accent);
    outline-offset:1px; }
  .wide { grid-column:1/-1; }
  .toggles { display:flex; gap:20px; align-items:center; padding-top:6px; }
  .toggles label { flex-direction:row; align-items:center; gap:7px;
    text-transform:none; letter-spacing:0; font-size:14px; opacity:1; }
  .toggles input { width:17px; height:17px; }
  button { font:inherit; font-weight:700; font-size:15px; padding:11px 22px;
    border:0; border-radius:999px; background:var(--accent); color:#fff;
    cursor:pointer; }
  button.quiet { background:transparent; color:var(--accent);
    border:1px solid var(--accent); padding:5px 13px; font-size:13px; }
  .actions { display:flex; gap:12px; align-items:center; margin-top:16px;
             flex-wrap:wrap; }
  .notice { font-size:14px; padding:11px 14px; border-radius:9px; }
  .done { background:rgba(34,197,94,.14); border:1px solid rgba(34,197,94,.5); }
  .failed { background:rgba(239,68,68,.14); border:1px solid rgba(239,68,68,.5); }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th { text-align:left; font-size:11px; letter-spacing:.06em;
       text-transform:uppercase; opacity:.6; padding:0 8px 8px; }
  td { padding:7px 8px; border-top:1px solid var(--line);
       vertical-align:middle; }
  td.wbs { font-family:ui-monospace,monospace; opacity:.75;
           white-space:nowrap; }
  td.num { text-align:right; white-space:nowrap;
           font-variant-numeric:tabular-nums; }
  .meter { position:relative; height:6px; border-radius:99px;
           background:var(--line); min-width:64px; }
  .meter i { position:absolute; inset:0 auto 0 0; border-radius:99px;
             background:var(--accent); }
  .scroll { overflow-x:auto; min-width:0; }
  .empty { opacity:.6; font-size:14px; }
  form.progress { display:flex; gap:6px; align-items:center; }
  form.progress input { width:64px; padding:5px 7px; font-size:13px; }
</style></head><body><div class="page">

<header><h1>__TITLE__</h1><span class="target">__TARGET__</span></header>

__NOTICE__

<form class="card" method="post" action="/task">
  <div class="fields">
    <label>__L_WBS__<input name="wbs" required placeholder="1.3" autofocus></label>
    <label class="wide">__L_TASK__
      <input name="name" required placeholder="Concretagem das sapatas"></label>
    <label>__L_START__<input type="date" name="start" required></label>
    <label>__L_FINISH__<input type="date" name="finish" required></label>
    <label>__L_ASTART__<input type="date" name="actual_start"></label>
    <label>__L_AFINISH__<input type="date" name="actual_finish"></label>
    <label>__L_PERCENT__<input name="percent" inputmode="numeric" placeholder="0"></label>
    <label>__L_AFTER__
      <select name="after"><option value="">__L_NONE__</option>__OPTIONS__</select>
    </label>
  </div>
  <div class="toggles">
    <label><input type="checkbox" name="milestone" value="1"> __L_MILESTONE__</label>
    <label><input type="checkbox" name="critical" value="1"> __L_CRITICAL__</label>
  </div>
  <div class="actions"><button type="submit">__L_SUBMIT__</button></div>
</form>

<div class="card"><div class="scroll">__TABLE__</div></div>

</div></body></html>
"""


def escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def render(
    adapter: ScheduleWorkbookAdapter,
    notice: str = "",
    kind: str = "done",
) -> str:
    tasks: List[Dict[str, str]] = adapter.tasks()

    options: str = "".join(
        f'<option value="{escape(task["id"])}">'
        f'{escape(task["wbs"])} - {escape(task["name"])}</option>'
        for task in tasks
    )

    if tasks:
        rows: List[str] = []
        task: Dict[str, str]
        for task in tasks:
            try:
                percent: int = int(float(task["percent"] or 0))
            except ValueError:
                percent = 0
            late: bool = bool(
                task["actual_finish"] and task["finish"]
                and task["actual_finish"] > task["finish"]
            )
            milestone: str = " ◆" if str(task["milestone"]).strip().upper() in {
                "TRUE", "1", "X", "SIM", "YES"
            } else ""
            rows.append(
                "<tr>"
                f'<td class="wbs">{escape(task["wbs"])}</td>'
                f'<td>{escape(task["name"])}{milestone}</td>'
                f'<td class="num">{escape(task["start"])}</td>'
                f'<td class="num">{escape(task["finish"])}</td>'
                f'<td class="num">{escape(task["actual_finish"]) or "—"}'
                f'{" ⚠" if late else ""}</td>'
                f'<td><div class="meter"><i style="width:{percent}%"></i></div></td>'
                f'<td class="num">{percent}%</td>'
                '<td><form class="progress" method="post" action="/progress">'
                f'<input type="hidden" name="id" value="{escape(task["id"])}">'
                f'<input name="percent" value="{percent}" inputmode="numeric">'
                '<button class="quiet" type="submit">ok</button>'
                "</form></td></tr>"
            )
        table: str = (
            f'<table><thead><tr><th>{LABELS["wbs"]}</th>'
            f'<th>{LABELS["task"]}</th><th>{LABELS["start"]}</th>'
            f'<th>{LABELS["col_finish"]}</th>'
            f'<th>{LABELS["col_actual_finish"]}</th><th></th><th>%</th>'
            f'<th>{LABELS["col_progress"]}</th></tr></thead><tbody>'
            + "".join(rows)
            + "</tbody></table>"
        )
    else:
        table = f'<p class="empty">{LABELS["empty"]}</p>'

    banner: str = (
        f'<div class="notice {kind}">{escape(notice)}</div>' if notice else ""
    )

    page: str = PAGE
    replacements: Dict[str, str] = {
        "__TITLE__": escape(LABELS["title"]),
        "__TARGET__": escape(adapter.workbook_path),
        "__NOTICE__": banner,
        "__OPTIONS__": options,
        "__TABLE__": table,
        "__L_WBS__": escape(LABELS["wbs"]),
        "__L_TASK__": escape(LABELS["task"]),
        "__L_START__": escape(LABELS["start"]),
        "__L_FINISH__": escape(LABELS["finish"]),
        "__L_ASTART__": escape(LABELS["actual_start"]),
        "__L_AFINISH__": escape(LABELS["actual_finish"]),
        "__L_PERCENT__": escape(LABELS["percent"]),
        "__L_AFTER__": escape(LABELS["after"]),
        "__L_NONE__": escape(LABELS["none"]),
        "__L_MILESTONE__": escape(LABELS["milestone"]),
        "__L_CRITICAL__": escape(LABELS["critical"]),
        "__L_SUBMIT__": escape(LABELS["submit"]),
    }
    placeholder: str
    value: str
    for placeholder, value in replacements.items():
        page = page.replace(placeholder, value)
    return page


# --------------------------------------------------------------- recording

def record_task(
    adapter: ScheduleWorkbookAdapter,
    fields: Dict[str, str],
) -> str:
    wbs: str = (fields.get("wbs") or "").strip()
    name: str = (fields.get("name") or "").strip()
    if not wbs or not name:
        raise ValueError("WBS e Tarefa são obrigatórios.")

    start: Optional[dt.datetime] = parse_date(fields.get("start"))
    finish: Optional[dt.datetime] = parse_date(fields.get("finish"))
    if start and finish and finish < start:
        raise ValueError(
            f"O fim ({finish:%d/%m}) é anterior ao início ({start:%d/%m})."
        )

    workbook: Workbook = adapter.open_workbook()
    try:
        task_rows = adapter.records(workbook, "IfcTask")
        time_rows = adapter.records(workbook, "IfcTaskTime")
        sequence_rows = adapter.records(workbook, "IfcRelSequence")

        if any(
            str(row.get("Identification") or "").strip() == wbs
            for row in task_rows
        ):
            raise ValueError(f"Já existe uma tarefa com WBS {wbs}.")

        task_id: str = adapter.next_identifier(
            [str(row.get("GlobalId") or "") for row in task_rows], "T-"
        )
        time_id: str = adapter.next_identifier(
            [str(row.get("GlobalId") or "") for row in time_rows], "TT-"
        )

        adapter.append(workbook, "IfcTask", {
            "GlobalId": task_id,
            "Identification": wbs,
            "Name": name,
            "TaskTime": time_id,
            "IsMilestone": "TRUE" if fields.get("milestone") else "",
            "IsCritical": "TRUE" if fields.get("critical") else "",
        })
        adapter.append(workbook, "IfcTaskTime", {
            "GlobalId": time_id,
            "ScheduleStart": start,
            "ScheduleFinish": finish,
            "ActualStart": parse_date(fields.get("actual_start")),
            "ActualFinish": parse_date(fields.get("actual_finish")),
            "PercentComplete": parse_percent(fields.get("percent")),
        })

        predecessor: str = (fields.get("after") or "").strip()
        if predecessor and adapter.sheet_names.get("IfcRelSequence"):
            adapter.append(workbook, "IfcRelSequence", {
                "GlobalId": adapter.next_identifier(
                    [str(row.get("GlobalId") or "") for row in sequence_rows],
                    "S-",
                ),
                "RelatingProcess": predecessor,
                "RelatedProcess": task_id,
                "SequenceType": "FINISH_START",
            })

        workbook.save(str(adapter.workbook_path))
    finally:
        workbook.close()

    return f"Gravado: {wbs} — {name}"


def record_progress(
    adapter: ScheduleWorkbookAdapter,
    fields: Dict[str, str],
) -> str:
    task_id: str = (fields.get("id") or "").strip()
    percent: Optional[int] = parse_percent(fields.get("percent"))
    if not task_id:
        raise ValueError("Tarefa não identificada.")

    workbook: Workbook = adapter.open_workbook()
    try:
        task_rows = adapter.records(workbook, "IfcTask")
        target = next(
            (
                row for row in task_rows
                if str(row.get("GlobalId") or "").strip() == task_id
            ),
            None,
        )
        if target is None:
            raise ValueError(f"Tarefa {task_id} não existe na planilha.")

        time_id: str = str(target.get("TaskTime") or "").strip()
        values: Dict[str, Any] = {"PercentComplete": percent}

        # A task at 100% with no finish date cannot be compared against its
        # plan, which is the whole reason the actual columns exist.
        if percent == 100:
            values["ActualFinish"] = today_at_midnight()
        if percent and percent > 0:
            current = next(
                (
                    row for row in adapter.records(workbook, "IfcTaskTime")
                    if str(row.get("GlobalId") or "").strip() == time_id
                ),
                {},
            )
            if not current.get("ActualStart"):
                values["ActualStart"] = (
                    current.get("ScheduleStart") or today_at_midnight()
                )

        if not adapter.update_task_time(workbook, time_id, values):
            raise ValueError(
                f"Não achei a linha de tempo {time_id} na aba "
                f"{adapter.sheet_names.get('IfcTaskTime')}."
            )
        workbook.save(str(adapter.workbook_path))
    finally:
        workbook.close()

    return f"{target.get('Identification')} — {target.get('Name')}: {percent}%"


# ----------------------------------------------------------------- serving

def make_handler(adapter: ScheduleWorkbookAdapter) -> Any:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: Any) -> None:
            return

        def _send(self, body: str, status: int = 200) -> None:
            payload: bytes = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if self.path.startswith("/favicon"):
                self.send_response(204)
                self.end_headers()
                return
            self._send(render(adapter))

        def do_POST(self) -> None:
            length: int = int(self.headers.get("Content-Length") or 0)
            raw: str = self.rfile.read(length).decode("utf-8")
            fields: Dict[str, str] = {
                key: values[0]
                for key, values in parse_qs(raw, keep_blank_values=True).items()
            }
            action: Callable[..., str] = (
                record_task if self.path == "/task" else record_progress
            )
            try:
                notice: str = action(adapter, fields)
                kind: str = "done"
            except (ValueError, ScheduleWorkbookError) as error:
                notice, kind = str(error), "failed"
            except Exception as error:  # noqa: BLE001
                notice, kind = f"{type(error).__name__}: {error}", "failed"
            self._send(render(adapter, notice, kind))

    return Handler


def serve(
    adapter: ScheduleWorkbookAdapter,
    port: int = 0,
    open_browser: bool = True,
) -> HTTPServer:
    server: HTTPServer = HTTPServer(("127.0.0.1", port), make_handler(adapter))
    if open_browser:
        address: str = f"http://127.0.0.1:{server.server_port}/"
        threading.Timer(0.4, lambda: webbrowser.open(address)).start()
    return server
