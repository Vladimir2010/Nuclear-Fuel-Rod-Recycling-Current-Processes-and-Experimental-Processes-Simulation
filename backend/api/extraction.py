from fastapi import APIRouter
from simulations import extraction
from simulations._envelope import build_response

router = APIRouter()


@router.get("/extraction")
def get_extraction(
    duration: float = 240.0,
    sample_interval: float = 10.0,
    uranium_mol: float = 2.57,
    aqueous_volume_l: float = 15.0,
    hno3_concentration_m: float = 4.5,
):
    run_result = extraction.run(duration, sample_interval, 0.5, uranium_mol, aqueous_volume_l, hno3_concentration_m)
    return build_response(
        "extraction", run_result["time"], run_result["results"], run_result["stage"], duration,
        extra_metadata={
            "process": "TBP solvent extraction (uranium moves from acid into organic phase)",
            "reaction": "UO2(2+) + 2 NO3- + 2 TBP(org) <-> UO2(NO3)2*2TBP(org)",
            "note": "опростен единичен контактор; реален завод ползва N-степенна каскада",
            "concentration_unit": "mol/L",
        },
    )
