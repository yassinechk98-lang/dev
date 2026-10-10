"""Interface graphique Tkinter : choisir un dossier, lancer l'analyse, gerer les menaces."""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__, updater
from .clamav import ClamdClient
from .cli import build_yara, scan_exclusions
from .quarantine import Quarantine
from .scanner import Scanner
from .signatures import load_default


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"FreeAV {__version__} - Antivirus gratuit")
        self.geometry("880x500")
        self.minsize(600, 380)

        self.quarantine = Quarantine()
        self.events: queue.Queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.worker: threading.Thread | None = None
        self.target = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.use_clamav = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Pret.")
        self.detections: dict = {}

        self._build()
        self.after(100, self._poll)

    def _build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Dossier a analyser :").pack(side="left")
        ttk.Entry(top, textvariable=self.target).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Parcourir...", command=self._browse).pack(side="left")

        actions = ttk.Frame(self, padding=(10, 0))
        actions.pack(fill="x")
        self.scan_btn = ttk.Button(actions, text="Analyser", command=self._start_scan)
        self.scan_btn.pack(side="left")
        self.stop_btn = ttk.Button(actions, text="Arreter", command=self.stop_flag.set,
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=6)
        ttk.Checkbutton(actions, text="Utiliser ClamAV (clamd)",
                        variable=self.use_clamav).pack(side="left", padx=12)
        ttk.Button(actions, text="Quarantaine...", command=self._show_quarantine).pack(side="right")
        self.update_btn = ttk.Button(actions, text="Mettre a jour les signatures",
                                     command=self._start_update)
        self.update_btn.pack(side="right", padx=6)

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", padx=10, pady=8)

        cols = ("menace", "moteur", "fichier")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for col, width in zip(cols, (180, 90, 440)):
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10)

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status).pack(side="left")
        ttk.Button(bottom, text="Mettre en quarantaine la selection",
                   command=self._quarantine_selected).pack(side="right")

    def _browse(self):
        folder = filedialog.askdirectory(initialdir=self.target.get())
        if folder:
            self.target.set(folder)

    def _start_scan(self):
        target = Path(self.target.get())
        if not target.exists():
            messagebox.showerror("FreeAV", f"Chemin introuvable :\n{target}")
            return
        self.tree.delete(*self.tree.get_children())
        self.stop_flag.clear()
        self.scan_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.progress.start(12)
        self.worker = threading.Thread(target=self._run_scan, args=(target,), daemon=True)
        self.worker.start()

    def _run_scan(self, target: Path):
        try:
            clamd = None
            if self.use_clamav.get():
                clamd = ClamdClient()
                if not clamd.ping():
                    self.events.put(("warn", "clamd injoignable : signatures uniquement."))
                    clamd = None
            scanner = Scanner(load_default(), clamd, yara=build_yara([]))
            report = scanner.scan([target], exclude=scan_exclusions(self.quarantine.directory, []),
                                  on_file=lambda p: self.events.put(("file", p)),
                                  should_stop=self.stop_flag.is_set)
            self.events.put(("done", report))
        except Exception as exc:  # ne jamais laisser la fenetre figee
            self.events.put(("failed", f"L'analyse a echoue : {exc}"))

    def _start_update(self):
        if not updater.load_auth_key():
            key = simpledialog.askstring(
                "Cle abuse.ch",
                "MalwareBazaar demande une cle gratuite (Auth-Key).\n"
                "Creez-la sur https://auth.abuse.ch puis collez-la ici :", parent=self)
            if not key or not key.strip():
                return
            try:
                updater.save_auth_key(key)
            except updater.UpdateError as exc:
                messagebox.showerror("FreeAV", str(exc), parent=self)
                return
        self.update_btn.config(state="disabled")
        self.status.set("Telechargement des signatures MalwareBazaar...")

        def work():
            try:
                _path, added, total = updater.update_malwarebazaar()
                msg = f"{added} nouvelles signatures, {total} au total."
            except (updater.UpdateError, OSError) as exc:
                msg = f"Mise a jour impossible : {exc}"
            self.events.put(("updated", msg))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "file":
                    self.status.set(f"Analyse : {payload}")
                elif kind == "warn":
                    messagebox.showwarning("FreeAV", payload)
                elif kind == "done":
                    self._finish(payload)
                elif kind == "failed":
                    self._reset_buttons()
                    self.status.set(payload)
                    messagebox.showerror("FreeAV", payload)
                elif kind == "updated":
                    self.update_btn.config(state="normal")
                    self.status.set(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _reset_buttons(self):
        self.progress.stop()
        self.scan_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def _finish(self, report):
        self._reset_buttons()
        self.detections = {}
        for det in report.detections:
            engine = f"{det.engine} (suspect)" if det.suspect else det.engine
            item = self.tree.insert("", "end", values=(det.threat, engine, str(det.path)))
            self.detections[item] = det
        if report.clean:
            verdict = "Aucune menace detectee."
        else:
            verdict = f"{len(report.threats)} menace(s), {len(report.suspects)} suspect(s) a verifier."
        if report.errors:
            verdict += f" {len(report.errors)} fichier(s) illisible(s)."
        self.status.set(f"{report.scanned} fichiers analyses. {verdict}")

    def _quarantine_selected(self):
        moved = 0
        for item in self.tree.selection():
            det = self.detections[item]
            path = det.path
            try:
                self.quarantine.isolate(Path(path), det.threat, det.sha256)
                self.tree.delete(item)
                moved += 1
            except OSError as exc:
                messagebox.showerror("FreeAV", f"Echec pour {path} :\n{exc}")
        if moved:
            self.status.set(f"{moved} fichier(s) mis en quarantaine, "
                            f"{len(self.tree.get_children())} menace(s) restante(s).")

    def _show_quarantine(self):
        win = tk.Toplevel(self)
        win.title("Quarantaine")
        win.geometry("640x300")
        tree = ttk.Treeview(win, columns=("menace", "origine"), show="headings")
        tree.heading("menace", text="Menace")
        tree.heading("origine", text="Emplacement d'origine")
        tree.column("menace", width=180)
        tree.column("origine", width=420)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh():
            tree.delete(*tree.get_children())
            for entry in self.quarantine.list():
                tree.insert("", "end", iid=entry["id"],
                            values=(entry["threat"], entry["original_path"]))

        def act(fn):
            for item_id in tree.selection():
                try:
                    fn(item_id)
                except OSError as exc:
                    messagebox.showerror("FreeAV", str(exc), parent=win)
            refresh()

        buttons = ttk.Frame(win, padding=(10, 0, 10, 10))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Restaurer",
                   command=lambda: act(self.quarantine.restore)).pack(side="left")
        ttk.Button(buttons, text="Supprimer definitivement",
                   command=lambda: act(self.quarantine.delete)).pack(side="left", padx=6)
        refresh()


def run():
    App().mainloop()


if __name__ == "__main__":
    run()
