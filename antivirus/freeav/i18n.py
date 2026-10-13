"""Langue de l'interface graphique : francais (par defaut) ou anglais.

Les textes de gui.py restent ecrits en francais et passent par _() ; EN donne leur traduction.
La langue est lue une seule fois (au premier texte affiche) : un changement s'applique au
prochain demarrage de FreeAV."""

from . import privacy, updater

LANG_SETTING = "language"
LANGUAGES = {"fr": "Français", "en": "English"}

_lang: str | None = None  # langue lue au premier appel de _()


def current() -> str:
    """Langue enregistree dans ~/.freeav/config.json : "fr" ou "en" (tout le reste vaut "fr")."""
    value = updater.load_setting(LANG_SETTING, None, updater.CONFIG_FILE)
    return value if isinstance(value, str) and value in LANGUAGES else "fr"


def set_language(code: str) -> None:
    if code not in LANGUAGES:
        raise ValueError(f"Langue inconnue : {code}")
    updater.save_setting(LANG_SETTING, code, updater.CONFIG_FILE)


def translate(text: str, lang: str) -> str:
    if lang == "en":
        return EN.get(text, text)
    return text


def _(text: str) -> str:
    global _lang
    if _lang is None:
        _lang = current()
    return translate(text, _lang)


EN = {
    # Fenetre principale
    "FreeAV {version} - Antivirus gratuit": "FreeAV {version} - Free antivirus",
    "Pret.": "Ready.",
    "Installer FreeAV sur ce PC": "Install FreeAV on this PC",
    "Dossier a analyser :": "Folder to scan:",
    "Parcourir...": "Browse...",
    "Analyse rapide": "Quick scan",
    "Analyser ce dossier": "Scan this folder",
    "Arreter": "Stop",
    "clamd (avance)": "clamd (advanced)",
    "Quarantaine...": "Quarantine...",
    "Reparer mon PC...": "Repair my PC...",
    "Mettre a jour les signatures": "Update signatures",
    "Moteurs : signatures FreeAV": "Engines: FreeAV signatures",
    "+ 2e avis Microsoft Defender": "+ Microsoft Defender second opinion",
    "Protection en temps reel (Telechargements et Bureau)":
        "Real-time protection (Downloads and Desktop)",
    "Protection automatique...": "Automatic protection...",
    "Confidentialite...": "Privacy...",
    "Chercher les nouvelles versions": "Check for new versions",
    "Menace": "Threat",
    "Moteur": "Engine",
    "Fichier": "File",
    "Mettre en quarantaine la selection": "Quarantine selected",
    "Redemarrez FreeAV pour appliquer la nouvelle langue.":
        "Restart FreeAV to apply the new language.",
    "Chemin introuvable :\n{target}": "Path not found:\n{target}",
    "clamd injoignable : signatures uniquement.": "clamd is unreachable: using signatures only.",
    "Analyse approfondie par {engine}...": "In-depth scan by {engine}...",
    "L'analyse a echoue : {error}": "The scan failed: {error}",
    "Attention : {count} menace(s) trouvee(s) lors de la derniere analyse":
        "Warning: {count} threat(s) found in the last scan",
    "Protection FreeAV active (Telechargements, Bureau, cles USB) : "
    "gardez Microsoft Defender active":
        "FreeAV protection is on (Downloads, Desktop, USB drives): keep Microsoft Defender "
        "turned on",
    "Protection en temps reel desactivee : cochez-la ci-dessous":
        "Real-time protection is off: turn it on below",
    "ClamAV integre": "Built-in ClamAV",
    "Microsoft Defender": "Microsoft Defender",
    "+ ClamAV integre : non utilise en administrateur":
        "+ Built-in ClamAV: not used when running as administrator",
    "+ ClamAV integre : pret": "+ Built-in ClamAV: ready",
    "+ ClamAV integre : non installe": "+ Built-in ClamAV: not installed",
    "Mettre a jour ClamAV": "Update ClamAV",
    "Installer ClamAV (gratuit)": "Install ClamAV (free)",
    "Installer le moteur antivirus ClamAV (Cisco Talos, gratuit, licence GPL-2.0) ?\n\n"
    "FreeAV telecharge ClamAV depuis le site officiel de Cisco Talos, puis ses signatures "
    "officielles (environ 300 Mo). Les analyses deviennent plus completes et plus longues.\n\n"
    "Le module RAR de ClamAV, dont la licence n'est pas libre, n'est pas installe : "
    "l'interieur des archives RAR n'est pas analyse.":
        "Install the ClamAV antivirus engine (Cisco Talos, free, GPL-2.0 license)?\n\n"
        "FreeAV downloads ClamAV from the official Cisco Talos website, then its official "
        "signatures (about 300 MB). Scans become more thorough and take longer.\n\n"
        "ClamAV's RAR module, which is not under a free license, is not installed: the "
        "contents of RAR archives are not scanned.",
    "Signatures ClamAV a jour.": "ClamAV signatures are up to date.",
    "ClamAV est installe : il sera utilise a chaque analyse.":
        "ClamAV is installed: it will be used for every scan.",
    "ClamAV : {error}": "ClamAV: {error}",
    "Reglage non enregistre : {error}": "Setting not saved: {error}",
    "Mettre a jour FreeAV": "Update FreeAV",
    "Une nouvelle version de FreeAV est disponible (version {build}).":
        "A new version of FreeAV is available (version {build}).",
    "Installer la nouvelle version de FreeAV ?\n\nElle est telechargee depuis la page "
    "officielle de FreeAV sur GitHub et verifiee (empreinte SHA-256) avant de remplacer "
    "l'ancienne. FreeAV redemarre ensuite.":
        "Install the new version of FreeAV?\n\nIt is downloaded from FreeAV's official GitHub "
        "page and verified (SHA-256 checksum) before it replaces the current one. FreeAV then "
        "restarts.",
    "Attendez la fin de l'analyse en cours.": "Please wait for the current scan to finish.",
    "Mise a jour impossible : {error}": "Update failed: {error}",
    "FreeAV est a jour. Il va redemarrer.": "FreeAV is up to date and will now restart.",
    "Rouvrez FreeAV vous-meme ({error}).": "Please reopen FreeAV yourself ({error}).",
    "Installer FreeAV sur ce PC ? FreeAV va faire ces changements :\n- {changes}\n\n"
    "Rien d'autre n'est modifie. La protection en temps reel et l'analyse quotidienne restent "
    "a activer vous-meme.":
        "Install FreeAV on this PC? FreeAV will make these changes:\n- {changes}\n\n"
        "Nothing else is changed. You can turn on real-time protection and the daily scan "
        "yourself afterwards.",
    "FreeAV est installe :\n- {done}\n\nVous pouvez l'ouvrir depuis le menu Demarrer ou le "
    "Bureau.":
        "FreeAV is installed:\n- {done}\n\nYou can open it from the Start menu or the Desktop.",
    "Installation impossible : {error}": "Installation failed: {error}",
    "Protection en temps reel arretee.": "Real-time protection stopped.",
    "Aucun dossier Telechargements ou Bureau trouve.": "No Downloads or Desktop folder found.",
    "Protection en temps reel arretee : {error}": "Real-time protection stopped: {error}",
    "Protection en temps reel active : {folders}": "Real-time protection is on: {folders}",
    "{path} : {message}": "{path}: {message}",
    " (suspect)": " (suspicious)",
    "quarantaine": "quarantined",
    "FreeAV - protection en temps reel": "FreeAV - real-time protection",
    "Cle abuse.ch": "abuse.ch key",
    "MalwareBazaar demande une cle gratuite (Auth-Key).\n"
    "Creez-la sur https://auth.abuse.ch puis collez-la ici :":
        "MalwareBazaar requires a free key (Auth-Key).\n"
        "Create one at https://auth.abuse.ch, then paste it here:",
    "Telechargement des signatures MalwareBazaar...": "Downloading MalwareBazaar signatures...",
    "{added} nouvelles signatures, {total} au total.": "{added} new signatures, {total} in total.",
    "Analyse : {path}": "Scanning: {path}",
    "Aucune menace detectee.": "No threats found.",
    "{threats} menace(s), {suspects} suspect(s) a verifier.":
        "{threats} threat(s), {suspects} suspicious item(s) to check.",
    " {count} fichier(s) illisible(s).": " {count} file(s) could not be read.",
    "{scanned} fichiers analyses. {verdict}": "{scanned} files scanned. {verdict}",
    "Echec pour {path} :\n{error}": "Failed for {path}:\n{error}",
    "{moved} fichier(s) mis en quarantaine, {remaining} menace(s) restante(s).":
        "{moved} file(s) quarantined, {remaining} threat(s) remaining.",
    # Quarantaine
    "Quarantaine": "Quarantine",
    "Emplacement d'origine": "Original location",
    "Restaurer": "Restore",
    "Supprimer definitivement": "Delete permanently",
    # Reparer mon PC
    "Danger": "Danger",
    "Suspect": "Suspicious",
    "Info": "Info",
    "Outil": "Tool",
    "{status} - {title} : {message}": "{status} - {title}: {message}",
    "OK": "OK",
    "ECHEC": "FAILED",
    "Reparer mon PC": "Repair my PC",
    "Diagnostic en cours (rien n'est modifie)...": "Running diagnostics (nothing is changed)...",
    "Gravite": "Severity",
    "Categorie": "Category",
    "Probleme": "Problem",
    "Detail": "Details",
    "Reparer la selection": "Repair selected",
    "Annuler la derniere reparation": "Undo last repair",
    "Actualiser": "Refresh",
    "\nVous pouvez tout annuler avec « Annuler la derniere reparation ».":
        "\nYou can undo all of it with \"Undo last repair\".",
    "Erreur : {error}": "Error: {error}",
    " (admin)": " (admin required)",
    "{count} probleme(s) a examiner.": "{count} problem(s) to review.",
    "Aucun probleme important detecte.": "No significant problems found.",
    "Selectionnez un ou plusieurs problemes reparables dans la liste.":
        "Select one or more repairable problems in the list.",
    "- {title} : {fix}": "- {title}: {fix}",
    " (DEFINITIF)": " (PERMANENT)",
    "\n\nAttention : les actions marquees DEFINITIF ne pourront pas etre annulees (fichiers "
    "temporaires supprimes, outils Windows).":
        "\n\nWarning: actions marked PERMANENT cannot be undone (deleted temporary files, "
        "Windows tools).",
    "Les autres modifications sont sauvegardees et annulables.":
        "All other changes are backed up and can be undone.",
    "Toutes ces modifications sont sauvegardees et annulables.":
        "All these changes are backed up and can be undone.",
    "FreeAV va effectuer :\n{text}{warning}\n\n{undoable} Continuer ?":
        "FreeAV will do the following:\n{text}{warning}\n\n{undoable} Continue?",
    "Reparation en cours...": "Repairing...",
    "Aucune reparation a annuler.": "There are no repairs to undo.",
    "Annuler la derniere serie de reparations ?": "Undo the last set of repairs?",
    # Protection automatique
    "Protection automatique": "Automatic protection",
    "Chaque jour, FreeAV met a jour ses signatures (si une cle abuse.ch est enregistree), "
    "analyse vos Telechargements et votre Bureau, verifie les points sensibles du PC et vous "
    "previent en cas de probleme. Aucun droit administrateur n'est necessaire et tout se "
    "retire en un clic.":
        "Every day, FreeAV updates its signatures (if an abuse.ch key is saved), scans your "
        "Downloads and Desktop, checks the sensitive areas of your PC and alerts you if "
        "something is wrong. No administrator rights are needed, and everything can be removed "
        "in one click.",
    "Heure de l'analyse :": "Scan time:",
    "Proteger aussi en temps reel a chaque ouverture de session":
        "Also turn on real-time protection every time I sign in",
    "Activer": "Turn on",
    "Tout retirer": "Remove all",
    "Fermer": "Close",
    "{name} : {state}": "{name}: {state}",
    "active": "on",
    "inactive": "off",
    "Protection automatique activee :\n- {done}": "Automatic protection turned on:\n- {done}",
    "Retirer aussi ClamAV et ses signatures (environ 450 Mo) ?\n\nDossier : {folder}":
        "Also remove ClamAV and its signatures (about 450 MB)?\n\nFolder: {folder}",
    "ClamAV et ses signatures retires": "ClamAV and its signatures removed",
    "Rien a retirer.": "Nothing to remove.",
    # Confidentialite
    "FreeAV - Confidentialite": "FreeAV - Privacy",
    privacy.SUMMARY:
        "FreeAV has no account and sends neither your files nor usage data. Scans run on this "
        "PC, without the network.\n\n"
        "FreeAV connects to the Internet only to:\n"
        "- check for a new version of FreeAV (github.com), if the box below is checked, and "
        "download it when you ask;\n"
        "- download signatures, if you save an abuse.ch key (mb-api.abuse.ch);\n"
        "- install ClamAV when you ask (github.com/Cisco-Talos) and update its signatures "
        "(database.clamav.net).\n\n"
        "The Microsoft Defender second opinion scans the same folders. Defender follows its own "
        "Windows settings: it may send samples to Microsoft if cloud-delivered protection is "
        "turned on in Windows Security.\n\n"
        "You can change these choices at any time in the main window.",
    "Politique complete : {url}": "Full policy: {url}",
    "Chercher les nouvelles versions de FreeAV (github.com)":
        "Check for new FreeAV versions (github.com)",
    "2e avis Microsoft Defender pendant les analyses":
        "Microsoft Defender second opinion during scans",
    "Valider": "OK",
    "Reglages non enregistres : {error}": "Settings not saved: {error}",
}
