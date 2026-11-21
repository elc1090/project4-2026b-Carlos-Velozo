"""Fabrica da aplicação MapeiaSUS."""

import click
from flask import (
    Flask,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from sqlalchemy import inspect, text
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import csrf, db, login_manager
from models import User
from utils import email_valido

# Rotas que continuam acessíveis quando REQUIRE_LOGIN=true.
ENDPOINTS_PUBLICOS = frozenset(
    {
        "static",
        "public.health",
        "auth.login",
        "auth.register",
        "auth.google_login",
    }
)


@login_manager.user_loader
def carregar_usuario(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def _registar_guardas(app: Flask) -> None:
    """Exige login quando REQUIRE_LOGIN=true."""

    @app.before_request
    def exigir_autenticacao():
        if not app.config.get("REQUIRE_LOGIN"):
            return None
        if request.endpoint in ENDPOINTS_PUBLICOS:
            return None
        if current_user.is_authenticated:
            return None

        if request.path.startswith("/api/"):
            return jsonify({"error": "Autenticação necessária."}), 401

        destino = request.full_path.rstrip("?")
        return redirect(url_for("auth.login", next=destino))


def _registar_tratamento_erros(app: Flask) -> None:
    @app.errorhandler(CSRFError)
    def erro_csrf(erro):
        if request.path.startswith(("/api/", "/auth/google")) or request.is_json:
            return jsonify({"error": "Token CSRF inválido ou expirado."}), 400
        return render_template("errors/400.html", motivo=erro.description), 400

    @app.errorhandler(403)
    def acesso_negado(erro):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Acesso negado."}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def nao_encontrado(erro):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Recurso não encontrado."}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def arquivo_muito_grande(erro):
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"error": "Arquivo muito grande."}), 413
        return (
            render_template(
                "errors/413.html",
                motivo="A imagem enviada excede o limite de 5 MB.",
            ),
            413,
        )


def _registar_comandos(app: Flask) -> None:
    def criar_utilizador(email, nome, password, admin):
        email = (email or "").strip().lower()
        nome = (nome or "").strip() or None

        if not email_valido(email):
            raise click.ClickException("E-mail inválido.")
        if len(password) < 8:
            raise click.ClickException("A senha deve ter pelo menos 8 caracteres.")

        existente = (
            db.session.query(User)
            .filter(db.func.lower(User.email) == email)
            .first()
        )
        if existente is not None:
            raise click.ClickException(f"Já existe um usuário com o e-mail {email}.")

        utilizador = User(
            email=email,
            nome=nome,
            role="admin" if admin else "user",
        )
        utilizador.definir_senha(password)
        db.session.add(utilizador)
        db.session.commit()
        click.echo(f"Usuário criado: {email} ({utilizador.role})")

    @app.cli.command("create-user")
    @click.option("--email", prompt="E-mail")
    @click.option("--nome", prompt="Nome", default="")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option("--admin", is_flag=True, help="Concede o papel de administrador.")
    def create_user(email, nome, password, admin):
        """Cria um usuário. Use --admin para administrador."""
        criar_utilizador(email, nome, password, admin)

    @app.cli.command("create-admin")
    @click.option("--email", prompt="E-mail")
    @click.option("--nome", prompt="Nome", default="")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(email, nome, password):
        """Cria um usuário com papel de administrador."""
        criar_utilizador(email, nome, password, True)

    @app.cli.command("set-password")
    @click.option("--email", prompt="E-mail")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def set_password(email, password):
        """Redefine a senha de um usuário existente."""
        email = (email or "").strip().lower()

        if len(password) < 8:
            raise click.ClickException("A senha deve ter pelo menos 8 caracteres.")

        utilizador = (
            db.session.query(User)
            .filter(db.func.lower(User.email) == email)
            .first()
        )
        if utilizador is None:
            raise click.ClickException(f"Usuário não encontrado: {email}")

        utilizador.definir_senha(password)
        db.session.commit()
        click.echo(f"Senha atualizada: {email}")


def _migrar_historico_por_cliente() -> None:
    """Adiciona cliente_id ao histórico de bancos antigos."""
    tabela = "historico_buscas"
    colunas = {coluna["name"] for coluna in inspect(db.engine).get_columns(tabela)}
    if "cliente_id" not in colunas:
        with db.engine.begin() as conexao:
            conexao.execute(
                text(f"ALTER TABLE {tabela} ADD COLUMN cliente_id VARCHAR(64)")
            )
            conexao.execute(
                text(
                    f"UPDATE {tabela} SET cliente_id = 'u:' || user_id "
                    "WHERE user_id IS NOT NULL"
                )
            )

    with db.engine.begin() as conexao:
        conexao.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_historico_buscas_cliente_id "
                f"ON {tabela} (cliente_id)"
            )
        )


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    # O proxy termina o TLS; sem isto url_for gera http.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    db.init_app(app)
    login_manager.init_app(app)
    # Antes do CSRF: sem sessão, não faz sentido exigir token.
    _registar_guardas(app)
    csrf.init_app(app)

    from admin.routes import bp as admin_bp
    from auth.routes import bp as auth_bp
    from public.routes import bp as public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    _registar_tratamento_erros(app)
    _registar_comandos(app)

    # Cria tabelas em falta; os dados vêm do seed.
    if app.config.get("AUTO_CREATE_TABLES"):
        with app.app_context():
            db.create_all()
            _migrar_historico_por_cliente()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
