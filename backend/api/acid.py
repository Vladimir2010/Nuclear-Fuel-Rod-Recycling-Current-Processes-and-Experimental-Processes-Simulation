from fastapi import APIRouter
from simulations import acid_dissolution
from simulations._envelope import build_response

router = APIRouter()


@router.get("/dissolution/acid")
def get_acid_dissolution(
    duration: float = 240.0,
    sample_interval: float = 10.0,
    mass_uo2_kg: float = 2.0,
    acid_concentration_m: float = 5.0,
    solution_volume_l: float = 15.0,
    temperature_c: float = 60.0,
    cooling_power_w: float = 1500.0,
    vented: bool = False,
):
    run_result = acid_dissolution.run(
        duration, sample_interval, 0.5,
        mass_uo2_kg, acid_concentration_m, solution_volume_l, temperature_c,
        cooling_power_w, vented,
    )
    return build_response(
        "acid-dissolution", run_result["time"], run_result["results"], run_result["stage"], duration,
        extra_metadata={
            "process": "PUREX-style HNO3 dissolution of UO2",
            "reaction_low_acid": "3UO2 + 8HNO3 -> 3UO2(NO3)2 + 2NO + 4H2O",
            "reaction_high_acid": "UO2 + 4HNO3 -> UO2(NO3)2 + 2NO2 + 2H2O",
            "mass_unit": "kg",
            "concentration_unit": "mol/L",
        },
    )
