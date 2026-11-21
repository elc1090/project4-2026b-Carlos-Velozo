"""Popula o banco a partir do CSV e do JSON.

Uso:
    python scripts/seed.py
    python scripts/seed.py --force
    python scripts/seed.py --reset   # apaga tudo
"""

import argparse
import csv
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models import Farmacia, FarmaciaMedicamento, Medicamento  # noqa: E402
from utils import remover_acentos  # noqa: E402

FICHEIRO_ENDERECOS = BASE_DIR / "enderecos.json"
FICHEIRO_CSV = BASE_DIR / "Medicamentos - unificado.csv"

# Colunas do CSV que representam grupos, não farmácias individuais.
COLUNAS_IGNORADAS = {
    "item",
    "distritais",
    "farmacias_distritais",
    "municipal",
    "popular",
    "ubs",
    "cid",
    "informacoes_adicionais",
    "local_de_dispensacao",
    "medicamento",
}

VALORES_VERDADEIROS = {"1", "1.0", "1.00", "sim", "s", "true", "x"}


def _flag(valor) -> bool:
    return str(valor or "").strip().lower() in VALORES_VERDADEIROS


def _normalizar_coluna(nome: str) -> str:
    return remover_acentos(nome).replace(" ", "_")


def _normalizar_imagem(caminho: str | None) -> str | None:
    """Converte 'static\\img\\x.png' (Windows) em '/static/img/x.png' (URL)."""
    if not caminho:
        return None
    return "/" + caminho.replace("\\", "/").strip().lstrip("/")


def _carregar_enderecos() -> dict:
    if not FICHEIRO_ENDERECOS.exists():
        raise FileNotFoundError(f"Ficheiro não encontrado: {FICHEIRO_ENDERECOS}")
    with open(FICHEIRO_ENDERECOS, encoding="utf-8") as ficheiro:
        return json.load(ficheiro)


def _garantir_farmacia(nome, info, cache, resumo) -> Farmacia:
    nome = nome.strip()
    if nome in cache:
        return cache[nome]

    farmacia = Farmacia.query.filter_by(nome=nome).first()
    if farmacia is None:
        marker = info.get("marker") or [0, 0]
        farmacia = Farmacia(
            nome=nome,
            endereco=(info.get("endereco") or "").strip(),
            lat=float(marker[0]),
            lng=float(marker[1]),
            imagem_url=_normalizar_imagem(info.get("imagem")),
        )
        db.session.add(farmacia)
        db.session.flush()
        resumo["farmacias_criadas"] += 1

    cache[nome] = farmacia
    return farmacia


def _garantir_medicamento(nome, cache, resumo) -> Medicamento | None:
    nome = " ".join((nome or "").split())
    if not nome:
        return None

    chave = nome.lower()
    if chave in cache:
        return cache[chave]

    medicamento = (
        db.session.query(Medicamento)
        .filter(db.func.lower(Medicamento.nome) == chave)
        .first()
    )
    if medicamento is None:
        medicamento = Medicamento(nome=nome, nome_busca=remover_acentos(nome))
        db.session.add(medicamento)
        db.session.flush()
        resumo["medicamentos_criados"] += 1

    cache[chave] = medicamento
    return medicamento


def _categorizar(farmacias: list[str]) -> dict[str, list[str]]:
    def contem(nome, *termos):
        normalizado = remover_acentos(nome)
        return any(termo in normalizado for termo in termos)

    return {
        "distritais": [n for n in farmacias if contem(n, "distrital")],
        "municipais": [n for n in farmacias if contem(n, "municipal", "central")],
        "especiais": [n for n in farmacias if contem(n, "especia")],
    }


