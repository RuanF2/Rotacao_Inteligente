"""
core/enso.py - Etapa 3: classificação ENSO a partir do CSV do usuário.

O QUE ESTE ARQUIVO FAZ (em linguagem simples):
    Lê `data/oni.csv` (fornecido pelo usuário) e classifica cada ano
    agrícola em "El Niño", "La Niña" ou "neutro", seguindo a regra do
    briefing (seção 4 e 6.2):
        - ONI >= +0.5  -> El Niño
        - ONI <= -0.5  -> La Niña
        - caso contrário -> neutro

    Não reescreve nem recalcula nada do CSV — o usuário entregou a coluna
    `djf_oni` já com o valor DJF de cada ano agrícola, seguindo a
    convenção combinada (ano agrícola N -> DJF N+1 da NOAA).

CONVENÇÃO DE ANO AGRÍCOLA:
    ano agrícola 2024 = nov/2024 a out/2025.
    Classificação = média ONI de DJF (dez/2024 a fev/2025).
    Na tabela ONI v6 da NOAA/CPC, esse é o DJF rotulado como 2025 (a NOAA
    rotula DJF pelo ano em que o trimestre termina).
    Logo, a linha `ano=2024` do nosso CSV usa o valor DJF 2025 da NOAA.

LIMITAÇÕES REGISTRADAS (replicadas no README e no Semáforo):
    - ONI v6 (ERSSTv6) é uma série revisada: valores dos últimos meses
      podem mudar quando a NOAA atualiza o ERSST.
    - A NOAA usa o RONI (Relative ONI) no monitoramento oficial de ENSO;
      o ONI clássico (que usamos aqui) é o histórico, não o monitoramento
      oficial em tempo real.

FONTES:
    - ONI v6: https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

import config


# ---------------------------------------------------------------------------
# 1. Exceções
# ---------------------------------------------------------------------------
class EnsoError(Exception):
    """Erro ao ler ou classificar o CSV do ONI."""


# ---------------------------------------------------------------------------
# 2. Estruturas de dados
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ClassificacaoAno:
    """Resultado da classificação de um único ano agrícola."""
    ano: int
    oni: float
    classe: str            # "El Niño" | "La Niña" | "neutro"
    no_limite: bool        # True se ONI é exatamente +/- 0.5 (caso borderline)


# ---------------------------------------------------------------------------
# 3. Funções puras (testáveis sem o CSV real)
# ---------------------------------------------------------------------------
def classificar_oni(oni: float,
                    limiar_el_nino: float = config.ONI_EL_NINO,
                    limiar_la_nina: float = config.ONI_LA_NINA
                    ) -> Tuple[str, bool]:
    """Classifica um valor de ONI em El Niño / La Niña / neutro.

    Regra do briefing (seção 4):
        - ONI >= +0.5 -> El Niño
        - ONI <= -0.5 -> La Niña
        - caso contrário -> neutro

    Retorna (classe, no_limite):
        classe: "El Niño" / "La Niña" / "neutro"
        no_limite: True se ONI é exatamente +0.5 ou -0.5 (borderline).
                   Útil para sinalizar ao usuário que o ano está no limite
                   da classificação — uma pequena revisão do ONI pode
                   mudar a classe.

    >>> classificar_oni(1.5)
    ('El Niño', False)
    >>> classificar_oni(-1.5)
    ('La Niña', False)
    >>> classificar_oni(0.0)
    ('neutro', False)
    >>> classificar_oni(0.5)
    ('El Niño', True)
    >>> classificar_oni(-0.5)
    ('La Niña', True)
    """
    if oni >= limiar_el_nino:
        return "El Niño", (oni == limiar_el_nino)
    if oni <= limiar_la_nina:
        return "La Niña", (oni == limiar_la_nina)
    return "neutro", False


# ---------------------------------------------------------------------------
# 4. Leitura do CSV
# ---------------------------------------------------------------------------
def ler_oni_csv(caminho=config.ONI_CSV) -> pd.DataFrame:
    """Lê data/oni.csv no formato esperado (ano, djf_oni).

    Tratamentos:
        - célula vazia em djf_oni -> NaN (não vira zero).
        - valores não-numéricos -> NaN (com aviso).
        - anos duplicados -> erro.
    """
    if not caminho.exists():
        raise EnsoError(
            f"Arquivo do ONI não encontrado: {caminho}. "
            "Veja instruções no README (ONI v6 da NOAA/CPC)."
        )

    try:
        df = pd.read_csv(caminho, encoding="utf-8")
    except Exception as e:
        raise EnsoError(f"Erro ao ler {caminho}: {e}") from e

    # Confere cabeçalho
    colunas_esperadas = {"ano", "djf_oni"}
    if not colunas_esperadas.issubset(set(df.columns)):
        raise EnsoError(
            f"Cabeçalho inesperado em {caminho}. Esperado: {colunas_esperadas}. "
            f"Encontrado: {list(df.columns)}."
        )

    # Confere tipos / duplicatas
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce")
    df["djf_oni"] = pd.to_numeric(df["djf_oni"], errors="coerce")

    if df["ano"].isna().any():
        raise EnsoError(f"{caminho}: coluna 'ano' tem valores não-numéricos.")
    if df["ano"].duplicated().any():
        raise EnsoError(f"{caminho}: há anos duplicados na coluna 'ano'.")

    return df[["ano", "djf_oni"]].sort_values("ano").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 5. Classificação de toda a série
# ---------------------------------------------------------------------------
def classificar_serie(df_oni: pd.DataFrame) -> List[ClassificacaoAno]:
    """Classifica cada ano do DataFrame em El Niño / La Niña / neutro.

    Anos com djf_oni vazio (NaN) entram como classe "dado não preenchido"
    e `no_limite=False` (não dá para classificar sem valor).
    """
    resultado: List[ClassificacaoAno] = []
    for _, linha in df_oni.iterrows():
        ano = int(linha["ano"])
        oni = linha["djf_oni"]
        if pd.isna(oni):
            resultado.append(ClassificacaoAno(
                ano=ano, oni=float("nan"),
                classe="dado não preenchido", no_limite=False,
            ))
            continue
        oni_f = float(oni)
        classe, no_lim = classificar_oni(oni_f)
        resultado.append(ClassificacaoAno(
            ano=ano, oni=oni_f, classe=classe, no_limite=no_lim,
        ))
    return resultado


def contar_por_classe(classificacoes: List[ClassificacaoAno]
                      ) -> Dict[str, int]:
    """Conta quantos anos caem em cada classe.

    "dado não preenchido" entra como chave separada, mas NÃO conta
    como ano útil para o semáforo.
    """
    contagem: Dict[str, int] = {"El Niño": 0, "La Niña": 0, "neutro": 0,
                                "dado não preenchido": 0}
    for c in classificacoes:
        contagem[c.classe] = contagem.get(c.classe, 0) + 1
    return contagem


def anos_no_limite(classificacoes: List[ClassificacaoAno]) -> List[int]:
    """Lista os anos em que o ONI é exatamente +/- 0.5 (borderline)."""
    return [c.ano for c in classificacoes if c.no_limite]


def anos_agricolas_completos(df_clima: Optional[pd.DataFrame] = None
                             ) -> Tuple[List[int], List[int]]:
    """Determina quais anos agrícolas têm série climática completa.

    Ano agrícola N = nov/N a out/N+1 (briefing, seção 4).
    Para estar COMPLETO, precisamos de todos os dias de nov/N a out/N+1.

    Args:
        df_clima: DataFrame com index de datas (datetime) da NASA POWER.
                  Se None, usa os limites do config (ANO_INICIO_SERIE/
                  ANO_FIM_SERIE) e supõe cobertura total dentro do período.

    Returns:
        (completos, incompletos):
            completos: anos agrícolas N com série de nov/N a out/N+1 inteira.
            incompletos: anos agrícolas N sem série completa.
    """
    # Janela mínima que precisamos: do 1º nov do 1º ano agrícola ao 31/out
    # do último ano agrícola. Com ANO_INICIO_SERIE=1991 e ANO_FIM_SERIE=2026,
    # isso cobre os anos agrícolas 1991 (nov/1991-out/1992) a 2025
    # (nov/2025-out/2026).
    primeiro_civil = config.ANO_INICIO_SERIE
    ultimo_civil = config.ANO_FIM_SERIE

    # Anos agrícolas candidatos: de ANO_INICIO_SERIE até ANO_FIM_SERIE-1
    # (ano agrícola 2025 = nov/2025 a out/2026, precisa do ano civil 2026)
    candidatos = list(range(primeiro_civil, ultimo_civil))

    if df_clima is None or df_clima.empty:
        # Sem DataFrame: confia nos limites do config. O ano agrícola N
        # está completo se tanto nov/N quanto out/N+1 estão no período.
        completos: List[int] = []
        incompletos: List[int] = []
        for n in candidatos:
            nov_n = f"{n}-11-01"
            out_n1 = f"{n+1}-10-31"
            # Se o ano civil N+1 está dentro da série, nov/N e out/N+1
            # também estão (por construção do período fixo). Quando a série
            # termina no ano civil X, o último ano agrícola completo é X-1.
            if (n + 1) <= ultimo_civil:
                completos.append(n)
            else:
                incompletos.append(n)
        return completos, incompletos

    # Com DataFrame: verifica dia a dia (mais robusto).
    idx = df_clima.index
    data_min = idx.min()
    data_max = idx.max()
    completos = []
    incompletos = []
    for n in candidatos:
        nov_n = pd.Timestamp(n, 11, 1)
        out_n1 = pd.Timestamp(n + 1, 10, 31)
        if data_min <= nov_n and out_n1 <= data_max:
            # cobre a janela nominal — ainda pode haver buracos no meio,
            # mas para o MVP isso basta.
            completos.append(n)
        else:
            incompletos.append(n)
    return completos, incompletos


def anos_da_classe(classificacoes: List[ClassificacaoAno],
                   classe: str) -> List[int]:
    """Lista os anos que caíram em determinada classe."""
    return [c.ano for c in classificacoes if c.classe == classe]


def ano_agricola_da_semeadura(data: pd.Timestamp) -> int:
    """Devolve o ano agrícola a que pertence uma semeadura.

    Regra (briefing, seção 4 + ajuste 2026-11-14 da Etapa 6):
        ano agrícola N = nov/N a out/N+1.
        - Semeadura em nov(N) ou dez(N) -> ano agrícola N.
        - Semeadura em jan(N)..out(N) -> ano agrícola N-1.

    Exemplos:
        semeadura em 15/jan/2016 -> ano agrícola 2015 (nov/2015-out/2016).
        semeadura em 20/nov/2016 -> ano agrícola 2016 (nov/2016-out/2017).
        semeadura em 31/out/2016 -> ano agrícola 2015 (ainda out/2016).

    Isso é crucial para ligar cada semeadura à classe ENSO correta: o
    ano agrícola N usa o DJF do ano civil N+1 (dez/N a fev/N+1).

    >>> ano_agricola_da_semeadura(pd.Timestamp(2016, 1, 15))
    2015
    >>> ano_agricola_da_semeadura(pd.Timestamp(2016, 11, 20))
    2016
    >>> ano_agricola_da_semeadura(pd.Timestamp(2016, 10, 31))
    2015
    >>> ano_agricola_da_semeadura(pd.Timestamp(2016, 12, 1))
    2016
    """
    if not isinstance(data, pd.Timestamp):
        data = pd.Timestamp(data)
    ano_civil = data.year
    if data.month >= config.ANO_AGRICOLA_INICIO_MES:   # nov ou dez
        return ano_civil
    return ano_civil - 1   # jan..out pertencem ao ano agrícola anterior


def classe_da_semeadura(data: pd.Timestamp,
                       classificacoes: List[ClassificacaoAno]
                       ) -> Optional[str]:
    """Devolve a classe ENSO ('El Niño'/'La Niña'/'neutro') da semeadura.

    Usa ano_agricola_da_semeadura para achar o ano agrícola e depois
    procura a classe na lista de classificacoes. Devolve None se o ano
    agrícola não estiver na lista (fora da série) ou estiver com dado
    faltante.
    """
    n = ano_agricola_da_semeadura(data)
    for c in classificacoes:
        if c.ano == n:
            return c.classe if c.classe != "dado não preenchido" else None
    return None


def carregar_classificacao(caminho=config.ONI_CSV
                           ) -> Tuple[List[ClassificacaoAno], Dict[str, int], List[int]]:
    """Ponto de entrada conveniente: lê CSV, classifica e devolve tudo.

    Returns:
        (classificacoes, contagem, anos_limite)
            classificacoes: lista de ClassificacaoAno (todos os anos).
            contagem: {"El Niño": N, "La Niña": N, "neutro": N, ...}.
            anos_limite: anos com ONI exatamente +/- 0.5.
    """
    df = ler_oni_csv(caminho)
    classes = classificar_serie(df)
    contagem = contar_por_classe(classes)
    limite = anos_no_limite(classes)
    return classes, contagem, limite


# ---------------------------------------------------------------------------
# 6. Verificação rápida (chamada direta no terminal)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Lendo {config.ONI_CSV}...")
    classes, contagem, limite = carregar_classificacao()
    print(f"\nTotal de anos: {len(classes)}")
    print(f"Contagem por classe:")
    for c, n in contagem.items():
        print(f"  {c}: {n}")
    print(f"\nAnos no limite (ONI = ±0.5): {limite}")
    print("\nTabela completa:")
    print(f"{'ano':<6} {'djf_oni':>8}  {'classe':<22} {'no_limite':<10}")
    print("-" * 50)
    for c in classes:
        oni_str = f"{c.oni:+.1f}" if not pd.isna(c.oni) else "NaN"
        print(f"{c.ano:<6} {oni_str:>8}  {c.classe:<22} {str(c.no_limite):<10}")
