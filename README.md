# TCC — Business Intelligence aplicado a pequenos negócios

**Autor:** Carlos Fernando Araújo Matos  
**Curso:** Especialização em Business Intelligence, Business Analytics e Big Data Aplicados a Negócios — FAFIRE  
**Cenário:** Nordeste Variedades Ltda. (empresa fictícia; dados sintéticos)

Este repositório contém o código-fonte, os dados gerados, o banco SQLite, os resultados analíticos e os arquivos necessários para reproduzir o artefato apresentado no TCC.

## Reprodutibilidade

Os quatro scripts principais do pipeline estao disponiveis em `scripts/` e foram revisados para manter alinhamento entre codigo, documentacao e resultados apresentados no TCC. O repositorio inclui ainda uma rotina de validacao que confere estrutura, integridade e indicadores centrais.

A execucao utiliza semente aleatoria fixa (`random.seed(42)`), o que permite regenerar a mesma base sintetica e repetir o processamento de ponta a ponta. O arquivo de referencia em `reference/dashboard_data_referencia.json` permite comparar automaticamente os resultados produzidos pela nova execucao.

## Requisitos

- Python 3.9 ou superior
- pandas 2.2.3

Instalação:

```bash
python -m pip install -r requirements.txt
```

## Execução em uma única etapa

A partir da raiz do projeto:

```bash
python executar_pipeline.py
```

O comando executa, nesta ordem:

1. `scripts/01_gerar_dados_brutos.py`
2. `scripts/02_etl.py`
3. `scripts/03_analise_previsao.py`
4. `scripts/04_gerar_dashboard.py`
5. `scripts/05_validar_previsao.py`
6. `validar_pipeline.py`

Também é possível executar cada script separadamente.

## Saídas esperadas

- `data/raw/vendas_bruto.csv`: base sintética bruta
- `data/processed/dw_vendas.sqlite3`: banco analítico
- `data/processed/dashboard_data.json`: indicadores, Curva ABC e previsão
- `data/processed/validacao_previsao.json`: validação temporal retrospectiva
- `dashboard.html`: painel analítico
- `logs/validacao_pipeline.json`: manifesto de validação

## Resultados centrais reproduzidos

| Indicador | Resultado |
|---|---:|
| Registros brutos | 7.429 |
| Registros válidos | 7.320 |
| Duplicidades removidas | 109 |
| Categorias reconstituídas | 310 |
| Produtos | 30 |
| Categorias | 5 |
| Faturamento bruto | R$ 1.606.086,63 |
| Devoluções | R$ 54.767,59 |
| Faturamento líquido | R$ 1.551.319,04 |
| Itens vendidos | 14.584 |
| Valor médio por operação | R$ 211,93 |
| R² da regressão sobre 24 meses | 0,305 |

## Validação temporal retrospectiva

Para responder à recomendação da orientação, os últimos três meses observados, outubro a dezembro de 2025, foram separados como teste. Os modelos foram ajustados apenas com janeiro de 2024 a setembro de 2025.

| Modelo | MAE | RMSE | MAPE |
|---|---:|---:|---:|
| Regressão linear | R$ 23.264,63 | R$ 24.684,15 | 25,21% |
| Média móvel de 3 meses | R$ 27.777,72 | R$ 33.533,21 | 27,23% |

O teste é exploratório e contém apenas três observações. Não permite afirmar superioridade geral entre modelos nem substituir uma validação com série mais longa e dados reais.

## Estrutura do modelo

O banco possui quatro tabelas:

- `fato_vendas`
- `dim_tempo`
- `dim_produto`
- `dim_categoria`

A tabela fato se relaciona diretamente com tempo e produto. A categoria é mantida em tabela própria ligada ao produto. Por isso, o modelo é descrito como **dimensional parcialmente normalizado**, com característica de floco de neve.

## Dashboard

O arquivo `dashboard.html` incorpora os dados analíticos no próprio HTML e não requer servidor web. A biblioteca Chart.js é carregada por CDN. Assim, os gráficos exigem acesso à internet no momento da abertura, salvo se a dependência for armazenada localmente.

## Dados sintéticos

Os dados foram gerados com `random.seed(42)`. Eles simulam uma loja varejista fictícia entre janeiro de 2024 e dezembro de 2025. Não correspondem a uma empresa real e não contêm dados pessoais.

## Auditoria

Execute:

```bash
python validar_pipeline.py
```

O validador confere:

- existência das tabelas esperadas;
- quantidade de registros e identificadores distintos;
- integridade referencial lógica;
- KPIs financeiros;
- R² da regressão;
- igualdade do JSON reproduzido com o artefato de referência;
- métricas do teste retrospectivo.

