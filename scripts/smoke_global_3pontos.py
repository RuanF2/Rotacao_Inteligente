"""
scripts/smoke_global_3pontos.py - Teste de fumaça online da camada global.

Roda o pipeline completo (NASA POWER -> ENSO -> janelas -> calculadora)
em 3 pontos FORA do caso de validação (Piauí):
  - Nairóbi, Quênia (-1.29, 36.82) — hemisfério sul, África equatorial
  - Iowa, EUA (41.6, -93.6) — hemisfério norte, clima temperado
  - Punjab, Índia (31.1, 75.3) — hemisfério norte, monção

Para cada ponto, mostra:
  1. Chuva anual média (mm/ano) e nº de anos baixados.
  2. Meses-janela de milho (ciclo 120d, agua 600mm) com os 2 critérios.
  3. Mediana da chuva do ano agrícola (nov-out) por classe ENSO
     (El Niño, La Niña, neutro).

Não interpreta os resultados como verdade agronômica — apenas reporta
e diz se alguma etapa quebrou ou se comportou de modo estranho em outro
hemisfério (ex.: ano agrícola nov-out e a ligação com o DJF).
"""
import sys
from pathlib import Path

# Garante que o pacote do projeto está no path
# Correção 2.0: a pasta fica na raiz do projeto (antes procurava em download/).
ROOT = Path(__file__).resolve().parent.parent / "rotacao_inteligente"
if not ROOT.exists():
    sys.exit(f"Pasta do núcleo não encontrada: {ROOT}")
sys.path.insert(0, str(ROOT))

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import config
from core import nasa_power, enso, janelas, culturas

PONTOS = [
    ("Nairóbi (Quênia)", -1.29, 36.82),
    ("Iowa (EUA)", 41.6, -93.6),
    ("Punjab (Índia)", 31.1, 75.3),
]

CULTURA = "milho"   # ciclo 120d, agua 600mm — cultura comercial universal


def chuva_anual_media(df):
    """Soma anual de PRECTOTCORR, depois média entre anos."""
    if "PRECTOTCORR" not in df.columns:
        return None
    s = df["PRECTOTCORR"].dropna()
    if s.empty:
        return None
    # Correção 2.0: só anos civis com >= 360 dias válidos (antes o ano
    # corrente, parcial, entrava na média e puxava o valor para baixo).
    contagem = s.resample("YE").count()
    anual = s.resample("YE").sum(min_count=1)[contagem >= 360]
    return float(anual.mean()), int(len(anual))


def chuva_por_ano_agricola_e_classe(df, completos, classificacoes):
    """Para cada ano agrícola completo, soma a chuva de nov/out
    (ano agrícola N = nov/N a out/N+1) e classifica por ENSO.

    Retorna {classe: [chuvas_dos_anos_da_classe]}.
    """
    if "PRECTOTCORR" not in df.columns:
        return {}
    s = df["PRECTOTCORR"].dropna()
    # Mapa ano_agr -> classe ENSO
    classes_map = {c.ano: c.classe for c in classificacoes}
    por_classe = {"El Niño": [], "La Niña": [], "neutro": []}
    for n in completos:
        if n not in classes_map:
            continue
        inicio = pd.Timestamp(n, 11, 1)
        fim = pd.Timestamp(n + 1, 10, 31)
        sub = s[(s.index >= inicio) & (s.index <= fim)]
        if len(sub) < 300:  # ano agrícola precisa ter quase todos os dias
            continue
        soma = float(sub.sum(min_count=1))
        classe = classes_map[n]
        if classe in por_classe:
            por_classe[classe].append(soma)
    return por_classe


