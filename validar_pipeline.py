"""Valida estrutura, integridade e resultados centrais do pipeline do TCC."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data/processed/dw_vendas.sqlite3"
JSON = ROOT / "data/processed/dashboard_data.json"
REF_JSON = ROOT / "reference/dashboard_data_referencia.json"
BACKTEST = ROOT / "data/processed/validacao_previsao.json"

EXPECTED = {
    "faturamento_bruto": 1606086.63,
    "total_devolucoes": 54767.59,
    "faturamento_liquido": 1551319.04,
    "n_transacoes": 7320,
    "itens_vendidos": 14584,
    "ticket_medio": 211.93,
    "r2": 0.305,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def close(a, b, tol=0.01):
    return math.isclose(float(a), float(b), abs_tol=tol)


def check(cond, label, details=""):
    status = "OK" if cond else "FALHA"
    print(f"[{status}] {label}" + (f" - {details}" if details else ""))
    if not cond:
        raise AssertionError(label)


def main():
    check(DB.exists(), "Banco SQLite gerado")
    check(JSON.exists(), "JSON analítico gerado")
    dados = json.loads(JSON.read_text(encoding="utf-8"))
    k = dados["kpis"]

    for chave in ["faturamento_bruto", "total_devolucoes", "faturamento_liquido", "ticket_medio"]:
        check(close(k[chave], EXPECTED[chave]), f"KPI {chave}", str(k[chave]))
    for chave in ["n_transacoes", "itens_vendidos"]:
        check(int(k[chave]) == EXPECTED[chave], f"KPI {chave}", str(k[chave]))
    check(close(dados["previsao"]["coeficientes"]["r2"], EXPECTED["r2"], 0.0001), "R² da regressão", str(dados["previsao"]["coeficientes"]["r2"]))

    conn = sqlite3.connect(DB)
    tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    check({"dim_tempo", "dim_categoria", "dim_produto", "fato_vendas"}.issubset(tabelas), "Quatro tabelas do modelo dimensional")
    fato = conn.execute("SELECT COUNT(*), COUNT(DISTINCT id_venda_origem) FROM fato_vendas").fetchone()
    check(fato == (7320, 7320), "Grão e unicidade de id_venda_origem", str(fato))
    check(conn.execute("SELECT COUNT(*) FROM dim_tempo").fetchone()[0] == 731, "Dimensão tempo com 731 datas")
    check(conn.execute("SELECT COUNT(*) FROM dim_categoria").fetchone()[0] == 5, "Dimensão categoria com 5 linhas")
    check(conn.execute("SELECT COUNT(*) FROM dim_produto").fetchone()[0] == 30, "Dimensão produto com 30 linhas")
    orphan_tempo = conn.execute("SELECT COUNT(*) FROM fato_vendas f LEFT JOIN dim_tempo d ON d.id_tempo=f.id_tempo WHERE d.id_tempo IS NULL").fetchone()[0]
    orphan_prod = conn.execute("SELECT COUNT(*) FROM fato_vendas f LEFT JOIN dim_produto d ON d.id_produto=f.id_produto WHERE d.id_produto IS NULL").fetchone()[0]
    orphan_cat = conn.execute("SELECT COUNT(*) FROM dim_produto p LEFT JOIN dim_categoria c ON c.id_categoria=p.id_categoria WHERE c.id_categoria IS NULL").fetchone()[0]
    check(orphan_tempo == orphan_prod == orphan_cat == 0, "Integridade referencial lógica", f"tempo={orphan_tempo}, produto={orphan_prod}, categoria={orphan_cat}")
    conn.close()

    if REF_JSON.exists():
        ref = json.loads(REF_JSON.read_text(encoding="utf-8"))
        check(dados == ref, "JSON reproduzido idêntico ao artefato de referência")

    if BACKTEST.exists():
        b = json.loads(BACKTEST.read_text(encoding="utf-8"))
        check(close(b["regressao_linear"]["metricas"]["mae"], 23264.63), "Backtest regressão MAE")
        check(close(b["regressao_linear"]["metricas"]["rmse"], 24684.15), "Backtest regressão RMSE")
        check(close(b["regressao_linear"]["metricas"]["mape_pct"], 25.21), "Backtest regressão MAPE")

    relatorio = {
        "status": "APROVADO",
        "sha256": {
            "dw_vendas.sqlite3": sha256(DB),
            "dashboard_data.json": sha256(JSON),
        },
        "observacao": "A igualdade binária do SQLite não é exigida. O conteúdo lógico e os resultados centrais são validados separadamente.",
    }
    out = ROOT / "logs/validacao_pipeline.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nVALIDAÇÃO CONCLUÍDA: APROVADO")


if __name__ == "__main__":
    main()
