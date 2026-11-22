"""Painel de administração: dashboard e CRUD de farmácias/medicamentos."""

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from auth.decorators import admin_required
from extensions import db
from historico import historico_recente, termos_mais_pesquisados_geral
from models import Farmacia, FarmaciaMedicamento, Medicamento, User
from utils import remover_acentos

from .forms import AdministradorForm, FarmaciaForm, MedicamentoForm
from .uploads import guardar_imagem, remover_imagem

bp = Blueprint("admin", __name__, url_prefix="/admin")

POR_PAGINA = 15
MEDICAMENTOS_POR_PAGINA = 20


def _pagina(nome: str = "pagina") -> int:
    try:
        return max(1, int(request.args.get(nome, 1)))
    except (TypeError, ValueError):
        return 1


def _url_args(**mudancas) -> str:
    """Constrói uma URL do endpoint atual preservando os filtros da query."""
    valores = request.args.to_dict(flat=True)
    valores.update(request.view_args or {})
    for chave, valor in mudancas.items():
        if valor in (None, ""):
            valores.pop(chave, None)
        else:
            valores[chave] = valor
    return url_for(request.endpoint, **valores)


def _urls_pagina(parametro: str = "pagina"):
    """Devolve uma função que gera a URL de uma página específica."""

    def url(numero: int) -> str:
        return _url_args(**{parametro: numero})

    return url


def _ordenacao(modelo, padrao: str = "nome"):
    """Valida a ordenação pedida e devolve (chave, critério SQL)."""
    opcoes = {
        "nome": func.lower(modelo.nome).asc(),
        "nome_desc": func.lower(modelo.nome).desc(),
        "recentes": modelo.id.desc(),
        "antigas": modelo.id.asc(),
    }
    escolha = (request.args.get("ordenar") or padrao).strip()
    if escolha not in opcoes:
        escolha = padrao
    return escolha, opcoes[escolha]


def _ids_do_formulario(nome: str) -> set[int]:
    ids = set()
    for valor in request.form.getlist(nome):
        try:
            ids.add(int(valor))
        except (TypeError, ValueError):
            continue
    return ids


def _consulta_medicamentos(termo: str):
    consulta = Medicamento.query
    if termo:
        termo_norm = remover_acentos(termo)
        consulta = consulta.filter(
            or_(
                Medicamento.nome_busca.like(f"%{termo_norm}%"),
                Medicamento.apresentacao.ilike(f"%{termo}%"),
            )
        )
    return consulta


def _contexto_inventario(farmacia: Farmacia) -> dict:
    inv_termo = (request.args.get("inv_q") or "").strip()
    inventario = _consulta_medicamentos(inv_termo).order_by(
        func.lower(Medicamento.nome)
    ).paginate(
        page=_pagina("inv_pagina"),
        per_page=MEDICAMENTOS_POR_PAGINA,
        error_out=False,
    )

    ids = [medicamento.id for medicamento in inventario.items]
    vinculos = {}
    if ids:
        registos = FarmaciaMedicamento.query.filter(
            FarmaciaMedicamento.farmacia_id == farmacia.id,
            FarmaciaMedicamento.medicamento_id.in_(ids),
        ).all()
        vinculos = {registo.medicamento_id: registo for registo in registos}

    return {
        "inventario": inventario,
        "vinculos": vinculos,
        "inv_termo": inv_termo,
        "total_disponiveis": FarmaciaMedicamento.query.filter_by(
            farmacia_id=farmacia.id, disponivel=True
        ).count(),
    }


def _render_farmacia(form: FarmaciaForm, farmacia: Farmacia | None):
    contexto = {
        "form": form,
        "farmacia": farmacia,
        "url_args": _url_args,
        "url_pagina": _urls_pagina("inv_pagina"),
    }
    if farmacia is not None:
        contexto.update(_contexto_inventario(farmacia))
    return render_template("admin/farmacia_form.html", **contexto)


@bp.get("/")
@admin_required
def dashboard():
    estatisticas = {
        "farmacias": Farmacia.query.filter_by(ativo=True).count(),
        "medicamentos": Medicamento.query.filter_by(ativo=True).count(),
        "vinculos": FarmaciaMedicamento.query.filter_by(disponivel=True).count(),
        "usuarios": User.query.filter_by(ativo=True).count(),
    }
    # Recentes: só do admin. Ranking: agregado, sem identificar clientes.
    pesquisas = historico_recente(6)
    mais_pesquisados = termos_mais_pesquisados_geral(5)
    return render_template(
        "admin/dashboard.html",
        estatisticas=estatisticas,
        pesquisas=pesquisas,
        mais_pesquisados=mais_pesquisados,
    )


