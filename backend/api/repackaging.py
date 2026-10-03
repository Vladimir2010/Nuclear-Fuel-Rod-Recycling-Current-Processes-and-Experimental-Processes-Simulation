from fastapi import APIRouter
from simulations import repackaging as repackaging_sim
from simulations._envelope import build_response

router = APIRouter()


@router.get("/repackaging")
def get_repackaging(
    duration: float = 90.0,
    sample_interval: float = 5.0,
    speed: float = 1.0,
    recovered_mass_kg: float = 0.965,
):
    run_result = repackaging_sim.run(duration, sample_interval, speed, recovered_mass_kg)
    return build_response(
        "repackaging", run_result["time"], run_result["results"], run_result["stage"], duration,
        extra_metadata={"process": "MOX pellet assembly + sintering", "mass_unit": "kg"},
    )
