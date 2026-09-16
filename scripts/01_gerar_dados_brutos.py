"""
01_gerar_dados_brutos.py

Gera um conjunto de dados sintético que simula a exportação bruta do sistema
transacional (PDV) de uma pequena empresa varejista fictícia, a "Nordeste
Variedades Ltda.", ao longo de dois anos (2024-2025).

O dataset é gerado propositalmente com problemas típicos de qualidade de
dados (valores ausentes, formatos inconsistentes, duplicidades, texto com
caixa alta/baixa misturada) para permitir demonstrar, na etapa de ETL, as
técnicas de limpeza e padronização discutidas nas disciplinas de Gestão da
Qualidade, ETL - Tratamento de Dados e Modelagem de Dados do curso.

Saída: data/raw/vendas_bruto.csv
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

CATEGORIAS_PRODUTOS = {
    "Eletrônicos": ["Fone de Ouvido Bluetooth", "Carregador USB-C", "Caixa de Som Portátil",
                     "Cabo HDMI", "Power Bank 10000mAh", "Mouse Sem Fio"],
    "Vestuário": ["Camiseta Básica", "Bermuda Jeans", "Boné Aba Reta", "Meia Esportiva",
                  "Jaqueta Corta-Vento", "Chinelo de Dedo"],
    "Alimentos": ["Café Torrado 500g", "Biscoito Recheado", "Suco de Caju 1L",
                  "Barra de Cereal", "Água de Coco 500ml", "Amendoim Torrado"],
    "Papelaria": ["Caderno Universitário", "Caneta Esferográfica", "Mochila Escolar",
                  "Estojo Simples", "Marcador de Texto", "Cola Bastão"],
    "Casa e Utilidades": ["Kit Panelas Antiaderente", "Jogo de Toalhas", "Vela Aromática",
                           "Organizador de Gaveta", "Escova de Limpeza", "Porta Sabonete"],
}

PRECOS_BASE = {}
for cat, produtos in CATEGORIAS_PRODUTOS.items():
    for p in produtos:
        PRECOS_BASE[p] = round(random.uniform(8, 250), 2)

FORMAS_PAGAMENTO = ["Dinheiro", "Cartão de Débito", "Cartão de Crédito", "Pix", "pix", "PIX"]

FORMATOS_DATA = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]

def data_aleatoria_no_periodo(inicio, fim):
    delta = (fim - inicio).days
    return inicio + timedelta(days=random.randint(0, delta))

def sazonalidade(dt):
    """Fator de sazonalidade: picos em maio (Dia das Mães), junho (S. João, força
    regional nordestina), novembro/dezembro (Black Friday e Natal)."""
    fator = 1.0
    if dt.month == 5:
        fator = 1.35
    elif dt.month == 6:
        fator = 1.45
    elif dt.month in (11, 12):
        fator = 1.6
    elif dt.month in (1, 2):
        fator = 0.75
    # leve tendência de crescimento ano a ano
    if dt.year == 2025:
        fator *= 1.12
    return fator

def gerar_linhas(inicio, fim, id_inicial=1):
    linhas = []
    idx = id_inicial
    dt = inicio
    while dt <= fim:
        fator = sazonalidade(dt)
        n_transacoes = max(1, int(random.gauss(9, 3) * fator))
        for _ in range(n_transacoes):
            categoria = random.choice(list(CATEGORIAS_PRODUTOS.keys()))
            produto = random.choice(CATEGORIAS_PRODUTOS[categoria])
            qtd = random.choices([1, 2, 3, 4, 5], weights=[45, 25, 15, 10, 5])[0]
            preco_unit = PRECOS_BASE[produto] * random.uniform(0.92, 1.08)

            # formato de data inconsistente (problema de qualidade proposital)
            fmt = random.choice(FORMATOS_DATA)
            data_str = dt.strftime(fmt)

            # texto de categoria/produto com inconsistência de caixa (~15% das linhas)
            cat_out = categoria
            prod_out = produto
            if random.random() < 0.15:
                cat_out = categoria.upper()
            if random.random() < 0.10:
                prod_out = produto.lower()

            # valores ausentes propositais (~4% categoria, ~2% forma de pagamento)
            cat_out = "" if random.random() < 0.04 else cat_out
            forma_pgto = "" if random.random() < 0.02 else random.choice(FORMAS_PAGAMENTO)

            # preço como string com vírgula decimal (padrão pt-BR de planilha)
            preco_str = f"{preco_unit:.2f}".replace(".", ",")

            # ~3% das linhas representam devoluções (quantidade negativa)
            if random.random() < 0.03:
                qtd = -abs(qtd)

            linhas.append({
                "id_venda": idx,
                "data_venda": data_str,
                "produto": prod_out,
                "categoria": cat_out,
                "quantidade": qtd,
                "preco_unitario": preco_str,
                "forma_pagamento": forma_pgto,
                "loja": "Matriz - Recife" if random.random() > 0.008 else "matriz-recife",
            })
            idx += 1
        dt += timedelta(days=1)
    return linhas, idx

linhas, prox_id = gerar_linhas(date(2024, 1, 1), date(2025, 12, 31))

# injeta duplicidades propositais (~1,5% de registros duplicados, comuns em
# exportações de PDV com reenvio de lote)
duplicatas = random.sample(linhas, k=int(len(linhas) * 0.015))
linhas.extend(duplicatas)
random.shuffle(linhas)

campos = ["id_venda", "data_venda", "produto", "categoria", "quantidade",
          "preco_unitario", "forma_pagamento", "loja"]

out_path = "data/raw/vendas_bruto.csv"
Path(out_path).parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=campos)
    writer.writeheader()
    writer.writerows(linhas)

print(f"Gerado {out_path} com {len(linhas)} linhas (incluindo duplicidades propositais).")
