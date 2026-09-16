# Relatório de validação da versão canônica

Este documento registra a reprodução técnica do artefato de Business Intelligence apresentado no TCC de Carlos Fernando Araújo Matos.

## Estado da versão

A pasta `scripts/` contém os scripts canônicos usados para gerar os artefatos desta versão. O arquivo `validar_pipeline.py` recalcula os resultados a partir do banco e exige a presença dos arquivos necessários à auditoria.

## Resultados centrais

- 7.429 registros brutos
- 109 duplicidades exatas removidas
- 7.320 registros finais
- 310 campos de categoria ausentes na base bruta
- 305 registros finais derivados dessas linhas após a remoção de duplicidades
- 731 datas em `dim_tempo`
- 5 categorias em `dim_categoria`
- 30 produtos em `dim_produto`
- 7.320 registros e 7.320 identificadores distintos em `fato_vendas`
- 61 ocorrências da grafia alternativa da loja na base bruta e 59 registros finais padronizados
- uma única identificação de loja após a padronização: `Matriz - Recife`
- faturamento bruto de R$ 1.606.086,63
- devoluções de R$ 54.767,59
- faturamento líquido de R$ 1.551.319,04
- 14.584 itens vendidos, excluídas as devoluções
- valor médio por operação de R$ 211,93
- R² da regressão linear de 0,305

## Validação temporal retrospectiva

A janela de outubro a dezembro de 2025 foi separada para teste. Os modelos foram ajustados com janeiro de 2024 a setembro de 2025.

Regressão linear:
- MAE: R$ 23.264,63
- RMSE: R$ 24.684,15
- MAPE: 25,21%

Média móvel de três meses:
- MAE: R$ 27.777,72
- RMSE: R$ 33.533,21
- MAPE: 27,23%

As métricas são calculadas antes do arredondamento das previsões para centavos. O teste contém apenas três observações e deve ser interpretado como verificação exploratória.

## Critério de aprovação

A validação exige CSV bruto, banco SQLite, JSON analítico, arquivo de backtest, dashboard e JSON de referência. O programa recalcula indicadores, séries, Curva ABC, regressão e métricas do teste retrospectivo. Uma divergência material ou a ausência de qualquer artefato obrigatório encerra a validação com status de falha.

## Testes negativos

A versão final também foi submetida a sete cenários de falha controlada, sempre em cópias descartáveis do projeto: banco adulterado, ausência do JSON de referência, ausência do arquivo de backtest, ausência do dashboard, ausência do CSV bruto, ausência do banco SQLite e reintrodução de uma grafia divergente da loja. O validador encerrou com status de falha em todos os sete casos.

O resumo dessas verificações está em `logs/testes_negativos.json`.
