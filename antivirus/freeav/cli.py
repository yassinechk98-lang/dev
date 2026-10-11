"""Interface en ligne de commande : python -m freeav scan <chemin>..."""

import argparse
import shutil
import sys
from pathlib import Path

import threading
import time

from . import __version__, updater, watcher, yara_engine
from .clamav import ClamdClient, ClamdError
from .paths import APP_DIR, YARA_DIR, ensure_private_dir
from .quarantine import DEFAULT_DIR, Quarantine
from .scanner import Scanner
from .signatures import load_default


def yara_sources(extra: list[str]) -> list[Path]:
    return [Path(p) for p in extra] + ([YARA_DIR] if YARA_DIR.is_dir() else [])


def scan_exclusions(quarantine_dir: Path, yara_extra: list[str]) -> set[Path]:
    """Ne jamais analyser les donnees de FreeAV lui-meme : quarantaine, bases
    telechargees et regles YARA (qui contiennent forcement des motifs "malveillants")."""
    return {APP_DIR, Path(quarantine_dir), *yara_sources(yara_extra)}


def build_yara(extra: list[str]) -> yara_engine.YaraEngine | None:
    sources = yara_sources(extra)
    if not sources:
        return None
    if not yara_engine.available():
        print("Attention : regles YARA ignorees, installez yara-python pour les utiliser.",
              file=sys.stderr)
        return None
    engine = yara_engine.YaraEngine(sources)
    for path, err in engine.rejected:
        print(f"Attention : regle YARA ignoree {path} : {err}", file=sys.stderr)
    return engine


def scan_argument(value: str | None) -> str | None:
    """Clic droit sur un lecteur : Windows passe "E:\\" et la ligne --scan "E:\\" se lit E:"
    (le \\" final est un guillemet echappe). On remet la barre."""
    if value and value.endswith('"'):
        value = value[:-1] + "\\"
    return value


def batch_engines(defender: bool = False, clamav: bool = True) -> list:
    """Moteurs complets en plus des signatures FreeAV : ClamAV integre (s'il est installe)
    et, sur demande, Microsoft Defender en deuxieme avis.

    En administrateur, ClamAV integre n'est pas lance : il est installe dans un dossier de
    l'utilisateur, modifiable sans droits, et ne doit pas tourner avec des droits eleves."""
    from .quarantine import _is_elevated
    engines = []
    if clamav and _is_elevated():
        print("Attention : en administrateur, ClamAV integre n'est pas utilise "
              "(lancez FreeAV normalement).", file=sys.stderr)
        clamav = False
    if clamav:
        from .clamav_local import ClamscanEngine, LocalClamav
        local = LocalClamav()
        if local.ready():
            engines.append(ClamscanEngine(local))
    if defender:
        from .defender import DefenderEngine, DefenderError
        try:
            engines.append(DefenderEngine())
        except DefenderError as exc:
            print(f"Attention : {exc}, deuxieme avis desactive.", file=sys.stderr)
    return engines


def build_scanner(args, realtime: bool = False) -> Scanner:
    db = load_default([Path(p) for p in args.db])
    clamd = None
    if args.clamav:
        clamd = ClamdClient(unix_socket=args.clamd_socket, host=args.clamd_host,
                            port=args.clamd_port, allow_remote=args.allow_remote_clamd)
        if not clamd.ping():
            print("Attention : clamd injoignable, analyse par signatures uniquement.",
                  file=sys.stderr)
            clamd = None
    # En temps reel, ClamAV integre (lent a demarrer) est laisse a l'analyse complete.
    engines = batch_engines(defender=getattr(args, "defender", False),
                            clamav=not realtime and not getattr(args, "no_clamav", False))
    return Scanner(db, clamd, yara=build_yara(args.yara), batch_engines=engines)


