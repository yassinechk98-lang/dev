# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Yassine

"""Ecrans de connexion (Tkinter) : connexion, code OTP, mot de passe oublie, creation de
l'acces, reglages et verrouillage. Ignores sans affichage (CI Linux) ; lances sur Windows."""

import time

import pytest

from freeav import login, updater

tk = pytest.importorskip("tkinter")
login_gui = pytest.importorskip("freeav.login_gui")

PASSWORD = "cheval-batterie-agrafe"
NEW_PASSWORD = "nouveau-mot-de-passe-1"


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"pas d'affichage : {exc}")
    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture(autouse=True)
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(login, "SCRYPT", {"n": 2 ** 10, "r": 8, "p": 1})
    monkeypatch.setattr(login, "SCRYPT_RECOVERY", {"n": 2 ** 10, "r": 8, "p": 1})
    monkeypatch.setattr(login, "LOGIN_FILE", tmp_path / "login.json")
    monkeypatch.setattr(updater, "CONFIG_FILE", tmp_path / "config.json")
    return tmp_path


def wait_for(root, condition, timeout=10.0):
    """Fait tourner l'interface jusqu'a ce que la condition soit vraie."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root.update()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("l'interface n'a pas atteint l'etat attendu")


def gone(window):
    return lambda: not window.winfo_exists()


def heading(window) -> str:
    """Titre de l'ecran affiche."""
    labels = [w for w in window.content.winfo_children() if isinstance(w, tk.Label)]
    return labels[0].cget("text") if labels else ""


def showing(window, title):
    return lambda: window.winfo_exists() and heading(window) == title


def sign_in(root, window, nickname="Yassine", password=PASSWORD):
    window.f_nick.set(nickname)
    window.f_pass.set(password)
    window.submit_login()


def test_without_login_freeav_opens_directly():
    assert login_gui.unlock() is True


def test_sign_in_with_nickname_and_password(root):
    login.create("Yassine", PASSWORD)
    window = login_gui.AccessWindow(root, "open")
    assert heading(window) == "Bon retour"
    sign_in(root, window)
    wait_for(root, gone(window))
    assert window.result is True


def test_wrong_password_gives_the_generic_message(root):
    login.create("Yassine", PASSWORD)
    window = login_gui.AccessWindow(root, "open")
    sign_in(root, window, password="pas-le-bon-mot-de-passe")
    wait_for(root, lambda: window.notice.text)
    assert window.notice.text == login.GENERIC_ERROR
    assert window.f_pass.get() == ""  # le mot de passe refuse est efface
    sign_in(root, window, nickname="Quelquun")
    wait_for(root, lambda: not window.busy)
    assert window.notice.text == login.GENERIC_ERROR  # meme message si le pseudo est faux
    window.destroy()


def test_too_many_attempts_disable_the_button(root):
    login.create("Yassine", PASSWORD)
    window = login_gui.AccessWindow(root, "open")
    for _ in range(login.MAX_FAILURES):
        sign_in(root, window, password="pas-le-bon-mot-de-passe")
        wait_for(root, lambda: not window.busy)
    assert "Réessayez dans" in window.notice.text
    assert window.primary.enabled is False
    window.destroy()


def test_second_step_asks_for_the_otp_code(root):
    secret = login.new_otp_secret()
    then = time.time() - 90
    login.create("Yassine", PASSWORD, secret, login.totp(secret, then), now=then)
    window = login_gui.AccessWindow(root, "open")
    sign_in(root, window)
    wait_for(root, showing(window, "Vérification en deux étapes"))
    window.boxes.set("000000" if login.totp(secret) != "000000" else "111111")
    window.submit_code()
    wait_for(root, lambda: window.notice.text)
    assert window.notice.text == login.CODE_ERROR
    assert window.boxes.get() == ""
    window.boxes.set(login.totp(secret))
    window.submit_code()
    wait_for(root, gone(window))
    assert window.result is True


def test_recovery_code_instead_of_the_app(root):
    secret = login.new_otp_secret()
    then = time.time() - 90
    codes = login.create("Yassine", PASSWORD, secret, login.totp(secret, then), now=then)
    window = login_gui.AccessWindow(root, "open")
    sign_in(root, window)
    wait_for(root, showing(window, "Vérification en deux étapes"))
    window.show_code(recovery=True)
    window.f_code.set(codes[0].lower())
    window.submit_code()
    wait_for(root, showing(window, "Bienvenue, Yassine"))
    window.primary.invoke()  # « Continuer » apres avoir vu le nombre de codes restants
    assert window.result is True
    assert len(login.load().recovery) == login.RECOVERY_CODES - 1


def test_forgot_password_with_a_recovery_code(root):
    codes = login.create("Yassine", PASSWORD)
    window = login_gui.AccessWindow(root, "open")
    window.show_forgot()
    window.f_nick.set("Yassine")
    window.f_code.set(codes[3])
    window.f_new.set(NEW_PASSWORD)
    window.f_confirm.set("autre-chose-encore")
    window.submit_forgot()
    assert window.notice.text == "Les deux mots de passe ne sont pas identiques."
    window.f_confirm.set(NEW_PASSWORD)
    window.submit_forgot()
    wait_for(root, showing(window, "Mot de passe changé"))
    window.primary.invoke()
    assert heading(window) == "Bon retour"
    sign_in(root, window, password=NEW_PASSWORD)
    wait_for(root, gone(window))
    assert window.result is True


