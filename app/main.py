"""Tk desktop interface for Hair Class Organizer."""

import logging
import queue
import tkinter as tk
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from tkinter import filedialog, ttk

from app import __version__
from app.config import APP_NAME, LOG_PATH, MODEL_ID, MODEL_LABELS, MOVES_DIR, AppSettings
from app.media import MediaResult, ScanOptions, move_media, plan_moves, scan_media

logger = logging.getLogger(__name__)


class MainView(ttk.Frame):
    def __init__(self, parent: tk.Misc, settings: AppSettings) -> None:
        super().__init__(parent, padding=12)
        self.settings = settings
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hair-organizer")
        self.future: Future | None = None
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.stop = Event()
        self.operation = ""
        self.results: list[MediaResult] = []
        self.move_plan: list[MediaResult] = []
        self.moved_paths: set[Path] = set()
        self.label_vars: dict[str, tk.BooleanVar] = {}

        self.source = tk.StringVar(master=self, value=settings.source)
        self.confidence = tk.DoubleVar(master=self, value=settings.confidence)
        self.include_videos = tk.BooleanVar(master=self, value=settings.include_videos)
        self.frame_percentage = tk.IntVar(master=self, value=settings.frame_percentage)
        self.video_workers = tk.IntVar(master=self, value=settings.video_workers)
        self.move_workers = tk.IntVar(master=self, value=settings.move_workers)
        self.device = tk.StringVar(master=self, value=settings.device)
        self.status = tk.StringVar(master=self, value="Ready")
        self.progress_metrics = tk.StringVar(master=self, value="0% (ETA --:--)")
        self.device_status = tk.StringVar(master=self, value="Device: not loaded")
        self.summary = tk.StringVar(master=self, value="0 media · 0 ready to move")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)
        self._build_header()
        self._build_source()
        self._build_options()
        self._build_actions()
        self._build_log()
        self._build_status()
        self.confidence.trace_add("write", self._refresh_move_plan)
        self.log_after_id = self.after(250, self._tail_log)

    def _build_header(self) -> None:
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=f"{APP_NAME} v{__version__}", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=MODEL_ID).grid(row=1, column=0, sticky="w")
        ttk.Label(header, textvariable=self.device_status).grid(row=0, column=1, rowspan=2, sticky="e")

    def _build_source(self) -> None:
        source_frame = ttk.LabelFrame(self, text="Media source", padding=10)
        source_frame.grid(row=1, column=0, sticky="ew")
        source_frame.columnconfigure(0, weight=1)
        self.source_entry = ttk.Entry(source_frame, textvariable=self.source)
        self.source_entry.grid(row=0, column=0, sticky="ew")
        folder_button = ttk.Button(source_frame, text="Browse folder…", command=self._browse_folder)
        folder_button.grid(row=0, column=1, padx=(8, 0))
        file_button = ttk.Button(source_frame, text="Browse file…", command=self._browse_file)
        file_button.grid(row=0, column=2, padx=(8, 0))
        self.inputs = [self.source_entry, folder_button, file_button]

    def _build_options(self) -> None:
        options = ttk.LabelFrame(self, text="Scan and move options", padding=10)
        options.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        options.columnconfigure(9, weight=1)

        ttk.Label(options, text="Move confidence").grid(row=0, column=0, sticky="w")
        confidence = ttk.Spinbox(options, from_=0.0, to=1.0, increment=0.05, textvariable=self.confidence, width=7)
        confidence.grid(row=0, column=1, sticky="w", padx=(8, 20))
        ttk.Checkbutton(options, text="Include videos", variable=self.include_videos).grid(row=0, column=2, sticky="w")
        ttk.Label(options, text="Video frame %").grid(row=0, column=3, sticky="w", padx=(20, 0))
        frame_position = ttk.Spinbox(options, from_=0, to=100, textvariable=self.frame_percentage, width=5)
        frame_position.grid(row=0, column=4, sticky="w", padx=(8, 20))
        ttk.Label(options, text="Video workers").grid(row=0, column=5, sticky="w")
        video_workers = ttk.Spinbox(options, from_=1, to=64, textvariable=self.video_workers, width=4)
        video_workers.grid(row=0, column=6, sticky="w", padx=(8, 20))
        ttk.Label(options, text="Move workers").grid(row=0, column=7, sticky="w")
        move_workers = ttk.Spinbox(options, from_=1, to=64, textvariable=self.move_workers, width=4)
        move_workers.grid(row=0, column=8, sticky="w", padx=(8, 20))
        ttk.Label(options, text="Device").grid(row=0, column=9, sticky="e")
        device = ttk.Combobox(
            options, textvariable=self.device, values=("auto", "cpu", "cuda:0"), state="readonly", width=9
        )
        device.grid(row=0, column=10, sticky="e", padx=(8, 0))
        self.inputs.extend([confidence, frame_position, video_workers, move_workers, device])

        labels = ttk.Frame(options)
        labels.grid(row=1, column=0, columnspan=11, sticky="w", pady=(10, 0))
        ttk.Label(labels, text="Move classes:").pack(side="left")
        for label in MODEL_LABELS:
            variable = tk.BooleanVar(master=self, value=True)
            variable.trace_add("write", self._refresh_move_plan)
            self.label_vars[label] = variable
            ttk.Checkbutton(labels, text=label, variable=variable).pack(side="left", padx=(8, 0))

    def _build_actions(self) -> None:
        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="ew", pady=10)
        self.scan_button = ttk.Button(actions, text="Scan media", command=self.start_scan)
        self.scan_button.pack(side="left")
        self.stop_button = ttk.Button(actions, text="Stop", command=self.stop.set, state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))
        self.move_button = ttk.Button(actions, text="Move qualifying media", command=self.start_move, state="disabled")
        self.move_button.pack(side="left", padx=(8, 0))
        ttk.Label(actions, textvariable=self.summary).pack(side="right")

    def _build_log(self) -> None:
        log = ttk.LabelFrame(self, text="Application log", padding=8)
        log.grid(row=4, column=0, sticky="nsew")
        log.columnconfigure(0, weight=1)
        log.rowconfigure(0, weight=1)
        self.log = tk.Text(log, wrap="none", state="disabled", font="TkFixedFont")
        vertical = ttk.Scrollbar(log, orient="vertical", command=self.log.yview)
        horizontal = ttk.Scrollbar(log, orient="horizontal", command=self.log.xview)
        self.log.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.log_position = 0

    def _tail_log(self) -> None:
        with LOG_PATH.open("r", encoding="utf-8") as stream:
            stream.seek(self.log_position)
            content = stream.read()
            self.log_position = stream.tell()
        if content:
            self.log.configure(state="normal")
            self.log.insert("end", content)
            self.log.see("end")
            self.log.configure(state="disabled")
        self.log_after_id = self.after(250, self._tail_log)

    def _build_status(self) -> None:
        status = ttk.Frame(self)
        status.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status).grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(status, mode="determinate", maximum=1)
        self.progress.grid(row=0, column=1, sticky="e", padx=(12, 0))
        ttk.Label(status, textvariable=self.progress_metrics).grid(row=0, column=2, sticky="e", padx=(8, 0))

    def _browse_folder(self) -> None:
        selection = filedialog.askdirectory(parent=self, initialdir=self.source.get() or None)
        if selection:
            self.source.set(selection)

    def _browse_file(self) -> None:
        selection = filedialog.askopenfilename(parent=self, initialdir=self.source.get() or None)
        if selection:
            self.source.set(selection)

    def _set_busy(self, busy: bool) -> None:
        for widget in self.inputs + [self.scan_button]:
            widget.state(["disabled"] if busy else ["!disabled"])
        self.stop_button.state(["!disabled"] if busy else ["disabled"])
        self.move_button.state(["disabled"] if busy or not self.move_plan else ["!disabled"])

    def start_scan(self) -> None:
        self._save_settings()
        self.results.clear()
        self.move_plan.clear()
        self.moved_paths.clear()
        self.progress.configure(value=0, maximum=1)
        self.progress_metrics.set("0% (ETA --:--)")
        self.status.set("Preparing scan")
        self.stop.clear()
        self.operation = "scan"
        self._set_busy(True)
        options = ScanOptions(
            source=Path(self.source.get()).resolve(),
            include_videos=self.include_videos.get(),
            frame_percentage=self.frame_percentage.get(),
            video_workers=self.video_workers.get(),
            png_compress_level=self.settings.png_compress_level,
            device=self.device.get(),
        )
        logger.info("Starting scan: %s", options)
        self.future = self.executor.submit(scan_media, options, self.stop, self.emit)
        self.after(75, self.poll)

    def start_move(self) -> None:
        self.stop.clear()
        self.operation = "move"
        self._set_busy(True)
        self.progress.configure(value=0, maximum=len(self.move_plan))
        self.progress_metrics.set("0% (ETA --:--)")
        self.status.set("Moving media")
        journal = MOVES_DIR / (datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f") + ".csv")
        logger.info("Moving %d media", len(self.move_plan))
        self.future = self.executor.submit(
            move_media, self.move_plan, journal, self.stop, self.emit, self.move_workers.get()
        )
        self.after(75, self.poll)

    def emit(self, kind: str, payload: object) -> None:
        logger.info("%s: %s", kind, payload)
        self.events.put((kind, payload))

    def poll(self) -> None:
        while not self.events.empty():
            kind, payload = self.events.get()
            if kind == "status":
                self.status.set(str(payload))
            elif kind == "device":
                self.device_status.set(f"Device: {payload}")
            elif kind == "total":
                self.progress.configure(maximum=max(int(payload), 1), value=0)
                self.progress_metrics.set("0% (ETA --:--)")
            elif kind == "frame_progress":
                completed, total, name, percentage, eta = payload
                self.progress.configure(value=completed)
                self.status.set(f"Extracting frames {completed}/{total}: {name}")
                self.progress_metrics.set(f"{percentage}% (ETA {eta})")
            elif kind == "progress":
                completed, total, name, percentage, eta = payload
                self.progress.configure(value=completed)
                self.status.set(f"Scanning media {completed}/{total}: {name}")
                self.progress_metrics.set(f"{percentage}% (ETA {eta})")
            elif kind == "moved":
                self.moved_paths.add(payload.source)
            elif kind == "move_progress":
                completed, total, name, percentage, eta = payload
                self.progress.configure(value=completed)
                self.status.set(f"Moving media {completed}/{total}: {name}")
                self.progress_metrics.set(f"{percentage}% (ETA {eta})")

        if not self.future.done():
            self.after(75, self.poll)
            return

        outcome = self.future.result()
        if self.operation == "scan":
            self.results = outcome
            self._refresh_move_plan()
            self.status.set(f"Scan complete: {len(self.results)} media classified")
            logger.info("Scan complete: %d media classified", len(self.results))
        else:
            self.results = [result for result in self.results if result.source not in self.moved_paths]
            self._refresh_move_plan()
            self.status.set(f"Move complete: {outcome} media moved")
            logger.info("Move complete: %d media moved", outcome)
        self._set_busy(False)

    def _refresh_move_plan(self, *_: str) -> None:
        selected = {label for label, variable in self.label_vars.items() if variable.get()}
        self.move_plan = plan_moves(self.results, Path(self.source.get()).resolve(), selected, self.confidence.get())
        self.summary.set(f"{len(self.results)} media · {len(self.move_plan)} ready to move")
        if self.future is None or self.future.done():
            self.move_button.state(["!disabled"] if self.move_plan else ["disabled"])

    def _save_settings(self) -> None:
        self.settings.source = self.source.get()
        self.settings.confidence = self.confidence.get()
        self.settings.include_videos = self.include_videos.get()
        self.settings.frame_percentage = self.frame_percentage.get()
        self.settings.video_workers = self.video_workers.get()
        self.settings.move_workers = self.move_workers.get()
        self.settings.device = self.device.get()
        self.settings.window_geometry = self.winfo_toplevel().geometry()
        self.settings.save()

    def close(self) -> None:
        self._save_settings()
        self.stop.set()
        self.after_cancel(self.log_after_id)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.winfo_toplevel().destroy()


def run(settings: AppSettings) -> None:
    root = tk.Tk()
    root.title(f"{APP_NAME} v{__version__}")
    root.geometry(settings.window_geometry)
    root.minsize(780, 520)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    style = ttk.Style(root)
    style.configure("Title.TLabel", font="TkHeadingFont")
    view = MainView(root, settings)
    view.grid(row=0, column=0, sticky="nsew")
    root.protocol("WM_DELETE_WINDOW", view.close)
    view.source_entry.focus_set()
    root.mainloop()
