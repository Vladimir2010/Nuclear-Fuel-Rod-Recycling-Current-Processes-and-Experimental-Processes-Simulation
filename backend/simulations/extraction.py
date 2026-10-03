"""
Етап: Екстракция на уран от киселинния разтвор с Tributyl Phosphate (TBP) -
частта от PUREX процеса СЛЕД разтварянето, при която ураниловият нитрат се
премества от водната (киселинна) фаза в органична (TBP) фаза.

  UO2(2+)(aq) + 2 NO3-(aq) + 2 TBP(org) <-> UO2(NO3)2*2TBP(org)

Опростяване спрямо пълния индустриален процес (документиран прозрачно, не
скрито): реалните заводи използват N-степенна противотокова каскада от
mixer-settler стъпки; тук моделираме ЕДИН добре разбъркан контактор със
същата равновесна химия (D_U от концентрация на нитрат + свободен TBP) и
същата кинетика на масопренос (ограничена от kL*A), вместо пълния SEPHIS
модел на йонна сила - достатъчно за да се види вярната физика на разделянето,
без N-стъпкова ODE система.

  D_U = C_U,org / C_U,aq = K_U' * [NO3-]^2 * [TBP]_free^2
  R_transfer = kL * A * (C_U,aq - C_U,aq_eq),  C_U,aq_eq = C_U,org / D_U
"""
TBP_TOTAL_ORG_MOL_L = 1.1     # ~30 vol% TBP в керосен разредител
K_U_EFFECTIVE = 0.8           # ефективна равновесна константа (опростен SEPHIS), калибрирана
                              # за D_U в реалистичен диапазон (~15-25) при типична киселинност
KL_A = 0.015                  # 1/s, общ коефициент на масопренос * междуфазна площ / обем
NITRATE_PER_URANYL = 2.0      # NO3- съпътстващ всеки UO2(NO3)2 в разтвора


def initial_state(uranium_mol: float, aqueous_volume_l: float, hno3_concentration_m: float,
                   organic_volume_l: float | None = None) -> dict:
    organic_volume_l = organic_volume_l if organic_volume_l is not None else aqueous_volume_l
    return {
        "c_u_aq": uranium_mol / aqueous_volume_l,
        "c_u_org": 0.0,
        "hno3_aq": hno3_concentration_m,
        "aqueous_volume_l": aqueous_volume_l,
        "organic_volume_l": organic_volume_l,
        "initial_uranium_mol": uranium_mol,
    }


def _distribution_coefficient(hno3_m: float, c_u_org: float) -> float:
    nitrate_m = hno3_m + NITRATE_PER_URANYL * c_u_org
    tbp_free = max(0.0, TBP_TOTAL_ORG_MOL_L - 2 * c_u_org)
    return K_U_EFFECTIVE * (nitrate_m ** 2) * (tbp_free ** 2)


def step(state: dict, dt: float) -> dict:
    dt = max(0.0, dt)
    s = dict(state)

    d_u = _distribution_coefficient(s["hno3_aq"], s["c_u_org"])
    c_u_aq_eq = s["c_u_org"] / d_u if d_u > 1e-9 else s["c_u_org"] * 1e9
    r_transfer_mol_l_s = KL_A * (s["c_u_aq"] - c_u_aq_eq)
    r_transfer_mol_l_s = max(0.0, r_transfer_mol_l_s)

    moles_transferred = min(r_transfer_mol_l_s * s["aqueous_volume_l"] * dt, s["c_u_aq"] * s["aqueous_volume_l"])

    s["c_u_aq"] = max(0.0, s["c_u_aq"] - moles_transferred / s["aqueous_volume_l"])
    s["c_u_org"] = s["c_u_org"] + moles_transferred / s["organic_volume_l"]

    uranium_in_org = s["c_u_org"] * s["organic_volume_l"]
    progress = (uranium_in_org / s["initial_uranium_mol"]) * 100 if s["initial_uranium_mol"] > 0 else 100.0

    return {
        "state": s,
        "progress": round(min(100.0, progress), 2),
        "c_u_aq_mol_l": round(s["c_u_aq"], 5),
        "c_u_org_mol_l": round(s["c_u_org"], 5),
        "uranium_extracted_mol": round(uranium_in_org, 4),
        "distribution_coefficient": round(d_u, 3),
    }


def run(duration: float, sample_interval: float = 5.0, internal_dt: float = 0.5,
        uranium_mol: float = 2.57, aqueous_volume_l: float = 15.0,
        hno3_concentration_m: float = 4.5, organic_volume_l: float | None = None) -> dict:
    state = initial_state(uranium_mol, aqueous_volume_l, hno3_concentration_m, organic_volume_l)

    time_s = [0.0]
    progresses = [0.0]
    c_aq = [state["c_u_aq"]]
    c_org = [0.0]
    extracted = [0.0]
    d_u_values = [_distribution_coefficient(hno3_concentration_m, 0.0)]
    stages = ["initial"]

    t = 0.0
    next_sample_t = sample_interval
    while t < duration:
        step_dt = min(internal_dt, duration - t)
        result = step(state, step_dt)
        state = result["state"]
        t += step_dt
        is_complete = result["progress"] >= 99.0

        if t >= next_sample_t - 1e-9 or is_complete or t >= duration:
            time_s.append(round(t, 2))
            progresses.append(round(result["progress"] / 100, 4))
            c_aq.append(result["c_u_aq_mol_l"])
            c_org.append(result["c_u_org_mol_l"])
            extracted.append(result["uranium_extracted_mol"])
            d_u_values.append(result["distribution_coefficient"])
            stages.append("complete" if is_complete else "extraction")
            next_sample_t += sample_interval

        if is_complete:
            break

    return {
        "time": time_s,
        "results": {
            "progress": progresses,
            "uranium_aqueous_mol_l": c_aq,
            "uranium_organic_mol_l": c_org,
            "uranium_extracted_mol": extracted,
            "distribution_coefficient": d_u_values,
        },
        "stage": stages,
    }