# -------------------------------------------------------------- administradores
def _render_administradores(form: AdministradorForm, termo: str = ""):
    consulta = User.query
    if termo:
        padrao = f"%{termo}%"
        consulta = consulta.filter(
            or_(User.nome.ilike(padrao), User.email.ilike(padrao))
        )

    paginacao = consulta.order_by(
        User.role.asc(), db.func.lower(User.email)
    ).paginate(page=_pagina(), per_page=POR_PAGINA, error_out=False)

    return render_template(
        "admin/administradores.html",
        form=form,
        paginacao=paginacao,
        termo=termo,
        admins_fixos={
            email.strip().lower()
            for email in (current_app.config.get("ADMIN_EMAILS") or [])
            if email and email.strip()
        },
        total_admins=User.query.filter_by(role="admin").count(),
        url_pagina=_urls_pagina(),
    )


@bp.route("/administradores", methods=["GET", "POST"])
@admin_required
def administradores():
    form = AdministradorForm()
    termo = (request.args.get("q") or "").strip()

    if form.validate_on_submit():
        email = (form.email.data or "").strip().lower()
        nome = form.nome.data or None
        senha = form.senha.data or ""
        usuario = (
            db.session.query(User)
            .filter(db.func.lower(User.email) == email)
            .first()
        )

        if usuario is None:
            if not senha:
                form.senha.errors.append("Defina uma senha inicial para a nova conta.")
                return _render_administradores(form, termo)

            usuario = User(email=email, nome=nome, role="admin", ativo=True)
            usuario.definir_senha(senha)
            db.session.add(usuario)
            mensagem = f"Administrador {email} criado."
        else:
            if senha:
                usuario.definir_senha(senha)
            if nome:
                usuario.nome = nome
            reativado = not usuario.ativo
            usuario.ativo = True
            usuario.role = "admin"
            mensagem = f"{email} agora é administrador."
            if reativado:
                mensagem += " A conta foi reativada."

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.email.errors.append("Não foi possível salvar este e-mail.")
            return _render_administradores(form, termo)

        flash(mensagem, "success")
        return redirect(url_for("admin.administradores"))

    return _render_administradores(form, termo)


@bp.post("/administradores/<int:usuario_id>/remover")
@admin_required
def remover_administrador(usuario_id: int):
    usuario = db.get_or_404(User, usuario_id)
    fixos = {
        email.strip().lower()
        for email in (current_app.config.get("ADMIN_EMAILS") or [])
        if email and email.strip()
    }

    if not usuario.is_admin:
        flash("Este usuário já não é administrador.", "warning")
    elif usuario.id == current_user.id:
        flash("Você não pode remover seu próprio acesso.", "error")
    elif (usuario.email or "").strip().lower() in fixos:
        flash("Este e-mail é administrador por configuração do sistema.", "error")
    elif User.query.filter_by(role="admin").count() <= 1:
        flash("Não é possível remover o último administrador.", "error")
    else:
        usuario.role = "user"
        db.session.commit()
        flash(f"Acesso de administrador removido de {usuario.email}.", "success")

    return redirect(url_for("admin.administradores"))


# ------------------------------------------------------------------ farmácias
@bp.get("/farmacias")
@admin_required
def farmacias():
    termo = (request.args.get("q") or "").strip()
    situacao = request.args.get("situacao", "todas")

    consulta = Farmacia.query
    if termo:
        padrao = f"%{termo}%"
        consulta = consulta.filter(
            or_(
                Farmacia.nome.ilike(padrao),
                Farmacia.endereco.ilike(padrao),
                Farmacia.bairro.ilike(padrao),
            )
        )
    if situacao == "ativas":
        consulta = consulta.filter(Farmacia.ativo.is_(True))
    elif situacao == "inativas":
        consulta = consulta.filter(Farmacia.ativo.is_(False))

    ordenacao, criterio = _ordenacao(Farmacia)
    paginacao = consulta.order_by(criterio).paginate(
        page=_pagina(), per_page=POR_PAGINA, error_out=False
    )

    contagens = {}
    ids = [farmacia.id for farmacia in paginacao.items]
    if ids:
        linhas = (
            db.session.query(
                FarmaciaMedicamento.farmacia_id,
                func.count(FarmaciaMedicamento.medicamento_id),
            )
            .filter(
                FarmaciaMedicamento.farmacia_id.in_(ids),
                FarmaciaMedicamento.disponivel.is_(True),
            )
            .group_by(FarmaciaMedicamento.farmacia_id)
            .all()
        )
        contagens = {farmacia_id: total for farmacia_id, total in linhas}

    return render_template(
        "admin/farmacias.html",
        paginacao=paginacao,
        termo=termo,
        situacao=situacao,
        ordenacao=ordenacao,
        contagens=contagens,
        url_args=_url_args,
        url_pagina=_urls_pagina(),
    )


