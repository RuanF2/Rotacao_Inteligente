"""
core/culturas.py - Etapa 4: leitura do banco de culturas e detecção de lacunas.

O QUE ESTE ARQUIVO FAZ (em linguagem simples):
    Lê `data/culturas.csv` (fornecido pelo briefing, parcial) e devolve uma
    estrutura de dados que a interface consegue consumir. Para cada cultura,
    lista os campos que estão vazios (lacunas), para o semáforo de confiança
    poder avisar ao usuário onde faltam dados.

REGRAS DO BRIEFING (seção 5.1) que este módulo segue:
    - Célula vazia = LACUNA (dado não informado). Nunca interpretar vazio
      como zero, nunca preencher por conta própria.
    - O app deve exibir "dado não preenchido" onde faltar valor.
    - Cada lacuna deve aparecer na lista de lacunas do semáforo.
    - Uma cultura SÓ É EXCLUÍDA DE ROTAÇÕES se faltar `ciclo_dias`
      (briefing 6.1, regra revisada pelo usuário em 2026-11-14). Não há
      exclusão por nome. Se `agua_mm_ciclo` estiver vazio, a cultura
      continua apta e a janela usa `config.CHUVA_MINIMA_CICLO_MM` como
      fallback, marcando o resultado como "parâmetro estimado pela
      equipe" (desconta ponto no semáforo).
    - `rendimento_potencial_kg_ha` vem de experimentos (muitos irrigados)
      e tende a ser maior que o real. `rendimento_regional_kg_ha` é o
      rendimento real do Piauí (IBGE), preenchido depois.

SOBRE `ciclo_dias` EM CULTURAS DE COBERTURA:
    Para culturas COMERCIAIS (milho, feijão, sorgo), `ciclo_dias` é o
    número de dias da semeadura à COLHEITA (ciclo completo).
    Para culturas de COBERTURA (crotalária, feijão-de-porco, guandu),
    `ciclo_dias` é o número de dias da semeadura até o CORTE no pico de
    floração — momento em que a biomassa acumulada é máxima e a cultura
    é rolada/incorporada ao solo para adubação verde. Não há colheita
    de grãos. Esta convenção vem das fontes citadas no CSV (Embrapa
    Agrobiologia, Embrapa CT181, Cadernos de Agroecologia ABA) e está
    documentada no README.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

import config


# ---------------------------------------------------------------------------
# 1. Exceções
# ---------------------------------------------------------------------------
class CulturasError(Exception):
    """Erro ao ler ou processar o banco de culturas."""


# ---------------------------------------------------------------------------
# 2. Estruturas de dados
# ---------------------------------------------------------------------------
# Colunas esperadas no CSV (briefing, seção 5.1).
COLUNAS_ESPERADAS = [
    "nome", "tipo", "ciclo_dias", "agua_mm_ciclo", "tmax_limite_c",
    "fixa_nitrogenio", "protecao_erosao", "valor_mercado",
    "taxa_semeadura_kg_ha", "rendimento_potencial_kg_ha",
    "rendimento_regional_kg_ha", "fonte",
]

# Campo que UMA cultura precisa ter preenchido para entrar em rotações
# (briefing 6.1, regra revisada pelo usuário em 2026-11-14).
# Antes era [ciclo_dias, agua_mm_ciclo]; agora só ciclo_dias. Se
# agua_mm_ciclo faltar, a cultura continua apta e usa
# config.CHUVA_MINIMA_CICLO_MM (marcado como "parâmetro estimado").
CAMPOS_ROTACAO_OBRIGATORIOS = ["ciclo_dias"]


@dataclass(frozen=True)
class Cultura:
    """Uma cultura do banco (uma linha do CSV).

    Todos os campos numéricos podem ser None (lacuna). O campo `lacunas`
    lista o nome de cada coluna que estava vazia no CSV.
    """
    nome: str
    tipo: str                          # "comercial" | "cobertura" | ""
    ciclo_dias: Optional[int]
    agua_mm_ciclo: Optional[float]
    tmax_limite_c: Optional[float]
    fixa_nitrogenio: Optional[str]     # "sim" | "nao" | None
    protecao_erosao: Optional[int]     # 1..3 ou None
    valor_mercado: Optional[int]       # 1..3 ou None
    taxa_semeadura_kg_ha: Optional[float]
    rendimento_potencial_kg_ha: Optional[float]
    rendimento_regional_kg_ha: Optional[float]
    fonte: str
    lacunas: List[str] = field(default_factory=list)

    # --- Propriedades de conveniência (consumidas pela interface) ---
    @property
    def tem_dados_para_rotacao(self) -> bool:
        """Tem `ciclo_dias` preenchido — mínimo para entrar em rotações.

        Regra revisada pelo usuário em 2026-11-14 (briefing 6.1): só
        `ciclo_dias` é obrigatório. `agua_mm_ciclo` vazio NÃO exclui a
        cultura — ela continua apta e a janela usa
        `config.CHUVA_MINIMA_CICLO_MM` (marcado "parâmetro estimado pela
        equipe"). Não há exclusão por nome.
        """
        return self.ciclo_dias is not None

    @property
    def campos_faltantes_para_rotacao(self) -> List[str]:
        """Quais campos obrigatórios para rotação estão vazios nesta cultura.

        Com a regra revisada, só `ciclo_dias` é obrigatório. Se faltar,
        a cultura não entra em rotações.
        """
        return [c for c in CAMPOS_ROTACAO_OBRIGATORIOS
                if getattr(self, c) is None]

    @property
    def agua_efetiva_mm_ciclo(self) -> float:
        """Demanda hídrica do ciclo a usar nos cálculos de janela.

        - Se `agua_mm_ciclo` está preenchido no CSV, usa ele (dado real).
        - Se está vazio, usa `config.CHUVA_MINIMA_CICLO_MM` (fallback da
          equipe, briefing 6.1). O resultado é "parâmetro estimado pela
          equipe" — ver `usa_agua_estimada`.

        Levanta CulturasError se ambos forem inválidos (csv vazio E
        config.CHUVA_MINIMA_CICLO_MM = None), pois aí não há como calcular
        a janela (regra "não invente dado").
        """
        if self.agua_mm_ciclo is not None:
            return float(self.agua_mm_ciclo)
        if config.CHUVA_MINIMA_CICLO_MM is None:
            raise CulturasError(
                f"{self.nome}: agua_mm_ciclo vazio no CSV e "
                "config.CHUVA_MINIMA_CICLO_MM é None — não é possível "
                "calcular a janela (regra 'não invente dado')."
            )
        return float(config.CHUVA_MINIMA_CICLO_MM)

    @property
    def usa_agua_estimada(self) -> bool:
        """True se a cultura usa o fallback da equipe em vez do CSV.

        True quando `agua_mm_ciclo` está vazio no CSV E
        `config.CHUVA_MINIMA_CICLO_MM` é o valor usado. Usado pelo
        semáforo para descontar 1 ponto quando um parâmetro estimado
        foi usado (briefing 6.5).
        """
        return (self.agua_mm_ciclo is None
                and config.CHUVA_MINIMA_CICLO_MM is not None)

    @property
    def tem_taxa_semeadura(self) -> bool:
        return self.taxa_semeadura_kg_ha is not None

    @property
    def tem_rendimento_regional(self) -> bool:
        return self.rendimento_regional_kg_ha is not None

    @property
    def tem_rendimento_potencial(self) -> bool:
        return self.rendimento_potencial_kg_ha is not None

    def valor_ou_aviso(self, atributo: str) -> str:
        """Devolve o valor como string ou o aviso de lacuna do config."""
        v = getattr(self, atributo, None)
        if v is None or v == "":
            return config.AVISO_DADO_FALTANTE
        return str(v)


# ---------------------------------------------------------------------------
# 3. Leitura do CSV
# ---------------------------------------------------------------------------
def ler_culturas_csv(caminho=config.CULTURAS_CSV) -> Dict[str, Cultura]:
    """Lê data/culturas.csv e devolve {nome: Cultura}.

    Tratamentos:
        - Célula vazia -> None (lacuna). NUNCA vira 0.
        - Espaços em branco -> "" (string vazia tratada como lacuna).
        - Linha duplicada (mesmo nome) -> erro.
        - Cabeçalho inesperado -> erro.
    """
    if not caminho.exists():
        raise CulturasError(
            f"Arquivo de culturas não encontrado: {caminho}."
        )

    # keep_default_na=False para que string vazia não vire NaN; tratamos
    # a lacuna explicitamente, mantendo o controle de qual coluna falta.
    try:
        df = pd.read_csv(caminho, encoding="utf-8", dtype=str,
                         keep_default_na=False)
    except Exception as e:
        raise CulturasError(f"Erro ao ler {caminho}: {e}") from e

    # Confere cabeçalho
    faltam = [c for c in COLUNAS_ESPERADAS if c not in df.columns]
    if faltam:
        raise CulturasError(
            f"{caminho}: faltam colunas ({faltam}). "
            f"Esperado: {COLUNAS_ESPERADAS}. Encontrado: {list(df.columns)}."
        )

    # Confere nomes únicos e não vazios
    nomes = df["nome"].str.strip()
    if nomes.duplicated().any():
        dup = nomes[nomes.duplicated()].tolist()
        raise CulturasError(f"{caminho}: culturas duplicadas: {dup}.")
    if (nomes == "").any():
        raise CulturasError(f"{caminho}: há linhas com 'nome' vazio.")

    culturas: Dict[str, Cultura] = {}
    for _, linha in df.iterrows():
        nome = linha["nome"].strip()
        lacunas: List[str] = []

        def _opt_float(col: str) -> Optional[float]:
            """Lê uma célula como float; string vazia -> None (lacuna)."""
            v = str(linha[col]).strip()
            if v == "":
                lacunas.append(col)
                return None
            try:
                return float(v)
            except ValueError:
                # não-numérico onde se esperava número -> vira lacuna
                lacunas.append(col)
                return None

        def _opt_int(col: str) -> Optional[int]:
            v = str(linha[col]).strip()
            if v == "":
                lacunas.append(col)
                return None
            try:
                return int(float(v))
            except ValueError:
                lacunas.append(col)
                return None

        def _opt_str(col: str) -> Optional[str]:
            v = str(linha[col]).strip()
            if v == "":
                lacunas.append(col)
                return None
            return v

        tipo = _opt_str("tipo")
        ciclo_dias = _opt_int("ciclo_dias")
        agua_mm_ciclo = _opt_float("agua_mm_ciclo")
        tmax_limite_c = _opt_float("tmax_limite_c")
        fixa_nitrogenio = _opt_str("fixa_nitrogenio")
        protecao_erosao = _opt_int("protecao_erosao")
        valor_mercado = _opt_int("valor_mercado")
        taxa_semeadura_kg_ha = _opt_float("taxa_semeadura_kg_ha")
        rendimento_potencial_kg_ha = _opt_float("rendimento_potencial_kg_ha")
        rendimento_regional_kg_ha = _opt_float("rendimento_regional_kg_ha")
        fonte = str(linha["fonte"]).strip()  # fonte é texto, não é lacuna

        culturas[nome] = Cultura(
            nome=nome,
            tipo=tipo or "",
            ciclo_dias=ciclo_dias,
            agua_mm_ciclo=agua_mm_ciclo,
            tmax_limite_c=tmax_limite_c,
            fixa_nitrogenio=fixa_nitrogenio,
            protecao_erosao=protecao_erosao,
            valor_mercado=valor_mercado,
            taxa_semeadura_kg_ha=taxa_semeadura_kg_ha,
            rendimento_potencial_kg_ha=rendimento_potencial_kg_ha,
            rendimento_regional_kg_ha=rendimento_regional_kg_ha,
            fonte=fonte,
            lacunas=lacunas,
        )
    return culturas


# ---------------------------------------------------------------------------
# 4. Funções utilitárias (consumidas pelo semáforo e pelo app)
# ---------------------------------------------------------------------------
def listar_lacunas(culturas: Dict[str, Cultura]) -> Dict[str, List[str]]:
    """Devolve {nome_cultura: [lista_de_campos_vazios]}.

    Útil para a seção "Dados que faltam" da interface (briefing 7).
    Culturas sem lacunas não aparecem no dicionário.
    """
    return {nome: c.lacunas for nome, c in culturas.items() if c.lacunas}


def culturas_para_rotacao(culturas: Dict[str, Cultura]) -> List[str]:
    """Lista nomes de culturas aptas a rotações.

    Critério (briefing 6.1, regra revisada em 2026-11-14): TEM que ter
    `ciclo_dias`. `agua_mm_ciclo` vazio NÃO exclui — a cultura continua
    apta e a janela usa `config.CHUVA_MINIMA_CICLO_MM` (marcado como
    "parâmetro estimado pela equipe"). Não há exclusão por nome.
    """
    return [nome for nome, c in culturas.items() if c.tem_dados_para_rotacao]


def culturas_excluidas(culturas: Dict[str, Cultura]) -> List[str]:
    """Lista nomes de culturas sem `ciclo_dias` (não entram em rotações)."""
    return [nome for nome, c in culturas.items()
            if not c.tem_dados_para_rotacao]


def carregar_banco(caminho=config.CULTURAS_CSV) -> Dict[str, Cultura]:
    """Ponto de entrada conveniente para o app."""
    return ler_culturas_csv(caminho)


# ---------------------------------------------------------------------------
# 5. Verificação rápida (chamada direta no terminal)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Lendo {config.CULTURAS_CSV}...")
    banco = carregar_banco()
    print(f"\nTotal de culturas: {len(banco)}")
    aptas = culturas_para_rotacao(banco)
    excl = culturas_excluidas(banco)
    print(f"Aptas a rotação (têm ciclo_dias): {aptas}")
    print(f"Excluídas (sem ciclo_dias): {excl}")
    print("\nÁgua efetiva por cultura (usada no cálculo de janela):")
    for nome, c in banco.items():
        if c.ciclo_dias is None:
            print(f"  {nome:<22} (sem ciclo_dias — fora de rotações)")
            continue
        efet = c.agua_efetiva_mm_ciclo
        tag = " [param. estimado pela equipe]" if c.usa_agua_estimada else ""
        print(f"  {nome:<22} agua_efetiva={efet:.0f} mm{tag}")
    print("\nLacunas por cultura:")
    for nome, c in banco.items():
        if c.lacunas:
            print(f"  {nome}: {c.lacunas}")
        else:
            print(f"  {nome}: (sem lacunas)")
