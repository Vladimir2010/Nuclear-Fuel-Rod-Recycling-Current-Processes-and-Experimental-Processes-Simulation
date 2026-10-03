"""
Пиропреработка: електрорафиниране в разтопена хлоридна сол (LiCl-KCl, ~500C).

Реална електрохимия (алтернатива на киселинното разтваряне, не негово продължение):
  E_eq(T) = E0 + (R*T)/(n*F) * ln(X_salt / X_cathode)     Нернст
  j(eta)  = j0 * [exp(a*n*F*eta/RT) - exp(-a*n*F*eta/RT)]  Butler-Volmer
  I       = j * A_electrode                                 (с ограничение
                                                               от transport-limited ток)
  dn      = I*dt / (n*F)                                    Закон на Фарадей
  Q_joule = I_total^2 * R_salt * dt                         Джаулово нагряване

U се отлага първи (най-близо до приложеното напрежение), Pu след него на
течен Cd/Bi катод; Nd (лантанид, отпадък) трябва да остане в солта — ако
играчът вдигне напрежението твърде високо, Nd започва да "замърсява"
продукта (точно механиката, описана в изходните материали).
"""
import math

F_CONST = 96485.0   # C/mol
R_GAS = 8.314        # J/(mol*K)

SPECIES = ["U", "Pu", "Nd"]
E0 = {"U": -2.40, "Pu": -2.70, "Nd": -3.10}       # V, срещу référence електрод
VALENCE = {"U": 3, "Pu": 3, "Nd": 3}
MOLAR_MASS = {"U": 238.03, "Pu": 239.05, "Nd": 144.24}  # g/mol

J0 = 50.0                 # A/m^2, exchange current density
ALPHA_TRANSFER = 0.5
ELECTRODE_AREA_M2 = 0.2
LIMITING_CURRENT_DENSITY = 800.0  # A/m^2, транспортно ограничение (реалистичен таван)

SALT_BASIS_MOL = 200.0     # "обем" на основната носеща сол (LiCl-KCl)
CATHODE_BASIS_MOL = 50.0   # капацитет на катодния слой преди силен back-EMF

SALT_CONDUCTIVITY_S_M = 150.0  # S/m при 500C
ELECTRODE_GAP_M = 0.05
SALT_CP = 1300.0          # J/(kg*K)
SALT_DENSITY_KG_L = 1.8
EUTECTIC_FREEZE_C = 355.0
AMBIENT_LOSS_COEFF = 8.0   # W/K, пасивна загуба на топлина към стените на тигела


def initial_state(mass_u_kg: float = 0.05, mass_pu_kg: float = 0.0015,
                   mass_nd_kg: float = 0.005, temperature_c: float = 500.0) -> dict:
    # Мащаб на лабораторна/хот-сел проба (грамове), не промишлена партида:
    # при реалистични плътности на тока рафинирането на килограмови количества
    # отнема часове - точно затова истинските pyro-експерименти тестват с проби.
    return {
        "mass_salt": {"U": mass_u_kg, "Pu": mass_pu_kg, "Nd": mass_nd_kg},
        "mass_cathode_solid": {"U": 0.0},
        "mass_cathode_liquid": {"Pu": 0.0},
        "mass_contamination_salt_side": {"Nd": 0.0},
        "initial_mass_u_pu_kg": mass_u_kg + mass_pu_kg,
        "temperature_c": temperature_c,
    }


def _mole_fraction_ratio(mass_salt_kg, mass_cathode_kg, species):
    moles_salt = mass_salt_kg * 1000 / MOLAR_MASS[species]
    moles_cathode = mass_cathode_kg * 1000 / MOLAR_MASS[species]
    x_salt = moles_salt / SALT_BASIS_MOL
    x_cathode = moles_cathode / CATHODE_BASIS_MOL
    return max(1e-6, x_salt / max(1e-9, x_cathode)) if x_cathode > 0 else max(1e-6, x_salt / 1e-6)


