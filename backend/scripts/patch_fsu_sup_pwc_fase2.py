"""Atualiza o escopo custom FSU_Sup_PWC_Fase2 no banco de dados.

Aplica as decisões faltantes para equivalência com o escopo bundle FSU_Sup_PWC:
  - mob:       adiciona sub "Método de retirada da CCAP?" + afterDec "Hidrato no conector TCap?"
  - conexao:   adiciona decisão "Abrir válvula da ANM com FT?"
  - gab:       converte ABAN 036 de always para decisão "Gabaritar coluna?"; adiciona "Não/N.A."
               às decisões de amortecimento; adiciona afterDec "Fluido amort. anular A pós-canhoneio?"
  - ret_conv:  converte always (ABAN 178+180) em decisão "Retirar ANM?"
  - feth_cop:  adiciona afterDec "Retirar plug 3,75" no TH (Fase 2)?"

Uso (a partir de backend/):
    python scripts/patch_fsu_sup_pwc_fase2.py
"""

import os
import sys
import json
import copy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import LogicScopeOverride  # noqa: E402

SCOPE_ID = "FSU_Sup_PWC_Fase2"


def pkg(pid: str, name: str) -> dict:
    return {"id": pid, "name": name}


def dec(question, answers, after_dec=None):
    d = {"question": question, "answers": answers}
    if after_dec:
        d["afterDec"] = after_dec
    return d


def ans(label, packages=None, active=False, sub=None, after_dec_items=None, note=None):
    a: dict = {"label": label}
    if active:
        a["active"] = True
    if packages:
        a["packages"] = packages
    if sub:
        a["sub"] = sub
    if note:
        a["note"] = note
    return a


def patch_mob(section: dict) -> dict:
    s = copy.deepcopy(section)
    decisions = s["decisions"]

    # decisions[1] = "Cap de corrosão (CCAP)?"
    # Adiciona sub à resposta "Sim" para método de retirada
    ccap_dec = decisions[1]
    assert ccap_dec["question"] == "Cap de corrosão (CCAP)?", \
        f"Esperado 'Cap de corrosão (CCAP)?', encontrado '{ccap_dec['question']}'"
    for a in ccap_dec["answers"]:
        if a["label"] == "Sim":
            a.pop("packages", None)  # remover ABAN 008 do topo — vai para sub
            a["sub"] = [{
                "question": "Método de retirada da CCAP?",
                "answers": [
                    {"label": "Coluna de trabalho", "active": True,
                     "packages": [pkg("ABAN 008", "Retirada de CCAP com coluna de trabalho (garatéia)")]},
                    {"label": "Cabo",
                     "packages": [pkg("ABAN 009", "Retirada de CCAP a cabo")]},
                ],
            }]

    # decisions[3] = "Retirar TCap?" — adiciona afterDec à pergunta do Método (dentro do ramo Sim)
    tcap_dec = decisions[3]
    assert tcap_dec["question"] == "Retirar TCap?", \
        f"Esperado 'Retirar TCap?', encontrado '{tcap_dec['question']}'"
    for a in tcap_dec["answers"]:
        if a["label"] == "Sim":
            metodo_sub = a.get("sub", [])
            for metodo_dec in metodo_sub:
                if metodo_dec.get("question") == "Método de retirada da TCap?":
                    metodo_dec["afterDec"] = [{
                        "question": "Hidrato no conector TCap?",
                        "answers": [
                            {"label": "Não", "active": True},
                            {"label": "Sim / Conting.",
                             "packages": [pkg("ABAN 177", "Jateamento de água aquecida no conector TCap")]},
                        ],
                    }]

    return s


def patch_conexao(section: dict) -> dict:
    s = copy.deepcopy(section)
    s["decisions"].append({
        "question": "Abrir válvula da ANM com FT?",
        "answers": [
            {"label": "Não", "active": True},
            {"label": "Martelete",
             "packages": [pkg("ABAN 143", "Flexitubo — Martelete para abertura de válvula ANM")]},
            {"label": "Motor + broca",
             "packages": [pkg("ABAN 124", "Flexitubo - Gabaritagem")]},
            {"label": "Ambos",
             "packages": [
                 pkg("ABAN 143", "Flexitubo — Martelete para abertura de válvula ANM"),
                 pkg("ABAN 124", "Flexitubo - Gabaritagem"),
             ]},
        ],
    })
    return s


