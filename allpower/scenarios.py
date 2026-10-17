from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta

HOSPITAL = {"name": "Bayou Regional Hospital", "fictional": True,
            "critical_kw": 420, "discretionary_kw": 180, "battery_kwh": 900,
            "battery_initial_kwh": 720, "battery_max_kw": 240,
            "generator_kw": 330, "generator_fuel_kwh": 1800,
            "solar_peak_kw": 110}

SCENARIOS = {
    "normal": {"name": "Normal operation", "description": "Reference conditions with sufficient supply.",
               "derating_mw": 0, "storm": False, "fault": False},
    "supply-loss": {"name": "Supply loss", "description": "A simulated generator derating tightens the reserve margin.",
                    "derating_mw": 12800, "storm": False, "fault": True},
    "storm": {"name": "Storm disruption", "description": "A fictional severe-weather stress test for local assets.",
              "derating_mw": 9300, "storm": True, "fault": True},
}

def demand_history(hours=24*70, seed=19):
    """Deterministic synthetic ERCOT-shaped demand, never described as observed."""
    import random
    rng = random.Random(seed)
    start = datetime(2024, 4, 1, tzinfo=timezone.utc)
    out = []
    for i in range(hours):
        t = start + timedelta(hours=i)
        hour = (t.hour - 5) % 24
        daily = 4800 * math.sin(2*math.pi*(hour-15)/24)
        weekly = -1900 if t.weekday() >= 5 else 0
        slow = 2600 * math.sin(2*math.pi*i/(24*31))
        value = 56600 + daily + weekly + slow + rng.gauss(0, 540)
        out.append({"timestamp": t.isoformat(), "demand_mw": round(value, 1), "provenance": "simulated"})
    return out

def forecast(history, horizon=6):
    """Seasonal benchmark uses the same hour one week earlier."""
    values = [float(row["demand_mw"]) for row in history]
    if len(values) < 168:
        raise ValueError("At least 168 continuous hourly observations are required")
    last = values[-1]
    result = []
    for h in range(1, horizon+1):
        weekly = values[-169+h]
        same_day = values[-25+h]
        estimate = .62*weekly + .28*same_day + .10*last
        result.append(round(estimate, 1))
    return result

def scenario_output(name, history=None, prediction=None, model_version="seasonal-benchmark-v1"):
    if name not in SCENARIOS:
        raise KeyError(name)
    info = SCENARIOS[name]
    history = history or demand_history()
    prediction = prediction or forecast(history)
    # These supply numbers are scenario assumptions, not ERCOT capacity observations.
    base_supply = 73700
    reserve = 4800
    supply = [base_supply - info["derating_mw"] - (900 if info["storm"] and h > 2 else 0)
              for h in range(1, 7)]
    margins = [round(s - reserve - d, 1) for s, d in zip(supply, prediction)]
    deficits = [max(0, -m) for m in margins]
    first = next((i+1 for i, x in enumerate(deficits) if x > 0), None)
    risk = "prepare" if first else "normal"
    return {"scenario": name, "scenario_name": info["name"], "description": info["description"],
            "input_timestamp": history[-1]["timestamp"], "model_version": model_version,
            "forecast_mw": prediction, "supply_mw": supply, "reserve_mw": reserve,
            "margin_mw": margins, "first_deficit_hour": first,
            "deficit_energy_mwh": round(sum(deficits), 1), "risk": risk,
            "provenance": {"demand_history": history[-1].get("provenance", "unknown"),
                           "supply": "simulated", "reserve": "simulated", "hospital": "simulated",
                           "asset_link": "simulated"},
            "inspection": {"asset": "Transmission insulator", "result": "inspection required" if info["fault"] else "no concern in scenario",
                           "provenance": "simulated scenario", "model_result": False},
            "hospital": HOSPITAL.copy()}
