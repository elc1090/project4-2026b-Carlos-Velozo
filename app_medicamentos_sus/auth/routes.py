"""Rotas de autenticação: login, cadastro, Google e logout."""

from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import User
from utils import email_valido

from .forms import LoginForm, RegisterForm
from .google import verificar_credencial_google

bp = Blueprint("auth", __name__)


def _destino_seguro(next_url: str | None) -> str | None:
    """Aceita apenas caminhos relativos, evitando open redirect."""
    if not next_url:
        return None
    if next_url.startswith(("//", "/\\", "\\\\")):
        return None
    partes = urlsplit(next_url)
    if partes.scheme or partes.netloc:
        return None
    return next_url


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("public.index"))

    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        utilizador = (
            db.session.query(User)
            .filter(db.func.lower(User.email) == email)
            .first()
        )

        # Não revela se o e-mail existe.
        if (
            utilizador is None
            or not utilizador.ativo
            or not utilizador.verificar_senha(form.senha.data)
        ):
            flash("E-mail ou senha inválidos.", "error")
            return render_template("auth/login.html", form=form)

        # E-mails em ADMIN_EMAILS recebem o papel de administrador.
        admins = current_app.config.get("ADMIN_EMAILS") or []
        if email in admins and not utilizador.is_admin:
            utilizador.role = "admin"
            db.session.commit()

        # Limpa a sessão antes de autenticar.
        session.clear()
        login_user(utilizador, remember=form.lembrar.data)
        flash(f"Bem-vindo, {utilizador.nome or utilizador.email}!", "success")

        destino = _destino_seguro(request.args.get("next"))
        if destino:
            return redirect(destino)
        if utilizador.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("public.index"))

    return render_template("auth/login.html", form=form)


@bp.route("/registrar", methods=["GET", "POST"])
def register():
    """Cadastro público por e-mail e senha."""
    if current_user.is_authenticated:
        return redirect(url_for("public.index"))

    if not current_app.config.get("ALLOW_REGISTRATION", True):
        flash(
            "O cadastro público está desativado. Peça a um administrador "
            "para criar sua conta.",
            "warning",
        )
        return redirect(url_for("auth.login"))

    form = RegisterForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        admins = current_app.config.get("ADMIN_EMAILS") or []
        utilizador = User(
            email=email,
            nome=(form.nome.data or "").strip() or None,
            role="admin" if email in admins else "user",
        )
        utilizador.definir_senha(form.senha.data)
        db.session.add(utilizador)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.email.errors.append("Já existe uma conta com este e-mail.")
        else:
            # Limpa a sessão antes de autenticar.
            session.clear()
            login_user(utilizador)
            flash(
                f"Conta criada. Bem-vindo, {utilizador.nome or utilizador.email}!",
                "success",
            )
            if utilizador.is_admin:
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("public.index"))

    return render_template("auth/register.html", form=form)


@bp.post("/auth/google")
def google_login():
    """Login com ID token do Google."""
    client_id = (current_app.config.get("GOOGLE_CLIENT_ID") or "").strip()
    if not client_id:
        return jsonify({"error": "Login com Google não está configurado."}), 503

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        dados = request.form

    credential = (dados.get("credential") or "").strip()
    if not credential:
        return jsonify({"error": "Credencial do Google ausente."}), 400

    info = verificar_credencial_google(credential, client_id)
    if info is None:
        return jsonify({"error": "Credencial do Google inválida ou expirada."}), 401

    email = (info.get("email") or "").strip().lower()
    google_sub = (info.get("sub") or "").strip()
    if not google_sub or not email_valido(email):
        return jsonify({"error": "Conta do Google sem e-mail válido."}), 401

    utilizador = User.query.filter_by(google_sub=google_sub).first()

    if utilizador is not None:
        if not utilizador.ativo:
            return jsonify({"error": "Conta desativada."}), 403
    else:
        # Conta antiga (CLI ou senha): vincula pelo e-mail verificado.
        utilizador = (
            db.session.query(User)
            .filter(db.func.lower(User.email) == email)
            .first()
        )
        if utilizador is not None:
            if not utilizador.ativo:
                return jsonify({"error": "Conta desativada."}), 403
            if utilizador.google_sub and utilizador.google_sub != google_sub:
                return jsonify(
                    {"error": "Este e-mail já está vinculado a outra conta Google."}
                ), 409
            utilizador.google_sub = google_sub

    nome_google = (info.get("name") or "").strip()[:120] or None
    admins = current_app.config.get("ADMIN_EMAILS") or []

    if utilizador is None:
        utilizador = User(
            email=email,
            nome=nome_google,
            google_sub=google_sub,
            role="admin" if email in admins else "user",
        )
        db.session.add(utilizador)
    else:
        if not utilizador.nome and nome_google:
            utilizador.nome = nome_google
        if email in admins and not utilizador.is_admin:
            utilizador.role = "admin"

    db.session.commit()

    # Limpa a sessão antes de autenticar.
    session.clear()
    login_user(utilizador)
    flash(f"Bem-vindo, {utilizador.nome or utilizador.email}!", "success")

    destino = _destino_seguro(dados.get("next"))
    if destino:
        return jsonify({"ok": True, "redirect": destino})
    if utilizador.is_admin:
        return jsonify({"ok": True, "redirect": url_for("admin.dashboard")})
    return jsonify({"ok": True, "redirect": url_for("public.index")})


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada.", "success")
    if current_app.config.get("REQUIRE_LOGIN"):
        return redirect(url_for("auth.login"))
    return redirect(url_for("public.index"))
