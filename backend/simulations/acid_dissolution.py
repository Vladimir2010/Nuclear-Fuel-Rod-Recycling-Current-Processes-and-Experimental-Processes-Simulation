"""
PUREX-подобен процес: разтваряне на UO2 в азотна киселина (HNO3).

Реална химия (не демонстративна апроксимация):
  3UO2 + 8HNO3 -> 3UO2(NO3)2 + 2NO + 4H2O   (ниска киселинност, <7M)
  UO2  + 4HNO3 ->  UO2(NO3)2 + 2NO2 + 2H2O   (висока киселинност, >=7M)

Кинетика:
  k(T)     = A0 * exp(-Ea / (R*T))                      Архениус
  A(t)     = A_initial * (M(t)/M_initial)^(2/3)         Shrinking Core
  r        = k(T) * A(t) * [HNO3]^n                     база (mol/s)
  r_final  = r * (1 + alpha * trapped_gas)              автокатализа от NOx/HNO2
  dQ       = r_final * dH_rxn * dt                      екзотермична топлина
  T_new    = T_old + (dQ - Q_cooling) / (m_solution*Cp) топлинен баланс

Симулацията е "stateful": всяко извикване на step() получава текущото
състояние и връща следващото, Python е единственото място, където се смята.
"""
import math

R_GAS = 8.314                 # J/(mol*K)
ACTIVATION_ENERGY = 48800.0   # J/mol (UO2 в HNO3)
ARRHENIUS_A0 = 4.0e6          # 1/s, тунинг константа (PDF: "5 минути или 5 часа")
REACTION_ORDER_N = 2.2        # ред на реакцията спрямо киселината (2.0-2.5)
AUTOCATALYTIC_ALPHA = 0.08    # ускорение на реакцията от натрупан NOx/HNO2
DELTA_H_RXN = 150000.0        # J/mol, силно екзотермична реакция
SOLUTION_CP = 3700.0          # J/(kg*K), специф. топлоемкост на киселинния разтвор
SOLUTION_DENSITY_KG_L = 1.3   # кг/л
MOLAR_MASS_UO2 = 270.03       # g/mol
BOILING_POINT_C = 116.0       # реалистична точка на кипене на концентрирана HNO3

LOW_ACID_THRESHOLD_M = 7.0    # под това -> нискокиселинна реакция (стехиометрия 8/3)
STOICH_HNO3_PER_UO2_LOW = 8.0 / 3.0
STOICH_HNO3_PER_UO2_HIGH = 4.0
STOICH_GAS_PER_UO2_LOW = 2.0 / 3.0   # mol NO на mol UO2
STOICH_GAS_PER_UO2_HIGH = 2.0        # mol NO2 на mol UO2

VENT_DECAY = 0.15  # делът газ, който остава в съда след проветряване за 1 стъпка


def initial_state(mass_uo2_kg: float = 2.0, acid_concentration_m: float = 5.0,
                   solution_volume_l: float = 15.0, temperature_c: float = 60.0) -> dict:
    density_uo2 = 10970.0  # kg/m^3
    volume_m3 = mass_uo2_kg / density_uo2
    radius_m = (3 * volume_m3 / (4 * math.pi)) ** (1 / 3)
    area_m2 = 4 * math.pi * radius_m ** 2

    return {
        "mass_uo2_kg": mass_uo2_kg,
        "initial_mass_uo2_kg": mass_uo2_kg,
        "initial_area_m2": area_m2,
        "acid_concentration_m": acid_concentration_m,
        "solution_volume_l": solution_volume_l,
        "uranyl_nitrate_mol": 0.0,
        "trapped_gas_mol": 0.0,
        "temperature_c": temperature_c,
    }


