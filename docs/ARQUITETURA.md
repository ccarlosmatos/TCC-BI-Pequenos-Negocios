# Arquitetura do projeto

## Fluxo do pipeline

```mermaid
flowchart LR
    A[Base sintetica CSV] --> B[ETL em Python]
    B --> C[SQLite\nmodelo dimensional]
    C --> D[Analise e previsao]
    D --> E[JSON de indicadores]
    E --> F[Dashboard HTML]
```

## Modelo dimensional

```mermaid
erDiagram
    DIM_TEMPO ||--o{ FATO_VENDAS : referencia
    DIM_PRODUTO ||--o{ FATO_VENDAS : referencia
    DIM_CATEGORIA ||--o{ DIM_PRODUTO : classifica

    DIM_TEMPO {
      int id_tempo PK
      date data
      int ano
      int mes
      int trimestre
      string ano_mes
    }

    DIM_CATEGORIA {
      int id_categoria PK
      string categoria
    }

    DIM_PRODUTO {
      int id_produto PK
      string produto
      int id_categoria FK
    }

    FATO_VENDAS {
      int id_venda_origem
      int id_tempo FK
      int id_produto FK
      int quantidade
      real preco_unitario
      real valor_total
      string forma_pagamento
      string loja
      bool eh_devolucao
    }
```

A tabela fato se relaciona diretamente com tempo e produto. A categoria permanece em uma tabela propria ligada a produto. Por isso, a implementacao e descrita como modelo dimensional parcialmente normalizado, com caracteristica de floco de neve.
