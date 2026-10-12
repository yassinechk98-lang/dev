"""Politique de confidentialite montree a la premiere ouverture de FreeAV, et ses deux reglages :
la recherche des nouvelles versions (github.com) et le 2e avis de Microsoft Defender.

Tant que la fenetre n'a pas ete validee, FreeAV ne cherche pas de nouvelle version."""

from . import selfupdate, updater

PRIVACY_URL = "https://freeav-antivirus-gratuit.netlify.app/confidentialite.html"
SEEN_SETTING = "privacy_seen"
DEFENDER_SETTING = "use_defender"

SUMMARY = (
    "FreeAV n'a pas de compte et n'envoie ni vos fichiers ni de donnees d'utilisation. Les "
    "analyses se font sur ce PC, sans reseau.\n\n"
    "FreeAV se connecte a Internet seulement pour :\n"
    "- chercher une nouvelle version de FreeAV (github.com), si la case ci-dessous est cochee, "
    "et la telecharger quand vous le demandez ;\n"
    "- telecharger des signatures, si vous enregistrez une cle abuse.ch (mb-api.abuse.ch) ;\n"
    "- installer ClamAV quand vous le demandez (github.com/Cisco-Talos) et mettre a jour ses "
    "signatures (database.clamav.net).\n\n"
    "Le 2e avis de Microsoft Defender analyse les memes dossiers. Defender suit ses propres "
    "reglages Windows : il peut envoyer des echantillons a Microsoft si la protection dans le "
    "cloud est activee dans Securite Windows.\n\n"
    "Vous pouvez changer ces choix a tout moment dans la fenetre principale.")


def needs_first_run() -> bool:
    return updater.load_setting(SEEN_SETTING, False, updater.CONFIG_FILE) is not True


def accept(check_updates: bool, defender: bool) -> None:
    selfupdate.set_auto_check(check_updates)
    set_defender(defender)
    updater.save_setting(SEEN_SETTING, True, updater.CONFIG_FILE)


def defender_enabled() -> bool:
    return updater.load_setting(DEFENDER_SETTING, True, updater.CONFIG_FILE) is not False


def set_defender(enabled: bool) -> None:
    updater.save_setting(DEFENDER_SETTING, bool(enabled), updater.CONFIG_FILE)