def step(state: dict, dt: float, cooling_power_w: float, vented: bool) -> dict:
    dt = max(0.0, min(dt, 2.0))
    s = dict(state)

    mass_fraction = max(0.0, s["mass_uo2_kg"] / s["initial_mass_uo2_kg"])
    current_area = s["initial_area_m2"] * (mass_fraction ** (2 / 3))

    temp_kelvin = s["temperature_c"] + 273.15
    k_t = ARRHENIUS_A0 * math.exp(-ACTIVATION_ENERGY / (R_GAS * temp_kelvin))

    acid = max(0.0, s["acid_concentration_m"])
    base_rate = k_t * current_area * (acid ** REACTION_ORDER_N)
    actual_rate = base_rate * (1 + AUTOCATALYTIC_ALPHA * s["trapped_gas_mol"])  # mol/s

    moles_dissolved = min(actual_rate * dt, s["mass_uo2_kg"] * 1000 / MOLAR_MASS_UO2)

    low_acid_regime = acid < LOW_ACID_THRESHOLD_M
    hno3_stoich = STOICH_HNO3_PER_UO2_LOW if low_acid_regime else STOICH_HNO3_PER_UO2_HIGH
    gas_stoich = STOICH_GAS_PER_UO2_LOW if low_acid_regime else STOICH_GAS_PER_UO2_HIGH

    s["mass_uo2_kg"] = max(0.0, s["mass_uo2_kg"] - moles_dissolved * MOLAR_MASS_UO2 / 1000)
    s["acid_concentration_m"] = max(0.0, acid - (moles_dissolved * hno3_stoich) / s["solution_volume_l"])
    s["uranyl_nitrate_mol"] += moles_dissolved

    gas_produced = moles_dissolved * gas_stoich
    if vented:
        s["trapped_gas_mol"] = (s["trapped_gas_mol"] + gas_produced) * VENT_DECAY
    else:
        s["trapped_gas_mol"] += gas_produced

    heat_generated_j = actual_rate * dt * DELTA_H_RXN
    heat_removed_j = cooling_power_w * dt
    solution_mass_kg = s["solution_volume_l"] * SOLUTION_DENSITY_KG_L
    delta_t = (heat_generated_j - heat_removed_j) / (solution_mass_kg * SOLUTION_CP)
    s["temperature_c"] = max(20.0, s["temperature_c"] + delta_t)

    progress = (1 - mass_fraction) * 100
    is_boiling = s["temperature_c"] >= BOILING_POINT_C

    return {
        "state": s,
        "progress": round(min(100.0, progress), 2),
        "temperature_c": round(s["temperature_c"], 1),
        "acid_concentration_m": round(s["acid_concentration_m"], 3),
        "uranyl_nitrate_mol": round(s["uranyl_nitrate_mol"], 2),
        "trapped_gas_mol": round(s["trapped_gas_mol"], 3),
        "mass_uo2_kg": round(s["mass_uo2_kg"], 4),
        "reaction_rate_mol_s": round(actual_rate, 5),
        "rate_constant_k": round(k_t, 8),
        "is_boiling": is_boiling,
        "regime": "low_acid (3UO2 + 8HNO3)" if low_acid_regime else "high_acid (UO2 + 4HNO3)",
    }


def run(duration: float, sample_interval: float = 5.0, internal_dt: float = 0.5,
        mass_uo2_kg: float = 2.0, acid_concentration_m: float = 5.0,
        solution_volume_l: float = 15.0, temperature_c: float = 60.0,
        cooling_power_w: float = 1500.0, vented: bool = False) -> dict:
    state = initial_state(mass_uo2_kg, acid_concentration_m, solution_volume_l, temperature_c)

    time_s = [0.0]
    temperatures = [temperature_c]
    progresses = [0.0]
    acids = [acid_concentration_m]
    uranyl = [0.0]
    gas = [0.0]
    mass_remaining = [mass_uo2_kg]
    rates = [0.0]
    boiling = [False]
    regimes = ["low_acid (3UO2 + 8HNO3)" if acid_concentration_m < LOW_ACID_THRESHOLD_M else "high_acid (UO2 + 4HNO3)"]
    stages = ["initial"]

    t = 0.0
    next_sample_t = sample_interval
    while t < duration:
        step_dt = min(internal_dt, duration - t)
        result = step(state, step_dt, cooling_power_w, vented)
        state = result["state"]
        t += step_dt
        is_complete = result["progress"] >= 99.9

        if t >= next_sample_t - 1e-9 or is_complete or t >= duration:
            time_s.append(round(t, 2))
            temperatures.append(result["temperature_c"])
            progresses.append(round(result["progress"] / 100, 4))
            acids.append(result["acid_concentration_m"])
            uranyl.append(result["uranyl_nitrate_mol"])
            gas.append(result["trapped_gas_mol"])
            mass_remaining.append(result["mass_uo2_kg"])
            rates.append(result["reaction_rate_mol_s"])
            boiling.append(result["is_boiling"])
            regimes.append(result["regime"])
            stages.append("complete" if is_complete else "dissolving_acid")
            next_sample_t += sample_interval

        if is_complete:
            break

    return {
        "time": time_s,
        "results": {
            "temperature": temperatures,
            "progress": progresses,
            "acid_concentration_m": acids,
            "uranyl_nitrate_mol": uranyl,
            "trapped_gas_mol": gas,
            "mass_uo2_remaining_kg": mass_remaining,
            "reaction_rate_mol_s": rates,
            "is_boiling": boiling,
            "regime": regimes,
        },
        "stage": stages,
    }