@bp.route("/farmacias/nova", methods=["GET", "POST"])
@admin_required
def nova_farmacia():
    form = FarmaciaForm()

    if form.validate_on_submit():
        nova_imagem = None
        if form.imagem.data and form.imagem.data.filename:
            try:
                nova_imagem = guardar_imagem(form.imagem.data)
            except (OSError, ValueError) as erro:
                flash(f"Não foi possível salvar a imagem: {erro}", "error")
                return _render_farmacia(form, None)

        if nova_imagem:
            imagem_url = nova_imagem
        elif form.remover_imagem.data:
            imagem_url = None
        else:
            imagem_url = form.imagem_url.data or None

        farmacia = Farmacia(
            nome=form.nome.data,
            endereco=form.endereco.data,
            bairro=form.bairro.data or None,
            lat=form.lat.data,
            lng=form.lng.data,
            imagem_url=imagem_url,
            telefone=form.telefone.data or None,
            horario=form.horario.data or None,
            ativo=form.ativo.data,
            criado_por=current_user.id,
        )
        db.session.add(farmacia)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if nova_imagem:
                remover_imagem(nova_imagem)
            form.nome.errors.append("Já existe uma farmácia com este nome.")
            return _render_farmacia(form, None)

        flash(
            f'Farmácia "{farmacia.nome}" criada. Agora associe os medicamentos.',
            "success",
        )
        return redirect(
            url_for("admin.editar_farmacia", farmacia_id=farmacia.id)
        )

    return _render_farmacia(form, None)


@bp.route("/farmacias/<int:farmacia_id>/editar", methods=["GET", "POST"])
@admin_required
def editar_farmacia(farmacia_id: int):
    farmacia = db.get_or_404(Farmacia, farmacia_id)
    form = FarmaciaForm(obj=farmacia, farmacia_id=farmacia.id)

    if form.validate_on_submit():
        nova_imagem = None
        if form.imagem.data and form.imagem.data.filename:
            try:
                nova_imagem = guardar_imagem(form.imagem.data)
            except (OSError, ValueError) as erro:
                flash(f"Não foi possível salvar a imagem: {erro}", "error")
                return _render_farmacia(form, farmacia)

        imagem_anterior = farmacia.imagem_url
        if nova_imagem:
            farmacia.imagem_url = nova_imagem
        elif form.remover_imagem.data:
            farmacia.imagem_url = None
        else:
            farmacia.imagem_url = form.imagem_url.data or None

        farmacia.nome = form.nome.data
        farmacia.endereco = form.endereco.data
        farmacia.bairro = form.bairro.data or None
        farmacia.lat = form.lat.data
        farmacia.lng = form.lng.data
        farmacia.telefone = form.telefone.data or None
        farmacia.horario = form.horario.data or None
        farmacia.ativo = form.ativo.data

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if nova_imagem:
                remover_imagem(nova_imagem)
            form.nome.errors.append("Já existe uma farmácia com este nome.")
            return _render_farmacia(form, farmacia)

        if imagem_anterior and imagem_anterior != farmacia.imagem_url:
            remover_imagem(imagem_anterior)

        flash("Farmácia atualizada com sucesso.", "success")
        return redirect(
            url_for("admin.editar_farmacia", farmacia_id=farmacia.id)
        )

    return _render_farmacia(form, farmacia)


@bp.post("/farmacias/<int:farmacia_id>/medicamentos")
@admin_required
def atualizar_inventario(farmacia_id: int):
    farmacia = db.get_or_404(Farmacia, farmacia_id)

    visiveis = _ids_do_formulario("visivel")
    disponiveis = _ids_do_formulario("disponivel")

    for medicamento_id in visiveis:
        if db.session.get(Medicamento, medicamento_id) is None:
            continue

        vinculo = db.session.get(
            FarmaciaMedicamento, (farmacia.id, medicamento_id)
        )
        marcado = medicamento_id in disponiveis

        if vinculo is None:
            if marcado:
                db.session.add(
                    FarmaciaMedicamento(
                        farmacia_id=farmacia.id,
                        medicamento_id=medicamento_id,
                        disponivel=True,
                        atualizado_por=current_user.id,
                    )
                )
        elif vinculo.disponivel != marcado:
            vinculo.disponivel = marcado
            vinculo.atualizado_por = current_user.id

    db.session.commit()
    flash("Inventário da farmácia atualizado.", "success")

    return redirect(
        url_for(
            "admin.editar_farmacia",
            farmacia_id=farmacia.id,
            inv_q=(request.form.get("inv_q") or "").strip() or None,
            inv_pagina=request.form.get("inv_pagina") or None,
        )
    )


