"""
Етап 1: Охлаждане на извадената горивна касета (decay heat), заменя старата
произволна Нютонова апроксимация с реална физика на остатъчния разпад.

Wigner-Way формула за мощността на остатъчния разпад:
  P_decay(t) = P0 * 0.066 * (t^-0.2 - (t+t0)^-0.2)      (валидна за t >= 10s)

Топлинен баланс на касетата (конвекция към хладителя + лъчение):
  Q_cooling = h*A*(T_rod - T_coolant) + eps*sigma*A*(T_rod_K^4 - T_coolant_K^4)
  dT/dt     = (P_decay - Q_cooling) / (m_rod * Cp_fuel)

"duration"/"time" тук са РЕАЛНИ физични секунди след изваждането от реактора
(не демо-секунди) - охлаждането във водния басейн реално отнема дни/седмици,
затова API повикващият подава голям duration (напр. 2 седмици), а честотата
на показване (sample_interval) определя колко точки се връщат.
"""
import math

P0_WATTS = 1.5e6           # номинална топлинна мощност на касетата по време на работа
T0_CORE_SECONDS = 9.5e7    # ~3 години експлоатация в активната зона
MASS_ROD_KG = 500.0
CP_FUEL = 300.0            # J/(kg*K)
SURFACE_AREA_M2 = 12.5
EMISSIVITY = 0.78
STEFAN_BOLTZMANN = 5.67e-8

MIN_VALID_T = 10.0         # формулата на Wigner-Way е валидна само за t >= 10s


def decay_power_w(t_after_shutdown_s: float) -> float:
    t = max(MIN_VALID_T, t_after_shutdown_s)
    decay_fraction = 0.066 * (t ** -0.2 - (t + T0_CORE_SECONDS) ** -0.2)
    return P0_WATTS * decay_fraction


def initial_state(t_after_shutdown_s: float = 60.0, temperature_c: float = 350.0) -> dict:
    return {"t_after_shutdown_s": t_after_shutdown_s, "temperature_c": temperature_c}


def step(state: dict, dt: float, h_coolant: float, coolant_temp_c: float) -> dict:
    dt = max(0.0, dt)
    s = dict(state)

    p_decay = decay_power_w(s["t_after_shutdown_s"])

    t_rod_k = s["temperature_c"] + 273.15
    t_coolant_k = coolant_temp_c + 273.15
    q_conv = h_coolant * SURFACE_AREA_M2 * (s["temperature_c"] - coolant_temp_c)
    q_rad = EMISSIVITY * STEFAN_BOLTZMANN * SURFACE_AREA_M2 * (t_rod_k ** 4 - t_coolant_k ** 4)
    q_cooling = q_conv + q_rad

    dT = (p_decay - q_cooling) / (MASS_ROD_KG * CP_FUEL) * dt
    s["temperature_c"] = s["temperature_c"] + dT
    s["t_after_shutdown_s"] = s["t_after_shutdown_s"] + dt

    return {
        "state": s,
        "temperature_c": round(s["temperature_c"], 1),
        "decay_power_w": round(p_decay, 1),
        "t_after_shutdown_s": round(s["t_after_shutdown_s"], 1),
    }


def run(duration: float, sample_interval: float = 43200.0, internal_dt: float = 2.0,
        initial_t_after_shutdown_s: float = 60.0, initial_temperature_c: float = 350.0,
        h_coolant: float = 2500.0, coolant_temp_c: float = 30.0) -> dict:
    state = initial_state(initial_t_after_shutdown_s, initial_temperature_c)
    span = max(1e-6, initial_temperature_c - coolant_temp_c)

    time_s = [0.0]
    temperatures = [initial_temperature_c]
    decay_powers = [decay_power_w(initial_t_after_shutdown_s)]
    progresses = [0.0]
    stages = ["initial"]

    t = 0.0
    next_sample_t = sample_interval
    while t < duration:
        step_dt = min(internal_dt, duration - t)
        result = step(state, step_dt, h_coolant, coolant_temp_c)
        state = result["state"]
        t += step_dt

        progress_fraction = min(1.0, max(0.0, 1 - (result["temperature_c"] - coolant_temp_c) / span))
        is_complete = progress_fraction >= 0.99

        if t >= next_sample_t - 1e-9 or is_complete or t >= duration:
            time_s.append(round(t, 1))
            temperatures.append(result["temperature_c"])
            decay_powers.append(result["decay_power_w"])
            progresses.append(round(progress_fraction, 4))
            stages.append("complete" if is_complete else "decay_cooling")
            next_sample_t += sample_interval

        if is_complete:
            break

    return {
        "time": time_s,
        "results": {
            "temperature": temperatures,
            "progress": progresses,
            "decay_power_w": decay_powers,
        },
        "stage": stages,
    }
