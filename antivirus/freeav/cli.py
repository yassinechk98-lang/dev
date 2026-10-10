"""Interface en ligne de commande : python -m freeav scan <chemin>..."""

import argparse
import sys
from pathlib import Path

from . import __version__, updater, yara_engine
from .clamav import ClamdClient, ClamdError
from .paths import APP_DIR, YARA_DIR
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


def build_scanner(args) -> Scanner:
    db = load_default([Path(p) for p in args.db])
    clamd = None
    if args.clamav:
        clamd = ClamdClient(unix_socket=args.clamd_socket, host=args.clamd_host,
                            port=args.clamd_port, allow_remote=args.allow_remote_clamd)
        if not clamd.ping():
            print("Attention : clamd injoignable, analyse par signatures uniquement.",
                  file=sys.stderr)
            clamd = None
    return Scanner(db, clamd, yara=build_yara(args.yara))


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
    print(f"FreeAV {__version__} : {len(scanner.db)} signatures chargees"
          + (f", {len(scanner.yara)} fichiers de regles YARA" if scanner.yara else "")
          + (", moteur ClamAV actif" if scanner.clamd else ""))
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
        backups = repair.list_backups()
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
    if repair.create_restore_point(system):
        print("Point de restauration Windows cree.")
    results, journal = repair.apply_fixes(chosen, system)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="freeav", description="Antivirus gratuit FreeAV")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--quarantine-dir", default=str(DEFAULT_DIR))
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="analyser des fichiers ou dossiers")
    scan.add_argument("paths", nargs="+")
    scan.add_argument("--db", action="append", default=[],
                      help="base de signatures supplementaire (.txt, .hdb, .hsb)")
    scan.add_argument("--quarantine", action="store_true",
                      help="mettre les fichiers infectes en quarantaine")
    scan.add_argument("--clamav", action="store_true", help="utiliser aussi le demon clamd")
    scan.add_argument("--clamd-socket", help="socket Unix de clamd")
    scan.add_argument("--clamd-host", default="127.0.0.1")
    scan.add_argument("--clamd-port", type=int, default=3310)
    scan.add_argument("--allow-remote-clamd", action="store_true",
                      help="autoriser un clamd sur une autre machine (vos fichiers y seront envoyes)")
    scan.add_argument("--yara", action="append", default=[], metavar="DOSSIER",
                      help="regles YARA (.yar) a appliquer, en plus de ~/.freeav/yara")
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
    rep.set_defaults(func=cmd_repair)

    gui = sub.add_parser("gui", help="ouvrir l'interface graphique")
    gui.set_defaults(func=lambda _args: __import__("freeav.gui", fromlist=["run"]).run())

    args = parser.parse_args(argv)
    return args.func(args) or 0
