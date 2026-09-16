"""
02_etl.py

Pipeline de ETL que converte o extrato bruto do PDV em um modelo dimensional
parcialmente normalizado, com característica de floco de neve, persistido em
SQLite.

Principais transformações:
  1. padronização de datas
  2. padronização de produto, categoria e identificação da loja
  3. conversão de preço do formato brasileiro para número
  4. reconstituição de categoria ausente a partir do produto
  5. tratamento de forma de pagamento ausente
  6. remoção de duplicidades exatas
  7. identificação de devoluções
  8. carga das dimensões e da tabela fato

Entrada: data/raw/vendas_bruto.csv
Saída:   data/processed/dw_vendas.sqlite3
"""
import sqlite3
from pathlib import Path
import pandas as pd

RAW_PATH = "data/raw/vendas_bruto.csv"
DB_PATH = "data/processed/dw_vendas.sqlite3"
LOJA_CANONICA = "Matriz - Recife"


def normaliza_texto(texto: str) -> str:
    if not isinstance(texto, str) or texto.strip() == "":
        return ""
    valor = " ".join(w.capitalize() for w in texto.strip().split())
    for antes, depois in {
        " E ": " e ", " De ": " de ", " Do ": " do ", " Da ": " da ",
        " Dos ": " dos ", " Das ": " das ", " Usb-C": " USB-C",
        " Hdmi": " HDMI", "10000mah": "10000mAh", " 1l": " 1L",
    }.items():
        valor = valor.replace(antes, depois)
    return valor


def normaliza_loja(texto: str) -> str:
    """Consolida as grafias conhecidas da única unidade simulada."""
    if not isinstance(texto, str) or texto.strip() == "":
        return "Não Informado"
    chave = texto.strip().lower().replace(" ", "").replace("_", "-")
    if chave in {"matriz-recife", "matriz--recife"}:
        return LOJA_CANONICA
    return normaliza_texto(texto)


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

    # Marcadores de rastreabilidade criados antes das transformações.
    df["_categoria_ausente_origem"] = df["categoria"].fillna("").str.strip().eq("")
    df["_loja_divergente_origem"] = df["loja"].fillna("").str.strip().ne(LOJA_CANONICA)
    grafias_loja_divergentes_bruto = int(df["_loja_divergente_origem"].sum())

    # 1. Datas.
    df["data_venda"] = df["data_venda"].apply(parse_data)

    # 2. Texto e identificação da loja.
    df["produto"] = df["produto"].apply(normaliza_texto)
    df["categoria"] = df["categoria"].apply(normaliza_texto)
    df["loja"] = df["loja"].apply(normaliza_loja)

    # 3. Preço em formato brasileiro para float.
    df["preco_unitario"] = (
        df["preco_unitario"].str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    # 4. Quantidade numérica.
    df["quantidade"] = df["quantidade"].astype(int)

    # 4b. Reconstitui categoria ausente pela categoria modal do mesmo produto.
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

    # 4c. Forma de pagamento ausente e variações de PIX.
    df["forma_pagamento"] = df["forma_pagamento"].replace("", pd.NA).fillna("Não Informado")
    df["forma_pagamento"] = df["forma_pagamento"].apply(
        lambda v: "Pix" if str(v).strip().upper() == "PIX"
        else normaliza_texto(v) if v != "Não Informado" else v
    )

    # Registros sem data válida não podem compor o modelo analítico.
    linhas_invalidas = int(df["data_venda"].isna().sum())
    df = df.dropna(subset=["data_venda"])

    # 5. Duplicidades exatas. Marcadores internos não participam da chave.
    chave_duplicidade = [
        "id_venda", "data_venda", "produto", "categoria", "quantidade",
        "preco_unitario", "forma_pagamento", "loja",
    ]
    duplicadas = int(df.duplicated(subset=chave_duplicidade).sum())
    df = df.drop_duplicates(subset=chave_duplicidade).copy()

    # 6. Devolução e valor líquido da linha.
    df["eh_devolucao"] = df["quantidade"] < 0
    df["valor_total"] = df["quantidade"] * df["preco_unitario"]

    relatorio = {
        "linhas_brutas": linhas_brutas,
        "linhas_data_invalida_removidas": linhas_invalidas,
        "linhas_duplicadas_removidas": duplicadas,
        "linhas_finais": len(df),
        "campos_categoria_ausentes_pre_etl": int(mask_categoria_vazia.sum()),
        "registros_finais_com_categoria_reconstituida": int(df["_categoria_ausente_origem"].sum()),
        "grafias_loja_divergentes_na_base_bruta": grafias_loja_divergentes_bruto,
        "registros_finais_com_loja_padronizada": int(df["_loja_divergente_origem"].sum()),
        "lojas_distintas_apos_padronizacao": int(df["loja"].nunique()),
    }
    return df, relatorio


def montar_modelo_dimensional(df: pd.DataFrame):
    datas_unicas = df["data_venda"].drop_duplicates().sort_values().reset_index(drop=True)
    dim_tempo = pd.DataFrame({"data": datas_unicas})
    dim_tempo["id_tempo"] = dim_tempo.index + 1
    dim_tempo["ano"] = dim_tempo["data"].dt.year
    dim_tempo["mes"] = dim_tempo["data"].dt.month
    dim_tempo["trimestre"] = dim_tempo["data"].dt.quarter
    dim_tempo["nome_mes"] = dim_tempo["data"].dt.strftime("%B")
    dim_tempo["ano_mes"] = dim_tempo["data"].dt.strftime("%Y-%m")
    dim_tempo["dia_semana"] = dim_tempo["data"].dt.strftime("%A")
    dim_tempo = dim_tempo[[
        "id_tempo", "data", "ano", "mes", "trimestre",
        "nome_mes", "ano_mes", "dia_semana",
    ]]

    categorias_unicas = sorted(df["categoria"].unique())
    dim_categoria = pd.DataFrame({"categoria": categorias_unicas})
    dim_categoria["id_categoria"] = dim_categoria.index + 1
    dim_categoria = dim_categoria[["id_categoria", "categoria"]]

    produtos_unicos = df[["produto", "categoria"]].drop_duplicates(subset=["produto"])
    produtos_unicos = produtos_unicos.merge(dim_categoria, on="categoria", how="left")
    produtos_unicos = produtos_unicos.reset_index(drop=True)
    produtos_unicos["id_produto"] = produtos_unicos.index + 1
    dim_produto = produtos_unicos[["id_produto", "produto", "id_categoria"]]

    fato = df.merge(
        dim_tempo[["id_tempo", "data"]], left_on="data_venda", right_on="data", how="left"
    )
    fato = fato.merge(dim_produto[["id_produto", "produto"]], on="produto", how="left")
    fato_vendas = fato[[
        "id_venda", "id_tempo", "id_produto", "quantidade", "preco_unitario",
        "valor_total", "forma_pagamento", "loja", "eh_devolucao",
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
    print(
        f"dim_tempo: {len(dim_tempo)} linhas | dim_categoria: {len(dim_categoria)} linhas | "
        f"dim_produto: {len(dim_produto)} linhas | fato_vendas: {len(fato_vendas)} linhas"
    )
