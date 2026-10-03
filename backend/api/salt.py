from fastapi import APIRouter
from simulations import salt_electrorefining
from simulations._envelope import build_response

router = APIRouter()


@router.get("/dissolution/salt")
def get_salt_electrorefining(
    duration: float = 240.0,
    sample_interval: float = 10.0,
    mass_u_kg: float = 0.05,
    mass_pu_kg: float = 0.0015,
    mass_nd_kg: float = 0.005,
    temperature_c: float = 500.0,
    voltage_applied: float = -2.5,
):
    run_result = salt_electrorefining.run(
        duration, sample_interval, 0.5,
        mass_u_kg, mass_pu_kg, mass_nd_kg, temperature_c, voltage_applied,
    )
    return build_response(
        "salt-electrorefining", run_result["time"], run_result["results"], run_result["stage"], duration,
        extra_metadata={
            "process": "Molten salt (LiCl-KCl) electrorefining / pyroprocessing",
            "cathode_solid": "U deposits on solid steel cathode",
            "cathode_liquid": "Pu deposits on liquid Cd/Bi cathode",
            "stays_in_salt": "Nd (lanthanide fission product, waste) - unless voltage is too aggressive",
            "mass_unit": "kg",
            "voltage_unit": "V",
        },
    )
