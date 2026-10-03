from fastapi import APIRouter
from simulations import purification
from simulations._envelope import build_response

router = APIRouter()


@router.get("/purification")
def get_purification(
    duration: float = 300.0,
    sample_interval: float = 10.0,
    uranium_mol: float = 2.27,
    organic_volume_l: float = 15.0,
    aqueous_product_volume_l: float = 5.0,
):
    run_result = purification.run(duration, sample_interval, 0.5, uranium_mol, organic_volume_l, aqueous_product_volume_l)
    return build_response(
        "purification", run_result["time"], run_result["results"], run_result["stage"], duration,
        extra_metadata={
            "process": "Stripping -> ADU precipitation -> calcination -> H2 reduction to UO2",
            "phases": ["stripping", "adu_precipitation", "calcination", "reduction_to_uo2"],
            "mass_unit": "kg",
        },
    )
