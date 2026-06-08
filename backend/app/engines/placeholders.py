"""Port Python do engine placeholders (abandono-app/src/engines/placeholders.ts).

Espelho server-side da substituição de tokens {{campo=glifo}}. A UI continua
usando a versão TS; esta é a fonte canônica no servidor. Paridade garantida por
backend/tests/test_placeholders.py contra golden de abandono-app/scripts/genPlaceholderFixtures.ts.

Mantém nomes/estrutura do original. As funções operam sobre dicts:
  ctx = {"data": ProjectData, "plan": BhaPlanFields, "pkgId": str, "pkgName": str}
`compute_data_sub_fields` recebe os package_lines por injeção (não lê arquivo),
para manter o engine puro e testável.
"""
from __future__ import annotations

import re

ProjectData = dict
BhaPlanFields = dict


def _slwlft_high_pkg_ids() -> list[str]:
    def pad(n: int) -> str:
        return f"ABAN {n:03d}"

    def rng(a: int, b: int) -> list[str]:
        return [pad(n) for n in range(a, b + 1)]

    return [
        "ABAN 031A", "ABAN 031B", "ABAN 032", "ABAN 033",  # teste BOP de arame + lubrificador
        *rng(36, 60),                                       # montagem/teste de trens via QTS
        "ABAN 079",                                         # estampagem paralela via QTS
        *rng(81, 100),                                      # perfilagem/CT — posicionar BHA via QTS
        "ABAN 119", "ABAN 120", "ABAN 121",                 # BOP-FT / injetor (flexitubo)
        "ABAN 122", "ABAN 123", "ABAN 124", "ABAN 125",     # acoplar injetor / teste estanqueidade FT
        "ABAN 237", "ABAN 238",                             # TAE / tampão bismuto via QTS
    ]


SLWLFT_HIGH_PKG_IDS: list[str] = _slwlft_high_pkg_ids()

# Chaves de BhaPlanFields que aparecem como token (resolvem de ctx.plan, não data).
PLAN_KEYS: set[str] = {
    "prof", "taeProf", "bpProf", "modelo", "bppAncoragemKlbf", "intervaloInteresseTopo",
    "intervaloInteresseBase", "broca", "diamLocalizador", "diamEstampador", "camDiamInt", "camDiamNom",
    "aplicadorCamisao", "camTipo", "diamCacamba", "tipoDesviador", "diamJdc", "modeloSlidingSleeve", "profFinal",
    "canhao", "tfaMin", "diam", "tfa", "driftRing", "jateamTopo", "jateamBase", "jateamPassadas",
    "motorFundo", "modeloBroca",
    "bpDiam", "taeDiamNom",
    "pwcCanhoneioTopo", "pwcCanhoneioBase",
}
# Teste de estanqueidade pós-instalação: campo dedicado com fallback p/ pressaoProva.
PROOF_EST: set[str] = {
    "pressaoEstStvR", "pressaoEstPlugR", "pressaoEstPlugF", "pressaoEstTae", "pressaoEstPlugTH",
}
# Tokens de prefixo Hold Point sempre ativos (sem flag).
ALWAYS_HP: dict[str, str] = {
    "_hpEcsBop": "[HOLD POINT - ECS/BOP] ",
}
# Tokens de prefixo Hold Point condicionais (governados por flag booleana em ProjectData).
HP_PREFIX_FLAG: dict[str, dict[str, str]] = {
    "_hpEstStvR":   {"flag": "pressaoEstStvRHp",   "prefix": "[HOLD POINT - SMAB] "},
    "_hpEstPlugR":  {"flag": "pressaoEstPlugRHp",  "prefix": "[HOLD POINT - SMAB] "},
    "_hpEstPlugF":  {"flag": "pressaoEstPlugFHp",  "prefix": "[HOLD POINT - SMAB] "},
    "_hpEstPlugTH": {"flag": "pressaoEstPlugTHHp", "prefix": "[HOLD POINT - SMAB] "},
    "_hpEstTae":    {"flag": "pressaoEstTaeHp",    "prefix": "[HOLD POINT - SMAB] "},
    "_hpPcabN2":    {"flag": "outrosPcabN2PsiHp",  "prefix": "[HOLD POINT - SMAB] "},
    "_hpRevcim":    {"flag": "revcimHp",           "prefix": "[HOLD POINT - REVCIM] "},
}

TOKEN_RE = re.compile(r"\{\{(\w+)=([^}]*)\}\}")


def _str(v: object) -> str:
    return v if isinstance(v, str) else ""


def resolve_field(field: str, ctx: dict) -> str:
    """Resolve o valor de um token. '' (vazio) → o chamador usa o glifo de fallback."""
    data = ctx.get("data") or {}
    plan = ctx.get("plan") or {}
    if field == "_bopBaixa":
        return "300" if data.get("pressaoBopArameHigh") else ""
    if field in ALWAYS_HP:
        return ALWAYS_HP[field]
    if field in HP_PREFIX_FLAG:
        flag = HP_PREFIX_FLAG[field]["flag"]
        prefix = HP_PREFIX_FLAG[field]["prefix"]
        val = data.get(flag)
        return prefix if (val is True or (isinstance(val, str) and val != "")) else ""
    if field in PROOF_EST:
        return _str(data.get(field)) or _str(data.get("pressaoProva"))
    if field == "camTipo":
        return _str(plan.get("camTipo")) or "permanente"
    if field in PLAN_KEYS:
        return _str(plan.get(field))
    return _str(data.get(field))


def fill_tokens(template: str, ctx: dict) -> str:
    """Substitui todos os tokens; campo vazio → glifo de fallback."""
    return TOKEN_RE.sub(lambda m: resolve_field(m.group(1), ctx) or m.group(2), template)


# Alias de compatibilidade (mesma assinatura usada pelos wrappers do AppContext).
apply_placeholders = fill_tokens


def has_tokens(text: str) -> bool:
    """A linha carrega algum token (logo, participa da substituição)."""
    return "{{" in text


def has_unfilled_tokens(text: str, ctx: dict) -> bool:
    """Algum token da linha está sem valor resolvido (linha incompleta)."""
    for m in TOKEN_RE.finditer(text):
        f = m.group(1)
        if f in ALWAYS_HP:
            continue
        if f in HP_PREFIX_FLAG:
            continue
        if not resolve_field(f, ctx):
            return True
    return False


def compute_data_sub_fields(package_lines: dict) -> set[str]:
    """Campos de ProjectData que, ao mudar, exigem re-substituição.

    Derivado dos tokens presentes nas linhas (package_lines injetado). Exclui tokens
    sintéticos (prefixo _) e chaves de plano; inclui as flags de HP e 'bhaPlans'.
    """
    found: set[str] = set()
    for pkg in package_lines.values():
        for ln in pkg:
            t = ln.get("text") if isinstance(ln, dict) else None
            if not t:
                continue
            for m in re.finditer(r"\{\{(\w+)=", t):
                f = m.group(1)
                if f.startswith("_"):
                    continue
                if f not in PLAN_KEYS:
                    found.add(f)
    for v in HP_PREFIX_FLAG.values():
        found.add(v["flag"])
    found.add("bhaPlans")
    return found
