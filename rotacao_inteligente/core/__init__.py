"""
core/__init__.py - Pacote com a lógica do projeto Rotação Inteligente.

Por que este arquivo existe:
    Transforma a pasta `core/` em um pacote Python, para que possamos
    fazer `from core import culturas` etc.

O que cada módulo vai fazer (ordem de entrega do briefing):
    nasa_power.py   - baixa e faz cache dos dados climáticos da NASA POWER.
    enso.py         - classifica anos agrícolas em El Niño / La Niña / neutro.
    culturas.py     - lê culturas.csv e lista as lacunas por cultura.
    planejador.py   - calculadora de sementes (kg -> m²) e colheita estimada.
    janelas.py      - detecta janelas de oportunidade na linha do tempo.
    resiliencia.py  - índice de resiliência por rotação e cenário.
    semaforo.py     - regras do semáforo de confiança (verde/amarelo/vermelho).
    alertas.py      - gera a mensagem pronta de alerta (sem envio real).

Etapa 1: ainda vazios. São preenchidos etapa por etapa.
"""
