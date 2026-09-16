"""
04_gerar_dashboard.py

Gera dashboard.html: um dashboard analítico estático (HTML + Chart.js),
com os dados de data/processed/dashboard_data.json embutidos diretamente
no arquivo. Não requer servidor web. A biblioteca Chart.js é carregada por
CDN, portanto a visualização dos gráficos requer acesso à internet, salvo
se essa dependência for armazenada localmente.

Painéis: KPIs, evolução mensal do faturamento com previsão, faturamento por
categoria, Curva ABC de produtos.
"""
import json

with open("data/processed/dashboard_data.json", encoding="utf-8") as f:
    dados = json.load(f)

kpis = dados["kpis"]
serie = dados["serie_mensal"]
categorias = dados["ranking_categorias"]
abc = dados["curva_abc"]
prev = dados["previsao"]

meses_hist = [p["ano_mes"] for p in serie]
valores_hist = [p["faturamento"] for p in serie]
meses_full = meses_hist + prev["meses_futuros"]
valores_reg = [None] * len(valores_hist) + prev["previsao_regressao_linear"]
valores_hist_padded = valores_hist + [None, None, None]
# ponto de conexão entre histórico e previsão
valores_reg[len(valores_hist) - 1] = valores_hist[-1]

dados_json_embed = json.dumps(dados, ensure_ascii=False)

def fmt_moeda_br(valor):
    texto = f"{valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_inteiro_br(valor):
    return f"{int(valor):,}".replace(",", ".")


