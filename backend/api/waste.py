from fastapi import APIRouter
from simulations import waste as waste_sim
from simulations._envelope import build_response

router = APIRouter()


@router.get("/waste")
def get_waste(
    duration: float = 90.0,
    sample_interval: float = 5.0,
    speed: float = 1.0,
    waste_mass_kg: float = 0.035,
):
    run_result = waste_sim.run(duration, sample_interval, speed, waste_mass_kg)
    return build_response(
        "waste", run_result["time"], run_result["results"], run_result["stage"], duration,
        extra_metadata={"process": "Vitrification (borosilicate glass encapsulation)", "mass_unit": "kg"},
    )
