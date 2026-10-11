"""Interface graphique Tkinter : choisir un dossier, lancer l'analyse, gerer les menaces."""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__, schedule, updater, watcher
from .clamav import ClamdClient
from .cli import batch_engines, build_yara, malware_checker, scan_exclusions
from .quarantine import Quarantine
from .scanner import Scanner
from .signatures import load_default


ENGINE_LABELS = {"clamav": "ClamAV integre", "defender": "Microsoft Defender"}
COLORS = {"ok": ("#e6f4ea", "#1b6e2d"), "warn": ("#fff4e5", "#8a4b00"),
          "danger": ("#fdecea", "#a1251b")}


class App(tk.Tk):
    def __init__(self, scan: str | None = None):
        super().__init__()
        self.title(f"FreeAV {__version__} - Antivirus gratuit")
        icon = Path(__file__).parent / "data" / "freeav.ico"  # ajoutee par la version Windows
        if icon.is_file():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                pass
        self.geometry("880x500")
        self.minsize(600, 380)

        self.quarantine = Quarantine()
        self.events: queue.Queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.worker: threading.Thread | None = None
        self.target = tk.StringVar(value=scan or str(Path.home() / "Downloads"))
        self.use_clamav = tk.BooleanVar(value=False)
        from .clamav_local import LocalClamav, manifest
        from .defender import find_mpcmdrun
        self.local_clamav = LocalClamav()
        self.clamav_offer = manifest() is not None
        self.has_defender = find_mpcmdrun() is not None
        self.use_defender = tk.BooleanVar(value=self.has_defender)
        self.clamav_state = tk.StringVar()
        self.header = tk.StringVar()
        self.last_threats = 0
        try:
            from .repair import System
            self.background = schedule.status(System())["protection en temps reel"]
        except Exception:
            self.background = False
        self.status = tk.StringVar(value="Pret.")
        self.detections: dict = {}
        self.realtime = tk.BooleanVar(value=False)
        self.watch_stop: threading.Event | None = None

        from . import selfupdate
        self.auto_check = tk.BooleanVar(value=selfupdate.auto_check_enabled())
        self._build()
        self._refresh_engines()
        self._refresh_header()
        self.after(100, self._poll)
        self.app_update = None
        if self.auto_check.get():
            threading.Thread(target=self._check_app_update, daemon=True).start()
        if scan:  # "Analyser avec FreeAV" depuis le clic droit de l'Explorateur
            self.after(400, self._start_scan)

    def _build(self):
        self.banner = tk.Frame(self, padx=12, pady=8)
        self.banner.pack(fill="x")
        self.banner_label = tk.Label(self.banner, textvariable=self.header, anchor="w",
                                     font=("Segoe UI", 13, "bold"))
        self.banner_label.pack(side="left", fill="x", expand=True)
        from . import installer
        from .repair import System
        if getattr(__import__("sys"), "frozen", False) and not installer.is_installed(System()):
            self.install_btn = ttk.Button(self.banner, text="Installer FreeAV sur ce PC",
                                          command=self._install_app)
            self.install_btn.pack(side="right")

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
        ttk.Checkbutton(actions, text="clamd (avance)",
                        variable=self.use_clamav).pack(side="left", padx=12)
        ttk.Button(actions, text="Quarantaine...", command=self._show_quarantine).pack(side="right")
        ttk.Button(actions, text="Reparer mon PC...",
                   command=lambda: RepairWindow(self)).pack(side="right", padx=6)
        self.update_btn = ttk.Button(actions, text="Mettre a jour les signatures",
                                     command=self._start_update)
        self.update_btn.pack(side="right", padx=6)

        engines = ttk.Frame(self, padding=(10, 8, 10, 0))
        engines.pack(fill="x")
        ttk.Label(engines, text="Moteurs : signatures FreeAV").pack(side="left")
        defender = ttk.Checkbutton(engines, text="+ 2e avis Microsoft Defender",
                                   variable=self.use_defender)
        defender.pack(side="left", padx=10)
        if not self.has_defender:
            defender.state(["disabled"])
        ttk.Label(engines, textvariable=self.clamav_state).pack(side="left", padx=10)
        self.clamav_btn = ttk.Button(engines, command=self._clamav_action)
        self.clamav_btn.pack(side="left")

        shield = ttk.Frame(self, padding=(10, 8, 10, 0))
        shield.pack(fill="x")
        ttk.Checkbutton(shield, text="Protection en temps reel (Telechargements et Bureau)",
                        variable=self.realtime, command=self._toggle_realtime).pack(side="left")
        ttk.Button(shield, text="Protection automatique...",
                   command=lambda: ScheduleWindow(self)).pack(side="right")
        ttk.Checkbutton(shield, text="Chercher les nouvelles versions", variable=self.auto_check,
                        command=self._toggle_auto_check).pack(side="right", padx=10)

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
            scanner = Scanner(load_default(), clamd, yara=build_yara([]),
                              batch_engines=batch_engines(defender=self.use_defender.get()))
            report = scanner.scan(
                [target], exclude=scan_exclusions(self.quarantine.directory, []),
                on_file=lambda p: self.events.put(("file", p)),
                should_stop=self.stop_flag.is_set,
                on_engine=lambda name: self.events.put(
                    ("status", f"Analyse approfondie par {ENGINE_LABELS.get(name, name)}...")))
            self.events.put(("done", report))
        except Exception as exc:  # ne jamais laisser la fenetre figee
            self.events.put(("failed", f"L'analyse a echoue : {exc}"))

    def _refresh_header(self):
        if self.last_threats:
            text, tone = f"Attention : {self.last_threats} menace(s) trouvee(s) lors de la derniere analyse", "danger"
        elif self.realtime.get():
            text, tone = "Votre PC est protege : protection en temps reel active", "ok"
        elif self.background:
            text, tone = "Votre PC est protege : FreeAV surveille en arriere-plan", "ok"
        else:
            text, tone = "Protection en temps reel desactivee : cochez-la ci-dessous", "warn"
        bg, fg = COLORS[tone]
        self.header.set(("\u2714  " if tone == "ok" else "\u26a0  ") + text)
        for widget in (self.banner, self.banner_label):
            widget.config(bg=bg)
        self.banner_label.config(fg=fg)

    def _refresh_engines(self):
        from .quarantine import _is_elevated
        if _is_elevated():
            self.clamav_state.set("+ ClamAV integre : non utilise en administrateur")
            self.clamav_btn.pack_forget()
        elif self.local_clamav.ready():
            self.clamav_state.set("+ ClamAV integre : pret")
            self.clamav_btn.config(text="Mettre a jour ClamAV")
        elif self.clamav_offer:
            self.clamav_state.set("+ ClamAV integre : non installe")
            self.clamav_btn.config(text="Installer ClamAV (gratuit)")
        else:
            self.clamav_state.set("")
            self.clamav_btn.pack_forget()

    def _clamav_action(self):
        ready = self.local_clamav.ready()
        if not ready and not messagebox.askyesno(
                "ClamAV", "Installer le moteur antivirus ClamAV (Cisco Talos, gratuit, licence "
                "GPL-2.0) ?\n\nFreeAV telecharge ClamAV depuis le site officiel de Cisco Talos, "
                "puis ses signatures officielles (environ 300 Mo). Les analyses deviennent plus "
                "completes et plus longues.\n\nLe module RAR de ClamAV, dont la licence n'est "
                "pas libre, n'est pas installe : l'interieur des archives RAR n'est pas analyse.",
                parent=self):
            return
        self.clamav_btn.state(["disabled"])

        def work():
            try:
                say = lambda message: self.events.put(("status", message))
                if ready:
                    self.local_clamav.update(say)
                    msg = "Signatures ClamAV a jour."
                else:
                    self.local_clamav.install(progress=say)
                    msg = "ClamAV est installe : il sera utilise a chaque analyse."
            except Exception as exc:
                msg = f"ClamAV : {exc}"
            self.events.put(("clamav_done", msg))

        threading.Thread(target=work, daemon=True).start()

    def _toggle_auto_check(self):
        from . import selfupdate
        try:
            selfupdate.set_auto_check(self.auto_check.get())
        except OSError as exc:
            messagebox.showerror("FreeAV", f"Reglage non enregistre : {exc}", parent=self)
        if self.auto_check.get() and not self.app_update:
            threading.Thread(target=self._check_app_update, daemon=True).start()

    def _check_app_update(self):
        from . import selfupdate
        try:
            release = selfupdate.check()
        except Exception:
            return  # pas de reseau : on reessaiera au prochain demarrage
        if release:
            self.events.put(("app_update", release))

    def _show_app_update(self, release):
        self.app_update = release
        self.app_update_btn = ttk.Button(self.banner, text="Mettre a jour FreeAV",
                                         command=self._apply_app_update)
        self.app_update_btn.pack(side="right", padx=6)
        self.status.set(f"Une nouvelle version de FreeAV est disponible (version {self.app_update.build}).")

    def _apply_app_update(self):
        from . import selfupdate
        from .repair import System
        if not messagebox.askyesno(
                "FreeAV", "Installer la nouvelle version de FreeAV ?\n\nElle est telechargee "
                "depuis la page officielle de FreeAV sur GitHub et verifiee (empreinte SHA-256) "
                "avant de remplacer l'ancienne. FreeAV redemarre ensuite.", parent=self):
            return
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("FreeAV", "Attendez la fin de l'analyse en cours.", parent=self)
            return
        self.app_update_btn.state(["disabled"])
        release = self.app_update

        def work():
            system = System()
            try:
                selfupdate.apply(release, system,
                                 progress=lambda m: self.events.put(("status", m)))
                self.events.put(("app_updated", str(selfupdate.update_target(system))))
            except Exception as exc:
                self.events.put(("app_update_failed", f"Mise a jour impossible : {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def _restart(self, exe: str):
        from . import selfupdate
        messagebox.showinfo("FreeAV", "FreeAV est a jour. Il va redemarrer.", parent=self)
        try:
            selfupdate.start_detached([exe])
        except Exception as exc:
            messagebox.showwarning("FreeAV", f"Rouvrez FreeAV vous-meme ({exc}).", parent=self)
        if self.watch_stop:
            self.watch_stop.set()
        self.destroy()

    def _install_app(self):
        from . import installer
        from .repair import System

        def work():
            try:
                done = installer.install(System())
                msg = ("FreeAV est installe :\n- " + "\n- ".join(done)
                       + "\n\nVous pouvez l'ouvrir depuis le menu Demarrer ou le Bureau.")
            except Exception as exc:
                msg = f"Installation impossible : {exc}"
            self.events.put(("installed", msg))

        self.install_btn.state(["disabled"])
        threading.Thread(target=work, daemon=True).start()

    def _toggle_realtime(self):
        self._refresh_header()
        if not self.realtime.get():
            if self.watch_stop:
                self.watch_stop.set()
                self.watch_stop = None
            self.status.set("Protection en temps reel arretee.")
            return
        folders = watcher.default_folders()
        if not folders:
            self.realtime.set(False)
            messagebox.showwarning("FreeAV", "Aucun dossier Telechargements ou Bureau trouve.")
            return
        stop = self.watch_stop = threading.Event()

        def work():
            try:
                scanner = Scanner(load_default(), yara=build_yara([]))
                watch = watcher.FolderWatcher(
                    scanner, folders, self.quarantine,
                    exclude=scan_exclusions(self.quarantine.directory, []),
                    on_event=lambda event: self.events.put(("watch", event)),
                    removable_drives=watcher.removable_drives)
                watch.run(stop)
            except Exception as exc:
                self.events.put(("watch_failed", f"Protection en temps reel arretee : {exc}"))

        threading.Thread(target=work, daemon=True).start()
        self.status.set(f"Protection en temps reel active : {', '.join(map(str, folders))}")

    def _show_watch_event(self, event):
        if event.kind in ("erreur", "usb"):
            self.status.set(f"{event.path} : {event.message}")
            return
        if event.detection:
            engine = event.detection.engine + (" (suspect)" if event.detection.suspect else "")
            label = "quarantaine" if event.kind == "quarantaine" else engine
            item = self.tree.insert("", "end", values=(event.detection.threat, label,
                                                       str(event.path)))
            if event.kind != "quarantaine":
                self.detections[item] = event.detection
        self.status.set(event.message)
        messagebox.showwarning("FreeAV - protection en temps reel",
                               f"{event.message}\n\n{event.path}", parent=self)

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
                elif kind == "status":
                    self.status.set(payload)
                elif kind == "clamav_done":
                    self.clamav_btn.state(["!disabled"])
                    self._refresh_engines()
                    self.status.set(payload)
                    messagebox.showinfo("FreeAV", payload)
                elif kind == "installed":
                    messagebox.showinfo("FreeAV", payload)
                elif kind == "app_update":
                    self._show_app_update(payload)
                elif kind == "app_updated":
                    self._restart(payload)
                    return
                elif kind == "app_update_failed":
                    self.app_update_btn.state(["!disabled"])
                    self.status.set(payload)
                    messagebox.showerror("FreeAV", payload)
                elif kind == "watch":
                    self._show_watch_event(payload)
                elif kind == "watch_failed":
                    self.realtime.set(False)
                    self.watch_stop = None
                    self._refresh_header()
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
        self.last_threats = len(report.threats)
        self._refresh_header()
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
            self.last_threats = sum(1 for i in self.tree.get_children()
                                    if (d := self.detections.get(i)) and not d.suspect)
            self._refresh_header()
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


SEVERITY_TEXT = {"danger": "Danger", "suspect": "Suspect", "info": "Info", "outil": "Outil"}


class RepairWindow(tk.Toplevel):
    """Diagnostic du PC, puis reparation des problemes choisis, avec annulation possible."""

    def __init__(self, master):
        super().__init__(master)
        from . import repair
        self.repair = repair
        self.system = repair.System()
        self.title("Reparer mon PC")
        self.geometry("900x460")
        self.events: queue.Queue = queue.Queue()
        self.findings: dict = {}
        self.status = tk.StringVar(value="Diagnostic en cours (rien n'est modifie)...")

        cols = ("gravite", "categorie", "probleme", "detail")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        for col, title, width in zip(cols, ("Gravite", "Categorie", "Probleme", "Detail"),
                                     (80, 120, 260, 420)):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        bar = ttk.Frame(self, padding=(10, 0, 10, 10))
        bar.pack(fill="x")
        ttk.Label(bar, textvariable=self.status).pack(side="left")
        self.fix_btn = ttk.Button(bar, text="Reparer la selection", command=self._fix_selected,
                                  state="disabled")
        self.fix_btn.pack(side="right")
        ttk.Button(bar, text="Annuler la derniere reparation",
                   command=self._undo).pack(side="right", padx=6)
        ttk.Button(bar, text="Actualiser", command=self._diagnose).pack(side="right")
        self._diagnose()
        self.after(100, self._poll)

    def _run(self, kind, fn):
        def work():
            try:
                self.events.put((kind, fn()))
            except Exception as exc:  # jamais de fenetre figee
                self.events.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _diagnose(self):
        self.fix_btn.config(state="disabled")
        self.status.set("Diagnostic en cours (rien n'est modifie)...")
        self._run("diagnosed", lambda: self.repair.diagnose(self.system, malware_checker()))

    def _poll(self):
        if not self.winfo_exists():
            return
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "diagnosed":
                    self._show(payload)
                elif kind == "fixed":
                    results, journal = payload
                    lines = [f"{'OK' if r.ok else 'ECHEC'} - {r.finding.title} : {r.message}"
                             for r in results]
                    if journal:
                        lines.append("\nVous pouvez tout annuler avec "
                                     "« Annuler la derniere reparation ».")
                    messagebox.showinfo("Reparer mon PC", "\n".join(lines), parent=self)
                    self._diagnose()
                elif kind == "undone":
                    messagebox.showinfo("Reparer mon PC", "\n".join(
                        f"{'OK' if ok else 'ECHEC'} - {t} : {m}" for t, ok, m in payload), parent=self)
                    self._diagnose()
                elif kind == "error":
                    self.status.set(f"Erreur : {payload}")
                    messagebox.showerror("Reparer mon PC", payload, parent=self)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _show(self, findings):
        self.tree.delete(*self.tree.get_children())
        self.findings = {}
        for f in findings:
            title = f.title + (" (admin)" if f.needs_admin and not self.system.is_admin else "")
            item = self.tree.insert("", "end", values=(SEVERITY_TEXT.get(f.severity, f.severity),
                                                       f.category, title, f.detail))
            self.findings[item] = f
        problems = [f for f in findings if f.severity in ("danger", "suspect")]
        self.status.set(f"{len(problems)} probleme(s) a examiner." if problems
                        else "Aucun probleme important detecte.")
        self.fix_btn.config(state="normal")

    def _fix_selected(self):
        chosen = [self.findings[i] for i in self.tree.selection() if self.findings[i].fixable]
        if not chosen:
            messagebox.showinfo("Reparer mon PC", "Selectionnez un ou plusieurs problemes "
                                "reparables dans la liste.", parent=self)
            return
        text = "\n".join(f"- {f.title} : {f.fix_label}"
                         + ("" if f.undoable else " (DEFINITIF)") for f in chosen)
        final = [f for f in chosen if not f.undoable]
        warning = ("\n\nAttention : les actions marquees DEFINITIF ne pourront pas etre "
                   "annulees (fichiers temporaires supprimes, outils Windows)." if final else "")
        undoable = "Les autres modifications sont sauvegardees et annulables." if final else \
            "Toutes ces modifications sont sauvegardees et annulables."
        if not messagebox.askyesno("Reparer mon PC", f"FreeAV va effectuer :\n{text}{warning}"
                                   f"\n\n{undoable} Continuer ?",
                                   icon="warning" if final else "question", parent=self):
            return
        self.fix_btn.config(state="disabled")
        self.status.set("Reparation en cours...")

        def work():
            self.repair.create_restore_point(self.system)
            return self.repair.apply_fixes(chosen, self.system)
        self._run("fixed", work)

    def _undo(self):
        try:
            backups = self.repair.list_backups(system=self.system)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Reparer mon PC", str(exc), parent=self)
            return
        if not backups:
            messagebox.showinfo("Reparer mon PC", "Aucune reparation a annuler.", parent=self)
            return
        if messagebox.askyesno("Reparer mon PC", "Annuler la derniere serie de reparations ?",
                               parent=self):
            self._run("undone", lambda: self.repair.undo(system=self.system))


class ScheduleWindow(tk.Toplevel):
    """Active ou retire l'analyse quotidienne et la protection a l'ouverture de session."""

    def __init__(self, app: App):
        super().__init__(app)
        self.title("Protection automatique")
        self.resizable(False, False)
        self.system = schedule.System()
        self.at = tk.StringVar(value="12:00")
        self.realtime = tk.BooleanVar(value=True)
        self.state = tk.StringVar()
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both")
        ttk.Label(body, wraplength=420, justify="left", text=(
            "Chaque jour, FreeAV met a jour ses signatures (si une cle abuse.ch est enregistree), "
            "analyse vos Telechargements et votre Bureau, verifie les points sensibles du PC et "
            "vous previent en cas de probleme. Aucun droit administrateur n'est necessaire et "
            "tout se retire en un clic.")).pack(anchor="w")
        row = ttk.Frame(body, padding=(0, 10, 0, 0))
        row.pack(fill="x")
        ttk.Label(row, text="Heure de l'analyse :").pack(side="left")
        ttk.Entry(row, textvariable=self.at, width=7).pack(side="left", padx=6)
        ttk.Checkbutton(body, text="Proteger aussi en temps reel a chaque ouverture de session",
                        variable=self.realtime).pack(anchor="w", pady=6)
        ttk.Label(body, textvariable=self.state, foreground="#1b6e2d").pack(anchor="w", pady=4)
        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(buttons, text="Activer", command=self._install).pack(side="left")
        ttk.Button(buttons, text="Tout retirer", command=self._remove).pack(side="left", padx=6)
        ttk.Button(buttons, text="Fermer", command=self.destroy).pack(side="right")
        self._refresh()

    def _refresh(self):
        current = schedule.status(self.system)
        self.state.set("\n".join(f"{name} : {'active' if on else 'inactive'}"
                                  for name, on in current.items()))

    def _install(self):
        try:
            done = schedule.install(self.system, schedule.program_command(self.system),
                                    at=self.at.get().strip(), realtime=self.realtime.get())
        except (schedule.ScheduleError, OSError) as exc:
            messagebox.showerror("FreeAV", str(exc), parent=self)
            return
        self._refresh()
        messagebox.showinfo("FreeAV", "Protection automatique activee :\n- " + "\n- ".join(done),
                            parent=self)

    def _remove(self):
        try:
            done = schedule.remove(self.system)
        except (schedule.ScheduleError, OSError) as exc:
            messagebox.showerror("FreeAV", str(exc), parent=self)
            return
        self._refresh()
        messagebox.showinfo("FreeAV", "\n".join(done) or "Rien a retirer.", parent=self)


def run(scan: str | None = None):
    App(scan=scan).mainloop()


if __name__ == "__main__":
    run()