def main():
    print("=" * 70)
    print("TESTE DE FUMAÇA GLOBAL — 3 PONTOS FORA DO CASO DE VALIDAÇÃO (PIAUÍ)")
    print("=" * 70)
    print(f"Cultura avaliada: {CULTURA} (ciclo 120d, agua 600mm do CSV padrão)")
    print(f"Período: {config.ANO_INICIO_SERIE}-{config.ANO_FIM_SERIE} "
          f"({config.ANO_FIM_SERIE - config.ANO_INICIO_SERIE + 1} anos civis)")
    print(f"ONI: {config.ONI_CSV.name} (mesma tabela para todos os pontos —")
    print("      a classificação ENSO é GLOBAL, não local).")
    print()

    # Carrega ENSO uma vez (mesma tabela para todos os pontos)
    classificacoes, contagem, _ = enso.carregar_classificacao()
    print(f"ENSO carregado: {len(classificacoes)} anos agrícolas classificados")
    print(f"  El Niño: {contagem.get('El Niño', 0)}, "
          f"La Niña: {contagem.get('La Niña', 0)}, "
          f"neutro: {contagem.get('neutro', 0)}")
    print()

    banco = culturas.carregar_banco()
    cultura_obj = banco[CULTURA]
    print(f"Cultura {CULTURA}: ciclo={cultura_obj.ciclo_dias}d, "
          f"agua_efetiva={cultura_obj.agua_efetiva_mm_ciclo}mm, "
          f"estimada={cultura_obj.usa_agua_estimada}")
    print()

    erros = []
    for nome, lat, lon in PONTOS:
        print("-" * 70)
        print(f"📍 {nome} — ({lat}, {lon})")
        print("-" * 70)
        try:
            # Origem dos dados, por variável, ANTES de carregar: se o arquivo de
            # cache já existe, nada é baixado; senão a variável vem da API ao vivo.
            em_cache = [v for v in config.NASA_POWER_VARS
                        if nasa_power._nome_cache(lat, lon, config.ANO_INICIO_SERIE,
                                                  config.ANO_FIM_SERIE, v).exists()]
            ao_vivo = [v for v in config.NASA_POWER_VARS if v not in em_cache]
            origem = ("cache local" if not ao_vivo else
                      "NASA POWER ao vivo" if not em_cache else "misto")
            print(f"  Origem dos dados: {origem} "
                  f"(cache: {len(em_cache)}/{len(config.NASA_POWER_VARS)} variáveis"
                  + (f"; baixadas agora: {ao_vivo}" if ao_vivo else "") + ")")
            df, falhas, _ = nasa_power.carregar_series(
                lat=lat, lon=lon,
                ano_inicio=config.ANO_INICIO_SERIE,
                ano_fim=config.ANO_FIM_SERIE,
            )
            if falhas:
                print(f"  ⚠️ Variáveis com falha: {falhas}")
                erros.append(f"{nome}: falhas={falhas}")
            print(f"  Período recebido: {df.index.min().date()} a {df.index.max().date()} "
                  f"({len(df)} dias, colunas: {', '.join(df.columns)})")
            if df.empty:
                print(f"  ❌ DataFrame vazio — pulando")
                erros.append(f"{nome}: DataFrame vazio")
                continue

            # 1. Chuva anual média
            res = chuva_anual_media(df)
            if res:
                media, n_anos = res
                print(f"  1. Chuva anual média: {media:.0f} mm/ano ({n_anos} anos)")
            else:
                print(f"  1. ❌ Sem dado de chuva")
                erros.append(f"{nome}: sem chuva")
                continue

            # Anos agrícolas completos
            completos, incompletos = enso.anos_agricolas_completos(df)
            print(f"     Anos agrícolas completos: {len(completos)} "
                  f"({completos[0]}-{completos[-1]})" if completos else
                  f"     ❌ Sem anos agrícolas completos")
            if not completos:
                erros.append(f"{nome}: sem AA completos")
                continue

            # 2. Meses-janela de milho
            r = janelas.calcular_janelas(df, cultura_obj,
                                         anos_agricolas_completos=completos)
            if r.aviso_geral and not r.janelas:
                print(f"  2. ❌ Janelas: {r.aviso_geral}")
                erros.append(f"{nome}: janelas vazias")
            else:
                print(f"  2. Meses-janela de {CULTURA}: {r.meses_janela}")
                # Detalhe: chuva do ciclo e estab por mês (mediana)
                for jm in r.janelas:
                    if jm.chuva_ciclo_mm is None:
                        continue
                    est = (f"{jm.chuva_estab_mm:.0f}"
                           if jm.chuva_estab_mm is not None else "—")
                    marca = "✓" if jm.e_janela else "✗"
                    print(f"       {janelas.nome_mes(jm.mes):>3}: {marca} "
                          f"ciclo={jm.chuva_ciclo_mm:>5.0f}/"
                          f"{jm.agua_necessaria_mm:>3.0f}mm, "
                          f"estab={est:>4}/{jm.estab_necessaria_mm:>2.0f}mm")

            # 3. Mediana da chuva do ano agrícola por classe ENSO
            por_classe = chuva_por_ano_agricola_e_classe(
                df, completos, classificacoes)
            print(f"  3. Mediana da chuva do ano agrícola por ENSO:")
            for classe in ("El Niño", "La Niña", "neutro"):
                vals = por_classe[classe]
                if vals:
                    med = float(np.median(vals))
                    print(f"       {classe:<10}: {med:>6.0f} mm "
                          f"(n={len(vals)}, min={min(vals):.0f}, "
                          f"max={max(vals):.0f})")
                else:
                    print(f"       {classe:<10}: (sem anos na classe)")

            # Observação: ano agrícola nov-out pode não fazer sentido
            # em hemisérios com sazonalidade diferente
            # (ex.: Iowa tem safra verão-outono, não nov-out).
            if lon < -30 or lat > 30:
                print(f"  ℹ️ NOTA: ano agrícola nov-out (briefing) pode não")
                print(f"     corresponder à safra local deste ponto. A ")
                print(f"     classificação ENSO (DJF) também é do")
                print(f"     hemisfério norte equatorial. Apenas reportado.")

        except Exception as e:
            print(f"  ❌ ERRO: {e}")
            erros.append(f"{nome}: {e}")
        print()

    print("=" * 70)
    print("RESUMO")
    print("=" * 70)
    if erros:
        print(f"❌ {len(erros)} erro(s)/aviso(s):")
        for e in erros:
            print(f"  - {e}")
    else:
        print("✅ Nenhuma etapa quebrou. Pipeline rodou nos 3 pontos.")
    resultado_ok = not erros
    print()
    print("Observações sobre comportamento em outro hemisfério:")
    print("- Ano agrícola nov-out é uma convenção do briefing (Piauí).")
    print("  Em Iowa/Punjab/Nairóbi, a safra local segue outra sazonalidade.")
    print("  A classificação ENSO (ONI/DJF) é global, mas a correlação com")
    print("  a chuva LOCAL varia por região (El Niño ↔ seca no NE brasileiro,")
    print("  ↔ chuva no sul dos EUA, etc.). Os números acima são reportados")
    print("  sem interpretação agronômica.")


    return resultado_ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