@bp.post("/farmacias/<int:farmacia_id>/excluir")
@admin_required
def excluir_farmacia(farmacia_id: int):
    farmacia = db.get_or_404(Farmacia, farmacia_id)
    nome = farmacia.nome
    imagem = farmacia.imagem_url

    db.session.delete(farmacia)
    db.session.commit()
    remover_imagem(imagem)

    flash(f'Farmácia "{nome}" excluída.', "success")
    return redirect(url_for("admin.farmacias"))


# --------------------------------------------------------------- medicamentos
@bp.get("/medicamentos")
@admin_required
def medicamentos():
    termo = (request.args.get("q") or "").strip()
    situacao = request.args.get("situacao", "todas")

    consulta = _consulta_medicamentos(termo)
    if situacao == "ativos":
        consulta = consulta.filter(Medicamento.ativo.is_(True))
    elif situacao == "inativos":
        consulta = consulta.filter(Medicamento.ativo.is_(False))

    ordenacao, criterio = _ordenacao(Medicamento)
    paginacao = consulta.order_by(criterio).paginate(
        page=_pagina(), per_page=POR_PAGINA, error_out=False
    )

    disponibilidades = {}
    ids = [medicamento.id for medicamento in paginacao.items]
    if ids:
        linhas = (
            db.session.query(
                FarmaciaMedicamento.medicamento_id,
                func.count(FarmaciaMedicamento.farmacia_id),
            )
            .join(Farmacia, Farmacia.id == FarmaciaMedicamento.farmacia_id)
            .filter(
                FarmaciaMedicamento.medicamento_id.in_(ids),
                FarmaciaMedicamento.disponivel.is_(True),
                Farmacia.ativo.is_(True),
            )
            .group_by(FarmaciaMedicamento.medicamento_id)
            .all()
        )
        disponibilidades = {medicamento_id: total for medicamento_id, total in linhas}

    return render_template(
        "admin/medicamentos.html",
        paginacao=paginacao,
        termo=termo,
        situacao=situacao,
        ordenacao=ordenacao,
        disponibilidades=disponibilidades,
        url_args=_url_args,
        url_pagina=_urls_pagina(),
    )


@bp.route("/medicamentos/novo", methods=["GET", "POST"])
@admin_required
def novo_medicamento():
    form = MedicamentoForm()

    if form.validate_on_submit():
        medicamento = Medicamento(
            nome=form.nome.data,
            nome_busca=remover_acentos(form.nome.data),
            apresentacao=form.apresentacao.data or None,
            ativo=form.ativo.data,
        )
        db.session.add(medicamento)
        db.session.commit()

        flash(f'Medicamento "{medicamento.nome}" criado.', "success")
        return redirect(
            url_for("admin.editar_medicamento", medicamento_id=medicamento.id)
        )

    return render_template(
        "admin/medicamento_form.html",
        form=form,
        medicamento=None,
        farmacias=[],
    )


@bp.route("/medicamentos/<int:medicamento_id>/editar", methods=["GET", "POST"])
@admin_required
def editar_medicamento(medicamento_id: int):
    medicamento = db.get_or_404(Medicamento, medicamento_id)
    form = MedicamentoForm(obj=medicamento, medicamento_id=medicamento.id)

    if form.validate_on_submit():
        medicamento.nome = form.nome.data
        medicamento.nome_busca = remover_acentos(form.nome.data)
        medicamento.apresentacao = form.apresentacao.data or None
        medicamento.ativo = form.ativo.data

        db.session.commit()
        flash("Medicamento atualizado com sucesso.", "success")
        return redirect(
            url_for("admin.editar_medicamento", medicamento_id=medicamento.id)
        )

    farmacias = (
        db.session.query(Farmacia)
        .join(
            FarmaciaMedicamento,
            FarmaciaMedicamento.farmacia_id == Farmacia.id,
        )
        .filter(
            FarmaciaMedicamento.medicamento_id == medicamento.id,
            FarmaciaMedicamento.disponivel.is_(True),
        )
        .order_by(func.lower(Farmacia.nome))
        .all()
    )

    return render_template(
        "admin/medicamento_form.html",
        form=form,
        medicamento=medicamento,
        farmacias=farmacias,
    )


@bp.post("/medicamentos/<int:medicamento_id>/excluir")
@admin_required
def excluir_medicamento(medicamento_id: int):
    medicamento = db.get_or_404(Medicamento, medicamento_id)
    nome = medicamento.nome

    db.session.delete(medicamento)
    db.session.commit()

    flash(f'Medicamento "{nome}" excluído.', "success")
    return redirect(url_for("admin.medicamentos"))
