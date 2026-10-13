import ast
import string
from pathlib import Path

import pytest

from freeav import i18n, privacy, updater

GUI = Path(i18n.__file__).with_name("gui.py")


@pytest.fixture
def config(tmp_path, monkeypatch):
    """Reglages dans un dossier temporaire (jamais le vrai ~/.freeav), langue relue."""
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(updater, "CONFIG_FILE", cfg)
    monkeypatch.setattr(i18n, "_lang", None)
    return cfg


def gui_strings():
    """Chaque texte litteral passe a _() ou i18n.translate() dans gui.py."""
    found = []
    for node in ast.walk(ast.parse(GUI.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name in ("_", "translate") and isinstance(node.args[0], ast.Constant):
            found.append(node.args[0].value)
    return found


def test_french_is_the_default(config):
    assert i18n.current() == "fr"
    assert i18n._("Analyse rapide") == "Analyse rapide"
    assert i18n._("Texte sans traduction") == "Texte sans traduction"
    assert not config.exists()


def test_english_returns_translations(config):
    i18n.set_language("en")
    assert updater.load_setting(i18n.LANG_SETTING, None, config) == "en"
    assert i18n.current() == "en"
    assert i18n._("Analyse rapide") == "Quick scan"
    assert i18n._("Analyse : {path}").format(path="C:\\a") == "Scanning: C:\\a"
    assert i18n._(privacy.SUMMARY).startswith("FreeAV has no account")
    assert i18n._("Texte sans traduction") == "Texte sans traduction"


def test_language_is_read_once(config):
    assert i18n._("Analyse rapide") == "Analyse rapide"
    i18n.set_language("en")
    assert i18n._("Analyse rapide") == "Analyse rapide"  # applique au prochain demarrage


@pytest.mark.parametrize("value", ["de", "", 3, None, ["en"]])
def test_unknown_language_falls_back_to_french(config, value):
    updater.save_setting(i18n.LANG_SETTING, value, config)
    assert i18n.current() == "fr"
    assert i18n._("Analyse rapide") == "Analyse rapide"


def test_set_language_rejects_unknown_code(config):
    with pytest.raises(ValueError):
        i18n.set_language("de")


def test_french_template_is_unchanged():
    assert i18n.translate("Analyse : {path}", "fr").format(path="x") == "Analyse : x"
    assert i18n.translate(privacy.SUMMARY, "fr") is privacy.SUMMARY


def test_every_gui_string_has_an_english_translation():
    strings = gui_strings()
    assert len(strings) > 100
    missing = sorted({s for s in strings if s not in i18n.EN})
    assert not missing, missing


def test_translations_keep_the_same_placeholders():
    def fields(text):
        return sorted(f for _, f, _, _ in string.Formatter().parse(text) if f is not None)

    for french, english in i18n.EN.items():
        assert english.strip(), french
        assert fields(french) == fields(english), french
