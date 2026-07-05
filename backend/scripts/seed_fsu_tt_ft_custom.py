"""Seed do escopo custom "Abandono FSU TT-FT (custom)" (scope_id=FSU_TT_FT_CUSTOM).

Cria/atualiza (upsert idempotente) uma linha em `logic_scope_overrides` com:
  - Seção 1 = cópia do MOB_descida do usuário (lido do próprio banco, scope_id=MOB_DESCIDA);
  - Seções 2–10 = fluxograma de abandono FSU TT-FT SEM as montagens/desmontagens de
    equipamento de pressão de WL/arame/FT (a engine `applyTransitions` as reconstrói pela
    tecnologia de cada pacote).

Uso (a partir de backend/, não precisa do backend no ar):
    python scripts/seed_fsu_tt_ft_custom.py

Grava direto no mesmo SQLite que o app lê (DATABASE_URL / sqlite:///./sprint_aban.db).
O formato de `sections` espelha LSec[] de abandono-app/src/data/logicSecs.ts.
"""

import os
import sys

# Permite `from app...` ao rodar o script direto (adiciona backend/ ao path).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import LogicScopeOverride  # noqa: E402

SCOPE_ID = "FSU_TT_FT_CUSTOM"
LABEL = "Abandono FSU TT-FT (custom)"
MOB_SOURCE_SCOPE = "MOB_DESCIDA"


def pkg(pid: str, name: str) -> dict:
    return {"id": pid, "name": name}


