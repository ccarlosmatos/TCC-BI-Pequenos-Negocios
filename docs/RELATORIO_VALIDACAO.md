# Relatório de validação do pacote reprodutível

Este pacote acompanha o TCC de Carlos Fernando Araújo Matos e documenta a reprodução do artefato de Business Intelligence.

## Resultado da execução

Status final: **APROVADO**.

O pipeline foi executado integralmente na sequência documentada e reproduziu os resultados centrais do trabalho:

- 7.429 registros brutos
- 7.320 registros válidos
- 109 duplicidades exatas removidas
- 310 categorias reconstituídas
- 731 datas em `dim_tempo`
- 5 categorias em `dim_categoria`
- 30 produtos em `dim_produto`
- 7.320 registros em `fato_vendas`
- 7.320 identificadores distintos de venda na base sintética
- faturamento bruto de R$ 1.606.086,63
- devoluções de R$ 54.767,59
- faturamento líquido de R$ 1.551.319,04
- 14.584 itens vendidos
- valor médio por operação de R$ 211,93
- R² da regressão linear de 0,305

O arquivo `dashboard_data.json` reproduzido é logicamente idêntico ao artefato de referência. O banco SQLite é validado por estrutura, contagens, integridade referencial e resultados centrais. Igualdade binária entre bancos SQLite recriados não é exigida.

## Validação temporal retrospectiva

Foi reservado o período de outubro a dezembro de 2025 para uma verificação temporal de três passos.

Regressão linear:
- MAE: R$ 23.264,63
- RMSE: R$ 24.684,15
- MAPE: 25,21%

Média móvel de três meses:
- MAE: R$ 27.777,72
- RMSE: R$ 33.533,21
- MAPE: 27,23%

A regressão apresentou menores erros nessa janela específica, mas três observações não permitem concluir superioridade geral do modelo.

## Rastreabilidade

Os quatro scripts recebidos do projeto original estão preservados em `codigo_original_recebido/`. A pasta `scripts/` contém a versão de entrega, com as mesmas regras centrais de cálculo e ajustes localizados de robustez, terminologia e validação.

Os registros detalhados estão em `logs/execucao_completa.txt` e `logs/validacao_pipeline.json`.
