"""Port Python do engine nippleDepth (abandono-app/src/engines/nippleDepth.ts).

Espelho server-side: a UI continua usando a versão TS (instantânea); esta versão
é a fonte canônica para recomputar/validar no servidor. A paridade entre as duas
é garantida por testes contra fixtures "golden" geradas a partir do TS real
(ver backend/tests/test_nipple_depth.py e abandono-app/scripts/genNippleFixtures.ts).

Mantém a mesma lógica, nomes e comentários-chave do original para facilitar o
diff lado a lado quando o TS mudar.
"""
from __future__ import annotations

import re

# `d` é o ProjectData vindo do front (dict). Só os campos de nipple são lidos;
# qualquer chave ausente é tratada como string vazia (igual ao default do front).
ProjectData = dict


def _g(d: ProjectData, key: str) -> str:
    v = d.get(key)
    return v if isinstance(v, str) else ""


def nipple_depth_for_bha(name: str, d: ProjectData) -> str | None:
    n = name.lower()

    def usable(type_: str, depth: str) -> str | None:
        return depth.strip() if (type_ and type_.strip().lower() != "não aplicável" and depth.strip()) else None

    # Casamento por LOCAL (TMF/TH): o tipo do nipple costuma vir vazio (não há
    # diâmetro a digitar); basta a profundidade e a linha não estar "Não Aplicável".
    def usable_loc(type_: str, depth: str) -> str | None:
        return depth.strip() if (type_.strip().lower() != "não aplicável" and depth.strip()) else None

    # Compara o tamanho normalizando o separador decimal (aceita "2.75" e "2,75").
    def size_in_type(type_: str, size: str) -> bool:
        return size in type_.replace(".", ",")

    # Ordem de prioridade de busca por tamanho.
    all_: list[tuple[str, str]] = [
        (_g(d, "nipple381"), _g(d, "nipple381Depth")),            # TMF prod.
        (_g(d, "nipple375"), _g(d, "nipple375Depth")),            # TMF anular
        (_g(d, "nipple281"), _g(d, "nipple281Depth")),            # TH prod.
        (_g(d, "nippleTHanular"), _g(d, "nippleTHanularDepth")),  # TH anular
        (_g(d, "nippleDhsv"), _g(d, "nippleDhsvDepth")),          # DHSV
        (_g(d, "nipple275"), _g(d, "nipple275Depth")),            # TSR
        (_g(d, "nipplesOutros"), _g(d, "nipplesOutrosDepth")),    # cauda prod.
    ]

    # 1) Tamanho explícito no nome do pacote.
    size_match = re.search(r'nipple\s+\S+\s+(\d+,\d+)\s*"', n) or re.search(r'\b(?:plug|stv|brv)\s+(\d+,\d+)\s*"', n)
    if size_match:
        size = size_match.group(1)
        # Pode haver mais de um nipple do mesmo tamanho — usa o primeiro com prof preenchida.
        for type_, depth in all_:
            if type_ and size_in_type(type_, size):
                u = usable(type_, depth)
                if u:
                    return u
        return None

    # 2) Local: TMF/TH + bore.
    if re.search(r"\btmf\b", n):
        if re.search(r"anular", n):
            return usable_loc(_g(d, "nipple375"), _g(d, "nipple375Depth"))
        if re.search(r"produ", n):
            return usable_loc(_g(d, "nipple381"), _g(d, "nipple381Depth"))
    if re.search(r"\bth\b", n):
        if re.search(r"anular", n):
            return usable_loc(_g(d, "nippleTHanular"), _g(d, "nippleTHanularDepth"))
        return usable_loc(_g(d, "nipple281"), _g(d, "nipple281Depth"))  # TH = bore de produção

    # 3) Camisão: instalado/retirado no perfil da DHSV → profundidade do nipple da DHSV.
    if re.search(r"camis", n):
        return usable_loc(_g(d, "nippleDhsv"), _g(d, "nippleDhsvDepth"))
    return None


def camisao_dhsv_fields(item: dict, d: ProjectData) -> dict | None:
    """Ø nominal do camisão e aplicador/pescador derivados do TIPO do nipple da DHSV."""
    if not re.search(r"camis", item.get("packageName", ""), re.IGNORECASE):
        return None
    t = _g(d, "nippleDhsv").strip()
    if not t or t.lower() == "não aplicável":
        return None
    m = re.search(r"(\d+,\d+)", t)
    if not m:
        return None
    size = m.group(1)
    gs = 'GS 4"' if float(size.replace(",", ".")) < 4 else 'GS 5"'
    return {"camDiamNom": size, "aplicadorCamisao": gs}


def gabarito_fields(item: dict, d: ProjectData) -> dict | None:
    """Gabaritagem (ABAN 036): localizador/estampador por combo dos nipples da cauda."""
    if not re.search(r"gabarit", item.get("packageName", ""), re.IGNORECASE):
        return None

    def size_of(t: str | None) -> str | None:
        m = re.search(r"(\d+,\d+)", t or "")
        return m.group(1) if m else None

    out: dict = {}
    s1, s2 = size_of(_g(d, "nipple275")), size_of(_g(d, "nipplesOutros"))
    if s1 and s2:
        sset = {s1, s2}
        combos = [
            {"nips": ["2,75", "2,81"], "loc": "2,81", "est": "2,50"},
            {"nips": ["3,50", "3,56"], "loc": "3,56", "est": "3,00"},
        ]
        hit = next((c for c in combos if all(nn in sset for nn in c["nips"])), None)
        if hit:
            out["diamLocalizador"] = hit["loc"]
            out["diamEstampador"] = hit["est"]

    cands = []
    for t, dep in ((_g(d, "nipple275"), _g(d, "nipple275Depth")), (_g(d, "nipplesOutros"), _g(d, "nipplesOutrosDepth"))):
        s = size_of(t)
        if s and dep.strip():
            cands.append({"size": float(s.replace(",", ".")), "depth": dep.strip()})
    if cands:
        cands.sort(key=lambda x: x["size"])
        out["profFinal"] = cands[0]["depth"]

    return out if out else None


def bha_derived_depth(item: dict, d: ProjectData) -> str | None:
    """Profundidade derivada do nipple para um BHA (arame/elétrico/FT). None = manual."""
    name = item.get("packageName", "")
    tech = item.get("technology", "")
    has_nipple_prof = (
        (tech == "wireline" and re.search(r"instala|retirada", name, re.IGNORECASE))
        or (tech == "electric" and re.search(r"stroker", name, re.IGNORECASE))
        or (tech == "ct" and re.search(r"plug|stv|brv|camis", name, re.IGNORECASE) and re.search(r"instala|retirada", name, re.IGNORECASE))
    )
    return nipple_depth_for_bha(name, d) if has_nipple_prof else None
