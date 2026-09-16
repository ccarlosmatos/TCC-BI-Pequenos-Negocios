"""Validação temporal simples dos modelos de referência.

Usa os últimos três meses observados (outubro a dezembro de 2025) como
conjunto de teste. Os modelos são ajustados somente com janeiro de 2024 a
setembro de 2025. A regressão produz três passos à frente. A média móvel usa
a média dos três últimos meses do conjunto de treino como referência fixa
para os três meses de teste.

Saída: data/processed/validacao_previsao.json
"""
import json
import math
import statistics
from pathlib import Path

IN_JSON = Path("data/processed/dashboard_data.json")
OUT_JSON = Path("data/processed/validacao_previsao.json")


def regressao_linear(valores):
    n = len(valores)
    xs = list(range(n))
    mx = statistics.mean(xs)
    my = statistics.mean(valores)
    b1 = sum((x - mx) * (y - my) for x, y in zip(xs, valores)) / sum((x - mx) ** 2 for x in xs)
    b0 = my - b1 * mx
    return b0, b1


def metricas(reais, previstos):
    erros_abs = [abs(r - p) for r, p in zip(reais, previstos)]
    return {
        "mae": round(statistics.mean(erros_abs), 2),
        "rmse": round(math.sqrt(statistics.mean([(r - p) ** 2 for r, p in zip(reais, previstos)])), 2),
        "mape_pct": round(statistics.mean([abs((r - p) / r) for r, p in zip(reais, previstos)]) * 100, 2),
    }


def main():
    dados = json.loads(IN_JSON.read_text(encoding="utf-8"))
    serie = dados["serie_mensal"]
    valores = [x["faturamento"] for x in serie]
    meses = [x["ano_mes"] for x in serie]

    treino = valores[:-3]
    reais = valores[-3:]
    meses_teste = meses[-3:]

    b0, b1 = regressao_linear(treino)
    n = len(treino)
    prev_reg = [round(b0 + b1 * (n + i), 2) for i in range(3)]
    media3 = round(statistics.mean(treino[-3:]), 2)
    prev_mm = [media3] * 3

    resultado = {
        "metodo": "holdout_temporal_3_meses",
        "treino": {"inicio": meses[0], "fim": meses[-4], "n_meses": len(treino)},
        "teste": {"inicio": meses_teste[0], "fim": meses_teste[-1], "n_meses": 3},
        "meses_teste": meses_teste,
        "realizado": reais,
        "regressao_linear": {
            "previsoes": prev_reg,
            "metricas": metricas(reais, prev_reg),
        },
        "media_movel_3m": {
            "previsoes": prev_mm,
            "metricas": metricas(reais, prev_mm),
        },
        "observacao": "Validação retrospectiva simples. A amostra é curta e os resultados não substituem avaliação em série mais longa ou dados reais.",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== Validação temporal: outubro a dezembro de 2025 ===")
    for nome in ("regressao_linear", "media_movel_3m"):
        m = resultado[nome]["metricas"]
        print(f"{nome}: MAE=R$ {m['mae']:,.2f} | RMSE=R$ {m['rmse']:,.2f} | MAPE={m['mape_pct']:.2f}%")
    print(f"Arquivo gravado em {OUT_JSON}")


if __name__ == "__main__":
    main()
