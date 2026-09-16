"""
03_analise_previsao.py

Consome o modelo dimensional (data/processed/dw_vendas.sqlite3) para gerar:
  1. KPIs descritivos (faturamento total, ticket médio, vendas líquidas)
  2. Série mensal de faturamento (2024-2025)
  3. Ranking de categorias e produtos
  4. Curva ABC de produtos (técnica descritiva de classificação e
     priorização gerencial)
  5. Previsão de faturamento para o 1º trimestre de 2026 usando regressão
     linear simples sobre a série mensal (técnica de análise de séries
     temporais) e média móvel de 3 meses como comparação

Saída: data/processed/dashboard_data.json (consumido pelo dashboard.html)
       e um resumo textual impresso no console (para citação no artigo).
"""
import json
import sqlite3
import statistics
from pathlib import Path

DB_PATH = "data/processed/dw_vendas.sqlite3"
OUT_JSON = "data/processed/dashboard_data.json"


def carregar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def kpis(conn):
    row = conn.execute("""
        SELECT
            SUM(CASE WHEN eh_devolucao = 0 THEN valor_total ELSE 0 END) AS faturamento_bruto,
            SUM(CASE WHEN eh_devolucao = 1 THEN -valor_total ELSE 0 END) AS total_devolucoes,
            SUM(valor_total) AS faturamento_liquido,
            COUNT(DISTINCT id_venda_origem) AS n_transacoes,
            SUM(CASE WHEN eh_devolucao = 0 THEN quantidade ELSE 0 END) AS itens_vendidos
        FROM fato_vendas
    """).fetchone()
    ticket_medio = row["faturamento_liquido"] / row["n_transacoes"]
    return {
        "faturamento_bruto": round(row["faturamento_bruto"], 2),
        "total_devolucoes": round(row["total_devolucoes"], 2),
        "faturamento_liquido": round(row["faturamento_liquido"], 2),
        "n_transacoes": row["n_transacoes"],
        "itens_vendidos": row["itens_vendidos"],
        "ticket_medio": round(ticket_medio, 2),
    }


def serie_mensal(conn):
    rows = conn.execute("""
        SELECT t.ano_mes AS ano_mes, SUM(f.valor_total) AS faturamento
        FROM fato_vendas f
        JOIN dim_tempo t ON t.id_tempo = f.id_tempo
        GROUP BY t.ano_mes
        ORDER BY t.ano_mes
    """).fetchall()
    return [{"ano_mes": r["ano_mes"], "faturamento": round(r["faturamento"], 2)} for r in rows]


def ranking_categorias(conn):
    rows = conn.execute("""
        SELECT c.categoria AS categoria, SUM(f.valor_total) AS faturamento
        FROM fato_vendas f
        JOIN dim_produto p ON p.id_produto = f.id_produto
        JOIN dim_categoria c ON c.id_categoria = p.id_categoria
        GROUP BY c.categoria
        ORDER BY faturamento DESC
    """).fetchall()
    return [{"categoria": r["categoria"], "faturamento": round(r["faturamento"], 2)} for r in rows]


def curva_abc_produtos(conn):
    rows = conn.execute("""
        SELECT p.produto AS produto, SUM(f.valor_total) AS faturamento
        FROM fato_vendas f
        JOIN dim_produto p ON p.id_produto = f.id_produto
        WHERE f.eh_devolucao = 0
        GROUP BY p.produto
        ORDER BY faturamento DESC
    """).fetchall()
    total = sum(r["faturamento"] for r in rows)
    acumulado = 0.0
    resultado = []
    for r in rows:
        acumulado += r["faturamento"]
        pct_acum = acumulado / total * 100
        if pct_acum <= 80:
            classe = "A"
        elif pct_acum <= 95:
            classe = "B"
        else:
            classe = "C"
        resultado.append({
            "produto": r["produto"],
            "faturamento": round(r["faturamento"], 2),
            "pct_acumulado": round(pct_acum, 1),
            "classe": classe,
        })
    return resultado


def regressao_linear_simples(valores_y):
    n = len(valores_y)
    xs = list(range(n))
    media_x = statistics.mean(xs)
    media_y = statistics.mean(valores_y)
    num = sum((xs[i] - media_x) * (valores_y[i] - media_y) for i in range(n))
    den = sum((xs[i] - media_x) ** 2 for i in range(n))
    b1 = num / den
    b0 = media_y - b1 * media_x
    return b0, b1


def previsao(serie):
    valores = [p["faturamento"] for p in serie]
    b0, b1 = regressao_linear_simples(valores)
    n = len(valores)

    # R² do ajuste, para reportar a qualidade do modelo no artigo
    media_y = statistics.mean(valores)
    ss_tot = sum((y - media_y) ** 2 for y in valores)
    ss_res = sum((valores[i] - (b0 + b1 * i)) ** 2 for i in range(n))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0

    meses_futuros = ["2026-01", "2026-02", "2026-03"]
    previsao_regressao = [round(b0 + b1 * (n + i), 2) for i in range(3)]

    media_movel_3m = round(statistics.mean(valores[-3:]), 2)
    previsao_media_movel = [media_movel_3m] * 3

    return {
        "coeficientes": {"intercepto": round(b0, 2), "inclinacao": round(b1, 2), "r2": round(r2, 3)},
        "meses_futuros": meses_futuros,
        "previsao_regressao_linear": previsao_regressao,
        "previsao_media_movel_3m": previsao_media_movel,
    }


if __name__ == "__main__":
    conn = carregar()
    dados = {
        "kpis": kpis(conn),
        "serie_mensal": serie_mensal(conn),
        "ranking_categorias": ranking_categorias(conn),
        "curva_abc": curva_abc_produtos(conn),
    }
    dados["previsao"] = previsao(dados["serie_mensal"])

    Path(OUT_JSON).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    print("=== KPIs Gerais ===")
    for k, v in dados["kpis"].items():
        print(f"{k}: {v}")

    print("\n=== Ranking de Categorias (faturamento) ===")
    for c in dados["ranking_categorias"]:
        print(f"{c['categoria']}: R$ {c['faturamento']:,.2f}")

    print("\n=== Curva ABC (classe A = ~80% do faturamento) ===")
    n_a = sum(1 for p in dados["curva_abc"] if p["classe"] == "A")
    n_b = sum(1 for p in dados["curva_abc"] if p["classe"] == "B")
    n_c = sum(1 for p in dados["curva_abc"] if p["classe"] == "C")
    print(f"Classe A: {n_a} produtos | Classe B: {n_b} produtos | Classe C: {n_c} produtos "
          f"(total {len(dados['curva_abc'])} produtos)")
    print("Top 5 produtos:")
    for p in dados["curva_abc"][:5]:
        print(f"  {p['produto']}: R$ {p['faturamento']:,.2f} (classe {p['classe']})")

    print("\n=== Previsão de Faturamento (1º trimestre de 2026) ===")
    prev = dados["previsao"]
    print(f"Regressão linear: intercepto={prev['coeficientes']['intercepto']}, "
          f"inclinação={prev['coeficientes']['inclinacao']}, R²={prev['coeficientes']['r2']}")
    for mes, val_reg, val_mm in zip(prev["meses_futuros"], prev["previsao_regressao_linear"],
                                     prev["previsao_media_movel_3m"]):
        print(f"  {mes}: regressão linear = R$ {val_reg:,.2f} | média móvel 3m = R$ {val_mm:,.2f}")

    print(f"\nDados exportados para {OUT_JSON}")
