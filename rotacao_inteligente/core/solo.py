"""
core/solo.py - Etapa 7: entrada de dados de solo pelo usuário (briefing 6.5).

O QUE ESTE ARQUIVO FAZ (em linguagem simples):
    Guarda os dados de solo que o usuário informa (textura, profundidade
    da camada arável, matéria orgânica, pH). Esses dados são usados pelo
    semáforo de confiança: se o usuário informou dados do próprio solo,
    sobe 1 ponto no semáforo (briefing 6.5: "dados do solo informados
    pelo usuário = +1").

    Por que isso importa: a NASA POWER dá clima, não solo. Os parâmetros
    de culturas do CSV são calibrados para o caso de validação (Piauí).
    Se o usuário tem dados do próprio solo, a confiança aumenta — o
    planejamento é mais local, menos genérico.

NÃO É UM MODELO DE SOLO:
    Não calculamos nada com esses dados (ainda). Eles só existem para:
    (a) registrar que o usuário informou dados locais; (b) o semáforo
    somar +1 ponto. Se a Fase 2 tiver um modelo de solo, estes dados
    podem alimentá-lo.

LACUNAS:
    - Textura: arenoza/argilosa/media (default None se não informado).
    - Profundidade (cm): default None.
    - Matéria orgânica (%): default None.
    - pH: default None.
    - Umidade inicial do solo (0..1): opcional, default None.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 1. Exceções
# ---------------------------------------------------------------------------
class SoloError(Exception):
    """Erro nos dados de solo."""


# ---------------------------------------------------------------------------
# 2. Estrutura de dados
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DadosSolo:
    """Dados de solo informados pelo usuário (Etapa 7).

    - `textura`: 'arenoza' / 'media' / 'argilosa' / None.
    - `profundidade_cm`: profundidade da camada arável (cm), ou None.
    - `materia_organica_pct`: matéria orgânica (%), ou None.
    - `ph`: pH do solo, ou None.
    - `umidade_inicial`: umidade inicial do solo (fração 0..1), ou None.
    - `observacoes`: texto livre do usuário (NÃO conta para `informado`).

    A flag `informado` é True se PELO MENOS 2 campos entre {textura,
    profundidade_cm, materia_organica_pct, ph, umidade_inicial} foram
    preenchidos (revisão 2026-11-14). Antes bastava 1 (incluindo só
    observações em texto livre), o que era fraco: uma nota solta não
    é "dado de solo". Agora exige 2 campos estruturados.

    O campo `observacoes` fica disponível para a Fase 2 (texto livre,
    complemento), mas não conta para o +1 do semáforo.
    """
    textura: Optional[str] = None
    profundidade_cm: Optional[float] = None
    materia_organica_pct: Optional[float] = None
    ph: Optional[float] = None
    umidade_inicial: Optional[float] = None
    observacoes: Optional[str] = None

    @property
    def informado(self) -> bool:
        """True se >= 2 campos estruturados preenchidos (semáforo +1).

        Campos estruturados: textura, profundidade_cm,
        materia_organica_pct, ph, umidade_inicial. Observações (texto
        livre) NÃO contam — uma nota solta não é "dado de solo".
        """
        campos_estruturados = (self.textura, self.profundidade_cm,
                                self.materia_organica_pct, self.ph,
                                self.umidade_inicial)
        preenchidos = sum(1 for v in campos_estruturados
                          if v is not None and v != "")
        return preenchidos >= 2


# ---------------------------------------------------------------------------
# 3. Construtor com validação básica
# ---------------------------------------------------------------------------
def criar_dados_solo(textura: Optional[str] = None,
                     profundidade_cm: Optional[float] = None,
                     materia_organica_pct: Optional[float] = None,
                     ph: Optional[float] = None,
                     umidade_inicial: Optional[float] = None,
                     observacoes: Optional[str] = None,
                     ) -> DadosSolo:
    """Cria DadosSolo com validação básica.

    >>> criar_dados_solo(textura='arenoza', profundidade_cm=30).informado
    True
    >>> criar_dados_solo().informado
    False
    """
    if textura is not None and textura not in ("arenoza", "media", "argilosa"):
        # Não levanta erro; só ignora valor inválido (não bloqueia o app).
        textura = None
    if profundidade_cm is not None and profundidade_cm <= 0:
        profundidade_cm = None
    if materia_organica_pct is not None and materia_organica_pct < 0:
        materia_organica_pct = None
    if ph is not None and not (0 <= ph <= 14):
        ph = None
    if umidade_inicial is not None and not (0 <= umidade_inicial <= 1):
        umidade_inicial = None
    return DadosSolo(
        textura=textura,
        profundidade_cm=profundidade_cm,
        materia_organica_pct=materia_organica_pct,
        ph=ph,
        umidade_inicial=umidade_inicial,
        observacoes=observacoes,
    )


# ---------------------------------------------------------------------------
# 4. Verificação rápida
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    s1 = criar_dados_solo()
    print(f"Sem dados: informado={s1.informado}")   # False
    s2 = criar_dados_solo(textura="arenoza", profundidade_cm=30,
                          materia_organica_pct=1.5, ph=5.8)
    print(f"Com 4 campos: informado={s2.informado}")   # True
    s2b = criar_dados_solo(textura="arenoza", profundidade_cm=30)
    print(f"Com 2 campos: informado={s2b.informado}")   # True
    s2c = criar_dados_solo(textura="arenoza")
    print(f"Com 1 campo (só textura): informado={s2c.informado}")   # False
    s2d = criar_dados_solo(observacoes="solo vermelho, bem drenado")
    print(f"Com só observacoes (texto livre): informado={s2d.informado}")   # False
    print(f"  textura={s2.textura}, profundidade={s2.profundidade_cm}, "
          f"MO={s2.materia_organica_pct}%, pH={s2.ph}")
    s3 = criar_dados_solo(textura="invalida", profundidade_cm=-5, ph=20)
    print(f"Com dados inválidos: informado={s3.informado}, "
          f"textura={s3.textura}, prof={s3.profundidade_cm}, ph={s3.ph}")
