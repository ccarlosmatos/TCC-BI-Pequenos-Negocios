"""
02_etl.py

Pipeline de ETL (Extração, Transformação e Carga) que converte o extrato
bruto do PDV (data/raw/vendas_bruto.csv) em um modelo dimensional
(modelo dimensional parcialmente normalizado, com característica de floco de neve) persistido em SQLite (data/processed/dw_vendas.sqlite3).

Etapas de transformação (qualidade de dados):
  1. Padronização de datas (múltiplos formatos -> ISO 8601)
  2. Padronização de texto (categoria/produto -> Title Case consistente)
  3. Conversão de preço (string pt-BR "1234,56" -> float)
  4. Tratamento de valores ausentes em categoria (reconstituídos a partir do
     produto) e em forma de pagamento (marcados como "Não Informado")
  5. Remoção de duplicidades exatas
  6. Sinalização de devoluções (quantidade negativa) em coluna própria,
     mantendo a venda líquida correta nas métricas
  7. Modelagem dimensional: dim_tempo, dim_produto, dim_categoria,
     fato_vendas
"""
import sqlite3
from pathlib import Path
import pandas as pd

RAW_PATH = "data/raw/vendas_bruto.csv"
DB_PATH = "data/processed/dw_vendas.sqlite3"


def normaliza_texto(texto: str) -> str:
    if not isinstance(texto, str) or texto.strip() == "":
        return ""
    texto = texto.strip()
    # normaliza espaços e caixa (Title Case), preservando acentuação
    return " ".join(w.capitalize() for w in texto.split())


