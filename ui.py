from threading import Lock

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import (BarColumn, MofNCompleteColumn, Progress,
                           TextColumn, TimeElapsedColumn)
from rich.text import Text

import config


class FetchLog:
    """Left panel: keyed entries updated in-place, auto-scrolls to bottom."""

    def __init__(self, maxlen: int = 500):
        self._entries: dict[str, str] = {}
        self._lock = Lock()
        self._maxlen = maxlen

    def set(self, key: str, markup: str) -> None:
        with self._lock:
            self._entries[key] = markup
            if len(self._entries) > self._maxlen:
                del self._entries[next(iter(self._entries))]

    def __rich_console__(self, console, options):
        with self._lock:
            lines = list(self._entries.values())
        if not lines:
            yield Text.from_markup("[dim]Waiting for Selenium…[/dim]")
            return
        visible = options.height or len(lines)
        for line in lines[-visible:]:
            yield Text.from_markup(line)


def build_download_ui() -> tuple[Console, FetchLog, Progress, Layout]:
    """Create and wire the split-screen download UI."""
    console   = Console()
    fetch_log = FetchLog()
    dl_prog   = Progress(
        TextColumn("{task.description}"),
        BarColumn(bar_width=config.BAR_BAR_WIDTH,
                  complete_style="cyan", finished_style="green"),
        TextColumn("[progress.percentage]{task.percentage:>5.1f}%"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        expand=True,
    )
    layout = Layout()
    layout.split_row(
        Layout(
            Panel(fetch_log,
                  title="[bold cyan]Fetching[/bold cyan]",
                  border_style="cyan"),
            name="left", ratio=1,
        ),
        Layout(
            Panel(dl_prog,
                  title="[bold green]Downloading[/bold green]",
                  border_style="green"),
            name="right", ratio=2,
        ),
    )
    return console, fetch_log, dl_prog, layout
