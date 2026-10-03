"""
Етап 3: Формиране на ново MOX гориво (сглобяване + синтероване).
"""
import math

REPACKAGING_RATE = 0.08  # 1/s, калибрирано за ~37s до завършване при speed=1
FINAL_DENSITY_FRACTION = 0.95  # теоретична плътност на синтерования MOX пелет


def compute(elapsed: float, speed: float, recovered_mass_kg: float = 0.965) -> dict:
    elapsed = max(0.0, elapsed)
    speed = max(0.1, speed)

    rate = REPACKAGING_RATE * speed
    progress_fraction = 1 - math.exp(-rate * elapsed)
    progress_fraction = min(1.0, max(0.0, progress_fraction))

    temperature = 400.0 + 400.0 * progress_fraction  # синтероване 400 -> 800 °C

    return {
        "temperature_c": round(temperature, 1),
        "progress": round(progress_fraction * 100, 2),
        "formed_mox_mass_kg": round(recovered_mass_kg * progress_fraction, 4),
        "sintered_density_fraction": round(0.75 + (FINAL_DENSITY_FRACTION - 0.75) * progress_fraction, 3),
    }


def run(duration: float, sample_interval: float = 5.0, speed: float = 1.0,
        recovered_mass_kg: float = 0.965) -> dict:
    time_s, temperatures, progress_fraction, mox_mass, density, stages = [], [], [], [], [], []

    t = 0.0
    while True:
        result = compute(t, speed, recovered_mass_kg)
        is_complete = result["progress"] >= 99.9

        time_s.append(round(t, 2))
        temperatures.append(result["temperature_c"])
        progress_fraction.append(round(result["progress"] / 100, 4))
        mox_mass.append(result["formed_mox_mass_kg"])
        density.append(result["sintered_density_fraction"])
        stages.append("initial" if t == 0 else ("complete" if is_complete else "repackaging"))

        if is_complete or t >= duration:
            break
        t = min(t + sample_interval, duration)

    return {
        "time": time_s,
        "results": {
            "temperature": temperatures,
            "progress": progress_fraction,
            "formed_mox_mass_kg": mox_mass,
            "sintered_density_fraction": density,
        },
        "stage": stages,
    }
