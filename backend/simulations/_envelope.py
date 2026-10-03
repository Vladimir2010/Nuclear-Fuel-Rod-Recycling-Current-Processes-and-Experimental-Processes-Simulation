"""
Общ формат на отговора за всички /api/* симулации, по спецификацията на
frontend екипа (React + Three.js): цялата поредица се връща в един отговор,
не се polling-ва на реално време.
"""
import uuid


def build_response(stage_id: str, time_s: list, results: dict, stage_labels: list,
                    requested_duration: float, extra_metadata: dict | None = None) -> dict:
    final = {key: values[-1] for key, values in results.items() if values}

    metadata = {"time_unit": "s", "temperature_unit": "°C"}
    if extra_metadata:
        metadata.update(extra_metadata)

    return {
        "simulation_id": f"{stage_id}-{uuid.uuid4().hex[:8]}",
        "status": "completed",
        "duration": requested_duration,
        "time": time_s,
        "results": results,
        "stage": stage_labels,
        "final": final,
        "metadata": metadata,
    }
