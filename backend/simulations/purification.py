"""
Пречистване на извлечения уран - последната химическа поредица преди
горивото да е готово за ново пресоване: stripping -> утаяване на ADU ->
калцинация -> редукция до UO2.

Фаза 1 (stripping): органичната фаза се промива с разредена HNO3 (~0.01M),
равновесието се обръща и уранът се връща във водна фаза. Документът
препоръчва "използвай същите D_U/баланс формули, но с рязко спаднал
[NO3-]"; опростяваме до бързо, почти пълно възстановяване от първи ред
(явно отбелязано - не е пълното symmetric D_U ODE).

Фаза 2 (утаяване на ADU):
  2 UO2(NO3)2 + 6 NH4OH -> (NH4)2U2O7(s) + 4 NH4NO3 + 3 H2O
  dC_ADU/dt = kN*(S-1)^m + kG*A_solid*(S-1)^n,   S = C_U,aq / C_eq

Фаза 3 (калцинация): (NH4)2U2O7 -> 2 UO3 + 2 NH3 + H2O, 400-600°C.

Фаза 4 (редукция с H2, Shrinking Core - точно уравнението от източника):
  dX/dt = 3*ks*P_H2 / (rho_UO3 * R0) * (1-X)^(2/3),   ks = A0*exp(-Ea/RT)
"""
import math

MOLAR_MASS_ADU_PER_U = 312.07   # g/mol U, (NH4)2U2O7 деленo на 2 U атома
MOLAR_MASS_UO3 = 286.03         # g/mol
MOLAR_MASS_UO2 = 270.03         # g/mol

STRIP_RATE = 0.12               # 1/s, бързо почти-пълно обратно извличане

C_EQ_ADU_MOL_L = 0.002          # граница на разтворимост на ADU
K_NUCLEATION = 0.0006
K_GROWTH = 0.03
NUCLEATION_ORDER = 2.0
GROWTH_ORDER = 1.0

CALCINATION_RATE = 0.06         # 1/s, 400 -> 600°C

REDUCTION_TEMP_K = 973.15       # ~700°C пещ за редукция
REDUCTION_EA = 60000.0          # J/mol, правдоподобна стойност за тв.-газ редукция на оксид
REDUCTION_A0 = 24.0              # 1/s, тунинг константа (аналог на A0 от Архениус),
                                  # калибрирана за разумна продължителност на редукцията
H2_PARTIAL_PRESSURE_ATM = 1.0
RHO_UO3_MOL_M3 = 29020.0        # моларна плътност на UO3 (~8.3 g/cm3 / 286.03 g/mol)
PARTICLE_RADIUS_M = 5e-5        # 50 микрона прахови частици UO3

PHASE_STRIPPING, PHASE_PRECIPITATION, PHASE_CALCINATION, PHASE_REDUCTION, PHASE_DONE = range(5)
PHASE_NAMES = {
    PHASE_STRIPPING: "stripping",
    PHASE_PRECIPITATION: "adu_precipitation",
    PHASE_CALCINATION: "calcination",
    PHASE_REDUCTION: "reduction_to_uo2",
    PHASE_DONE: "complete",
}


def initial_state(uranium_mol: float, organic_volume_l: float, aqueous_product_volume_l: float = 5.0) -> dict:
    return {
        "phase": PHASE_STRIPPING,
        "uranium_mol": uranium_mol,
        "c_u_org": uranium_mol / organic_volume_l,
        "c_u_aq": 0.0,
        "organic_volume_l": organic_volume_l,
        "aqueous_product_volume_l": aqueous_product_volume_l,
        "adu_mol": 0.0,
        "uo3_mol": 0.0,
        "reduction_x": 0.0,
        "calcination_progress": 0.0,
    }