def parse_data(valor: str):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return pd.to_datetime(valor, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.NaT


def carregar_e_limpar():
    df = pd.read_csv(RAW_PATH, dtype=str)
    linhas_brutas = len(df)

    # 1. datas
    df["data_venda"] = df["data_venda"].apply(parse_data)

    # 2. texto padronizado
    df["produto"] = df["produto"].apply(normaliza_texto)
    df["categoria"] = df["categoria"].apply(normaliza_texto)
    df["loja"] = df["loja"].apply(normaliza_texto)

    # 3. preço pt-BR -> float
    df["preco_unitario"] = (
        df["preco_unitario"].str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    # 4. quantidade numérica
    df["quantidade"] = df["quantidade"].astype(int)

    # 4b. reconstitui categoria ausente a partir do produto (join com o
    # mapeamento mais frequente produto->categoria já observado nos dados)
    mapa_produto_categoria = (
        df[df["categoria"] != ""]
        .groupby("produto")["categoria"]
        .agg(lambda s: s.value_counts().idxmax())
        .to_dict()
    )
    mask_categoria_vazia = df["categoria"] == ""
    df.loc[mask_categoria_vazia, "categoria"] = df.loc[mask_categoria_vazia, "produto"].map(
        mapa_produto_categoria
    )
    df["categoria"] = df["categoria"].fillna("Não Classificado")

    # 4c. forma de pagamento ausente
    df["forma_pagamento"] = df["forma_pagamento"].replace("", pd.NA).fillna("Não Informado")
    df["forma_pagamento"] = df["forma_pagamento"].str.upper().replace(
        {"PIX": "Pix"}
    )
    df["forma_pagamento"] = df["forma_pagamento"].apply(
        lambda v: "Pix" if v.upper() == "PIX" else normaliza_texto(v) if v != "Não Informado" else v
    )

    # linhas com data inválida não podem ser aproveitadas (registro corrompido)
    linhas_invalidas = df["data_venda"].isna().sum()
    df = df.dropna(subset=["data_venda"])

    # 5. remoção de duplicidades exatas (mesmo id_venda + todos os atributos)
    duplicadas = df.duplicated(
        subset=["id_venda", "data_venda", "produto", "categoria", "quantidade",
                "preco_unitario", "forma_pagamento", "loja"]
    ).sum()
    df = df.drop_duplicates(
        subset=["id_venda", "data_venda", "produto", "categoria", "quantidade",
                "preco_unitario", "forma_pagamento", "loja"]
    )

    # 6. sinaliza devolução e calcula valor líquido da linha
    df["eh_devolucao"] = df["quantidade"] < 0
    df["valor_total"] = df["quantidade"] * df["preco_unitario"]

    relatorio = {
        "linhas_brutas": linhas_brutas,
        "linhas_data_invalida_removidas": int(linhas_invalidas),
        "linhas_duplicadas_removidas": int(duplicadas),
        "linhas_finais": len(df),
        "categorias_reconstituidas": int(mask_categoria_vazia.sum()),
    }
    return df, relatorio


def montar_modelo_dimensional(df: pd.DataFrame):
    # dim_tempo
    datas_unicas = df["data_venda"].drop_duplicates().sort_values().reset_index(drop=True)
    dim_tempo = pd.DataFrame({"data": datas_unicas})
    dim_tempo["id_tempo"] = dim_tempo.index + 1
    dim_tempo["ano"] = dim_tempo["data"].dt.year
    dim_tempo["mes"] = dim_tempo["data"].dt.month
    dim_tempo["trimestre"] = dim_tempo["data"].dt.quarter
    dim_tempo["nome_mes"] = dim_tempo["data"].dt.strftime("%B")
    dim_tempo["ano_mes"] = dim_tempo["data"].dt.strftime("%Y-%m")
    dim_tempo["dia_semana"] = dim_tempo["data"].dt.strftime("%A")
    dim_tempo = dim_tempo[["id_tempo", "data", "ano", "mes", "trimestre",
                           "nome_mes", "ano_mes", "dia_semana"]]

    # dim_categoria
    categorias_unicas = sorted(df["categoria"].unique())
    dim_categoria = pd.DataFrame({"categoria": categorias_unicas})
    dim_categoria["id_categoria"] = dim_categoria.index + 1
    dim_categoria = dim_categoria[["id_categoria", "categoria"]]

    # dim_produto
    produtos_unicos = df[["produto", "categoria"]].drop_duplicates(subset=["produto"])
    produtos_unicos = produtos_unicos.merge(dim_categoria, on="categoria", how="left")
    produtos_unicos = produtos_unicos.reset_index(drop=True)
    produtos_unicos["id_produto"] = produtos_unicos.index + 1
    dim_produto = produtos_unicos[["id_produto", "produto", "id_categoria"]]

    # fato_vendas
    fato = df.merge(dim_tempo[["id_tempo", "data"]], left_on="data_venda", right_on="data", how="left")
    fato = fato.merge(dim_produto[["id_produto", "produto"]], on="produto", how="left")
    fato_vendas = fato[[
        "id_venda", "id_tempo", "id_produto", "quantidade", "preco_unitario",
        "valor_total", "forma_pagamento", "loja", "eh_devolucao"
    ]].rename(columns={"id_venda": "id_venda_origem"})

    return dim_tempo, dim_categoria, dim_produto, fato_vendas


def gravar_sqlite(dim_tempo, dim_categoria, dim_produto, fato_vendas):
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    dim_tempo.to_sql("dim_tempo", conn, if_exists="replace", index=False)
    dim_categoria.to_sql("dim_categoria", conn, if_exists="replace", index=False)
    dim_produto.to_sql("dim_produto", conn, if_exists="replace", index=False)
    fato_vendas.to_sql("fato_vendas", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fato_tempo ON fato_vendas(id_tempo)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fato_produto ON fato_vendas(id_produto)")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    df_limpo, relatorio = carregar_e_limpar()
    dim_tempo, dim_categoria, dim_produto, fato_vendas = montar_modelo_dimensional(df_limpo)
    gravar_sqlite(dim_tempo, dim_categoria, dim_produto, fato_vendas)

    print("=== Relatório de Qualidade de Dados (ETL) ===")
    for k, v in relatorio.items():
        print(f"{k}: {v}")
    print(f"\nModelo dimensional gravado em {DB_PATH}")
    print(f"dim_tempo: {len(dim_tempo)} linhas | dim_categoria: {len(dim_categoria)} linhas | "
          f"dim_produto: {len(dim_produto)} linhas | fato_vendas: {len(fato_vendas)} linhas")
