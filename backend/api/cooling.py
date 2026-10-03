from fastapi import APIRouter
from simulations import decay_cooling
from simulations._envelope import build_response

router = APIRouter()


@router.get("/cooling")
def get_cooling(
    duration: float = 1209600.0,   # 14 дни реално физично време по подразбиране
    sample_interval: float = 43200.0,  # на всеки 12 часа
    initial_t_after_shutdown_s: float = 60.0,
    initial_temperature: float = 350.0,
    h_coolant: float = 300.0,
    coolant_temperature: float = 30.0,
):
    run_result = decay_cooling.run(
        duration, sample_interval, 2.0,
        initial_t_after_shutdown_s, initial_temperature, h_coolant, coolant_temperature,
    )
    return build_response(
        "cooling", run_result["time"], run_result["results"], run_result["stage"], duration,
        extra_metadata={
            "process": "Decay heat cooling (Wigner-Way formula + convection/radiation)",
            "note": "time е РЕАЛНО физично време в секунди след изваждане от реактора, не демо-време",
            "power_unit": "W",
        },
    )