def test_forgot_password_refuses_a_wrong_code(root):
    login.create("Yassine", PASSWORD)
    window = login_gui.AccessWindow(root, "open")
    window.show_forgot()
    window.f_nick.set("Yassine")
    window.f_code.set("AAAA-BBBB")
    window.f_new.set(NEW_PASSWORD)
    window.f_confirm.set(NEW_PASSWORD)
    window.submit_forgot()
    wait_for(root, lambda: not window.busy)
    assert window.notice.text == "Pseudo ou code incorrect."
    login.verify("Yassine", PASSWORD)  # l'ancien mot de passe marche toujours
    window.destroy()


def test_setup_without_otp(root):
    window = login_gui.AccessWindow(root, "setup")
    window.f_nick.set("Yassine")
    window.f_pass.set("court")
    window.f_confirm.set("court")
    window.submit_account()
    assert "12" in window.notice.text
    window._otp_switched(False)
    window.f_pass.set(PASSWORD)
    window.f_confirm.set(PASSWORD)
    window.submit_account()
    wait_for(root, showing(window, "Notez vos codes de secours"))
    assert window.primary.enabled is False  # il faut d'abord cocher la case
    window.confirm_box.toggle()
    window.primary.invoke()
    assert heading(window) == "FreeAV est protégé"
    window.primary.invoke()
    assert window.result is True
    account = login.load()
    assert account.nickname == "Yassine" and not account.otp
    login.verify("Yassine", PASSWORD)


def test_setup_with_otp_and_qr_code(root):
    window = login_gui.AccessWindow(root, "setup")
    window.f_nick.set("Yassine")
    window.f_pass.set(PASSWORD)
    window.f_confirm.set(PASSWORD)
    window.submit_account()
    assert heading(window) == "Scannez ce QR code"
    assert not login.enabled()  # rien n'est enregistre avant le bon code
    window.boxes.set(login.totp(window.secret))
    window.submit_qr()
    wait_for(root, showing(window, "Notez vos codes de secours"))
    assert login.load().otp_secret == window.secret


def test_manage_needs_the_password_then_changes_settings(root):
    login.create("Yassine", PASSWORD)
    window = login_gui.AccessWindow(root, "manage")
    assert window.f_nick.get() == "Yassine"
    sign_in(root, window)
    wait_for(root, showing(window, "Connexion à FreeAV"))
    window.show_change_password()
    window.f_new.set(NEW_PASSWORD)
    window.f_confirm.set(NEW_PASSWORD)
    window._save_password("Yassine")
    wait_for(root, showing(window, "Connexion à FreeAV"))
    assert window.notice.text == "Mot de passe changé."
    login.verify("Yassine", NEW_PASSWORD)
    window._renew()
    wait_for(root, showing(window, "Notez vos codes de secours"))
    window.confirm_box.toggle()
    window.primary.invoke()
    wait_for(root, showing(window, "Connexion à FreeAV"))
    window._remove()
    wait_for(root, showing(window, "Connexion retirée"))
    assert not login.enabled()
    window.destroy()


def test_enable_otp_from_the_settings(root):
    login.create("Yassine", PASSWORD)
    window = login_gui.AccessWindow(root, "manage")
    sign_in(root, window)
    wait_for(root, showing(window, "Connexion à FreeAV"))
    window.show_qr(enabling=True)
    window.boxes.set(login.totp(window.secret))
    window.submit_qr()
    wait_for(root, showing(window, "Connexion à FreeAV"))
    assert login.load().otp
    window.destroy()


def test_lock_hides_the_main_window_until_sign_in(root):
    login.create("Yassine", PASSWORD)
    app = tk.Toplevel(root)
    app.banner = tk.Frame(app)
    app.banner.pack()
    app.watch_stop = None
    login_gui.attach(app, offer_now=False)
    assert app.lock_btn.winfo_manager() == "pack"  # « Verrouiller » visible

    def unlock_it():
        window = next(w for w in app.winfo_children() if isinstance(w, login_gui.AccessWindow))
        assert app.state() == "withdrawn"
        sign_in(root, window)
    root.after(300, unlock_it)
    login_gui.lock(app)
    assert app.winfo_exists() and app.state() == "normal"
    app.destroy()


def test_offer_is_shown_only_once(root):
    app = tk.Toplevel(root)
    app.banner = tk.Frame(app)
    login_gui.attach(app, offer_now=False)
    shown = []

    def later():  # « Plus tard »
        shown.extend(w for w in app.winfo_children() if isinstance(w, login_gui.AccessWindow))
        shown[0].finish(None)
    root.after(300, later)
    login_gui.offer(app)
    assert len(shown) == 1
    login_gui.offer(app)  # deja proposee : rien ne s'ouvre
    assert updater.load_setting(login_gui.OFFERED_SETTING, False, updater.CONFIG_FILE) is True
    app.destroy()


def test_code_boxes_accept_a_pasted_code(root):
    got = []
    boxes = login_gui.CodeBoxes(root, got.append)
    boxes.pack()
    root.clipboard_clear()
    root.clipboard_append("123 456")
    boxes._paste()
    wait_for(root, lambda: got)
    assert got == ["123456"]


def test_strength_meter_labels(root):
    meter = login_gui.StrengthMeter(root)
    meter.update_for("")
    assert meter.label.cget("text") == "12 caractères ou plus"
    meter.update_for("court")
    assert meter.label.cget("text") == "Trop court"
    meter.update_for("motdepasse123")
    assert meter.label.cget("text") == "Trop facile"
    meter.update_for("Tr3s-l0ng-et-varie-!")
    assert meter.score >= 3
