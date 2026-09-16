# Versão canônica do projeto

**Versão:** 1.0  
**Data de referência:** 16 de setembro de 2026

Esta é a versão de referência do artefato técnico associado ao TCC de Carlos Fernando Araújo Matos. O mesmo conjunto de scripts centrais é apresentado no Apêndice C do trabalho e distribuído no pacote digital de reprodução.

A versão consolida:

- identificação da única loja simulada como `Matriz - Recife`
- distinção entre 310 campos de categoria ausentes na base bruta e 305 registros finais derivados dessas linhas após a deduplicação
- cálculo das métricas do teste retrospectivo antes do arredondamento de apresentação
- validação obrigatória dos artefatos de entrada e saída
- recálculo dos indicadores diretamente do SQLite
- comparação do JSON analítico com o artefato de referência e com os dados incorporados ao dashboard

A execução de referência deve terminar com `VALIDAÇÃO CONCLUÍDA: APROVADO`. Os hashes dos arquivos da versão estão registrados em `logs/MANIFEST.sha256`.