def _farmacias_da_linha(linha: dict, categorias: dict, todas: list[str]) -> list[str]:
    """Distribui o medicamento pelas farmácias da linha."""
    item = (linha.get("item") or "").strip()
    local = (linha.get("local_de_dispensacao") or "").strip()

    # Linhas sem ITEM e sem LOCAL_DE_DISPENSACAO = medicamentos especiais.
    if not item and not local:
        return categorias["especiais"]

    alvos: list[str] = []

    if _flag(linha.get("municipal")):
        alvos.extend(categorias["municipais"])

    if _flag(linha.get("distritais")) or _flag(linha.get("farmacias_distritais")):
        alvos.extend(categorias["distritais"])
    else:
        # Colunas com o nome de uma farmácia específica (ex.: DISTRITAL KENNEDY).
        for coluna, valor in linha.items():
            if coluna in COLUNAS_IGNORADAS or not _flag(valor):
                continue
            # Chaves normalizadas usam "_" no lugar de espaço.
            coluna_busca = coluna.replace("_", " ")
            for nome_farmacia in todas:
                if coluna_busca and coluna_busca in remover_acentos(nome_farmacia):
                    alvos.append(nome_farmacia)

    return list(dict.fromkeys(alvos))


def _vincular(farmacia, medicamento, existentes, resumo) -> None:
    chave = (farmacia.id, medicamento.id)
    if chave in existentes:
        return
    db.session.add(
        FarmaciaMedicamento(
            farmacia_id=farmacia.id,
            medicamento_id=medicamento.id,
        )
    )
    existentes.add(chave)
    resumo["vinculos_criados"] += 1


def _ler_csv():
    with open(FICHEIRO_CSV, encoding="utf-8-sig", newline="") as ficheiro:
        amostra = ficheiro.read(4096)
        ficheiro.seek(0)
        delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
        reader = csv.DictReader(ficheiro, delimiter=delimitador)
        for linha in reader:
            yield {_normalizar_coluna(k): v for k, v in linha.items() if k}


def run_seed(reset: bool = False, force: bool = False) -> dict:
    app = create_app()
    resumo = {
        "farmacias_criadas": 0,
        "medicamentos_criados": 0,
        "vinculos_criados": 0,
        "linhas_lidas": 0,
    }

    with app.app_context():
        if reset:
            print("A apagar tabelas existentes (--reset)...")
            db.drop_all()

        db.create_all()

        if db.session.query(Farmacia.id).first() is not None and not (reset or force):
            print("A base já contém farmácias. Seed ignorado (use --reset ou --force).")
            return resumo

        enderecos = _carregar_enderecos()
        cache_farmacias: dict[str, Farmacia] = {}

        for nome, info in enderecos.items():
            _garantir_farmacia(nome, info, cache_farmacias, resumo)

        todas = list(cache_farmacias.keys())
        categorias = _categorizar(todas)

        existentes = {
            (vinculo.farmacia_id, vinculo.medicamento_id)
            for vinculo in FarmaciaMedicamento.query.all()
        }
        cache_medicamentos: dict[str, Medicamento] = {}

        for linha in _ler_csv():
            resumo["linhas_lidas"] += 1
            medicamento = _garantir_medicamento(
                linha.get("medicamento"), cache_medicamentos, resumo
            )
            if medicamento is None:
                continue

            for nome_farmacia in _farmacias_da_linha(linha, categorias, todas):
                _vincular(
                    cache_farmacias[nome_farmacia],
                    medicamento,
                    existentes,
                    resumo,
                )

        db.session.commit()

    print(
        "Seed concluído: "
        f"{resumo['farmacias_criadas']} farmácias, "
        f"{resumo['medicamentos_criados']} medicamentos, "
        f"{resumo['vinculos_criados']} vínculos "
        f"({resumo['linhas_lidas']} linhas do CSV)."
    )
    return resumo


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Popula a base do MapeiaSUS.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Apaga todas as tabelas antes de recriar (destrutivo).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reaplica os dados base mesmo que já existam farmácias.",
    )
    args = parser.parse_args(argv)
    run_seed(reset=args.reset, force=args.force)


if __name__ == "__main__":
    main()
