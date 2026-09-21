"""Tk desktop interface for Hair Class Organizer."""

import os
import queue
import tkinter as tk
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from tkinter import filedialog, ttk

from app import __version__
from app.config import APP_NAME, DATA_DIR, MODEL_ID, MODEL_LABELS, AppSettings
from app.media import MediaResult, ScanOptions, move_media, plan_moves, scan_media


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
        self.device = tk.StringVar(master=self, value=settings.device)
        self.status = tk.StringVar(master=self, value="Ready")
        self.device_status = tk.StringVar(master=self, value="Device: not loaded")
        self.summary = tk.StringVar(master=self, value="0 media · 0 ready to move")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)
        self._build_header()
        self._build_source()
        self._build_options()
        self._build_actions()
        self._build_results()
        self._build_status()
        self.confidence.trace_add("write", self._refresh_move_plan)

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
        options.columnconfigure(5, weight=1)

        ttk.Label(options, text="Move confidence").grid(row=0, column=0, sticky="w")
        confidence = ttk.Spinbox(options, from_=0.0, to=1.0, increment=0.05, textvariable=self.confidence, width=7)
        confidence.grid(row=0, column=1, sticky="w", padx=(8, 20))
        ttk.Checkbutton(options, text="Include videos", variable=self.include_videos).grid(row=0, column=2, sticky="w")
        ttk.Label(options, text="Video frame %").grid(row=0, column=3, sticky="w", padx=(20, 0))
        frame_position = ttk.Spinbox(options, from_=0, to=100, textvariable=self.frame_percentage, width=5)
        frame_position.grid(row=0, column=4, sticky="w", padx=(8, 20))
        ttk.Label(options, text="Device").grid(row=0, column=5, sticky="e")
        device = ttk.Combobox(
            options, textvariable=self.device, values=("auto", "cpu", "cuda:0"), state="readonly", width=9
        )
        device.grid(row=0, column=6, sticky="e", padx=(8, 0))
        self.inputs.extend([confidence, frame_position, device])

        labels = ttk.Frame(options)
        labels.grid(row=1, column=0, columnspan=7, sticky="w", pady=(10, 0))
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

    def _build_results(self) -> None:
        table = ttk.Frame(self)
        table.grid(row=4, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        columns = ("source", "type", "label", "confidence", "status")
        self.tree = ttk.Treeview(table, columns=columns, show="headings")
        self.tree.heading("source", text="Source")
        self.tree.heading("type", text="Type")
        self.tree.heading("label", text="Hair color")
        self.tree.heading("confidence", text="Confidence")
        self.tree.heading("status", text="Status")
        self.tree.column("source", minwidth=260, stretch=True)
        self.tree.column("type", width=75, stretch=False)
        self.tree.column("label", width=110, stretch=False)
        self.tree.column("confidence", width=100, anchor="e", stretch=False)
        self.tree.column("status", width=120, stretch=False)
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<Double-Button-1>", self._open_selected)

    def _build_status(self) -> None:
        status = ttk.Frame(self)
        status.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status).grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(status, mode="determinate", maximum=1)
        self.progress.grid(row=0, column=1, sticky="e", padx=(12, 0))

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
        self.tree.delete(*self.tree.get_children())
        self.progress.configure(value=0, maximum=1)
        self.stop.clear()
        self.operation = "scan"
        self._set_busy(True)
        options = ScanOptions(
            source=Path(self.source.get()).resolve(),
            include_videos=self.include_videos.get(),
            frame_percentage=self.frame_percentage.get(),
            png_compress_level=self.settings.png_compress_level,
            device=self.device.get(),
        )
        self.future = self.executor.submit(scan_media, options, self.stop, self.emit)
        self.after(75, self.poll)

    def start_move(self) -> None:
        self.stop.clear()
        self.operation = "move"
        self._set_busy(True)
        self.progress.configure(value=0, maximum=len(self.move_plan))
        self.status.set("Moving original media")
        journal = DATA_DIR / "moves" / (datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f") + ".csv")
        self.future = self.executor.submit(move_media, self.move_plan, journal, self.stop, self.emit)
        self.after(75, self.poll)

    def emit(self, kind: str, payload: object) -> None:
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
            elif kind == "result":
                self._add_result(payload)
            elif kind == "progress":
                completed, total, name = payload
                self.progress.configure(value=completed)
                self.status.set(f"Scanning {completed}/{total}: {name}")
            elif kind == "moved":
                self.moved_paths.add(payload.source)
                self.progress.step()
                self._render_result(payload)

        if not self.future.done():
            self.after(75, self.poll)
            return

        outcome = self.future.result()
        if self.operation == "scan":
            self.results = outcome
            self._refresh_move_plan()
            self.status.set(f"Scan complete: {len(self.results)} media classified")
        else:
            self.results = [result for result in self.results if result.source not in self.moved_paths]
            self._refresh_move_plan()
            self.status.set(f"Move complete: {outcome} media moved")
        self._set_busy(False)

    def _add_result(self, result: MediaResult) -> None:
        self.results.append(result)
        self._render_result(result)

    def _render_result(self, result: MediaResult) -> None:
        item_id = str(result.source)
        values = (
            result.source.name,
            result.media_type,
            result.label,
            f"{result.confidence:.1%}",
            "Moved" if result.source in self.moved_paths else "Ready",
        )
        if self.tree.exists(item_id):
            self.tree.item(item_id, values=values)
        else:
            self.tree.insert("", "end", iid=item_id, values=values)

    def _refresh_move_plan(self, *_: str) -> None:
        selected = {label for label, variable in self.label_vars.items() if variable.get()}
        self.move_plan = plan_moves(self.results, Path(self.source.get()).resolve(), selected, self.confidence.get())
        self.summary.set(f"{len(self.results)} media · {len(self.move_plan)} ready to move")
        if self.future is None or self.future.done():
            self.move_button.state(["!disabled"] if self.move_plan else ["disabled"])

    def _open_selected(self, _event: tk.Event) -> None:
        selection = self.tree.selection()
        if selection:
            os.startfile(Path(selection[0]).parent)

    def _save_settings(self) -> None:
        self.settings.source = self.source.get()
        self.settings.confidence = self.confidence.get()
        self.settings.include_videos = self.include_videos.get()
        self.settings.frame_percentage = self.frame_percentage.get()
        self.settings.device = self.device.get()
        self.settings.window_geometry = self.winfo_toplevel().geometry()
        self.settings.save()

    def close(self) -> None:
        self._save_settings()
        self.stop.set()
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