def build_abandono_sections() -> list[dict]:
    """Seções 2–10 (abandono FSU TT-FT) — sem montagens/desmontagens de WL/arame/FT."""

    # ── SEÇÃO 2 — DHSV / BLOCOS ANM ──────────────────────────────────────────
    sec_dhsv = {
        "id": "custom_dhsv",
        "label": "DHSV / BLOCOS ANM",
        "phase": "Fase 1A",
        "color": "blue",
        "decisions": [
            {
                "question": "Instalação de camisão na DHSV?",
                "answers": [
                    {"label": "Não", "active": True, "packages": [
                        pkg("ABAN 028", "Teste bloco produção da ANM"),
                        pkg("ABAN 029", "Teste bloco anular da ANM"),
                        pkg("ABAN 030", "Teste funcional de DHSV (bullheading)"),
                    ]},
                    {"label": "Sim", "packages": [
                        pkg("ABAN 028", "Teste bloco produção da ANM"),
                        pkg("ABAN 029", "Teste bloco anular da ANM"),
                    ]},
                    {"label": "Contingência", "packages": [
                        pkg("ABAN 028", "Teste bloco produção da ANM"),
                        pkg("ABAN 029", "Teste bloco anular da ANM"),
                        pkg("ABAN 030", "Teste funcional de DHSV (bullheading)"),
                    ]},
                ],
            },
        ],
    }

    # ── SEÇÃO 3 — GABARITAGEM / ANULAR (sem ABAN 031A montagem arame) ─────────
    sec_gab = {
        "id": "custom_gab",
        "label": "GABARITAGEM / ANULAR",
        "phase": "Fase 1A",
        "color": "blue",
        "always": [pkg("ABAN 036", "Gabaritagem da coluna (arame)")],
        "decisions": [
            {
                "question": "Plug no TH?",
                "answers": [
                    {"label": "Não", "active": True},
                    {"label": "Sim", "packages": [pkg("ABAN 052", "Retirada de plug 3,75\" no TH")]},
                ],
            },
            {
                "question": "Amortecimento COP — fluido?",
                "answers": [
                    {"label": "Diesel + FCBA", "active": True, "packages": [
                        pkg("ABAN 061", "Limpeza e Amort. COP (bullheading diesel + FCBA)")]},
                    {"label": "MEG + FCBA", "packages": [
                        pkg("ABAN 062", "Limpeza e Amort. COP (bullheading MEG + FCBA)")]},
                    {"label": "Diesel puro", "packages": [
                        pkg("ABAN 219", "Preenchimento de anular A e coluna com diesel")]},
                ],
            },
            {
                "question": "Pressão no anular A?",
                "answers": [
                    {"label": "Zero", "active": True, "packages": [
                        pkg("ABAN 063", "Amort. anular A (despressurização total + bullheading FCBA)")]},
                    {"label": "Top kill — diesel", "packages": [
                        pkg("ABAN 064", "Amort. anular A (steps depress. + top kill diesel)")]},
                    {"label": "Top kill — MEG", "packages": [
                        pkg("ABAN 065", "Amort. anular A (steps depress. + top kill MEG/FCBA)")]},
                ],
            },
            {
                "question": "Log de pressão anular?",
                "answers": [
                    {"label": "Não", "active": True},
                    {"label": "Sim", "packages": [pkg("ABAN 047", "Registro de pressão e temperatura")]},
                ],
            },
        ],
    }

    tipo_csb_primario = {
        "question": "Tipo de CSB Primário?",
        "answers": [
            {"label": "TAE", "active": True, "packages": [
                pkg("ABAN 237", "Instalação de TAE (CSB primário)")]},
            {"label": "Plug wireline", "packages": [
                pkg("ABAN 040", "Plug em nipple R 2,75\""),
                pkg("ABAN 221", "Teste influxo c/ N2 (plug) — DPR"),
            ]},
        ],
    }

    # ── SEÇÃO 4 — CSB PRIMÁRIO (sem ABAN 085 montagem elétrico) ───────────────
    sec_csb1 = {
        "id": "custom_csb1",
        "label": "CSB PRIMÁRIO",
        "phase": "Fase 1A",
        "color": "blue",
        "decisions": [
            {
                "question": "CSB Primário já instalado?",
                "answers": [
                    {"label": "Sim", "active": True, "note": "(etapa omitida)"},
                    {"label": "Não", "sub": [tipo_csb_primario]},
                ],
            },
        ],
    }

    # ── SEÇÃO 5 — LIMPEZA / CONFIRMAÇÃO ──────────────────────────────────────
    sec_limp = {
        "id": "custom_limp",
        "label": "LIMPEZA / CONFIRMAÇÃO",
        "phase": "Fase 1A",
        "color": "blue",
        "always": [pkg("ABAN 222", "Confirmação de limpeza do poço")],
        "decisions": [],
    }

    # ── SEÇÃO 6 — CORTE DE COLUNA (sem ABAN 085 montagem elétrico) ────────────
    sec_corte = {
        "id": "custom_corte",
        "label": "CORTE DE COLUNA",
        "phase": "Fase 1A",
        "color": "blue",
        "decisions": [
            {
                "question": "Cortar coluna abaixo do TH?",
                "answers": [
                    {"label": "Não — há PDI", "active": True, "note": "(coluna sacável; corte omitido)"},
                    {"label": "Sim — sem PDI", "sub": [{
                        "question": "Método de corte?",
                        "answers": [
                            {"label": "Mecânico", "active": True, "packages": [
                                pkg("ABAN 113", "Corte de coluna (cortador mecânico)")]},
                            {"label": "Químico", "packages": [
                                pkg("ABAN 117", "Corte de coluna (cortador químico)")]},
                            {"label": "Plasma", "packages": [
                                pkg("ABAN 118", "Corte de coluna (cortador a plasma)")]},
                            {"label": "Explosivo", "packages": [
                                pkg("ABAN 225", "Corte de coluna (explosivo)")]},
                        ],
                    }]},
                ],
            },
        ],
    }

    def tipo_csb_secundario() -> dict:
        return {
            "question": "Tipo de CSB Secundário?",
            "answers": [
                {"label": "TAE", "active": True, "packages": [
                    pkg("ABAN 237", "TAE — CSB secundário")]},
                {"label": "Plug TH", "packages": [
                    pkg("ABAN 042", "Plug 3,75\" no TH")]},
            ],
        }

    # ── SEÇÃO 7 — CSB SECUNDÁRIO (sem ABAN 085 / ABAN 031A montagens) ─────────
    sec_csb2 = {
        "id": "custom_csb2",
        "label": "CSB SECUNDÁRIO",
        "phase": "Fase 1A",
        "color": "blue",
        "decisions": [
            {
                "question": "Canhoneio raso (tubingPerf)?",
                "answers": [
                    {"label": "Não", "active": True, "sub": [tipo_csb_secundario()]},
                    {"label": "Sim — cabo elétrico", "packages": [
                        pkg("ABAN 101", "Perfuração da coluna (tubing puncher elétrico)")],
                        "sub": [tipo_csb_secundario()]},
                    {"label": "Sim — arame", "packages": [
                        pkg("ABAN 045", "Perfuração da coluna (eFire — arame)")],
                        "sub": [tipo_csb_secundario()]},
                    {"label": "Sim — FT", "packages": [
                        pkg("ABAN 154", "Perfuração da coluna (tubing puncher FT)")],
                        "sub": [tipo_csb_secundario()]},
                ],
            },
        ],
    }

    # ── SEÇÃO 8 — FLOWLINES ──────────────────────────────────────────────────
    sec_flow = {
        "id": "custom_flow",
        "label": "FLOWLINES",
        "phase": "Extra Abandono",
        "color": "amber",
        "decisions": [
            {
                "question": "Limpar flowlines?",
                "answers": [
                    {"label": "Não", "active": True, "note": "(bloco omitido)"},
                    {"label": "Sim", "sub": [
                        {
                            "question": "Hidrato nas flowlines?",
                            "answers": [
                                {"label": "Não", "active": True},
                                {"label": "Sim / Conting.", "packages": [
                                    pkg("ABAN 167", "Dissociação hidrato — flowline prod. (DP)"),
                                    pkg("ABAN 168", "Dissociação hidrato — flowline anular (DP)"),
                                ]},
                            ],
                        },
                        {
                            "question": "Método de limpeza?",
                            "answers": [
                                {"label": "Bombeio direto", "active": True, "packages": [
                                    pkg("ABAN 066", "Limpeza de linha — DPR/Bore 4\" > FLPO"),
                                    pkg("ABAN 067", "Limpeza de linha — DPR/Bore 4\" > XO > FLGL"),
                                ]},
                                {"label": "N₂ lift", "packages": [
                                    pkg("ABAN 254", "Limpeza de Flowline(s) — N₂ Lift")]},
                            ],
                        },
                    ]},
                ],
            },
        ],
    }

    # ── SEÇÃO 9 — PLUG TMF FINAL ─────────────────────────────────────────────
    tmf_pkgs = [
        pkg("ABAN 213", "Desassentamento parcial WO (plug anular TMF)"),
        pkg("ABAN 250", "Instalação plug no TMF (bore anular)"),
        pkg("ABAN 024", "Teste interface — bore produção"),
        pkg("ABAN 027", "Teste interface — bore anular"),
    ]
    sec_tmf = {
        "id": "custom_tmf",
        "label": "PLUG TMF FINAL",
        "phase": "Fase 1A",
        "color": "blue",
        "decisions": [
            {
                "question": "Instalar plug no TMF — anular?",
                "answers": [
                    {"label": "Não", "active": True, "note": "(bloco omitido)"},
                    {"label": "Sim", "packages": list(tmf_pkgs), "sub": [{
                        "question": "Instalar plug no TMF — produção?",
                        "answers": [
                            {"label": "Não", "active": True},
                            {"label": "Sim / Conting.", "packages": [
                                pkg("ABAN 249", "Instalação plug no TMF (bore produção)")]},
                        ],
                    }]},
                    {"label": "Contingência", "packages": list(tmf_pkgs)},
                ],
            },
        ],
    }

    # ── SEÇÃO 10 — RETIRADA DO WO ────────────────────────────────────────────
    sec_ret = {
        "id": "custom_ret",
        "label": "RETIRADA DO WO",
        "phase": "Fase 1A",
        "color": "blue",
        "decisions": [
            {
                "question": "Retirar ANM?",
                "answers": [
                    {"label": "Não", "active": True, "packages": [
                        pkg("ABAN 213", "Retirada do conjunto de WO (DPR/HCR)")]},
                    {"label": "Sim", "packages": [
                        pkg("ABAN 178", "Desassentamento de ANM e retirada (DPR/HCR)"),
                        pkg("ABAN 180", "Desmobilização de FIBOP/BOPW/TRT/ANM"),
                    ]},
                ],
            },
        ],
    }

    return [sec_dhsv, sec_gab, sec_csb1, sec_limp, sec_corte, sec_csb2, sec_flow, sec_tmf, sec_ret]