html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Dashboard BI — Nordeste Variedades Ltda.</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1420; --card: #1a2232; --accent: #4f8ff7; --accent2: #34d399;
    --text: #e8ecf4; --muted: #93a1b8; --border: #2a3448;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif;
    background: var(--bg); color: var(--text); padding: 24px 32px 48px;
  }}
  h1 {{ font-size: 22px; font-weight: 600; margin: 0 0 4px; }}
  .subtitle {{ color: var(--muted); font-size: 13px; margin-bottom: 24px; }}
  .kpi-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px; margin-bottom: 28px;
  }}
  .kpi-card {{
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 16px 18px;
  }}
  .kpi-card .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
  .kpi-card .value {{ font-size: 22px; font-weight: 700; margin-top: 6px; }}
  .grid-2 {{ display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 16px; }}
  .card {{
    background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 18px;
  }}
  .card h2 {{ font-size: 14px; margin: 0 0 14px; color: var(--text); font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 6px 4px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 500; }}
  .classe-A {{ color: var(--accent2); font-weight: 600; }}
  .classe-B {{ color: #f5c451; font-weight: 600; }}
  .classe-C {{ color: #93a1b8; }}
  .footer-note {{ color: var(--muted); font-size: 11px; margin-top: 24px; }}
</style>
</head>
<body>
<h1>Nordeste Variedades Ltda. — Painel Analítico de Vendas</h1>
<div class="subtitle">Dashboard gerado a partir do modelo dimensional parcialmente normalizado construído no pipeline de ETL — período 2024–2025, com previsão para o 1º trimestre de 2026</div>

<div class="kpi-grid">
  <div class="kpi-card"><div class="label">Faturamento Líquido</div><div class="value">R$ {fmt_moeda_br(kpis['faturamento_liquido'])}</div></div>
  <div class="kpi-card"><div class="label">Faturamento Bruto</div><div class="value">R$ {fmt_moeda_br(kpis['faturamento_bruto'])}</div></div>
  <div class="kpi-card"><div class="label">Devoluções</div><div class="value">R$ {fmt_moeda_br(kpis['total_devolucoes'])}</div></div>
  <div class="kpi-card"><div class="label">Operações contabilizadas</div><div class="value">{fmt_inteiro_br(kpis['n_transacoes'])}</div></div>
  <div class="kpi-card"><div class="label">Itens Vendidos</div><div class="value">{fmt_inteiro_br(kpis['itens_vendidos'])}</div></div>
  <div class="kpi-card"><div class="label">Valor médio por operação</div><div class="value">R$ {fmt_moeda_br(kpis['ticket_medio'])}</div></div>
</div>

<div class="grid-2">
  <div class="card">
    <h2>Faturamento Mensal — Histórico e Previsão (Regressão Linear)</h2>
    <canvas id="chartSerie" height="110"></canvas>
  </div>
  <div class="card">
    <h2>Faturamento por Categoria</h2>
    <canvas id="chartCategoria" height="140"></canvas>
  </div>
</div>

<div class="grid-2">
  <div class="card">
    <h2>Curva ABC — Distribuição do Faturamento por Produto</h2>
    <canvas id="chartABC" height="120"></canvas>
  </div>
  <div class="card">
    <h2>Classificação ABC dos Produtos (Top 10)</h2>
    <table>
      <thead><tr><th>Produto</th><th>Faturamento</th><th>% Acum.</th><th>Classe</th></tr></thead>
      <tbody>
        {''.join(f"<tr><td>{p['produto']}</td><td>R$ {fmt_moeda_br(p['faturamento'])}</td><td>{p['pct_acumulado']}%</td><td class='classe-{p['classe']}'>{p['classe']}</td></tr>" for p in abc[:10])}
      </tbody>
    </table>
  </div>
</div>

<div class="footer-note">
  Modelo de previsão: regressão linear simples sobre a série mensal de faturamento (R² = {prev['coeficientes']['r2']}).
  Trabalho de Conclusão de Curso — Especialização em Business Intelligence, Business Analytics e Big Data Aplicados a Negócios — FAFIRE.
</div>

<script>
const dados = {dados_json_embed};

new Chart(document.getElementById('chartSerie'), {{
  type: 'line',
  data: {{
    labels: {json.dumps(meses_full)},
    datasets: [
      {{
        label: 'Faturamento realizado',
        data: {json.dumps(valores_hist_padded)},
        borderColor: '#4f8ff7', backgroundColor: 'rgba(79,143,247,0.15)',
        tension: 0.25, fill: true, spanGaps: false,
      }},
      {{
        label: 'Previsão (regressão linear)',
        data: {json.dumps(valores_reg)},
        borderColor: '#34d399', borderDash: [6,4],
        tension: 0.25, fill: false, spanGaps: false,
      }}
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ labels: {{ color: '#e8ecf4' }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#93a1b8' }}, grid: {{ color: '#2a3448' }} }},
      y: {{ ticks: {{ color: '#93a1b8' }}, grid: {{ color: '#2a3448' }} }}
    }}
  }}
}});

new Chart(document.getElementById('chartCategoria'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps([c['categoria'] for c in categorias])},
    datasets: [{{
      label: 'Faturamento (R$)',
      data: {json.dumps([c['faturamento'] for c in categorias])},
      backgroundColor: '#4f8ff7'
    }}]
  }},
  options: {{
    indexAxis: 'y',
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: '#93a1b8' }}, grid: {{ color: '#2a3448' }} }},
      y: {{ ticks: {{ color: '#93a1b8' }}, grid: {{ display: false }} }}
    }}
  }}
}});

new Chart(document.getElementById('chartABC'), {{
  type: 'line',
  data: {{
    labels: {json.dumps([p['produto'] for p in abc])},
    datasets: [{{
      label: '% Acumulado do Faturamento',
      data: {json.dumps([p['pct_acumulado'] for p in abc])},
      borderColor: '#f5c451', backgroundColor: 'rgba(245,196,81,0.1)',
      fill: true, tension: 0.15, pointRadius: 2,
    }}]
  }},
  options: {{
    plugins: {{ legend: {{ labels: {{ color: '#e8ecf4' }} }} }},
    scales: {{
      x: {{ ticks: {{ display: false }}, grid: {{ display: false }} }},
      y: {{ ticks: {{ color: '#93a1b8' }}, grid: {{ color: '#2a3448' }}, min: 0, max: 100 }}
    }}
  }}
}});
</script>
</body>
</html>
"""

with open("dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)

print("dashboard.html gerado com sucesso.")
