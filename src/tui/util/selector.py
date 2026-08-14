import sys
import os
import tty
import termios
import select
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich.box import ROUNDED

class Keyboard:
    """
    Captures key presses without requiring Enter (Standard Lib only).
    Works on macOS/Linux.
    Uses low-level os.read to avoid buffering issues.
    """
    def __call__(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            # Use os.read for unbuffered reading
            ch_bytes = os.read(fd, 1)
            ch = ch_bytes.decode(errors='ignore')
            
            if ch == '\x1b':  # Escape sequence
                # Check if there are more characters to read immediately
                # 0.1s timeout to distinguish between standalone ESC and sequence
                r, _, _ = select.select([fd], [], [], 0.1)
                if r:
                    ch2_bytes = os.read(fd, 1)
                    ch2 = ch2_bytes.decode(errors='ignore')
                    ch += ch2
                    
                    if ch2 == '[' or ch2 == 'O':
                        # Expecting a third character for arrows (e.g. A, B, C, D)
                        r2, _, _ = select.select([fd], [], [], 0.1)
                        if r2:
                            ch3_bytes = os.read(fd, 1)
                            ch += ch3_bytes.decode(errors='ignore')
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

class FileSelector:
    def __init__(self, console=None):
        self.console = console or Console()
        self.keyboard = Keyboard()

    def _build_visual_rows(self, files: list[str]) -> list[dict]:
        """
        Builds a flattened list of visual rows representing the file tree.
        """
        tree = {}
        for f in files:
            parts = f.split('/')
            current = tree
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = None # None indicates file
            
        rows = []
        
        # Add Root
        rows.append({"label": "📁 IFC Files", "value": None, "is_file": False})
        
        def traverse(node, depth=0, prefix=""):
            keys = sorted(node.keys())
            for key in keys:
                val = node[key]
                is_file = val is None
                
                if is_file:
                    icon = "📄"
                    full_path = f"{prefix}/{key}" if prefix else key
                    rows.append({
                        "label": f"{'  ' * depth}{icon} {key}",
                        "value": full_path,
                        "is_file": True
                    })
                else:
                    icon = "📂"
                    rows.append({
                        "label": f"{'  ' * depth}{icon} {key}",
                        "value": None,
                        "is_file": False
                    })
                    traverse(val, depth + 1, prefix=f"{prefix}/{key}" if prefix else key)
                    
        traverse(tree, depth=1)
        return rows

    def select_file(self, files: list[str], title="Select a File") -> str:
        """
        Displays an interactive menu to select a file from the list.
        Returns the selected file path or None if cancelled.
        """
        if not files:
            return None
            
        visual_rows = self._build_visual_rows(files)
        
        # Start selection at first file if possible
        selected_idx = 0
        for i, row in enumerate(visual_rows):
            if row['is_file']:
                selected_idx = i
                break
                
        offset = 0
        max_visible = 20  # Increased for better visibility
        
        def generate_content():
            nonlocal offset
            
            # Adjust offset to keep selected_idx in view
            if selected_idx < offset:
                offset = selected_idx
            elif selected_idx >= offset + max_visible:
                offset = selected_idx - max_visible + 1
                
            menu_text = Text()
            
            visible_rows = visual_rows[offset : offset + max_visible]
            
            for idx, row in enumerate(visible_rows):
                real_idx = offset + idx
                
                label = row['label']
                
                if real_idx == selected_idx:
                    # Use reverse video style for selection (standard terminal look)
                    # And ensure full width background for selection line
                    menu_text.append(f"{label}", style="reverse")
                    menu_text.append("\n")
                else:
                    menu_text.append(f"{label}\n", style="white")
            
            # Scroll indicators
            if offset > 0:
                menu_text.append("... (more above)", style="dim")
            
            # Footer instructions
            instructions = "[cyan]ESC[/] [dim]Quit[/]  [cyan]↑/↓[/] [dim]Move[/]  [cyan]Enter[/] [dim]Select[/]"
                
            return Panel(
                Align.left(menu_text),
                title=f"[bold]{title}[/bold]",
                subtitle=instructions,
                subtitle_align="left",
                border_style="white",
                box=ROUNDED,
                expand=True,
                padding=(1, 2)
            )

        # Using auto_refresh=True might help with responsiveness, 
        # but let's stick to manual control to ensure input doesn't lag rendering
        with Live(generate_content(), console=self.console, screen=True, refresh_per_second=20, auto_refresh=False) as live:
            while True:
                live.update(generate_content())
                live.refresh()
                
                key = self.keyboard()
                
                # Support standard brackets [A and application mode OA
                if key in ('\x1b[A', '\x1bOA'):  # UP
                    new_idx = selected_idx - 1
                    if new_idx >= 0:
                        selected_idx = new_idx
                elif key in ('\x1b[B', '\x1bOB'):  # DOWN
                    new_idx = selected_idx + 1
                    if new_idx < len(visual_rows):
                        selected_idx = new_idx
                elif key == '\r' or key == '\n':  # ENTER
                    row = visual_rows[selected_idx]
                    if row['is_file']:
                        return row['value']
                elif key == '\x1b':  # ESC only (standalone)
                    return None

class SimpleMenuSelector:
    def __init__(self, console=None):
        self.console = console or Console()
        self.keyboard = Keyboard()

    def select_option(self, options: list[dict], title="Select an Option") -> str:
        """
        Displays an interactive menu to select an option from the list.
        options: List of dicts with 'label' and 'value'.
        Returns the selected value or None if cancelled.
        """
        if not options:
            return None
            
        selected_idx = 0
        
        def generate_content():
            menu_text = Text()
            
            for idx, option in enumerate(options):
                label = option['label']
                
                if idx == selected_idx:
                    menu_text.append(f"{label}", style="reverse")
                    menu_text.append("\n")
                else:
                    menu_text.append(f"{label}\n", style="white")
            
            # Footer instructions
            instructions = "[cyan]ESC[/] [dim]Back[/]  [cyan]↑/↓[/] [dim]Move[/]  [cyan]Enter[/] [dim]Select[/]"
                
            return Panel(
                Align.center(menu_text, vertical="middle"),
                title=f"[bold]{title}[/bold]",
                subtitle=instructions,
                subtitle_align="left",
                border_style="white",
                box=ROUNDED,
                expand=True,
                padding=(2, 4)
            )

        with Live(generate_content(), console=self.console, screen=True, refresh_per_second=20, auto_refresh=False) as live:
            while True:
                live.update(generate_content())
                live.refresh()
                
                key = self.keyboard()
                
                if key in ('\x1b[A', '\x1bOA'):  # UP
                    new_idx = selected_idx - 1
                    if new_idx >= 0:
                        selected_idx = new_idx
                elif key in ('\x1b[B', '\x1bOB'):  # DOWN
                    new_idx = selected_idx + 1
                    if new_idx < len(options):
                        selected_idx = new_idx
                elif key == '\r' or key == '\n':  # ENTER
                    return options[selected_idx]['value']
                elif key == '\x1b':  # ESC only (standalone)
                    return None