def count_decisions(sections: list[dict]) -> int:
    total = 0

    def walk(decs):
        nonlocal total
        for d in decs or []:
            total += 1
            for a in d.get("answers", []):
                walk(a.get("sub"))
            walk(d.get("afterDec"))

    for sec in sections:
        walk(sec.get("decisions"))
    return total


def main() -> None:
    db = SessionLocal()
    try:
        mob = db.get(LogicScopeOverride, MOB_SOURCE_SCOPE)
        if mob is None or not mob.sections:
            raise SystemExit(
                f"ERRO: escopo de mobilização '{MOB_SOURCE_SCOPE}' não encontrado no banco "
                "(ou sem seções). Crie/salve o MOB_descida antes de rodar este seed."
            )

        # Seção 1 = REUSO VIVO do MOB_descida (referência, não cópia): edições no MOB_descida
        # propagam automaticamente. A engine/painel de perguntas expandem o `ref` na geração.
        mob_label = mob.label or "MOB_descida"
        mob_ref_section = {
            "id": "ref_mob_descida",
            "label": f"Fluxograma: {mob_label}",
            "phase": "Incluído",
            "color": "gray",
            "decisions": [],
            "ref": {"scopeId": MOB_SOURCE_SCOPE, "label": mob_label},
        }

        sections = [mob_ref_section] + build_abandono_sections()

        row = db.get(LogicScopeOverride, SCOPE_ID)
        action = "atualizado" if row is not None else "criado"
        if row is None:
            row = LogicScopeOverride(scope_id=SCOPE_ID, is_custom=True)
            db.add(row)
        row.is_custom = True
        row.label = LABEL
        row.sections = sections
        row.author = "seed"
        db.commit()

        print(f"Escopo '{SCOPE_ID}' {action} com sucesso.")
        print(f"  label   : {LABEL}")
        print(f"  seções  : {len(sections)} (1 = MOB_descida + {len(sections) - 1} de abandono)")
        print(f"  decisões: {count_decisions(sections)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