def step(state: dict, dt: float) -> dict:
    dt = max(0.0, dt)
    s = dict(state)

    if s["phase"] == PHASE_STRIPPING:
        moved = s["c_u_org"] * (1 - math.exp(-STRIP_RATE * dt))
        s["c_u_org"] -= moved
        s["c_u_aq"] += moved * s["organic_volume_l"] / s["aqueous_product_volume_l"]
        if s["c_u_org"] * s["organic_volume_l"] < 0.01 * s["uranium_mol"]:
            s["phase"] = PHASE_PRECIPITATION

    elif s["phase"] == PHASE_PRECIPITATION:
        saturation = max(1.0, s["c_u_aq"] / C_EQ_ADU_MOL_L)
        a_solid = max(0.05, (s["adu_mol"]) ** (2 / 3))
        rate = K_NUCLEATION * (saturation - 1) ** NUCLEATION_ORDER + K_GROWTH * a_solid * (saturation - 1) ** GROWTH_ORDER
        precipitated = min(rate * dt, s["c_u_aq"] * s["aqueous_product_volume_l"] / 2)
        s["c_u_aq"] = max(0.0, s["c_u_aq"] - 2 * precipitated / s["aqueous_product_volume_l"])
        s["adu_mol"] += precipitated  # мол ADU формулни единици (по 2 U всяка)
        if s["c_u_aq"] <= C_EQ_ADU_MOL_L * 1.05:
            s["phase"] = PHASE_CALCINATION

    elif s["phase"] == PHASE_CALCINATION:
        remaining_fraction = 1 - s["calcination_progress"]
        converted = remaining_fraction * (1 - math.exp(-CALCINATION_RATE * dt))
        s["calcination_progress"] += converted
        if s["calcination_progress"] >= 0.995:
            s["uo3_mol"] = s["adu_mol"] * 2  # всяка ADU единица -> 2 UO3
            s["phase"] = PHASE_REDUCTION

    elif s["phase"] == PHASE_REDUCTION:
        ks = REDUCTION_A0 * math.exp(-REDUCTION_EA / (8.314 * REDUCTION_TEMP_K))
        x = s["reduction_x"]
        dX = 3 * ks * H2_PARTIAL_PRESSURE_ATM / (RHO_UO3_MOL_M3 * PARTICLE_RADIUS_M) * ((1 - x) ** (2 / 3)) * dt
        s["reduction_x"] = min(1.0, x + dX)
        if s["reduction_x"] >= 0.995:
            s["phase"] = PHASE_DONE

    uo2_formed_mol = s["uo3_mol"] * s["reduction_x"]
    overall_progress = {
        PHASE_STRIPPING: 0.05 * min(1.0, 1 - s["c_u_org"] * s["organic_volume_l"] / max(1e-9, s["uranium_mol"])),
        PHASE_PRECIPITATION: 0.05 + 0.35 * min(1.0, (s["adu_mol"] * 2) / max(1e-9, s["uranium_mol"])),
        PHASE_CALCINATION: 0.40 + 0.20 * s["calcination_progress"],
        PHASE_REDUCTION: 0.60 + 0.40 * s["reduction_x"],
        PHASE_DONE: 1.0,
    }[s["phase"]]

    return {
        "state": s,
        "phase": PHASE_NAMES[s["phase"]],
        "progress": round(min(100.0, overall_progress * 100), 2),
        "uranium_aqueous_mol_l": round(s["c_u_aq"], 5),
        "adu_mol": round(s["adu_mol"], 4),
        "calcination_progress": round(s["calcination_progress"], 3),
        "uo2_formed_mol": round(uo2_formed_mol, 4),
        "uo2_formed_kg": round(uo2_formed_mol * MOLAR_MASS_UO2 / 1000, 4),
        "reduction_x": round(s["reduction_x"], 4),
    }


def run(duration: float, sample_interval: float = 5.0, internal_dt: float = 0.5,
        uranium_mol: float = 2.27, organic_volume_l: float = 15.0,
        aqueous_product_volume_l: float = 5.0) -> dict:
    state = initial_state(uranium_mol, organic_volume_l, aqueous_product_volume_l)

    time_s = [0.0]
    progresses = [0.0]
    adu = [0.0]
    calcination = [0.0]
    uo2_kg = [0.0]
    reduction_x = [0.0]
    stages = ["initial"]

    t = 0.0
    next_sample_t = sample_interval
    while t < duration:
        step_dt = min(internal_dt, duration - t)
        result = step(state, step_dt)
        state = result["state"]
        t += step_dt
        is_complete = result["phase"] == "complete"

        if t >= next_sample_t - 1e-9 or is_complete or t >= duration:
            time_s.append(round(t, 2))
            progresses.append(round(result["progress"] / 100, 4))
            adu.append(result["adu_mol"])
            calcination.append(result["calcination_progress"])
            uo2_kg.append(result["uo2_formed_kg"])
            reduction_x.append(result["reduction_x"])
            stages.append(result["phase"])
            next_sample_t += sample_interval

        if is_complete:
            break

    return {
        "time": time_s,
        "results": {
            "progress": progresses,
            "adu_mol": adu,
            "calcination_progress": calcination,
            "uo2_formed_kg": uo2_kg,
            "reduction_x": reduction_x,
        },
        "stage": stages,
    }
