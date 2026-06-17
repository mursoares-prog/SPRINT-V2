"""Port Python do sequenceEngine (abandono-app/src/engines/sequenceEngine.ts).

Espelho server-side de generateSchedule / recomputeTransitions. A UI continua
usando o TS; este é o gerador canônico no servidor. Paridade garantida por
backend/tests/test_sequence_engine.py contra golden de
abandono-app/scripts/genSequenceFixtures.ts.

Os dados (SEQUENCES, PACKAGES, PACKAGE_DURATIONS) vêm de backend/app/data/*.json,
exportados do TS por scripts/dumpEngineData.ts (sem retradução manual).

`inputs` é o WizardInputs como dict. Tradução fiel da lógica TS — nomes e estrutura
mantidos próximos do original para diff lado a lado.
"""
from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"


def _load(name: str) -> dict:
    return json.loads((_DATA / name).read_text(encoding="utf-8"))


PACKAGES: dict = _load("packages.json")
PACKAGE_DURATIONS: dict = _load("package_durations.json")
SEQUENCES: dict = _load("sequences.json")


def get_package(pid: str) -> dict | None:
    return PACKAGES.get(pid)


def get_duration(pid: str, percentile: float) -> float:
    d = PACKAGE_DURATIONS.get(pid)
    if not d:
        return 0.3
    if percentile <= 50:
        return d["P50"]
    if percentile >= 90:
        return d["P90"]
    x = d["P50"] + (d["P90"] - d["P50"]) * (percentile - 50) / 40
    # Replica parseFloat(x.toFixed(2)) do JS (round-half-away-from-zero no double).
    return float(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _c(v, default):
    """Equivalente ao operador ?? do TS (substitui só None/undefined)."""
    return default if v is None else v


def _yes_or_conting(v) -> bool:
    return v == "yes" or v == "contingency"


def _is_conting(v) -> bool:
    return v == "contingency"


def derive_base_mode(scope_id: str) -> str:
    return "through_casing" if scope_id.startswith("FS2") else "through_tubing"


def get_mount_package(tech, rig_type, op_type, mode):
    if tech == "wireline":
        if op_type == "LWO":
            return "ABAN 031B"
        return "ABAN 032" if rig_type == "ANC" else "ABAN 031A"
    if tech == "ct":
        return "ABAN 121" if rig_type == "ANC" else "ABAN 119"
    if tech == "electric":
        if mode == "through_casing":
            return None
        return "ABAN 086" if rig_type == "ANC" else "ABAN 085"
    return None


def get_dismount_package(tech, rig_type, op_type, mode):
    if tech == "wireline":
        return "ABAN 205" if op_type == "LWO" else "ABAN 204"
    if tech == "electric":
        if mode == "through_casing":
            return None
        return "ABAN 242" if op_type == "LWO" else "ABAN 243"
    if tech == "ct":
        return "ABAN 148" if op_type == "LWO" else "ABAN 161"
    return None


def _new_item(uid, package_id, pkg, phase, duration, opts) -> dict:
    return {
        "uid": uid,
        "packageId": package_id,
        "packageName": pkg["name"],
        "category": pkg["category"],
        "technology": pkg["technology"],
        "transitionTechnology": opts.get("transitionTechnology"),
        "phase": phase,
        "duration": duration,
        "isContingency": opts.get("isContingency", False),
        "contingencyReason": opts.get("contingencyReason"),
        "autoInserted": opts.get("autoInserted"),
        "annularBore": opts.get("annularBore"),
        "startDay": 0,
        "endDay": 0,
    }


def apply_timeline(items: list[dict]) -> list[dict]:
    day = 0.0
    out = []
    for item in items:
        start = day
        day += item["duration"]
        out.append({**item, "startDay": start, "endDay": day})
    return out


def make_auto_item(package_id, phase, percentile, is_contingency=False) -> dict:
    pkg = get_package(package_id)
    return {
        "uid": f"auto-{package_id}",
        "packageId": package_id,
        "packageName": pkg["name"],
        "category": pkg["category"],
        "technology": pkg["technology"],
        "transitionTechnology": None,
        "phase": phase,
        "duration": get_duration(package_id, percentile),
        "isContingency": is_contingency,
        "contingencyReason": None,
        "autoInserted": True,
        "annularBore": None,
        "startDay": 0,
        "endDay": 0,
    }


def generate_schedule(inputs: dict) -> list[dict]:
    rig_type = inputs["rigType"]
    operation_type = inputs["operationType"]
    scope_id = inputs["scopeId"]
    percentile = inputs["percentile"]
    equipments = _c(inputs.get("subseaEquipments"), [])
    base_mode = derive_base_mode(scope_id)
    uses_fs1_barrier = scope_id in ("FS1_Mec", "FSU_Conv_BOP", "FSU_Conv_RCMA", "FSU_Sup_COP", "FSU_Sup_PWC")
    rcma_fluid_csb = scope_id == "FSU_Conv_RCMA" and inputs.get("rcmaCsbPrincipal") == "fluid_csb"
    seq = SEQUENCES[scope_id]
    steps = seq["ANC"] if rig_type == "ANC" else seq["DP"]

    items: list[dict] = []
    uid_counter = [0]

    def next_uid():
        uid_counter[0] += 1
        return f"item-{uid_counter[0]}"

    def add_item(lst, package_id, phase, opts=None):
        opts = opts or {}
        pkg = get_package(package_id)
        if not pkg:
            return
        lst.append(_new_item(next_uid(), package_id, pkg, phase, get_duration(package_id, percentile), opts))

    current_tech = "none"
    bop_active = False
    post_perf_processed = False

    for step in steps:
        cond = step.get("condition")
        pkg_marker = step["packageId"]
        sphase = step["phase"]

        # ─── Condições ───────────────────────────────────────────────
        if cond == "clean_flowlines" and not inputs.get("cleanFlowlines"):
            continue
        if cond == "remove_anm" and not inputs.get("removeANM"):
            continue
        if cond == "not_remove_anm" and inputs.get("removeANM"):
            continue
        if cond == "no_pdi" and inputs.get("hasPDI") is not False:
            continue
        if cond == "stuck_risk" and not _yes_or_conting(inputs.get("hasStuckStringRisk")):
            continue
        if cond == "dhsv_no_sleeve" and any(v in ("yes", "contingency") for v in _c(inputs.get("installCamisao"), [])):
            continue
        if cond == "transponder_cot" and inputs.get("transponderMode") == "rov":
            continue
        if cond == "transponder_rov" and inputs.get("transponderMode") != "rov":
            continue
        if cond == "fejat" and not _yes_or_conting(inputs.get("contingencyFejat")):
            continue

        # ─── POST_MOB_INJECT ─────────────────────────────────────────
        if pkg_marker == "POST_MOB_INJECT":
            has_cc = "corrosion_cap" in equipments
            if has_cc:
                ccap_pkg = "ABAN 009" if operation_type == "LWO" else "ABAN 008"
                ccap_before = inputs.get("corrosionCapBeforeIntervention")
                if ccap_before is False:
                    add_item(items, ccap_pkg, "Fase 0")
                elif ccap_before is True:
                    if inputs.get("includeCcapBackup") is not False:
                        add_item(items, ccap_pkg, "Fase 0", {
                            "isContingency": True,
                            "contingencyReason": "Contingência: CCAP não retirada pela embarcação de apoio",
                        })
                    if _yes_or_conting(inputs.get("contingencyCcapWorkstring")):
                        ccap_conting = _is_conting(inputs.get("contingencyCcapWorkstring"))
                        add_item(items, ccap_pkg, "Fase 0", {
                            "isContingency": ccap_conting,
                            "contingencyReason": ("Contingência: retirada de CCAP a cabo" if operation_type == "LWO"
                                                  else "Contingência: retirada de CCAP com coluna de trabalho (garatéia)") if ccap_conting else None,
                        })
                else:
                    if _yes_or_conting(inputs.get("contingencyCcapWorkstring")):
                        ccap_conting = _is_conting(inputs.get("contingencyCcapWorkstring"))
                        add_item(items, ccap_pkg, "Fase 0", {
                            "isContingency": ccap_conting,
                            "contingencyReason": ("Contingência: retirada de CCAP a cabo" if operation_type == "LWO"
                                                  else "Contingência: retirada de CCAP com coluna de trabalho (garatéia)") if ccap_conting else None,
                        })
            has_tree_cap = "tree_cap" in equipments or "mini_tree_cap" in equipments
            if has_tree_cap and inputs.get("tcapRemovalMethod") == "rov":
                add_item(items, "ABAN 010", "Fase 0")
            continue

        # ─── ITF_INJECT ──────────────────────────────────────────────
        if pkg_marker == "ITF_INJECT":
            has_workstring_tcap = "tree_cap" in equipments and inputs.get("tcapRemovalMethod") != "rov"
            anc_tcap_by_rov = rig_type == "ANC" and "tree_cap" in equipments and inputs.get("tcapRemovalMethod") == "rov"
            if operation_type == "LWO":
                if not has_workstring_tcap:
                    add_item(items, "ABAN 206", sphase)
                    if rig_type == "DP":
                        add_item(items, "ABAN 014", sphase)
                    elif anc_tcap_by_rov:
                        add_item(items, "ABAN 015", sphase)
            elif rig_type == "DP" and not has_workstring_tcap:
                add_item(items, "ABAN 246", sphase)
                add_item(items, "ABAN 014", sphase)
            elif anc_tcap_by_rov:
                add_item(items, "ABAN 247", sphase)
                add_item(items, "ABAN 015", sphase)
            continue

        # ─── ANM_HYDRATE_INJECT ──────────────────────────────────────
        if pkg_marker == "ANM_HYDRATE_INJECT":
            if _yes_or_conting(inputs.get("anmHydrate")) and "hydrate" in _c(inputs.get("anmValveContingency"), []):
                conting = _is_conting(inputs.get("anmHydrate"))
                for block in ("producao", "anular"):
                    if block == "producao":
                        add_item(items, "ABAN 169" if rig_type == "ANC" else "ABAN 165", sphase, {
                            "isContingency": conting,
                            "contingencyReason": "Contingência: dissociação de hidrato na ANM — bloco de produção" if conting else None,
                        })
                    if block == "anular":
                        add_item(items, "ABAN 170" if rig_type == "ANC" else "ABAN 166", sphase, {
                            "isContingency": conting,
                            "contingencyReason": "Contingência: dissociação de hidrato na ANM — bloco de anular" if conting else None,
                        })
            continue

        # ─── ANM_VALVE_INJECT ────────────────────────────────────────
        if pkg_marker == "ANM_VALVE_INJECT":
            has_prod_bore_plug = inputs.get("hasTmfPlug") and "production" in _c(inputs.get("tmfPlugBores"), [])
            if not has_prod_bore_plug:
                conts = _c(inputs.get("anmValveContingency"), [])
                if "jateamento" in conts:
                    add_item(items, "ABAN 125", sphase, {"isContingency": True, "contingencyReason": "Contingência: jateamento com flexitubo para abertura de válvulas da ANM"})
                if "gabarit_ft" in conts:
                    add_item(items, "ABAN 124", sphase, {"isContingency": True, "contingencyReason": "Contingência: gabaritagem com motor de fundo e broca para abertura de válvulas da ANM"})
            continue

        # ─── TCAP_INJECT ─────────────────────────────────────────────
        if pkg_marker == "TCAP_INJECT":
            if inputs.get("tcapRemovalMethod") == "rov":
                continue
            if "tree_cap" in equipments:
                add_item(items, "ABAN 245" if rig_type == "ANC" else "ABAN 244", sphase)
                add_item(items, "ABAN 018", sphase)
                add_item(items, "ABAN 019", sphase)

                def emit_tcap_hydrate_contingency():
                    if _yes_or_conting(inputs.get("contingencyTcapHydrate")):
                        add_item(items, "ABAN 177", sphase, {
                            "isContingency": _is_conting(inputs.get("contingencyTcapHydrate")),
                            "contingencyReason": "Contingência: dissociação de hidrato no conector da TCap — jateamento de água aquecida" if _is_conting(inputs.get("contingencyTcapHydrate")) else None,
                        })

                if inputs.get("tcapDisposition") == "surface":
                    add_item(items, "ABAN 022" if rig_type == "ANC" else "ABAN 021", sphase)
                    emit_tcap_hydrate_contingency()
                    add_item(items, "ABAN 012" if rig_type == "ANC" else "ABAN 011", sphase)
                    if operation_type == "LWO":
                        add_item(items, "ABAN 206", sphase)
                    else:
                        add_item(items, "ABAN 247" if rig_type == "ANC" else "ABAN 246", sphase)
                    add_item(items, "ABAN 015" if rig_type == "ANC" else "ABAN 014", sphase)
                    surf_fluid = _c(inputs.get("tcapSurfaceFluid"), "n2")
                    if surf_fluid == "n2":
                        add_item(items, "ABAN 017" if rig_type == "ANC" else "ABAN 016", sphase)
                    elif surf_fluid == "inhibited_pre":
                        add_item(items, "ABAN 209" if rig_type == "ANC" else "ABAN 215", sphase)
                else:
                    add_item(items, "ABAN 020", sphase)
                    emit_tcap_hydrate_contingency()
                    if operation_type == "LWO":
                        add_item(items, "ABAN 206", sphase)
                    else:
                        add_item(items, "ABAN 247" if rig_type == "ANC" else "ABAN 246", sphase)
                    add_item(items, "ABAN 015" if rig_type == "ANC" else "ABAN 014", sphase)
                    if not inputs.get("riserFluid") or inputs.get("riserFluid") == "n2":
                        add_item(items, "ABAN 017" if rig_type == "ANC" else "ABAN 016", sphase)
                    else:
                        add_item(items, "ABAN 209" if rig_type == "ANC" else "ABAN 215", sphase)
            continue

        # ─── POST_ANM_FLUID_INJECT ───────────────────────────────────
        if pkg_marker == "POST_ANM_FLUID_INJECT":
            if ("tree_cap" in equipments and inputs.get("tcapRemovalMethod") != "rov"
                    and inputs.get("tcapDisposition") == "surface" and inputs.get("tcapSurfaceFluid") == "inhibited_post"):
                add_item(items, "ABAN 217" if rig_type == "ANC" else "ABAN 216", sphase)
            continue

        # ─── FLOWLINE_INJECT ─────────────────────────────────────────
        if pkg_marker == "FLOWLINE_INJECT":
            lines = _c(inputs.get("flowlineLines"), ["flpo"])
            method = _c(inputs.get("flowlineMethod"), "direct_pumping")
            if _yes_or_conting(inputs.get("flowlineHydrate")):
                fl_conting = _is_conting(inputs.get("flowlineHydrate"))
                has_brv = inputs.get("dhsvBrvType") == "insertable"
                hydrate_lines = _c(inputs.get("flowlineHydrateLines"), lines)
                for line in hydrate_lines:
                    if line == "flpo":
                        add_item(items, (("ABAN 175" if has_brv else "ABAN 171") if rig_type == "ANC" else ("ABAN 173" if has_brv else "ABAN 167")), sphase,
                                 {"isContingency": fl_conting, "contingencyReason": "Contingência: dissociação de hidrato na flowline de produção" if fl_conting else None})
                    if line == "flgl":
                        add_item(items, (("ABAN 176" if has_brv else "ABAN 172") if rig_type == "ANC" else ("ABAN 174" if has_brv else "ABAN 168")), sphase,
                                 {"isContingency": fl_conting, "contingencyReason": "Contingência: dissociação de hidrato na flowline de gas lift" if fl_conting else None})
            if method == "n2_lift":
                add_item(items, "ABAN 254", sphase)
            else:
                if "flpo" in lines:
                    add_item(items, "ABAN 066", sphase)
                if "flgl" in lines:
                    add_item(items, "ABAN 067", sphase)
            continue

        # ─── RISER_FLUID_INJECT ──────────────────────────────────────
        if pkg_marker == "RISER_FLUID_INJECT":
            if rig_type == "ANC" and "tree_cap" in equipments:
                continue
            if rig_type == "DP" and "tree_cap" in equipments and inputs.get("tcapRemovalMethod") != "rov":
                continue
            if rig_type == "ANC":
                if operation_type != "LWO":
                    add_item(items, "ABAN 247", sphase)
                add_item(items, "ABAN 015", sphase)
            if not inputs.get("riserFluid") or inputs.get("riserFluid") == "n2":
                add_item(items, "ABAN 017" if rig_type == "ANC" else "ABAN 016", sphase)
            else:
                add_item(items, "ABAN 209" if rig_type == "ANC" else "ABAN 215", sphase)
            continue

        # ─── LIMPEZA_INJECT ──────────────────────────────────────────
        if pkg_marker == "LIMPEZA_INJECT":
            if post_perf_processed and scope_id == "FSU_TT_BDC" and rig_type == "ANC" and inputs.get("stdvDispositionAfterTest") == "keep":
                continue
            has_camisao_conting = "contingency" in _c(inputs.get("installCamisao"), [])
            if has_camisao_conting:
                pkg = "ABAN 061"
            elif inputs.get("initialFillFluid") == "inhibited":
                pkg = "ABAN 062"
            elif inputs.get("initialFillFluid") == "diesel":
                pkg = "ABAN 219"
            else:
                pkg = "ABAN 061"
            add_item(items, pkg, sphase)
            continue

        # ─── DHSV_TEST_INJECT ────────────────────────────────────────
        if pkg_marker == "DHSV_TEST_INJECT":
            if "contingency" in _c(inputs.get("installCamisao"), []):
                add_item(items, "ABAN 030", sphase)
            continue

        # ─── ANULAR_A_INJECT ─────────────────────────────────────────
        if pkg_marker == "ANULAR_A_INJECT":
            if inputs.get("anularAMinPressure") == "nonzero":
                pkg = "ABAN 064" if inputs.get("anularFluid") == "diesel" else "ABAN 065"
            else:
                pkg = "ABAN 063"
            add_item(items, pkg, sphase)
            continue

        # ─── STDV_TEST_INJECT ────────────────────────────────────────
        if pkg_marker == "STDV_TEST_INJECT":
            if inputs.get("testColumnWithStdv"):
                add_item(items, "ABAN 038", sphase)
                if inputs.get("stdvDispositionAfterTest") != "keep":
                    add_item(items, "ABAN 048", sphase)
            continue

        # ─── PERF_INJECT ─────────────────────────────────────────────
        if pkg_marker == "PERF_INJECT":
            eff = "through_casing" if bop_active else base_mode
            amort_pkg = "ABAN 255"  # amortecimento de Anular A pos-canhoneio (bullheading FCBA) - consolidado
            if uses_fs1_barrier:
                if not rcma_fluid_csb and _c(inputs.get("fs1PerfProfunda"), "yes") == "yes":
                    method = _c(inputs.get("tubingPerfMethod"), "electric")
                    perf_tech = "wireline" if method == "wireline" else "ct" if method == "ct" else "electric"
                    perf_pkg = "ABAN 045" if method == "wireline" else "ABAN 154" if method == "ct" else "ABAN 101"
                    if current_tech != perf_tech:
                        if current_tech != "none":
                            dis = get_dismount_package(current_tech, rig_type, operation_type, eff)
                            if dis:
                                add_item(items, dis, sphase, {"autoInserted": True})
                        mnt = get_mount_package(perf_tech, rig_type, operation_type, eff)
                        if mnt:
                            add_item(items, mnt, sphase, {"autoInserted": True})
                        current_tech = perf_tech
                    add_item(items, perf_pkg, sphase)
                    add_item(items, amort_pkg, sphase)
                post_perf_processed = True
                continue
            skip_amort = scope_id == "FSU_TT_BDC" and rig_type == "ANC" and inputs.get("stdvDispositionAfterTest") == "keep"
            if inputs.get("tubingPerfMethod") == "wireline":
                add_item(items, "ABAN 045", sphase)
                if not skip_amort:
                    add_item(items, amort_pkg, sphase)
            else:
                perf_tech = "ct" if inputs.get("tubingPerfMethod") == "ct" else "electric"
                perf_pkg = "ABAN 154" if inputs.get("tubingPerfMethod") == "ct" else "ABAN 101"
                if current_tech != perf_tech:
                    if current_tech != "none":
                        dis = get_dismount_package(current_tech, rig_type, operation_type, eff)
                        if dis:
                            add_item(items, dis, sphase, {"autoInserted": True})
                    mnt = get_mount_package(perf_tech, rig_type, operation_type, eff)
                    if mnt:
                        add_item(items, mnt, sphase, {"autoInserted": True})
                    current_tech = perf_tech
                add_item(items, perf_pkg, sphase)
                if not skip_amort:
                    add_item(items, amort_pkg, sphase)
            post_perf_processed = True
            continue

        # ─── JATEAR_INJECT ───────────────────────────────────────────
        if pkg_marker == "JATEAR_INJECT":
            if inputs.get("csbPrimary") != "inflatable_packer" and _yes_or_conting(inputs.get("jatearCopCoi")):
                conting125 = _is_conting(inputs.get("jatearCopCoi"))
                add_item(items, "ABAN 125", sphase, {
                    "isContingency": conting125,
                    "contingencyReason": "Contingência: jateamento COP/COI com FT" if conting125 else None,
                })
            continue

        # ─── CSB_INJECT ──────────────────────────────────────────────
        if pkg_marker == "CSB_INJECT":
            if scope_id == "FSU_TT_BDC" and rig_type == "ANC" and inputs.get("stdvDispositionAfterTest") == "keep":
                continue
            csb = "tae" if (scope_id == "FSU_TT_BDC" and rig_type == "DP") else _c(inputs.get("csbPrimary"), "stdv")
            csb_pkg_id = ("ABAN 040" if csb == "plug" else "ABAN 237" if csb == "tae"
                          else "ABAN 162" if csb == "inflatable_packer" else "ABAN 038")
            csb_pkg = get_package(csb_pkg_id)
            if csb_pkg:
                new_tech = csb_pkg["technology"]
                effective_mode_now = "through_casing" if bop_active else base_mode
                if new_tech != "none" and new_tech != current_tech:
                    if current_tech != "none":
                        dis = get_dismount_package(current_tech, rig_type, operation_type, effective_mode_now)
                        if dis:
                            add_item(items, dis, sphase, {"autoInserted": True})
                    mnt = get_mount_package(new_tech, rig_type, operation_type, effective_mode_now)
                    if mnt:
                        add_item(items, mnt, sphase, {"autoInserted": True})
                    current_tech = new_tech
                if csb == "inflatable_packer":
                    add_item(items, "ABAN 125", sphase)
                add_item(items, csb_pkg_id, sphase)
            continue

        # ─── FT_CEMENT_INJECT ────────────────────────────────────────
        if pkg_marker == "FT_CEMENT_INJECT":
            ft_mode = _c(inputs.get("ttFtCementMode"), "single")
            logging_mode = _c(inputs.get("loggingMode"), "polias")
            eff = "through_casing" if bop_active else base_mode

            def transition(to_tech, opts=None):
                nonlocal current_tech
                opts = opts or {}
                if to_tech == current_tech or to_tech == "none":
                    return
                if current_tech != "none":
                    d = get_dismount_package(current_tech, rig_type, operation_type, eff)
                    if d:
                        add_item(items, d, sphase, {"autoInserted": True, **opts})
                m = get_mount_package(to_tech, rig_type, operation_type, eff)
                if m:
                    add_item(items, m, sphase, {"autoInserted": True, **opts})
                current_tech = to_tech

            def dismount_for_polias(opts=None):
                nonlocal current_tech
                opts = opts or {}
                if current_tech != "none":
                    dis = get_dismount_package(current_tech, rig_type, operation_type, eff)
                    if dis:
                        add_item(items, dis, sphase, opts)
                    current_tech = "none"

            if ft_mode == "single":
                add_item(items, "ABAN 156", sphase)
                if logging_mode == "pressure_equipment":
                    transition("electric")
                    add_item(items, "ABAN 105", sphase)
                else:
                    dismount_for_polias()
                    add_item(items, "ABAN 234", sphase, {"transitionTechnology": "none"})
                    add_item(items, "ABAN 105", sphase, {"transitionTechnology": "none"})
            elif ft_mode == "distinct":
                add_item(items, "ABAN 155", sphase)
                if logging_mode == "pressure_equipment":
                    transition("electric")
                    add_item(items, "ABAN 105", sphase)
                    transition("ct")
                    add_item(items, "ABAN 157", sphase)
                else:
                    dismount_for_polias()
                    add_item(items, "ABAN 105", sphase, {"transitionTechnology": "none"})
                    transition("ct")
                    add_item(items, "ABAN 157", sphase)
                    dismount_for_polias()
                    add_item(items, "ABAN 234", sphase, {"transitionTechnology": "none"})
            else:
                add_item(items, "ABAN 155", sphase)
                eval_conting = {"isContingency": True, "contingencyReason": "Contingência: perfilagem de cimento se parâmetros da 1ª etapa inconclusivos"}
                if logging_mode == "polias":
                    if current_tech != "none":
                        dis = get_dismount_package(current_tech, rig_type, operation_type, eff)
                        if dis:
                            add_item(items, dis, sphase, eval_conting)
                        current_tech = "none"
                add_item(items, "ABAN 105", sphase, {**eval_conting, "transitionTechnology": "none" if logging_mode == "polias" else None})
                if logging_mode == "polias":
                    m = get_mount_package("ct", rig_type, operation_type, eff)
                    if m:
                        add_item(items, m, sphase, eval_conting)
                    current_tech = "ct"
                add_item(items, "ABAN 157", sphase)
                if logging_mode != "pressure_equipment":
                    dismount_for_polias()
                    add_item(items, "ABAN 234", sphase, {"transitionTechnology": "none"})

            if inputs.get("perforationTestContingency"):
                p_opts = {"isContingency": True, "contingencyReason": "Contingência: canhoneio deep penetration (cabo elétrico) + BPP inflável com FT"}
                add_item(items, "ABAN 102", sphase, p_opts)
                add_item(items, "ABAN 162", sphase, p_opts)

            if current_tech != "none" and current_tech != "bop":
                dis = get_dismount_package(current_tech, rig_type, operation_type, eff)
                if dis:
                    add_item(items, dis, sphase)
                current_tech = "none"
            continue

        # ─── BDC_CEMENT_INJECT ───────────────────────────────────────
        if pkg_marker == "BDC_CEMENT_INJECT":
            add_item(items, "ABAN 084" if inputs.get("cementMethod") == "logging" else "ABAN 083", sphase)
            if inputs.get("perforationTestContingency"):
                p_opts = {"isContingency": True, "contingencyReason": "Contingência: canhoneio deep penetration (cabo elétrico) + BPP inflável com FT"}
                add_item(items, "ABAN 102", sphase, p_opts)
                add_item(items, "ABAN 162", sphase, p_opts)
            continue

        # ─── BDC_FT_CONTING_INJECT ───────────────────────────────────
        if pkg_marker == "BDC_FT_CONTING_INJECT":
            if inputs.get("contingencyTtFt"):
                ft_mode = _c(inputs.get("ttFtCementMode"), "single")
                logging_mode = _c(inputs.get("loggingMode"), "polias")
                conting = {"isContingency": True, "contingencyReason": "Contingência TT-FT: coluna não estanque — jateamento e cimentação com FT"}
                cont_polias = {**conting, "transitionTechnology": "none"}
                add_item(items, "ABAN 125", sphase, conting)
                if ft_mode == "single":
                    add_item(items, "ABAN 156", sphase, conting)
                    if logging_mode == "pressure_equipment":
                        add_item(items, "ABAN 105", sphase, conting)
                    else:
                        add_item(items, "ABAN 234", sphase, cont_polias)
                        add_item(items, "ABAN 105", sphase, cont_polias)
                elif ft_mode == "distinct":
                    add_item(items, "ABAN 155", sphase, conting)
                    if logging_mode == "pressure_equipment":
                        add_item(items, "ABAN 105", sphase, conting)
                        add_item(items, "ABAN 157", sphase, conting)
                    else:
                        add_item(items, "ABAN 105", sphase, cont_polias)
                        add_item(items, "ABAN 157", sphase, conting)
                        add_item(items, "ABAN 234", sphase, cont_polias)
                else:
                    add_item(items, "ABAN 155", sphase, conting)
                    add_item(items, "ABAN 105", sphase, cont_polias if logging_mode == "polias" else conting)
                    add_item(items, "ABAN 157", sphase, conting)
                    if logging_mode != "pressure_equipment":
                        add_item(items, "ABAN 234", sphase, cont_polias)
                if inputs.get("perforationTestContingency"):
                    add_item(items, "ABAN 102", sphase, conting)
                    add_item(items, "ABAN 162", sphase, conting)
            continue

        # ─── RCMA_CSB_PRINCIPAL_INJECT ───────────────────────────────
        if pkg_marker == "RCMA_CSB_PRINCIPAL_INJECT":
            if inputs.get("rcmaCsbPrincipal") == "cement_plug":
                pkg_order = ["ABAN 159", "ABAN 160", "ABAN 078", "ABAN 079", "ABAN 080", "ABAN 081", "ABAN 082", "ABAN 083", "ABAN 084"]
                for pkg_id in pkg_order:
                    if pkg_id in _c(inputs.get("rcmaCementPkgs"), []):
                        add_item(items, pkg_id, sphase)
            continue

        # ─── FS1_CSB_PRIMARY_INJECT ──────────────────────────────────
        if pkg_marker == "FS1_CSB_PRIMARY_INJECT":
            if inputs.get("fs1CsbAlreadyInstalled") is True:
                continue
            csb = _c(inputs.get("fs1CsbPrimary"), "tae")
            eff_mode = "through_casing" if bop_active else base_mode

            def trans(to_tech):
                nonlocal current_tech
                if to_tech == current_tech or to_tech == "none":
                    return
                if current_tech != "none":
                    d = get_dismount_package(current_tech, rig_type, operation_type, eff_mode)
                    if d:
                        add_item(items, d, sphase, {"autoInserted": True})
                m = get_mount_package(to_tech, rig_type, operation_type, eff_mode)
                if m:
                    add_item(items, m, sphase, {"autoInserted": True})
                current_tech = to_tech

            if csb == "tae":
                trans("electric")
                add_item(items, "ABAN 237", sphase)
            elif csb == "stdv":
                add_item(items, "ABAN 038", sphase)
            elif csb == "cement_plug":
                trans("ct")
                add_item(items, "ABAN 156", sphase)
                if current_tech != "none":
                    dis = get_dismount_package(current_tech, rig_type, operation_type, eff_mode)
                    if dis:
                        add_item(items, dis, sphase, {"autoInserted": True})
                    current_tech = "none"
                add_item(items, "ABAN 234", sphase, {"transitionTechnology": "none"})
            elif csb == "ecsb":
                if current_tech != "none":
                    dis = get_dismount_package(current_tech, rig_type, operation_type, eff_mode)
                    if dis:
                        add_item(items, dis, sphase, {"autoInserted": True})
                    current_tech = "none"
                add_item(items, "ABAN 079", sphase, {"transitionTechnology": "none"})
            else:
                add_item(items, "ABAN 040", sphase)
                add_item(items, "ABAN 220" if rig_type == "ANC" else "ABAN 221", sphase)
            continue

        # ─── FS1_CSB_SECONDARY_INJECT ────────────────────────────────
        if pkg_marker == "FS1_CSB_SECONDARY_INJECT":
            is_rcma_fluid_principal = inputs.get("scopeId") == "FSU_Conv_RCMA" and inputs.get("rcmaCsbPrincipal") == "fluid_csb"
            if is_rcma_fluid_principal:
                continue
            csb2 = _c(inputs.get("fs1CsbSecondary"), "plug_th")
            eff_mode = "through_casing" if bop_active else base_mode
            do_rasa_perf = (not uses_fs1_barrier) or _c(inputs.get("fs1PerfRasa"), "yes") == "yes"
            if do_rasa_perf:
                method = _c(inputs.get("tubingPerfMethod"), "electric") if uses_fs1_barrier else "electric"
                rasa_tech = "wireline" if method == "wireline" else "ct" if method == "ct" else "electric"
                rasa_pkg = "ABAN 045" if method == "wireline" else "ABAN 154" if method == "ct" else "ABAN 101"
                if current_tech != rasa_tech:
                    if current_tech != "none":
                        d = get_dismount_package(current_tech, rig_type, operation_type, eff_mode)
                        if d:
                            add_item(items, d, sphase, {"autoInserted": True})
                    m = get_mount_package(rasa_tech, rig_type, operation_type, eff_mode)
                    if m:
                        add_item(items, m, sphase, {"autoInserted": True})
                    current_tech = rasa_tech
                add_item(items, rasa_pkg, sphase)

            def trans2(to_tech):
                nonlocal current_tech
                if to_tech == current_tech or to_tech == "none":
                    return
                if current_tech != "none":
                    d = get_dismount_package(current_tech, rig_type, operation_type, eff_mode)
                    if d:
                        add_item(items, d, sphase, {"autoInserted": True})
                m = get_mount_package(to_tech, rig_type, operation_type, eff_mode)
                if m:
                    add_item(items, m, sphase, {"autoInserted": True})
                current_tech = to_tech

            if csb2 == "tae":
                trans2("electric")
                add_item(items, "ABAN 237", sphase)
            else:
                trans2("wireline")
                add_item(items, "ABAN 042", sphase)
            continue

        # ─── RCMA_CEMENT_LOG_INJECT ──────────────────────────────────
        if pkg_marker == "RCMA_CEMENT_LOG_INJECT":
            if inputs.get("bopPwcPreLog") is not False:
                add_item(items, "ABAN 107", sphase, {"transitionTechnology": "none"})
                current_tech = "none"
            continue

        # ─── PRE_CEMENT_LOG_INJECT ───────────────────────────────────
        if pkg_marker == "PRE_CEMENT_LOG_INJECT":
            if inputs.get("bopPwcPreLog") is not False:
                eff_mode = "through_casing" if bop_active else base_mode
                if current_tech != "electric":
                    if current_tech != "none":
                        d = get_dismount_package(current_tech, rig_type, operation_type, eff_mode)
                        if d:
                            add_item(items, d, sphase, {"autoInserted": True})
                    m = get_mount_package("electric", rig_type, operation_type, eff_mode)
                    if m:
                        add_item(items, m, sphase, {"autoInserted": True})
                    current_tech = "electric"
                add_item(items, "ABAN 106", sphase)
                current_tech = "none"
            continue

        # ─── CAUDA_INTER_INJECT ──────────────────────────────────────
        if pkg_marker == "CAUDA_INTER_INJECT":
            if _yes_or_conting(inputs.get("supIntermTailFishing")):
                is_contig = _is_conting(inputs.get("supIntermTailFishing"))
                main_pkg = "ABAN 192" if inputs.get("supIntermTailMethod") == "specific_tool" else "ABAN 191"
                add_item(items, main_pkg, sphase, {"isContingency": is_contig, "contingencyReason": "Contingência: pescaria de cauda intermediária" if is_contig else None})
                contig_opts = {"isContingency": True, "contingencyReason": "Contingência: corte / estampagem de cauda intermediária"}
                add_item(items, "ABAN 193", sphase, contig_opts)
                add_item(items, "ABAN 194", sphase, contig_opts)
            continue

        # ─── PACKER_FISHING_INJECT ───────────────────────────────────
        if pkg_marker == "PACKER_FISHING_INJECT":
            if _yes_or_conting(inputs.get("fs2PackerFishing")):
                is_contig = _is_conting(inputs.get("fs2PackerFishing"))
                main_opts = {"isContingency": is_contig, "contingencyReason": "Contingência: pescaria de packer" if is_contig else None}
                add_item(items, "ABAN 192", sphase, main_opts)
                contig_opts = {"isContingency": True, "contingencyReason": "Contingência: corte de packer c/ sapata de lavagem / estampagem"}
                add_item(items, "ABAN 193", sphase, contig_opts)
                add_item(items, "ABAN 194", sphase, contig_opts)
            continue

        # ─── ISOLATION_INJECT ────────────────────────────────────────
        if pkg_marker == "ISOLATION_INJECT":
            eff_mode = "through_casing" if bop_active else base_mode
            is_rcma_scope = inputs.get("scopeId") in ("FSU_Conv_RCMA", "FS2_Conv_RCMA")
            default_iso = {"needsCorrection": False, "plugType": "bpp"}
            isolations = inputs.get("isolations") if inputs.get("isolations") else [default_iso]

            def ensure_iso_tech(tech, opts=None):
                nonlocal current_tech
                opts = opts or {}
                if current_tech == tech:
                    return
                if current_tech != "none":
                    d = get_dismount_package(current_tech, rig_type, operation_type, eff_mode)
                    if d:
                        add_item(items, d, sphase, {"autoInserted": True, **opts})
                m = get_mount_package(tech, rig_type, operation_type, eff_mode)
                if m:
                    add_item(items, m, sphase, {"autoInserted": True, **opts})
                current_tech = tech

            if inputs.get("bopPwcPreLog") is not False and not is_rcma_scope:
                ensure_iso_tech("electric")
                add_item(items, "ABAN 106", sphase)
                current_tech = "none"

            for iso in isolations:
                iso_conting = iso.get("corrContingency") is True
                corr_opts = {"isContingency": True, "contingencyReason": "Contingência: correção de cimentação antes do tampão final"} if iso_conting else {}
                cond_conting = {"isContingency": True, "contingencyReason": "Contingência: condicionamento do revestimento após avaliação de cimentação"}
                if not iso.get("needsCorrection"):
                    ensure_iso_tech("workstring")
                    add_item(items, "ABAN 200" if iso.get("plugType") == "pata_de_mula" else "ABAN 199", sphase)
                else:
                    method = _c(iso.get("corrMethod"), "pwc" if scope_id.startswith("FS2") else "convencional")
                    needs_in_block_log = inputs.get("bopPwcPreLog") is False or is_rcma_scope
                    if method == "convencional":
                        if needs_in_block_log:
                            ensure_iso_tech("electric", corr_opts)
                            add_item(items, "ABAN 106", sphase, corr_opts)
                            current_tech = "none"
                        ensure_iso_tech("workstring", corr_opts)
                        add_item(items, "ABAN 233", sphase, cond_conting)
                        ensure_iso_tech("electric", corr_opts)
                        add_item(items, "ABAN 103", sphase, corr_opts)
                        current_tech = "none"
                        ensure_iso_tech("workstring", corr_opts)
                        add_item(items, "ABAN 202", sphase, corr_opts)
                        add_item(items, "ABAN 200", sphase, corr_opts)
                    else:
                        if needs_in_block_log:
                            ensure_iso_tech("electric", corr_opts)
                            add_item(items, "ABAN 106", sphase, corr_opts)
                            current_tech = "none"
                            ensure_iso_tech("workstring", corr_opts)
                            add_item(items, "ABAN 233", sphase, cond_conting)
                        ensure_iso_tech("workstring", corr_opts)
                        add_item(items, "ABAN 231", sphase, corr_opts)
                        if iso.get("pwcValidation") == "perfil":
                            ensure_iso_tech("workstring", corr_opts)
                            add_item(items, "ABAN 200", sphase, corr_opts)
                        else:
                            ensure_iso_tech("workstring", corr_opts)
                            add_item(items, "ABAN 200", sphase, {**corr_opts, "isContingency": True, "contingencyReason": "Contingência: tampão final após correção de cimentação PWC"})
            continue

        # ─── BOP_CORRECTION_INJECT ───────────────────────────────────
        if pkg_marker == "BOP_CORRECTION_INJECT":
            eff_mode = "through_casing"
            method = _c(inputs.get("bopCorrectionMethod"), "convencional")

            def ensure_tech(tech):
                nonlocal current_tech
                if current_tech == tech:
                    return
                if current_tech != "none":
                    d = get_dismount_package(current_tech, rig_type, operation_type, eff_mode)
                    if d:
                        add_item(items, d, sphase, {"autoInserted": True})
                m = get_mount_package(tech, rig_type, operation_type, eff_mode)
                if m:
                    add_item(items, m, sphase, {"autoInserted": True})
                current_tech = tech

            if method == "convencional":
                if inputs.get("bopPwcPreLog") is not False:
                    ensure_tech("electric")
                    add_item(items, "ABAN 106", sphase)
                    current_tech = "none"
                ensure_tech("electric")
                add_item(items, "ABAN 103", sphase)
                current_tech = "none"
                ensure_tech("workstring")
                add_item(items, "ABAN 202", sphase)
                add_item(items, "ABAN 200", sphase)
                ensure_tech("electric")
                add_item(items, "ABAN 106", sphase)
                current_tech = "none"
            else:
                if inputs.get("bopPwcPreLog") is not False:
                    ensure_tech("electric")
                    add_item(items, "ABAN 106", sphase)
                    current_tech = "none"
                ensure_tech("workstring")
                add_item(items, "ABAN 231", sphase)
                validation = _c(inputs.get("bopPwcValidation"), "params")
                if validation == "perfil":
                    ensure_tech("electric")
                    add_item(items, "ABAN 106", sphase)
                    current_tech = "none"
                    ensure_tech("workstring")
                    add_item(items, "ABAN 200", sphase)
                else:
                    ensure_tech("electric")
                    add_item(items, "ABAN 106", sphase)
                    current_tech = "none"
                    ensure_tech("workstring")
                    add_item(items, "ABAN 200", sphase, {"isContingency": True, "contingencyReason": "Contingência: tampão final após correção de cimentação PWC"})
            continue

        # ─── DISMOUNT_INJECT ─────────────────────────────────────────
        if pkg_marker == "DISMOUNT_INJECT":
            if current_tech != "none" and current_tech != "bop":
                effective_mode_now = "through_casing" if bop_active else base_mode
                dis = get_dismount_package(current_tech, rig_type, operation_type, effective_mode_now)
                if dis:
                    add_item(items, dis, sphase, {"autoInserted": True})
                current_tech = "none"
            continue

        # ─── PLUG_INJECT ─────────────────────────────────────────────
        if pkg_marker == "PLUG_INJECT":
            if inputs.get("hasTmfPlug"):
                has_prod_plug = "production" in _c(inputs.get("tmfPlugBores"), [])
                has_anul_plug = "annular" in _c(inputs.get("tmfPlugBores"), [])
                if has_anul_plug:
                    add_item(items, "ABAN 035", sphase, {"annularBore": True})
                    for m in _c(inputs.get("tmfPlugContingencyAnul"), []):
                        if m == "stroker":
                            add_item(items, "ABAN 089", sphase, {"isContingency": True, "contingencyReason": "Contingência: retirada de plug do TMF (anular) com stroker", "annularBore": True})
                        if m == "ft":
                            add_item(items, "ABAN 122", sphase, {"isContingency": True, "contingencyReason": "Contingência: retirada de plug do TMF (anular) com flexitubo"})
                    if rig_type == "DP":
                        eff_mode = "through_casing" if bop_active else base_mode
                        dis = get_dismount_package(current_tech, rig_type, operation_type, eff_mode)
                        if dis:
                            add_item(items, dis, sphase, {"autoInserted": True})
                        ct_mnt = get_mount_package("ct", rig_type, operation_type, eff_mode)
                        if ct_mnt:
                            add_item(items, ct_mnt, sphase, {"autoInserted": True})
                        current_tech = "ct"
                        add_item(items, "ABAN 125", sphase)
                        add_item(items, "ABAN 162", sphase)
                        ct_dis = get_dismount_package("ct", rig_type, operation_type, eff_mode)
                        if ct_dis:
                            add_item(items, ct_dis, sphase, {"autoInserted": True})
                        wire_mnt = get_mount_package("wireline", rig_type, operation_type, eff_mode)
                        if wire_mnt:
                            add_item(items, wire_mnt, sphase, {"autoInserted": True})
                        current_tech = "wireline"
                    add_item(items, "ABAN 029", sphase)
                if has_prod_plug:
                    add_item(items, "ABAN 034", sphase)
                    for m in _c(inputs.get("tmfPlugContingencyProd"), []):
                        if m == "stroker":
                            add_item(items, "ABAN 088", sphase, {"isContingency": True, "contingencyReason": "Contingência: retirada de plug do TMF (produção) com stroker"})
                        if m == "ft":
                            add_item(items, "ABAN 123", sphase, {"isContingency": True, "contingencyReason": "Contingência: retirada de plug do TMF (produção) com flexitubo"})
                    add_item(items, "ABAN 028", sphase)
            if inputs.get("hasTmfPlug") and "production" in _c(inputs.get("tmfPlugBores"), []):
                conts = _c(inputs.get("anmValveContingency"), [])
                if "jateamento" in conts:
                    add_item(items, "ABAN 125", sphase, {"isContingency": True, "contingencyReason": "Contingência: jateamento com flexitubo para abertura de válvulas da ANM"})
                if "gabarit_ft" in conts:
                    add_item(items, "ABAN 124", sphase, {"isContingency": True, "contingencyReason": "Contingência: gabaritagem com motor de fundo e broca para abertura de válvulas da ANM"})
            if inputs.get("hasThPlug"):
                add_item(items, "ABAN 052", sphase)
                for m in _c(inputs.get("thPlugContingency"), []):
                    if m == "stroker":
                        add_item(items, "ABAN 094", sphase, {"isContingency": True, "contingencyReason": "Contingência: retirada de plug do TH com stroker"})
                    if m == "ft":
                        add_item(items, "ABAN 140", sphase, {"isContingency": True, "contingencyReason": "Contingência: retirada de plug do TH com flexitubo"})
            continue

        # ─── CAMISAO_INJECT ──────────────────────────────────────────
        if pkg_marker == "CAMISAO_INJECT":
            camisao_arr = [v for v in _c(inputs.get("installCamisao"), []) if v != "no"]
            effective_mode_now = "through_casing" if bop_active else base_mode
            if inputs.get("gaugeTech") != "no" and inputs.get("gaugeCamisaoAcoplado"):
                add_item(items, "ABAN 036", sphase, {"isContingency": inputs.get("gaugeContingency") is True})
            for slot in ("yes", "contingency"):
                if slot not in camisao_arr:
                    continue
                is_contingency = slot == "contingency"
                if not inputs.get("camisaoMethod") or inputs.get("camisaoMethod") == "wireline":
                    add_item(items, "ABAN 037", sphase, {"isContingency": is_contingency})
                else:
                    dis = get_dismount_package(current_tech, rig_type, operation_type, effective_mode_now)
                    if dis:
                        add_item(items, dis, sphase, {"autoInserted": True})
                    ct_mount = get_mount_package("ct", rig_type, operation_type, effective_mode_now)
                    if ct_mount:
                        add_item(items, ct_mount, sphase, {"autoInserted": True})
                    add_item(items, "ABAN 126", sphase, {"isContingency": is_contingency})
                    ct_dis = get_dismount_package("ct", rig_type, operation_type, effective_mode_now)
                    if ct_dis:
                        add_item(items, ct_dis, sphase, {"autoInserted": True})
                    wire_mnt = get_mount_package("wireline", rig_type, operation_type, effective_mode_now)
                    if wire_mnt:
                        add_item(items, wire_mnt, sphase, {"autoInserted": True})
                    current_tech = "wireline"
            if inputs.get("gaugeTech") != "no" and not inputs.get("gaugeCamisaoAcoplado"):
                gauge_package = "ABAN 098" if inputs.get("gaugeTech") == "electric" else "ABAN 124" if inputs.get("gaugeTech") == "ct" else "ABAN 036"
                add_item(items, gauge_package, sphase, {"isContingency": inputs.get("gaugeContingency") is True})
            if _yes_or_conting(inputs.get("contingencyGabaritFT")):
                add_item(items, "ABAN 124", sphase, {
                    "isContingency": _is_conting(inputs.get("contingencyGabaritFT")),
                    "contingencyReason": "Contingência: gabaritagem com motor de fundo e broca via flexitubo" if _is_conting(inputs.get("contingencyGabaritFT")) else None,
                })
            continue

        # ─── TMF_PLUG_END_INJECT ─────────────────────────────────────
        if pkg_marker == "TMF_PLUG_END_INJECT":
            if _yes_or_conting(inputs.get("installTmfPlugEndProd")) or _yes_or_conting(inputs.get("installTmfPlugEndAnul")):
                eff_mode = "through_casing" if bop_active else base_mode

                def ensure_wireline():
                    nonlocal current_tech
                    if current_tech != "wireline":
                        if current_tech != "none":
                            d = get_dismount_package(current_tech, rig_type, operation_type, eff_mode)
                            if d:
                                add_item(items, d, sphase, {"autoInserted": True})
                        m = get_mount_package("wireline", rig_type, operation_type, eff_mode)
                        if m:
                            add_item(items, m, sphase, {"autoInserted": True})
                        current_tech = "wireline"

                if _yes_or_conting(inputs.get("installTmfPlugEndProd")):
                    ensure_wireline()
                    add_item(items, "ABAN 249", sphase, {"isContingency": _is_conting(inputs.get("installTmfPlugEndProd"))})
                if rig_type == "DP" and _yes_or_conting(inputs.get("installTmfPlugEndAnul")):
                    conting = _is_conting(inputs.get("installTmfPlugEndAnul"))
                    if current_tech != "none":
                        d = get_dismount_package(current_tech, rig_type, operation_type, eff_mode)
                        if d:
                            add_item(items, d, sphase, {"autoInserted": True})
                        current_tech = "none"
                    add_item(items, "ABAN 213", sphase, {"isContingency": conting})
                    ensure_wireline()
                    add_item(items, "ABAN 250", sphase, {"isContingency": conting})
                    has_prod_plug = _yes_or_conting(inputs.get("installTmfPlugEndProd"))
                    add_item(items, "ABAN 026" if has_prod_plug else "ABAN 024", sphase, {"isContingency": conting})
                    add_item(items, "ABAN 027", sphase, {"isContingency": conting})
                elif rig_type != "DP" and _yes_or_conting(inputs.get("installTmfPlugEndAnul")):
                    ensure_wireline()
                    add_item(items, "ABAN 250", sphase, {"isContingency": _is_conting(inputs.get("installTmfPlugEndAnul"))})
            continue

        # ─── TAIL_FISHING_INJECT ─────────────────────────────────────
        if pkg_marker == "TAIL_FISHING_INJECT":
            fishing_pkg = {
                "camisao_wireline": "ABAN 055", "camisao_stroker": "ABAN 097", "camisao_ct": "ABAN 134",
                "stv_r_wireline": "ABAN 048", "stv_r_stroker": "ABAN 090", "stv_r_ct": "ABAN 136",
                "stv_f_wireline": "ABAN 049", "stv_f_stroker": "ABAN 091", "stv_f_ct": "ABAN 137",
                "plug_r_wireline": "ABAN 050", "plug_r_stroker": "ABAN 092", "plug_r_ct": "ABAN 138",
                "plug_f_wireline": "ABAN 051", "plug_f_stroker": "ABAN 093", "plug_f_ct": "ABAN 139",
                "brv_f_wireline": "ABAN 053", "brv_f_stroker": "ABAN 095", "brv_f_ct": "ABAN 141",
                "brv_r_wireline": "ABAN 054", "brv_r_stroker": "ABAN 096", "brv_r_ct": "ABAN 142",
            }
            element_order = {"stv_f": 0, "plug_f": 1, "brv_f": 2, "stv_r": 3, "plug_r": 4, "brv_r": 5, "camisao": 6}
            method_order = {"wireline": 0, "stroker": 1, "ct": 2}
            sorted_items = sorted(_c(inputs.get("tailFishingItems"), []),
                                  key=lambda fi: (element_order.get(fi["element"], 99), method_order.get(fi["method"], 0)))
            for fi in sorted_items:
                pkg_id = fishing_pkg.get(f"{fi['element']}_{fi['method']}")
                if pkg_id:
                    add_item(items, pkg_id, sphase)
            continue

        # ─── VGL_INJECT ──────────────────────────────────────────────
        if pkg_marker == "VGL_INJECT":
            if inputs.get("vglAction") in ("remove", "replace"):
                has_camisao = any(v in ("yes", "contingency") for v in _c(inputs.get("installCamisao"), []))
                camisao_remove_pkg = {"wireline": "ABAN 055", "ct": "ABAN 134"}
                camisao_install_pkg = {"wireline": "ABAN 037", "ct": "ABAN 126"}
                camisao_method = _c(inputs.get("camisaoMethod"), "wireline")
                vgl_opts = {"isContingency": inputs.get("vglContingency") is True}
                if inputs.get("vglInstallStv"):
                    add_item(items, "ABAN 038", sphase, vgl_opts)
                if has_camisao:
                    add_item(items, camisao_remove_pkg.get(camisao_method), sphase, vgl_opts)
                vgl_fishing_pkg = {"wireline": "ABAN 056", "stroker": "ABAN 114"}
                pkg_id = vgl_fishing_pkg.get(_c(inputs.get("vglFishingMethod"), "wireline"))
                if pkg_id:
                    add_item(items, pkg_id, sphase, vgl_opts)
                if inputs.get("vglAction") == "replace":
                    add_item(items, "ABAN 057", sphase, vgl_opts)
                if has_camisao:
                    add_item(items, camisao_install_pkg.get(camisao_method), sphase, vgl_opts)
                if inputs.get("vglInstallStv") and inputs.get("vglRemoveStv"):
                    add_item(items, "ABAN 048", sphase, vgl_opts)
            continue

        # ─── BOP_TEST_INJECT ─────────────────────────────────────────
        if pkg_marker == "BOP_TEST_INJECT":
            is_fs2_non_rcma = (inputs.get("scopeId") or "").startswith("FS2") and inputs.get("scopeId") != "FS2_Conv_RCMA"
            if is_fs2_non_rcma and inputs.get("bopTestMethod") == "feth_on_th":
                pass
            elif is_fs2_non_rcma and inputs.get("bopTestMethod") == "ponteira_orman":
                add_item(items, "ABAN 240", sphase)
            elif is_fs2_non_rcma and inputs.get("bopTestMethod") == "coluna_flutuada":
                add_item(items, "ABAN 229", sphase)
            else:
                add_item(items, "ABAN 228", sphase)
            continue

        # ─── BOP_TEST_FETH_INJECT ────────────────────────────────────
        if pkg_marker == "BOP_TEST_FETH_INJECT":
            is_fs2_non_rcma = (inputs.get("scopeId") or "").startswith("FS2") and inputs.get("scopeId") != "FS2_Conv_RCMA"
            if is_fs2_non_rcma and inputs.get("bopTestMethod") == "feth_on_th":
                add_item(items, "ABAN 241", sphase)
            continue

        # ─── COP_CUT_INJECT ──────────────────────────────────────────
        if pkg_marker == "COP_CUT_INJECT":
            if _yes_or_conting(inputs.get("fs2CopCutContingency")):
                is_contig = _is_conting(inputs.get("fs2CopCutContingency"))
                cut_opts = {"isContingency": is_contig, "contingencyReason": "Contingência: corte de COP/COI após falha de desassentamento do TH" if is_contig else None}
                is_rcma = scope_id == "FS2_Conv_RCMA"
                if is_rcma:
                    add_item(items, "ABAN 252", sphase, cut_opts)
                    add_item(items, "ABAN 183", sphase, cut_opts)
                    add_item(items, "ABAN 188", sphase, cut_opts)
                else:
                    add_item(items, "ABAN 186", sphase, cut_opts)
                    if _yes_or_conting(inputs.get("fs2ThPlugRemoval")):
                        is_plug_conting = _is_conting(inputs.get("fs2ThPlugRemoval"))
                        add_item(items, "ABAN 052", sphase, {
                            **cut_opts,
                            **({"isContingency": True, "contingencyReason": "Contingência: retirada de plug 3,75\" no TH antes do free point"} if is_plug_conting else {}),
                        })
                    add_item(items, "ABAN 251", sphase, cut_opts)
                    if inputs.get("fs2CopCutMethod") == "ct":
                        add_item(items, "ABAN 121" if rig_type == "ANC" else "ABAN 119", sphase, cut_opts)
                        add_item(items, "ABAN 150", sphase, cut_opts)
                        add_item(items, "ABAN 148" if operation_type == "LWO" else "ABAN 161", sphase, cut_opts)
                    elif inputs.get("fs2CopCutMethod") == "slip_shot":
                        add_item(items, "ABAN 115", sphase, cut_opts)
                    elif inputs.get("fs2CopCutMethod") == "string_shot":
                        add_item(items, "ABAN 116", sphase, cut_opts)
                    else:
                        add_item(items, "ABAN 113", sphase, cut_opts)
                    add_item(items, "ABAN 190", sphase, cut_opts)
            continue

        # ─── UEP_CLEAN_INJECT ────────────────────────────────────────
        if pkg_marker == "UEP_CLEAN_INJECT":
            if _yes_or_conting(inputs.get("cleanWithUep")):
                is_contig = _is_conting(inputs.get("cleanWithUep"))
                opts = {"isContingency": is_contig, "contingencyReason": "Contingência: limpeza do poço em conjunto com UEP" if is_contig else None}
                for pkg_id in _c(inputs.get("cleanWithUepPackages"), []):
                    add_item(items, pkg_id, sphase, opts)
            continue

        # ─── INVESTIGATION_INJECT ────────────────────────────────────
        if pkg_marker == "INVESTIGATION_INJECT":
            logs = _c(inputs.get("investigationLogs"), [])
            methods = _c(inputs.get("investigationLogMethods"), {})
            contingency = _c(inputs.get("investigationLogContingency"), {})
            log_order = ["registro_pressao", "fluxo_anular", "furo_cop", "caliper", "imageamento", "free_point"]
            for log in log_order:
                if log not in logs:
                    continue
                method = methods.get(log)
                is_conting_log = contingency.get(log) is True
                pkg_id = None
                if log == "registro_pressao":
                    pkg_id = "ABAN 104" if method == "electric" else "ABAN 147" if method == "ct" else "ABAN 047"
                elif log == "fluxo_anular":
                    pkg_id = "ABAN 151" if method == "ct" else "ABAN 100"
                elif log == "furo_cop":
                    pkg_id = "ABAN 152" if method == "ct" else "ABAN 099"
                elif log == "caliper":
                    pkg_id = "ABAN 111"
                elif log == "imageamento":
                    pkg_id = "ABAN 112"
                elif log == "free_point":
                    pkg_id = "ABAN 251"
                if pkg_id:
                    add_item(items, pkg_id, sphase, {"isContingency": is_conting_log})
            continue

        # ─── BRV_INSERTABLE_INJECT ───────────────────────────────────
        if pkg_marker == "BRV_INSERTABLE_INJECT":
            if inputs.get("dhsvBrvType") == "insertable":
                add_item(items, "ABAN 054", sphase)
            continue

        # ─── Pacote normal ───────────────────────────────────────────
        effective_pkg_id = pkg_marker
        if effective_pkg_id == "ABAN 031A" and operation_type == "LWO":
            effective_pkg_id = "ABAN 031B"
        if operation_type == "LWO":
            if effective_pkg_id == "ABAN 182":
                effective_pkg_id = "ABAN 183"
            if effective_pkg_id == "ABAN 187":
                effective_pkg_id = "ABAN 188"
        if effective_pkg_id == "ABAN 003" and inputs.get("dmmWithEquipment"):
            effective_pkg_id = "ABAN 005" if scope_id.startswith("FS2") else "ABAN 004"
        if inputs.get("hasTmfPlug"):
            tmf_bores = _c(inputs.get("tmfPlugBores"), [])
            if effective_pkg_id == "ABAN 024" and "production" in tmf_bores:
                effective_pkg_id = "ABAN 026"
            if effective_pkg_id == "ABAN 025" and "annular" in tmf_bores:
                effective_pkg_id = "ABAN 027"
        if inputs.get("hasTmfPlug"):
            tmf_bores = _c(inputs.get("tmfPlugBores"), [])
            if effective_pkg_id == "ABAN 028" and "production" in tmf_bores:
                continue
            if effective_pkg_id == "ABAN 029" and "annular" in tmf_bores:
                continue

        if (effective_pkg_id == "ABAN 211"
                and (not "tree_cap" in equipments or inputs.get("tcapRemovalMethod") == "rov")):
            continue
        if (effective_pkg_id == "ABAN 212"
                and "tree_cap" in equipments and inputs.get("tcapRemovalMethod") != "rov"):
            continue
        if (effective_pkg_id in ("ABAN 011", "ABAN 012")
                and "tree_cap" in equipments and inputs.get("tcapRemovalMethod") != "rov"):
            continue

        pkg = get_package(effective_pkg_id)
        if not pkg:
            continue

        new_tech = pkg["technology"]
        effective_mode = "through_casing" if bop_active else base_mode

        if pkg.get("isMountOp"):
            if current_tech == new_tech:
                continue
            if current_tech != "none":
                dis = get_dismount_package(current_tech, rig_type, operation_type, effective_mode)
                if dis:
                    add_item(items, dis, sphase, {"autoInserted": True})
            if new_tech == "bop":
                bop_active = True
            current_tech = new_tech
        elif pkg.get("isDismountOp"):
            if new_tech == "bop":
                bop_active = False
            current_tech = "none"
        elif new_tech != "none" and new_tech != current_tech:
            if current_tech != "none":
                dis = get_dismount_package(current_tech, rig_type, operation_type, effective_mode)
                if dis:
                    add_item(items, dis, sphase, {"autoInserted": True})
            mnt = get_mount_package(new_tech, rig_type, operation_type, effective_mode)
            if mnt:
                add_item(items, mnt, sphase, {"autoInserted": True})
            current_tech = new_tech

        final_is_contingency = (_is_conting(inputs.get("hasStuckStringRisk")) if cond == "stuck_risk"
                                else _is_conting(inputs.get("contingencyFejat")) if cond == "fejat"
                                else step.get("isContingency", False) or False)
        final_contingency_reason = ("Corte preventivo de coluna marcado como contingência pelo projetista"
                                    if (cond == "stuck_risk" and _is_conting(inputs.get("hasStuckStringRisk")))
                                    else step.get("contingencyReason"))
        add_item(items, effective_pkg_id, sphase, {
            "isContingency": final_is_contingency,
            "contingencyReason": final_contingency_reason,
            "transitionTechnology": step.get("transitionTechnology"),
        })
        if pkg.get("noDismountAfter"):
            current_tech = "none"

    # Strip auto-inserted e reconstrói transições
    base_items = [i for i in items if not i.get("autoInserted")]
    rebuilt_items = apply_transitions(base_items, rig_type, operation_type, percentile, base_mode)

    tcap_unseating_ids = {"ABAN 020", "ABAN 021", "ABAN 022", "ABAN 177"}
    last_tcap_idx = -1
    for i, item in enumerate(rebuilt_items):
        if item["packageId"] in tcap_unseating_ids:
            last_tcap_idx = i

    timeline_items = apply_timeline(rebuilt_items)

    if last_tcap_idx >= 0:
        return [({**item, "phase": "Fase 0"} if i <= last_tcap_idx else item) for i, item in enumerate(timeline_items)]

    start_phase = "Fase 2" if scope_id.startswith("FS2") else "Fase 1A"
    return [({**item, "phase": start_phase} if item["phase"] == "Fase 0" else item) for item in timeline_items]


def apply_transitions(base, rig_type, operation_type, percentile, base_mode="through_tubing"):
    def cleaned_keep(item):
        pkg = get_package(item["packageId"])
        if not pkg:
            return True
        if pkg["technology"] == "bop":
            return True
        return not pkg.get("isMountOp") and not pkg.get("isDismountOp")

    cleaned = [i for i in base if cleaned_keep(i)]

    result: list[dict] = []
    state = {
        "mounted_tech": "none",
        "bop_active": False,
        "mount_is_contingency": False,
        "session_has_non_contingency": False,
        "mount_item_idx": -1,
        "annular_bore_session": False,
        "overlay_tech": "none",
        "overlay_annular_bore": False,
        "pending_contingency_remount_tech": "none",
        "mount_is_contingency_restoration": False,
    }

    def mode():
        return "through_casing" if state["bop_active"] else base_mode

    def is_firm_session():
        return state["mounted_tech"] != "none" and (not state["mount_is_contingency"] or state["session_has_non_contingency"])

    def resolve_mount_pkg(tech, use_annular_bore):
        if tech == "wireline" and rig_type == "ANC" and use_annular_bore:
            return "ABAN 031B" if operation_type == "LWO" else "ABAN 033"
        return get_mount_package(tech, rig_type, operation_type, mode())

    def dismount_overlay(phase):
        if state["overlay_tech"] == "none":
            return
        d = get_dismount_package(state["overlay_tech"], rig_type, operation_type, mode())
        if d:
            result.append(make_auto_item(d, phase, percentile, True))
        state["overlay_tech"] = "none"
        state["overlay_annular_bore"] = False

    def promote_mount_to_firm():
        if state["mount_is_contingency_restoration"]:
            return
        if state["mount_is_contingency"] and not state["session_has_non_contingency"] and state["mount_item_idx"] >= 0:
            result[state["mount_item_idx"]]["isContingency"] = False

    def dismount(phase, force_contingency=False):
        dismount_overlay(phase)
        if state["mounted_tech"] == "none" or state["mounted_tech"] == "bop":
            state["mounted_tech"] = "none"
            return
        is_conting = force_contingency or (state["mount_is_contingency"] and not state["session_has_non_contingency"])
        d = get_dismount_package(state["mounted_tech"], rig_type, operation_type, mode())
        if d:
            result.append(make_auto_item(d, phase, percentile, is_conting))
        state["mounted_tech"] = "none"
        state["annular_bore_session"] = False
        state["mount_is_contingency"] = False
        state["session_has_non_contingency"] = False
        state["mount_item_idx"] = -1
        state["mount_is_contingency_restoration"] = False

    def ensure_mount(tech, phase, trigger_is_contingency, use_annular_bore=False):
        original_trigger_is_contingency = trigger_is_contingency
        is_contingency_restoration = False
        if state["mounted_tech"] == "none" and state["overlay_tech"] == "none" and state["pending_contingency_remount_tech"] == tech:
            trigger_is_contingency = True
            is_contingency_restoration = True
            state["pending_contingency_remount_tech"] = "none"
        same_firm_bore = tech != "wireline" or rig_type != "ANC" or state["annular_bore_session"] == use_annular_bore
        same_overlay_bore = tech != "wireline" or rig_type != "ANC" or state["overlay_annular_bore"] == use_annular_bore

        if state["overlay_tech"] != "none":
            if tech == state["overlay_tech"] and same_overlay_bore:
                return
            if tech == state["mounted_tech"] and same_firm_bore and not trigger_is_contingency:
                dismount_overlay(phase)
                promote_mount_to_firm()
                state["session_has_non_contingency"] = True
                return
            dismount_overlay(phase)
            if tech == state["mounted_tech"] and same_firm_bore:
                if not trigger_is_contingency:
                    promote_mount_to_firm()
                    state["session_has_non_contingency"] = True
                return
            if trigger_is_contingency and is_firm_session():
                m = resolve_mount_pkg(tech, use_annular_bore)
                if m:
                    result.append(make_auto_item(m, phase, percentile, True))
                state["overlay_tech"] = tech
                state["overlay_annular_bore"] = use_annular_bore
                return

        if tech == state["mounted_tech"] and same_firm_bore:
            if not trigger_is_contingency:
                promote_mount_to_firm()
                state["session_has_non_contingency"] = True
            return
        if trigger_is_contingency and is_firm_session():
            m = resolve_mount_pkg(tech, use_annular_bore)
            if m:
                result.append(make_auto_item(m, phase, percentile, True))
            state["overlay_tech"] = tech
            state["overlay_annular_bore"] = use_annular_bore
            return
        if state["mounted_tech"] != "none":
            dismount(phase)
        m = resolve_mount_pkg(tech, use_annular_bore)
        if m:
            result.append(make_auto_item(m, phase, percentile, trigger_is_contingency))
            state["mount_item_idx"] = len(result) - 1
        else:
            state["mount_item_idx"] = -1
        state["mounted_tech"] = tech
        state["annular_bore_session"] = tech == "wireline" and use_annular_bore
        state["mount_is_contingency"] = trigger_is_contingency
        state["session_has_non_contingency"] = not original_trigger_is_contingency
        state["mount_is_contingency_restoration"] = is_contingency_restoration

    def next_tech_is_contingency_overlay(from_idx, current_tech):
        seen_contingency_different_tech = False
        for i in range(from_idx, len(cleaned)):
            p = get_package(cleaned[i]["packageId"])
            if not p:
                continue
            if p.get("isMountOp") or p.get("isDismountOp"):
                return False
            if p["technology"] == "bop":
                continue
            eff_tech = cleaned[i]["transitionTechnology"] if cleaned[i].get("transitionTechnology") is not None else p["technology"]
            if eff_tech == "none":
                continue
            is_polias = cleaned[i].get("transitionTechnology") == "none" and p["technology"] in ("wireline", "electric", "ct")
            if is_polias:
                return False
            if cleaned[i]["isContingency"]:
                if eff_tech != current_tech:
                    seen_contingency_different_tech = True
            else:
                return seen_contingency_different_tech and eff_tech == current_tech
        return False

    def needs_tech_ahead(from_idx, tech, current_annular_bore=False):
        for i in range(from_idx, len(cleaned)):
            p = get_package(cleaned[i]["packageId"])
            if not p:
                continue
            if p.get("isMountOp") or p.get("isDismountOp"):
                return False
            if p["technology"] == "bop":
                continue
            eff_tech = cleaned[i]["transitionTechnology"] if cleaned[i].get("transitionTechnology") is not None else p["technology"]
            is_polias_ahead = cleaned[i].get("transitionTechnology") == "none" and p["technology"] in ("wireline", "electric", "ct")
            if is_polias_ahead:
                return False
            if eff_tech == tech:
                if tech == "wireline" and rig_type == "ANC" and bool(cleaned[i].get("annularBore")) != current_annular_bore:
                    return False
                return True
            if not cleaned[i]["isContingency"] and eff_tech != "none":
                return False
        return False

    for idx in range(len(cleaned)):
        item = cleaned[idx]
        pkg = get_package(item["packageId"])
        if not pkg:
            result.append(item)
            continue

        if pkg["technology"] == "bop" and pkg.get("isMountOp"):
            dismount(item["phase"])
            state["bop_active"] = True
            result.append(item)
            continue
        if pkg["technology"] == "bop" and pkg.get("isDismountOp"):
            dismount(item["phase"])
            state["bop_active"] = False
            result.append(item)
            continue

        effective_tech = item["transitionTechnology"] if item.get("transitionTechnology") is not None else pkg["technology"]
        is_polias = item.get("transitionTechnology") == "none" and pkg["technology"] in ("wireline", "electric", "ct")

        if is_polias:
            if (item["isContingency"] and state["mounted_tech"] != "none" and state["mounted_tech"] != "bop"
                    and needs_tech_ahead(idx + 1, state["mounted_tech"], state["annular_bore_session"])):
                state["pending_contingency_remount_tech"] = state["mounted_tech"]
                dismount(item["phase"], True)
            else:
                dismount(item["phase"])
            result.append(item)
            continue

        if effective_tech in ("wireline", "electric", "ct"):
            if (item["isContingency"] and state["overlay_tech"] == "none" and is_firm_session()
                    and effective_tech != state["mounted_tech"]
                    and needs_tech_ahead(idx + 1, state["mounted_tech"], state["annular_bore_session"])):
                state["pending_contingency_remount_tech"] = state["mounted_tech"]
                dismount(item["phase"], True)
            ensure_mount(effective_tech, item["phase"], item["isContingency"], item.get("annularBore") is True)
            result.append(item)
            if pkg.get("noDismountAfter"):
                state["overlay_tech"] = "none"
                state["overlay_annular_bore"] = False
                state["mounted_tech"] = "none"
                state["annular_bore_session"] = False
                state["mount_is_contingency"] = False
                state["session_has_non_contingency"] = False
        else:
            result.append(item)

        if state["overlay_tech"] != "none" and not needs_tech_ahead(idx + 1, state["overlay_tech"], state["overlay_annular_bore"]):
            dismount_overlay(item["phase"])
        if state["mounted_tech"] != "none" and state["mounted_tech"] != "bop" and not needs_tech_ahead(idx + 1, state["mounted_tech"], state["annular_bore_session"]):
            if not next_tech_is_contingency_overlay(idx + 1, state["mounted_tech"]):
                dismount(item["phase"])

    return result


def recompute_transitions(items, rig_type, operation_type, percentile, scope_id=None):
    base = [i for i in items if not i.get("autoInserted")]
    return apply_timeline(apply_transitions(base, rig_type, operation_type, percentile,
                                            derive_base_mode(scope_id) if scope_id else "through_tubing"))
