"""
Етап 4: Кондициониране на отпадъка (остъкляване / vitrification).
"""
import math

WASTE_RATE = 0.07  # 1/s, калибрирано за ~43s до завършване при speed=1


def compute(elapsed: float, speed: float, waste_mass_kg: float = 0.035) -> dict:
    elapsed = max(0.0, elapsed)
    speed = max(0.1, speed)

    rate = WASTE_RATE * speed
    progress_fraction = 1 - math.exp(-rate * elapsed)
    progress_fraction = min(1.0, max(0.0, progress_fraction))

    temperature = 200.0 + 950.0 * progress_fraction  # остъкляване 200 -> 1150 °C

    return {
        "temperature_c": round(temperature, 1),
        "progress": round(progress_fraction * 100, 2),
        "vitrified_mass_kg": round(waste_mass_kg * progress_fraction, 4),
        "encapsulation_fraction": round(progress_fraction, 3),
    }


def run(duration: float, sample_interval: float = 5.0, speed: float = 1.0,
        waste_mass_kg: float = 0.035) -> dict:
    time_s, temperatures, progress_fraction, vitrified, encapsulation, stages = [], [], [], [], [], []

    t = 0.0
    while True:
        result = compute(t, speed, waste_mass_kg)
        is_complete = result["progress"] >= 99.9

        time_s.append(round(t, 2))
        temperatures.append(result["temperature_c"])
        progress_fraction.append(round(result["progress"] / 100, 4))
        vitrified.append(result["vitrified_mass_kg"])
        encapsulation.append(result["encapsulation_fraction"])
        stages.append("initial" if t == 0 else ("complete" if is_complete else "waste"))

        if is_complete or t >= duration:
            break
        t = min(t + sample_interval, duration)

    return {
        "time": time_s,
        "results": {
            "temperature": temperatures,
            "progress": progress_fraction,
            "vitrified_mass_kg": vitrified,
            "encapsulation_fraction": encapsulation,
        },
        "stage": stages,
    }
