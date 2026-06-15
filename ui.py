from threading import Lock

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (BarColumn, MofNCompleteColumn, Progress,
                           TextColumn, TimeElapsedColumn)
from rich.text import Text

import config
from events import DownloadObserver


class FetchLog:
    """Left panel: keyed entries updated in-place, auto-scrolls to bottom."""

    def __init__(self, maxlen: int = 500):
        self._entries: dict[str, str] = {}
        self._lock = Lock()
        self._maxlen = maxlen

    def set(self, key: str, markup: str) -> None:
        with self._lock:
            self._entries.pop(key, None)
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


def _bar_desc(phase: str, chapter_text: str, grayscale: bool) -> str:
    """Fixed-width task description with rich colour markup."""
    suffix = " [gs]" if grayscale else ""
    name = (chapter_text + suffix)[:config.BAR_NAME_WIDTH]
    color = "cyan" if phase == "↓" else "yellow"
    return f"[bold {color}]{phase}[/bold {color}]  {name:<{config.BAR_NAME_WIDTH}}"


class RichDownloadObserver(DownloadObserver):
    """Renders download progress to the split-screen rich terminal UI."""

    def __init__(self, grayscale: bool = False):
        self._grayscale = grayscale
        self._console, self._fetch_log, self._prog, self._layout = build_download_ui()
        self._live: Live | None = None
        self._total = 0
        self._lock = Lock()
        self._nums: dict[str, int] = {}   # key → 1-based selection index
        self._tasks: dict[str, int] = {}  # key → rich task id

    # ── lifecycle ────────────────────────────────────────────────────────────
    def start(self, total_chapters: int) -> None:
        self._total = total_chapters
        self._live = Live(self._layout, console=self._console,
                          refresh_per_second=8, transient=False)
        self._live.__enter__()

    def stop(self) -> None:
        if self._live is not None:
            self._live.__exit__(None, None, None)
            self._live = None

    # ── fetch panel ──────────────────────────────────────────────────────────
    def fetch_skipped(self, key: str, num: int) -> None:
        with self._lock:
            self._nums[key] = num
        self._fetch_log.set(key, f"  [dim][{num}/{self._total}] ⊘  {key}[/dim]")

    def fetch_started(self, key: str, num: int) -> None:
        with self._lock:
            self._nums[key] = num
        self._fetch_log.set(key, f"  [{num}/{self._total}] [cyan]↓[/cyan]  {key}")

    def fetch_failed(self, key: str, num: int) -> None:
        self._fetch_log.set(key, f"  [red][{num}/{self._total}] ✗  {key}[/red]")

    def fetch_retry(self, key: str, num: int, attempt: int, max_attempts: int) -> None:
        self._fetch_log.set(
            key,
            f"  [{num}/{self._total}]"
            f" [yellow]↻ retry {attempt}/{max_attempts}[/yellow]  {key}")

    # ── download + build progress ────────────────────────────────────────────
    def download_started(self, key: str, total_images: int) -> None:
        with self._lock:
            finished = [t for t in self._prog.tasks if t.finished]
            if finished and len(self._prog.tasks) >= config.MAX_PROGRESS_TASKS:
                self._prog.remove_task(finished[0].id)
            self._tasks[key] = self._prog.add_task(
                _bar_desc("↓", key, self._grayscale), total=total_images)

    def image_downloaded(self, key: str) -> None:
        tid = self._tasks.get(key)
        if tid is not None:
            self._prog.advance(tid)

    def build_started(self, key: str, total_pages: int) -> None:
        tid = self._tasks.get(key)
        if tid is not None:
            self._prog.update(tid, description=_bar_desc("→", key, self._grayscale),
                              total=total_pages, completed=0)

    def page_built(self, key: str) -> None:
        tid = self._tasks.get(key)
        if tid is not None:
            self._prog.advance(tid)

    def chapter_saved(self, key: str, filename: str, pages: int, spreads: int) -> None:
        with self._lock:
            num = self._nums.get(key, 0)
        self._fetch_log.set(
            key, f"  [{num}/{self._total}] [bold green]✓[/bold green]  {key}")
        extra = f" (+{spreads} from spreads)" if spreads else ""
        self._prog.console.print(
            f"  [bold green]✓[/bold green] [green]{filename}[/green]"
            f"  [dim]({pages} pages{extra})[/dim]")

    def chapter_failed(self, key: str, num: int) -> None:
        self._fetch_log.set(
            key, f"  [{num}/{self._total}] [bold red]✗[/bold red]  {key}")
        self._prog.console.print(
            f"  [red]✗ {key} failed permanently[/red]"
            f"  [dim](see manga_downloader.log)[/dim]")

    def message(self, text: str) -> None:
        self._prog.console.print(f"  [dim]{text}[/dim]")