def cmd_scan(args) -> int:
    missing = [p for p in args.paths if not Path(p).exists()]
    if missing:
        print(f"Erreur : chemin introuvable : {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        scanner = build_scanner(args)
    except (ClamdError, ValueError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    quarantine = Quarantine(Path(args.quarantine_dir))
    names = {"clamav": "ClamAV integre", "defender": "Microsoft Defender"}
    print(f"FreeAV {__version__} : {len(scanner.db)} signatures chargees"
          + (f", {len(scanner.yara)} fichiers de regles YARA" if scanner.yara else "")
          + (", moteur ClamAV actif" if scanner.clamd else "")
          + "".join(f", {names.get(e.name, e.name)} actif" for e in scanner.batch_engines))
    report = scanner.scan([Path(p) for p in args.paths],
                          exclude=scan_exclusions(quarantine.directory, args.yara))

    failed = 0
    for det in report.detections:
        label = "SUSPECT" if det.suspect else "MENACE "
        line = f"{label} {det.path}  ->  {det.threat} ({det.engine})"
        if args.quarantine and det.suspect:
            line += "  [a verifier, pas de quarantaine automatique]"
        elif args.quarantine:
            try:
                quarantine.isolate(det.path, det.threat, det.sha256)
                line += "  [mis en quarantaine]"
            except OSError as exc:
                failed += 1
                line += f"  [quarantaine impossible : {exc}]"
        print(line)
    for path, err in report.errors:
        print(f"ERREUR  {path} : {err}", file=sys.stderr)

    print(f"\n{report.scanned} fichiers analyses, {report.skipped} ignores (plus de "
          f"{scanner.max_size // (1024 * 1024)} Mo), {len(report.threats)} menace(s), "
          f"{len(report.suspects)} suspect(s), {len(report.errors) + failed} erreur(s).")
    return 1 if report.detections else 0


def cmd_quarantine(args) -> int:
    quarantine = Quarantine(Path(args.quarantine_dir))
    item_id = args.restore or args.delete
    if item_id and not quarantine.exists(item_id):
        print(f"Erreur : aucun element {item_id!r} en quarantaine.", file=sys.stderr)
        return 2
    if args.restore:
        try:
            print(f"Restaure : {quarantine.restore(args.restore)}")
        except FileExistsError as exc:
            print(f"Erreur : {exc}", file=sys.stderr)
            return 2
    elif args.delete:
        quarantine.delete(args.delete)
        print("Supprime definitivement.")
    else:
        items = quarantine.list()
        if not items:
            print("La quarantaine est vide.")
        for item in items:
            print(f"{item['id']}  {item['threat']}  {item['original_path']}")
    return 0


def malware_checker(scanner: Scanner | None = None):
    """Adapte le scanner pour le module de reparation : nom de la menace ou None.
    Une base de signatures abimee ne doit pas empecher de reparer le PC."""
    if scanner is None:
        try:
            scanner = Scanner(load_default())
        except (OSError, ValueError) as exc:
            print(f"Attention : signatures illisibles ({exc}), verification des programmes "
                  "desactivee.", file=sys.stderr)
            return lambda path: None

    def is_malware(path: Path) -> str | None:
        try:
            detection = scanner.scan_file(path)
        except Exception:
            return None
        return detection.threat if detection and not detection.suspect else None
    return is_malware


SEVERITY_LABELS = {"danger": "DANGER ", "suspect": "SUSPECT", "info": "INFO   ", "outil": "OUTIL  "}


def cmd_repair(args) -> int:
    from . import repair

    if args.list_backups:
        try:
            backups = repair.list_backups()
        except (OSError, ValueError) as exc:
            print(f"Erreur : {exc}", file=sys.stderr)
            return 2
        print("\n".join(str(b) for b in backups) or "Aucune reparation a annuler.")
        return 0
    if args.undo is not None:
        try:
            report = repair.undo(Path(args.undo) if args.undo else None)
        except (OSError, ValueError) as exc:
            print(f"Erreur : {exc}", file=sys.stderr)
            return 2
        for title, ok, message in report:
            print(f"{'ANNULE ' if ok else 'ECHEC  '} {title} : {message}")
        return 0 if all(ok for _, ok, _ in report) else 1

    system = repair.System()
    print("Diagnostic du PC en cours (aucune modification)...")
    findings = repair.diagnose(system, malware_checker())
    if not args.fix and not args.fix_dangers:
        problems = [f for f in findings if f.severity != "outil"]
        if not problems:
            print("Aucun probleme detecte.")
        for f in findings:
            admin = " [admin]" if f.needs_admin else ""
            fix = f"  -> reparer : freeav repair --fix {f.id}{admin}" if f.fixable else ""
            print(f"{SEVERITY_LABELS.get(f.severity, f.severity)} [{f.category}] {f.title}\n"
                  f"         {f.detail}{fix}")
        if not system.is_admin and any(f.needs_admin for f in findings):
            print("\nCertaines reparations demandent de lancer FreeAV en administrateur.")
        return 1 if any(f.severity in ("danger", "suspect") for f in problems) else 0

    wanted = set(args.fix or [])
    chosen = [f for f in findings if f.id in wanted
              or (args.fix_dangers and f.severity == "danger" and f.fixable)]
    unknown = wanted - {f.id for f in chosen}
    if unknown:
        print(f"Erreur : probleme introuvable : {', '.join(sorted(unknown))} "
              "(relancez 'freeav repair' pour voir la liste)", file=sys.stderr)
        return 2
    if not chosen:
        print("Rien a reparer.")
        return 0
    final = [f for f in chosen if not f.undoable]
    if final and not args.yes:
        print("Ces actions sont DEFINITIVES et ne pourront pas etre annulees :\n"
              + "\n".join(f"  - {f.title} : {f.fix_label}" for f in final)
              + "\nRelancez avec --yes pour confirmer.", file=sys.stderr)
        return 2
    if repair.create_restore_point(system):
        print("Point de restauration Windows cree.")
    try:
        results, journal = repair.apply_fixes(chosen, system)
    except (OSError, ValueError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    for r in results:
        print(f"{'REPARE ' if r.ok else 'ECHEC  '} {r.finding.title} : {r.message}")
    if journal:
        print(f"\nPour tout annuler : freeav repair --undo   (sauvegarde : {journal})")
    return 0 if all(r.ok for r in results) else 1


def cmd_update(args) -> int:
    try:
        if args.auth_key and args.save_key:
            updater.save_auth_key(args.auth_key)
            print("Cle Auth-Key enregistree dans ~/.freeav/config.json.")
        print("Telechargement des signatures MalwareBazaar (abuse.ch)...")
        path, added, total = updater.update_malwarebazaar(args.url, auth_key=args.auth_key or None)
    except (updater.UpdateError, OSError) as exc:
        print(f"Erreur : mise a jour impossible : {exc}", file=sys.stderr)
        return 2
    print(f"{added} nouvelles signatures, {total} au total dans {path}")
    return 0


def cmd_watch(args) -> int:
    folders = [Path(p) for p in args.folders] or watcher.default_folders()
    folders = [f for f in folders if f.is_dir()]
    if not folders:
        print("Erreur : aucun dossier a surveiller.", file=sys.stderr)
        return 2
    try:
        scanner = build_scanner(args, realtime=True)
    except (ClamdError, ValueError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    quarantine = Quarantine(Path(args.quarantine_dir)) if args.quarantine else None

    def on_event(event: watcher.WatchEvent) -> None:
        print(f"{time.strftime('%H:%M:%S')} {event.kind.upper():11} {event.path} : {event.message}",
              flush=True)
        if args.notify and event.kind not in ("erreur", "usb"):
            watcher.notify("FreeAV - protection en temps reel", f"{event.message}\n\n{event.path}")

    watch = watcher.FolderWatcher(scanner, folders, quarantine,
                                  exclude=scan_exclusions(Path(args.quarantine_dir), args.yara),
                                  on_event=on_event, removable_drives=watcher.removable_drives)
    print(f"Protection en temps reel active sur : {', '.join(map(str, folders))} "
          "(Ctrl+C pour arreter)", flush=True)
    stop = threading.Event()
    try:
        from .schedule import STOP_FILE
        watch.run(stop, interval=args.interval, stop_file=STOP_FILE)
    except KeyboardInterrupt:
        stop.set()
    print(f"Arret de la protection ({watch.scanned} nouveaux fichiers analyses).")
    return 0


LOG_FILE = APP_DIR / "logs" / "auto.log"
LOG_MAX = 1024 * 1024


def _log(lines: list[str]) -> None:
    ensure_private_dir(LOG_FILE.parent)
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > LOG_MAX:
        LOG_FILE.replace(LOG_FILE.with_suffix(".old.log"))
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.writelines(f"{stamp} {line}\n" for line in lines)


def cmd_auto(args) -> int:
    """Entretien automatique : mise a jour, analyse des dossiers a risque, controle du PC."""
    from . import repair

    lines, alerts = [], []
    if updater.load_auth_key():
        try:
            _, added, total = updater.update_malwarebazaar()
            lines.append(f"mise a jour : {added} nouvelles signatures ({total} au total)")
        except (updater.UpdateError, OSError) as exc:
            lines.append(f"mise a jour impossible : {exc}")
    else:
        lines.append("mise a jour ignoree : aucune cle abuse.ch enregistree")

    folders = watcher.default_folders()
    scanner = None
    try:
        scanner = build_scanner(args)
    except (ClamdError, ValueError) as exc:
        lines.append(f"analyse impossible : {exc}")
    if scanner and folders:
        quarantine = Quarantine(Path(args.quarantine_dir))
        report = scanner.scan(folders, exclude=scan_exclusions(quarantine.directory, args.yara))
        lines.append(f"analyse de {', '.join(map(str, folders))} : {report.scanned} fichiers, "
                     f"{len(report.threats)} menace(s), {len(report.suspects)} suspect(s)")
        for det in report.detections:
            status = "a verifier"
            if not det.suspect:
                try:
                    quarantine.isolate(det.path, det.threat, det.sha256)
                    status = "mis en quarantaine"
                except OSError as exc:
                    status = f"quarantaine impossible : {exc}"
            lines.append(f"  {det.threat} : {det.path} ({status})")
            alerts.append(f"{det.threat} : {det.path.name} ({status})")

    findings = repair.diagnose(repair.System(), malware_checker(scanner))
    dangers = [f for f in findings if f.severity == "danger"]
    lines.append(f"controle du PC : {len(dangers)} probleme(s) grave(s)")
    for f in dangers:
        lines.append(f"  {f.title} : {f.detail}")
        alerts.append(f"{f.title} (ouvrez FreeAV > Reparer mon PC)")

    newer = None
    try:
        from . import selfupdate
        newer = selfupdate.check()
        if newer:
            lines.append(f"nouvelle version de FreeAV disponible (version {newer.build})")
    except Exception as exc:  # pas de reseau : ce n'est pas un probleme du PC
        lines.append(f"verification de version impossible : {exc}")

    _log(lines)
    print("\n".join(lines))
    if newer and args.notify and not alerts:
        watcher.notify("FreeAV - nouvelle version", "Une nouvelle version de FreeAV est "
                       "disponible.\n\nOuvrez FreeAV et cliquez sur « Mettre a jour FreeAV ».")
    if alerts and args.notify:
        watcher.notify("FreeAV - analyse automatique", "FreeAV a trouve des problemes :\n\n"
                       + "\n".join(alerts[:8]) + f"\n\nJournal : {LOG_FILE}")
    return 1 if alerts else 0


def cmd_app_update(args) -> int:
    from . import selfupdate
    from .repair.platform import System
    try:
        if args.from_file:  # essai de la CI : meme chemin qu'une vraie mise a jour, sans reseau
            if not args.sha256:
                raise selfupdate.SelfUpdateError("--sha256 obligatoire avec --from-file")
            source = Path(args.from_file)
            release = selfupdate.Release(args.build, args.sha256, source.stat().st_size,
                                         source.as_uri())
            fetcher = lambda url, limit, dest: shutil.copyfile(source, dest)
        else:
            fetcher = None
            if not selfupdate.current_build():
                print("Cette copie de FreeAV ne se met pas a jour toute seule (code source : git pull).")
                return 0
            release = selfupdate.check()
            if not release:
                print("FreeAV est a jour.")
                return 0
            print(f"Nouvelle version disponible : version {release.build}")
            if args.check:
                return 0
            if not args.yes and input("Installer maintenant ? [o/N] ").strip().lower() not in ("o", "oui"):
                print("Rien n'a ete modifie.")
                return 0
        for step in selfupdate.apply(release, System(), progress=print, fetcher=fetcher):
            print(f"  - {step}")
    except (selfupdate.SelfUpdateError, OSError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_clamav(args) -> int:
    from .clamav_local import ClamavError, LocalClamav, manifest

    local = LocalClamav()
    try:
        if args.remove:
            local.uninstall()
            print("ClamAV integre supprime.")
        elif args.install:
            local.install(progress=lambda message: print(message, flush=True))
            print("ClamAV est installe et a jour : il sera utilise a chaque analyse.")
        elif args.update:
            print(local.update(progress=lambda message: print(message, flush=True)))
        else:
            info = manifest()
            state = ("pret" if local.ready() else "installe, sans signatures" if local.installed()
                     else "non installe")
            print(f"ClamAV integre : {state} ({local.root})")
            if not local.installed():
                print("Installation : freeav clamav --install" if info else
                      "Cette version de FreeAV ne propose pas l'installation de ClamAV.")
    except (ClamavError, OSError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    return 0


def _dialog(kind: str, title: str, message: str) -> bool:
    """Boite de dialogue Windows (FreeAV.exe n'a pas de console quand on le lance depuis
    Parametres > Applications ou un raccourci)."""
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        try:
            return bool(getattr(messagebox, kind)(title, message, parent=root))
        finally:
            root.destroy()
    except Exception:
        return kind != "askyesno"


def cmd_install(args) -> int:
    from . import installer
    from .repair import System

    try:
        done = installer.install(System())
    except (installer.InstallError, OSError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        if not args.quiet:
            _dialog("showerror", "FreeAV", f"Installation impossible : {exc}")
        return 2
    message = "FreeAV est installe :\n" + "\n".join(f"  - {d}" for d in done)
    print(message)
    if not args.quiet:
        _dialog("showinfo", "FreeAV", message)
    return 0


def cmd_uninstall(args) -> int:
    from . import installer
    from .repair import System

    if not args.yes and not _dialog(
            "askyesno", "Desinstaller FreeAV",
            "Desinstaller FreeAV de ce PC ?\n\nLa protection automatique, les raccourcis, le "
            "clic droit et le moteur ClamAV integre seront retires. Votre quarantaine est gardee."):
        return 1
    try:
        done = installer.uninstall(System())
    except (installer.InstallError, OSError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        if not args.yes:
            _dialog("showerror", "FreeAV", f"Desinstallation incomplete : {exc}")
        return 2
    message = "FreeAV est desinstalle :\n" + "\n".join(f"  - {d}" for d in done)
    print(message)
    if not args.yes:
        _dialog("showinfo", "FreeAV", message)
    return 0


def cmd_schedule(args) -> int:
    from . import schedule
    from .repair import System

    system = System()
    try:
        if args.status:
            for name, active in schedule.status(system).items():
                print(f"{name} : {'active' if active else 'inactive'}")
            return 0
        if args.remove:
            done = schedule.remove(system)
            print("\n".join(done) or "Rien a retirer.")
            return 0
        done = schedule.install(system, schedule.program_command(system), at=args.at,
                                realtime=not args.no_realtime)
    except (schedule.ScheduleError, OSError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    print("Protection automatique installee :\n" + "\n".join(f"  - {d}" for d in done)
          + "\nPour tout retirer : freeav schedule --remove")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="freeav", description="Antivirus gratuit FreeAV")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--quarantine-dir", default=str(DEFAULT_DIR))
    sub = parser.add_subparsers(dest="command", required=True)

    def engine_options(p):
        p.add_argument("--db", action="append", default=[],
                       help="base de signatures supplementaire (.txt, .hdb, .hsb)")
        p.add_argument("--clamav", action="store_true", help="utiliser aussi le demon clamd")
        p.add_argument("--clamd-socket", help="socket Unix de clamd")
        p.add_argument("--clamd-host", default="127.0.0.1")
        p.add_argument("--clamd-port", type=int, default=3310)
        p.add_argument("--allow-remote-clamd", action="store_true",
                       help="autoriser un clamd sur une autre machine (vos fichiers y seront envoyes)")
        p.add_argument("--yara", action="append", default=[], metavar="DOSSIER",
                       help="regles YARA (.yar) a appliquer, en plus de ~/.freeav/yara")
        p.add_argument("--defender", action="store_true",
                       help="deuxieme avis de Microsoft Defender (Windows)")
        p.add_argument("--no-clamav", action="store_true",
                       help="ne pas utiliser le ClamAV integre")

    scan = sub.add_parser("scan", help="analyser des fichiers ou dossiers")
    scan.add_argument("paths", nargs="+")
    engine_options(scan)
    scan.add_argument("--quarantine", action="store_true",
                      help="mettre les fichiers infectes en quarantaine")
    scan.set_defaults(func=cmd_scan)

    quar = sub.add_parser("quarantine", help="gerer la quarantaine")
    group = quar.add_mutually_exclusive_group()
    group.add_argument("--restore", metavar="ID")
    group.add_argument("--delete", metavar="ID")
    quar.set_defaults(func=cmd_quarantine)

    upd = sub.add_parser("update", help="telecharger les dernieres signatures publiques")
    upd.add_argument("--url", default=updater.MALWAREBAZAAR_URL, help=argparse.SUPPRESS)
    upd.add_argument("--auth-key", help="cle Auth-Key gratuite d'abuse.ch (https://auth.abuse.ch)")
    upd.add_argument("--save-key", action="store_true",
                     help="memoriser la cle pour les prochaines mises a jour")
    upd.set_defaults(func=cmd_update)

    rep = sub.add_parser("repair", help="diagnostiquer et reparer les problemes du PC")
    rep.add_argument("--fix", nargs="+", metavar="ID", help="reparer ces problemes")
    rep.add_argument("--fix-dangers", action="store_true",
                     help="reparer tous les problemes marques DANGER")
    rep.add_argument("--undo", nargs="?", const="", metavar="SAUVEGARDE",
                     help="annuler la derniere reparation (ou celle indiquee)")
    rep.add_argument("--list-backups", action="store_true", help="lister les sauvegardes")
    rep.add_argument("--yes", action="store_true",
                     help="confirmer les actions definitives (nettoyage, outils Windows)")
    rep.set_defaults(func=cmd_repair)

    watch = sub.add_parser("watch", help="protection en temps reel (Telechargements, Bureau)")
    watch.add_argument("folders", nargs="*", help="dossiers a surveiller")
    engine_options(watch)
    watch.add_argument("--quarantine", action="store_true",
                       help="mettre les menaces en quarantaine des leur arrivee")
    watch.add_argument("--notify", action="store_true", help="afficher une alerte Windows")
    watch.add_argument("--interval", type=float, default=2.0, help=argparse.SUPPRESS)
    watch.set_defaults(func=cmd_watch)

    auto = sub.add_parser("auto", help="entretien automatique (mise a jour, analyse, controle)")
    engine_options(auto)
    auto.add_argument("--notify", action="store_true", help="afficher une alerte Windows")
    auto.set_defaults(func=cmd_auto)

    appup = sub.add_parser("app-update", help="installer la derniere version de FreeAV (Windows)")
    appup.add_argument("--check", action="store_true", help="seulement verifier")
    appup.add_argument("--yes", action="store_true", help="installer sans demander")
    appup.add_argument("--from-file", help=argparse.SUPPRESS)
    appup.add_argument("--sha256", help=argparse.SUPPRESS)
    appup.add_argument("--build", type=int, default=0, help=argparse.SUPPRESS)
    appup.set_defaults(func=cmd_app_update)
    clam = sub.add_parser("clamav", help="moteur ClamAV integre (Windows)")
    clam_group = clam.add_mutually_exclusive_group()
    clam_group.add_argument("--install", action="store_true", help="installer ClamAV et ses signatures")
    clam_group.add_argument("--update", action="store_true", help="mettre a jour les signatures")
    clam_group.add_argument("--remove", action="store_true", help="supprimer ClamAV integre")
    clam.set_defaults(func=cmd_clamav)

    sched = sub.add_parser("schedule", help="installer la protection automatique (Windows)")
    sched.add_argument("--at", default="12:00", metavar="HH:MM",
                       help="heure de l'analyse quotidienne (12:00 par defaut)")
    sched.add_argument("--no-realtime", action="store_true",
                       help="ne pas lancer la protection en temps reel a l'ouverture de session")
    sched.add_argument("--remove", action="store_true", help="tout retirer")
    sched.add_argument("--status", action="store_true", help="voir ce qui est installe")
    sched.set_defaults(func=cmd_schedule)

    inst = sub.add_parser("install", help="installer FreeAV sur ce PC (Windows)")
    inst.add_argument("--quiet", action="store_true", help="sans fenetre de confirmation")
    inst.set_defaults(func=cmd_install)
    uninst = sub.add_parser("uninstall", help="desinstaller FreeAV (Windows)")
    uninst.add_argument("--yes", action="store_true", help="sans confirmation")
    uninst.set_defaults(func=cmd_uninstall)

    gui = sub.add_parser("gui", help="ouvrir l'interface graphique")
    gui.add_argument("--scan", metavar="CHEMIN", help="analyser tout de suite ce fichier ou dossier")
    gui.set_defaults(func=lambda a: __import__("freeav.gui", fromlist=["run"]).run(
        scan=scan_argument(a.scan)))

    args = parser.parse_args(argv)
    return args.func(args) or 0
