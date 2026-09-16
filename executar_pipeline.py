"""Executa todo o pipeline e a validação em uma única chamada."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ETAPAS = [
    "scripts/01_gerar_dados_brutos.py",
    "scripts/02_etl.py",
    "scripts/03_analise_previsao.py",
    "scripts/04_gerar_dashboard.py",
    "scripts/05_validar_previsao.py",
    "validar_pipeline.py",
]

for etapa in ETAPAS:
    print(f"\n>>> Executando {etapa}")
    subprocess.run([sys.executable, str(ROOT / etapa)], cwd=ROOT, check=True)
print("\nPipeline executado e validado com sucesso.")
