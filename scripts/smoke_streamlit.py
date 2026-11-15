"""Smoke test do Streamlit: inicia o servidor, espera subir, faz
Playwright e encerra. Tudo dentro do Python para evitar problemas de
shell com processos em background."""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "rotacao_inteligente"
PORT = 8527

# Inicia o streamlit
proc = subprocess.Popen(
    ["python3", "-m", "streamlit", "run", "app.py",
     "--server.headless", "true", "--server.port", str(PORT),
     "--browser.gatherUsageStats", "false"],
    cwd=str(ROOT),
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)

try:
    # Espera o servidor subir
    up = False
    for i in range(40):
        try:
            urllib.request.urlopen(
                f"http://localhost:{PORT}/_stcore/health", timeout=2)
            print(f"streamlit OK apos {i}s")
            up = True
            break
        except Exception:
            time.sleep(1)
    if not up:
        print("streamlit nao subiu")
        proc.terminate()
        sys.exit(1)

    # Playwright
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page()
        page.goto(f"http://localhost:{PORT}", wait_until="networkidle",
                  timeout=30000)
        page.wait_for_timeout(8000)
        html = page.content()
        termos = ['Comparativo de rotações', 'Semáforo de confiança',
                  'El Niño', 'Janelas de oportunidade', 'Escolha o local',
                  'ferramenta global', 'pior cenário', 'Dados climáticos',
                  'Planejador de sementes', 'Cenários ENSO']
        for t in termos:
            print(f"  {t}: {html.count(t)}x")
        b.close()
finally:
    proc.terminate()
    proc.wait(timeout=5)