def step(state: dict, dt: float, voltage_applied: float) -> dict:
    dt = max(0.0, min(dt, 2.0))
    s = {
        "mass_salt": dict(state["mass_salt"]),
        "mass_cathode_solid": dict(state["mass_cathode_solid"]),
        "mass_cathode_liquid": dict(state["mass_cathode_liquid"]),
        "mass_contamination_salt_side": dict(state["mass_contamination_salt_side"]),
        "initial_mass_u_pu_kg": state["initial_mass_u_pu_kg"],
        "temperature_c": state["temperature_c"],
    }
    temp_kelvin = s["temperature_c"] + 273.15

    cathode_mass_for = {
        "U": s["mass_cathode_solid"].get("U", 0.0),
        "Pu": s["mass_cathode_liquid"].get("Pu", 0.0),
        "Nd": s["mass_contamination_salt_side"].get("Nd", 0.0),
    }

    total_current = 0.0
    mass_transferred = {}
    currents = {}

    for species in SPECIES:
        n = VALENCE[species]
        ratio = _mole_fraction_ratio(s["mass_salt"][species], cathode_mass_for[species], species)
        e_eq = E0[species] + (R_GAS * temp_kelvin) / (n * F_CONST) * math.log(ratio)

        # eta < 0 (приложеният потенциал е по-отрицателен от равновесния) -> катодна
        # посока -> отлагане. j по конвенция излиза отрицателен за катодния клон,
        # затова взимаме -j като положителен "ток на отлагане".
        eta = voltage_applied - e_eq
        exponent = min(40.0, max(-40.0, ALPHA_TRANSFER * n * F_CONST * eta / (R_GAS * temp_kelvin)))
        j = J0 * (math.exp(exponent) - math.exp(-exponent))
        j_deposition = max(0.0, min(LIMITING_CURRENT_DENSITY, -j))

        current_i = j_deposition * ELECTRODE_AREA_M2
        currents[species] = current_i
        total_current += current_i

        moles_moved = current_i * dt / (n * F_CONST)
        mass_moved_kg = moles_moved * MOLAR_MASS[species] / 1000
        mass_moved_kg = min(mass_moved_kg, s["mass_salt"][species])
        mass_transferred[species] = mass_moved_kg

    for species in SPECIES:
        s["mass_salt"][species] = max(0.0, s["mass_salt"][species] - mass_transferred[species])

    s["mass_cathode_solid"]["U"] = s["mass_cathode_solid"].get("U", 0.0) + mass_transferred["U"]
    s["mass_cathode_liquid"]["Pu"] = s["mass_cathode_liquid"].get("Pu", 0.0) + mass_transferred["Pu"]
    s["mass_contamination_salt_side"]["Nd"] = (
        s["mass_contamination_salt_side"].get("Nd", 0.0) + mass_transferred["Nd"]
    )

    r_salt = (1.0 / SALT_CONDUCTIVITY_S_M) * (ELECTRODE_GAP_M / ELECTRODE_AREA_M2)
    q_joule = (total_current ** 2) * r_salt * dt
    q_loss = AMBIENT_LOSS_COEFF * (s["temperature_c"] - 25.0) * dt
    total_salt_mass_kg = sum(s["mass_salt"].values()) + 40.0  # + маса на носещата сол (приблизително)
    delta_t = (q_joule - q_loss) / (total_salt_mass_kg * SALT_CP)
    s["temperature_c"] = s["temperature_c"] + delta_t

    recovered_kg = s["mass_cathode_solid"]["U"] + s["mass_cathode_liquid"]["Pu"]
    progress = (recovered_kg / s["initial_mass_u_pu_kg"]) * 100
    contamination_fraction = (
        s["mass_contamination_salt_side"]["Nd"] / max(1e-6, recovered_kg + s["mass_contamination_salt_side"]["Nd"])
    )
    is_frozen = s["temperature_c"] < EUTECTIC_FREEZE_C

    return {
        "state": s,
        "progress": round(min(100.0, progress), 2),
        "temperature_c": round(s["temperature_c"], 1),
        "mass_u_cathode_kg": round(s["mass_cathode_solid"]["U"], 4),
        "mass_pu_cathode_kg": round(s["mass_cathode_liquid"]["Pu"], 4),
        "mass_nd_contamination_kg": round(s["mass_contamination_salt_side"]["Nd"], 5),
        "contamination_fraction": round(contamination_fraction, 4),
        "current_u_a": round(currents["U"], 3),
        "current_pu_a": round(currents["Pu"], 3),
        "current_nd_a": round(currents["Nd"], 3),
        "total_current_a": round(total_current, 3),
        "is_frozen": is_frozen,
    }


def run(duration: float, sample_interval: float = 5.0, internal_dt: float = 0.5,
        mass_u_kg: float = 0.05, mass_pu_kg: float = 0.0015, mass_nd_kg: float = 0.005,
        temperature_c: float = 500.0, voltage_applied: float = -2.5) -> dict:
    state = initial_state(mass_u_kg, mass_pu_kg, mass_nd_kg, temperature_c)

    time_s = [0.0]
    temperatures = [temperature_c]
    progresses = [0.0]
    mass_u = [0.0]
    mass_pu = [0.0]
    mass_nd_contam = [0.0]
    contamination = [0.0]
    current_u = [0.0]
    current_pu = [0.0]
    current_nd = [0.0]
    stages = ["initial"]

    t = 0.0
    next_sample_t = sample_interval
    while t < duration:
        step_dt = min(internal_dt, duration - t)
        result = step(state, step_dt, voltage_applied)
        state = result["state"]
        t += step_dt
        is_complete = result["progress"] >= 99.9

        if t >= next_sample_t - 1e-9 or is_complete or t >= duration:
            time_s.append(round(t, 2))
            temperatures.append(result["temperature_c"])
            progresses.append(round(result["progress"] / 100, 4))
            mass_u.append(result["mass_u_cathode_kg"])
            mass_pu.append(result["mass_pu_cathode_kg"])
            mass_nd_contam.append(result["mass_nd_contamination_kg"])
            contamination.append(result["contamination_fraction"])
            current_u.append(result["current_u_a"])
            current_pu.append(result["current_pu_a"])
            current_nd.append(result["current_nd_a"])
            stages.append("complete" if is_complete else "electrorefining")
            next_sample_t += sample_interval

        if is_complete:
            break

    return {
        "time": time_s,
        "results": {
            "temperature": temperatures,
            "progress": progresses,
            "mass_u_cathode_kg": mass_u,
            "mass_pu_cathode_kg": mass_pu,
            "mass_nd_contamination_kg": mass_nd_contam,
            "contamination_fraction": contamination,
            "current_u_a": current_u,
            "current_pu_a": current_pu,
            "current_nd_a": current_nd,
        },
        "stage": stages,
    }
