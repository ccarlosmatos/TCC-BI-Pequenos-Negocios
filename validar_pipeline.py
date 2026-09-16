"""Auditoria reprodutível do pipeline do TCC.

O validador não confia apenas no JSON analítico. Ele exige todos os artefatos
obrigatórios, recalcula os principais indicadores diretamente do banco SQLite,
reconstrói as séries analíticas, refaz a regressão e o teste retrospectivo e
confere se o dashboard contém o mesmo objeto de dados publicado no JSON.

Saída:
    logs/validacao_pipeline.json

Código de saída:
    0  = todas as verificações aprovadas
    1  = uma ou mais verificações falharam
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sqlite3
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data/raw/vendas_bruto.csv"
DB = ROOT / "data/processed/dw_vendas.sqlite3"
JSON_ANALITICO = ROOT / "data/processed/dashboard_data.json"
BACKTEST = ROOT / "data/processed/validacao_previsao.json"
DASHBOARD = ROOT / "dashboard.html"
REF_JSON = ROOT / "reference/dashboard_data_referencia.json"
LOG = ROOT / "logs/validacao_pipeline.json"

REQUIRED_FILES = {
    "CSV bruto": RAW,
    "Banco SQLite": DB,
    "JSON analítico": JSON_ANALITICO,
    "Validação retrospectiva": BACKTEST,
    "Dashboard HTML": DASHBOARD,
    "JSON de referência": REF_JSON,
}

EXPECTED = {
    "linhas_brutas": 7429,
    "duplicidades_exatas": 109,
    "categorias_ausentes_bruto": 310,
    "categorias_reconstituidas_retidas": 305,
    "loja_canonica": "Matriz - Recife",
    "linhas_fato": 7320,
    "ids_venda_distintos": 7320,
    "dim_tempo": 731,
    "dim_categoria": 5,
    "dim_produto": 30,
    "movimentos_positivos": 7094,
    "movimentos_devolucao": 226,
    "faturamento_bruto": 1606086.63,
    "total_devolucoes": 54767.59,
    "faturamento_liquido": 1551319.04,
    "n_transacoes": 7320,
    "itens_vendidos": 14584,
    "ticket_medio": 211.93,
    "r2": 0.305,
}

checks: list[dict] = []


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def close(a, b, tol=0.01) -> bool:
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=tol)


def check(cond: bool, label: str, details: str = "") -> None:
    status = "OK" if cond else "FALHA"
    print(f"[{status}] {label}" + (f" - {details}" if details else ""))
    checks.append({"status": status, "verificacao": label, "detalhes": details})


def write_report(status: str, hashes: dict | None = None, observacoes: list[str] | None = None) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "status": status,
        "checks": checks,
        "sha256": hashes or {},
        "observacoes": observacoes or [],
    }
    LOG.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def regressao_linear(valores_y: list[float]) -> tuple[float, float, float]:
    n = len(valores_y)
    xs = list(range(n))
    media_x = statistics.mean(xs)
    media_y = statistics.mean(valores_y)
    num = sum((xs[i] - media_x) * (valores_y[i] - media_y) for i in range(n))
    den = sum((xs[i] - media_x) ** 2 for i in range(n))
    b1 = num / den
    b0 = media_y - b1 * media_x
    ss_tot = sum((y - media_y) ** 2 for y in valores_y)
    ss_res = sum((valores_y[i] - (b0 + b1 * i)) ** 2 for i in range(n))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return b0, b1, r2


def metricas(reais: list[float], previstos: list[float]) -> dict:
    erros_abs = [abs(r - p) for r, p in zip(reais, previstos)]
    return {
        "mae": round(statistics.mean(erros_abs), 2),
        "rmse": round(math.sqrt(statistics.mean([(r - p) ** 2 for r, p in zip(reais, previstos)])), 2),
        "mape_pct": round(statistics.mean([abs((r - p) / r) for r, p in zip(reais, previstos)]) * 100, 2),
    }


def normaliza_registros(lista: list[dict], campos: list[str]) -> list[tuple]:
    return [tuple(item[c] for c in campos) for item in lista]


def extrair_json_do_dashboard(html: str) -> dict:
    match = re.search(r"const\s+dados\s*=\s*(\{.*?\});\s*\n\s*new\s+Chart", html, flags=re.DOTALL)
    if not match:
        raise ValueError("objeto 'const dados = {...}' não localizado no dashboard")
    return json.loads(match.group(1))


def main() -> None:
    # 1. Presença obrigatória dos artefatos. Ausência de qualquer item reprova.
    for nome, path in REQUIRED_FILES.items():
        check(path.is_file(), f"Artefato obrigatório: {nome}", str(path.relative_to(ROOT)))

    if any(item["status"] == "FALHA" for item in checks):
        write_report("FALHA", observacoes=["A validação foi interrompida porque faltam artefatos obrigatórios."])
        print("\nVALIDAÇÃO CONCLUÍDA: FALHA")
        raise SystemExit(1)

    # 2. Base bruta: estrutura, volume e problemas deliberadamente introduzidos.
    with RAW.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)
        headers = reader.fieldnames or []
    expected_headers = [
        "id_venda", "data_venda", "produto", "categoria", "quantidade",
        "preco_unitario", "forma_pagamento", "loja",
    ]
    check(headers == expected_headers, "Cabeçalho do CSV bruto", str(headers))
    check(len(raw_rows) == EXPECTED["linhas_brutas"], "Quantidade de registros brutos", str(len(raw_rows)))
    unique_raw = {tuple(row[h] for h in expected_headers) for row in raw_rows}
    duplicates_raw = len(raw_rows) - len(unique_raw)
    blank_categories = sum(not (row["categoria"] or "").strip() for row in raw_rows)
    check(duplicates_raw == EXPECTED["duplicidades_exatas"], "Duplicidades exatas no CSV bruto", str(duplicates_raw))
    check(blank_categories == EXPECTED["categorias_ausentes_bruto"], "Campos de categoria ausentes no CSV bruto", str(blank_categories))
    unique_rows_ordered = list({tuple(row[h] for h in expected_headers): row for row in raw_rows}.values())
    blank_categories_retained = sum(not (row["categoria"] or "").strip() for row in unique_rows_ordered)
    check(
        blank_categories_retained == EXPECTED["categorias_reconstituidas_retidas"],
        "Registros finais derivados de linhas com categoria ausente",
        str(blank_categories_retained),
    )

    # 3. Conteúdo analítico publicado.
    dados = json.loads(JSON_ANALITICO.read_text(encoding="utf-8"))
    ref = json.loads(REF_JSON.read_text(encoding="utf-8"))
    backtest_publicado = json.loads(BACKTEST.read_text(encoding="utf-8"))
    check(dados == ref, "JSON analítico idêntico ao artefato de referência")

    expected_top_keys = {"kpis", "serie_mensal", "ranking_categorias", "curva_abc", "previsao"}
    check(set(dados) == expected_top_keys, "Estrutura de primeiro nível do JSON analítico", str(sorted(dados)))

    # 4. Banco: tabelas, dimensões, grão, integridade e KPIs recalculados.
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required_tables = {"dim_tempo", "dim_categoria", "dim_produto", "fato_vendas"}
        check(required_tables.issubset(tabelas), "Quatro tabelas do modelo dimensional", str(sorted(tabelas)))

        fato = conn.execute("SELECT COUNT(*) n, COUNT(DISTINCT id_venda_origem) ids FROM fato_vendas").fetchone()
        check(fato["n"] == EXPECTED["linhas_fato"], "Quantidade de linhas da fato", str(fato["n"]))
        check(fato["ids"] == EXPECTED["ids_venda_distintos"], "Identificadores distintos de venda", str(fato["ids"]))
        check(fato["n"] == fato["ids"], "Unicidade de id_venda_origem na base sintética", f"linhas={fato['n']}, ids={fato['ids']}")

        dim_counts = {
            "dim_tempo": conn.execute("SELECT COUNT(*) FROM dim_tempo").fetchone()[0],
            "dim_categoria": conn.execute("SELECT COUNT(*) FROM dim_categoria").fetchone()[0],
            "dim_produto": conn.execute("SELECT COUNT(*) FROM dim_produto").fetchone()[0],
        }
        for nome, valor in dim_counts.items():
            check(valor == EXPECTED[nome], f"Quantidade de registros em {nome}", str(valor))

        movimentos = dict(conn.execute("SELECT eh_devolucao, COUNT(*) FROM fato_vendas GROUP BY eh_devolucao").fetchall())
        check(movimentos.get(0) == EXPECTED["movimentos_positivos"], "Movimentos positivos", str(movimentos.get(0)))
        check(movimentos.get(1) == EXPECTED["movimentos_devolucao"], "Movimentos de devolução", str(movimentos.get(1)))

        lojas = [r[0] for r in conn.execute("SELECT DISTINCT loja FROM fato_vendas ORDER BY loja").fetchall()]
        check(lojas == [EXPECTED["loja_canonica"]], "Identificação da loja padronizada", str(lojas))

        orphan_tempo = conn.execute(
            "SELECT COUNT(*) FROM fato_vendas f LEFT JOIN dim_tempo d ON d.id_tempo=f.id_tempo WHERE d.id_tempo IS NULL"
        ).fetchone()[0]
        orphan_prod = conn.execute(
            "SELECT COUNT(*) FROM fato_vendas f LEFT JOIN dim_produto d ON d.id_produto=f.id_produto WHERE d.id_produto IS NULL"
        ).fetchone()[0]
        orphan_cat = conn.execute(
            "SELECT COUNT(*) FROM dim_produto p LEFT JOIN dim_categoria c ON c.id_categoria=p.id_categoria WHERE c.id_categoria IS NULL"
        ).fetchone()[0]
        check(orphan_tempo == orphan_prod == orphan_cat == 0, "Integridade referencial lógica", f"tempo={orphan_tempo}, produto={orphan_prod}, categoria={orphan_cat}")

        row = conn.execute("""
            SELECT
                SUM(CASE WHEN eh_devolucao = 0 THEN valor_total ELSE 0 END) AS faturamento_bruto,
                SUM(CASE WHEN eh_devolucao = 1 THEN -valor_total ELSE 0 END) AS total_devolucoes,
                SUM(valor_total) AS faturamento_liquido,
                COUNT(DISTINCT id_venda_origem) AS n_transacoes,
                SUM(CASE WHEN eh_devolucao = 0 THEN quantidade ELSE 0 END) AS itens_vendidos
            FROM fato_vendas
        """).fetchone()
        db_kpis = {
            "faturamento_bruto": round(row["faturamento_bruto"], 2),
            "total_devolucoes": round(row["total_devolucoes"], 2),
            "faturamento_liquido": round(row["faturamento_liquido"], 2),
            "n_transacoes": int(row["n_transacoes"]),
            "itens_vendidos": int(row["itens_vendidos"]),
        }
        db_kpis["ticket_medio"] = round(db_kpis["faturamento_liquido"] / db_kpis["n_transacoes"], 2)

        json_kpis = dados["kpis"]
        for chave in ["faturamento_bruto", "total_devolucoes", "faturamento_liquido", "ticket_medio"]:
            check(close(db_kpis[chave], EXPECTED[chave]), f"KPI {chave} recalculado do SQLite", str(db_kpis[chave]))
            check(close(db_kpis[chave], json_kpis[chave]), f"SQLite x JSON: {chave}", f"db={db_kpis[chave]}, json={json_kpis[chave]}")
        for chave in ["n_transacoes", "itens_vendidos"]:
            check(db_kpis[chave] == EXPECTED[chave], f"KPI {chave} recalculado do SQLite", str(db_kpis[chave]))
            check(db_kpis[chave] == int(json_kpis[chave]), f"SQLite x JSON: {chave}", f"db={db_kpis[chave]}, json={json_kpis[chave]}")

        serie_db = [
            {"ano_mes": r["ano_mes"], "faturamento": round(r["faturamento"], 2)}
            for r in conn.execute("""
                SELECT t.ano_mes, SUM(f.valor_total) AS faturamento
                FROM fato_vendas f
                JOIN dim_tempo t ON t.id_tempo=f.id_tempo
                GROUP BY t.ano_mes
                ORDER BY t.ano_mes
            """)
        ]
        check(serie_db == dados["serie_mensal"], "Série mensal recalculada do SQLite coincide com JSON")
        check(len(serie_db) == 24, "Série mensal com 24 observações", str(len(serie_db)))

        ranking_db = [
            {"categoria": r["categoria"], "faturamento": round(r["faturamento"], 2)}
            for r in conn.execute("""
                SELECT c.categoria, SUM(f.valor_total) AS faturamento
                FROM fato_vendas f
                JOIN dim_produto p ON p.id_produto=f.id_produto
                JOIN dim_categoria c ON c.id_categoria=p.id_categoria
                GROUP BY c.categoria
                ORDER BY faturamento DESC
            """)
        ]
        check(ranking_db == dados["ranking_categorias"], "Ranking de categorias recalculado do SQLite coincide com JSON")

        rows_abc = conn.execute("""
            SELECT p.produto, SUM(f.valor_total) AS faturamento
            FROM fato_vendas f
            JOIN dim_produto p ON p.id_produto=f.id_produto
            WHERE f.eh_devolucao=0
            GROUP BY p.produto
            ORDER BY faturamento DESC
        """).fetchall()
        total_abc = sum(r["faturamento"] for r in rows_abc)
        acumulado = 0.0
        abc_db = []
        for r in rows_abc:
            acumulado += r["faturamento"]
            pct = acumulado / total_abc * 100
            classe = "A" if pct <= 80 else "B" if pct <= 95 else "C"
            abc_db.append({
                "produto": r["produto"],
                "faturamento": round(r["faturamento"], 2),
                "pct_acumulado": round(pct, 1),
                "classe": classe,
            })
        check(abc_db == dados["curva_abc"], "Curva ABC recalculada do SQLite coincide com JSON")

    finally:
        conn.close()

    # 5. Regressão e previsão recalculadas a partir da série obtida do banco.
    valores = [x["faturamento"] for x in serie_db]
    b0, b1, r2 = regressao_linear(valores)
    prev_reg = [round(b0 + b1 * (len(valores) + i), 2) for i in range(3)]
    mm3 = round(statistics.mean(valores[-3:]), 2)
    prev_mm = [mm3] * 3
    prev_json = dados["previsao"]

    check(close(round(r2, 3), EXPECTED["r2"], 0.0001), "R² recalculado a partir do SQLite", str(round(r2, 3)))
    check(close(round(b0, 2), prev_json["coeficientes"]["intercepto"]), "Intercepto recalculado coincide com JSON")
    check(close(round(b1, 2), prev_json["coeficientes"]["inclinacao"]), "Inclinação recalculada coincide com JSON")
    check(close(round(r2, 3), prev_json["coeficientes"]["r2"], 0.0001), "R² recalculado coincide com JSON")
    check(prev_reg == prev_json["previsao_regressao_linear"], "Previsão por regressão recalculada coincide com JSON")
    check(prev_mm == prev_json["previsao_media_movel_3m"], "Previsão por média móvel recalculada coincide com JSON")

    # 6. Backtest recalculado de forma independente a partir da série do banco.
    treino = valores[:-3]
    reais = valores[-3:]
    b0_t, b1_t, _ = regressao_linear(treino)
    prev_reg_t_raw = [b0_t + b1_t * (len(treino) + i) for i in range(3)]
    prev_reg_t = [round(v, 2) for v in prev_reg_t_raw]
    media3_t_raw = statistics.mean(treino[-3:])
    prev_mm_t_raw = [media3_t_raw] * 3
    prev_mm_t = [round(v, 2) for v in prev_mm_t_raw]
    metricas_reg = metricas(reais, prev_reg_t_raw)
    metricas_mm = metricas(reais, prev_mm_t_raw)

    check(backtest_publicado["meses_teste"] == [x["ano_mes"] for x in serie_db[-3:]], "Meses do backtest coincidem com a série do banco")
    check(backtest_publicado["realizado"] == reais, "Valores realizados do backtest coincidem com o banco")
    check(backtest_publicado["regressao_linear"]["previsoes"] == prev_reg_t, "Previsões do backtest por regressão recalculadas")
    check(backtest_publicado["media_movel_3m"]["previsoes"] == prev_mm_t, "Previsões do backtest por média móvel recalculadas")
    check(backtest_publicado["regressao_linear"]["metricas"] == metricas_reg, "Métricas do backtest por regressão recalculadas", str(metricas_reg))
    check(backtest_publicado["media_movel_3m"]["metricas"] == metricas_mm, "Métricas do backtest por média móvel recalculadas", str(metricas_mm))

    # 7. O dashboard deve incorporar exatamente o mesmo objeto analítico do JSON.
    try:
        dados_dashboard = extrair_json_do_dashboard(DASHBOARD.read_text(encoding="utf-8"))
        check(dados_dashboard == dados, "Dados incorporados ao dashboard idênticos ao JSON analítico")
    except Exception as exc:
        check(False, "Leitura dos dados incorporados ao dashboard", str(exc))

    hashes = {str(path.relative_to(ROOT)): sha256(path) for path in REQUIRED_FILES.values()}
    failed = [item for item in checks if item["status"] == "FALHA"]
    status = "FALHA" if failed else "APROVADO"
    write_report(
        status,
        hashes=hashes,
        observacoes=[
            "O SQLite é validado por conteúdo lógico e resultados recalculados. Igualdade binária entre bancos recriados não é exigida.",
            "A validação temporal usa somente três meses de teste e deve ser interpretada como verificação exploratória.",
        ],
    )

    print(f"\nVALIDAÇÃO CONCLUÍDA: {status}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