def patch_gab(section: dict) -> dict:
    s = copy.deepcopy(section)

    # Remove ABAN 036 de always (fica só ABAN 031A)
    s["always"] = [a for a in s.get("always", []) if a["id"] != "ABAN 036"]

    decisions = s["decisions"]

    # Insere "Gabaritar coluna?" no índice 1 (após "Plug no TH?")
    gabaritar_dec = {
        "question": "Gabaritar coluna?",
        "answers": [
            {"label": "Arame", "active": True,
             "packages": [pkg("ABAN 036", "Gabaritagem da coluna (arame)")]},
            {"label": "Perfilagem",
             "packages": [pkg("ABAN 098", "Perfilagem caliper — cabo elétrico")]},
            {"label": "Flexitubo",
             "packages": [pkg("ABAN 124", "Flexitubo - Gabaritagem")]},
            {"label": "Não"},
        ],
    }
    decisions.insert(1, gabaritar_dec)

    # Agora os índices são: 0=PlugTH, 1=Gabaritar(new), 2=AmortCOP, 3=PressaoAnular, 4=RegPressao

    # decisions[2] = "Amortecimento COP — fluido?" — adiciona "Não / N.A."
    amort_dec = decisions[2]
    assert amort_dec["question"] == "Amortecimento COP — fluido?", \
        f"Esperado 'Amortecimento COP — fluido?', encontrado '{amort_dec['question']}'"
    amort_dec["answers"].append({"label": "Não / N.A."})

    # decisions[3] = "Pressão no anular A?" — adiciona "Não / N.A." + afterDec
    pressao_dec = decisions[3]
    assert pressao_dec["question"] == "Pressão no anular A?", \
        f"Esperado 'Pressão no anular A?', encontrado '{pressao_dec['question']}'"
    pressao_dec["answers"].append({"label": "Não / N.A."})
    pressao_dec["afterDec"] = [{
        "question": "Fluido amort. anular A pós-canhoneio?",
        "answers": [
            {"label": "Não incluir", "active": True},
            {"label": "Incluir",
             "packages": [pkg("ABAN 255", "Amortecimento do anular A pós-canhoneio (FCBA)")]},
        ],
    }]

    return s


def patch_ret_conv(section: dict) -> dict:
    s = copy.deepcopy(section)
    # Remove always (ABAN 178, 180) e converte em decisão
    s.pop("always", None)
    s["decisions"] = [{
        "question": "Retirar ANM?",
        "answers": [
            {"label": "Sim", "active": True,
             "packages": [
                 pkg("ABAN 178", "Desassentamento de ANM e retirada (DPR/HCR)"),
                 pkg("ABAN 180", "Desmobilização de FIBOP/BOPW/TRT/ANM"),
             ]},
            {"label": "Não"},
        ],
    }]
    return s


def patch_feth_cop(section: dict) -> dict:
    s = copy.deepcopy(section)
    # decisions[0] = "Coluna presa — corte? (conting.)" — adiciona afterDec
    feth_dec = s["decisions"][0]
    assert feth_dec["question"] == "Coluna presa — corte? (conting.)", \
        f"Esperado 'Coluna presa — corte? (conting.)', encontrado '{feth_dec['question']}'"
    feth_dec["afterDec"] = [{
        "question": "Retirar plug 3,75\" no TH (Fase 2)?",
        "answers": [
            {"label": "Não", "active": True},
            {"label": "Sim",
             "packages": [pkg("ABAN 052", "Retirada de plug 3,75\" no TH")]},
        ],
    }]
    return s


PATCHERS = {
    "mob":       patch_mob,
    "conexao":   patch_conexao,
    "gab":       patch_gab,
    "ret_conv":  patch_ret_conv,
    "feth_cop":  patch_feth_cop,
}


def main():
    db = SessionLocal()
    try:
        row = db.query(LogicScopeOverride).filter(
            LogicScopeOverride.scope_id == SCOPE_ID
        ).first()
        if not row:
            print(f"Escopo '{SCOPE_ID}' não encontrado no banco.")
            sys.exit(1)

        raw = row.sections
        sections = raw if isinstance(raw, list) else json.loads(raw)

        updated = []
        for sec in sections:
            patcher = PATCHERS.get(sec["id"])
            if patcher:
                print(f"  Aplicando patch em seção '{sec['id']}'...")
                updated.append(patcher(sec))
            else:
                updated.append(sec)

        row.sections = updated
        db.commit()
        print(f"\nEscopo '{SCOPE_ID}' atualizado com sucesso ({len(updated)} seções).")

        # Sumário das seções resultantes
        for s in updated:
            print(f"  id={s['id']}: dec={len(s.get('decisions',[]))}, always={len(s.get('always',[]))}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
