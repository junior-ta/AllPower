"""Six-hour hospital backup planning. Grid loss is a scenario assumption."""
from __future__ import annotations

def plan(forecast_record):
    h = forecast_record["hospital"]
    start = forecast_record["first_deficit_hour"]
    # Illustrative local interruption: begins at the first regional tight-margin hour.
    # No physical feeder linkage is asserted.
    grid = [h["critical_kw"] if start is None or i+1 < start else 0 for i in range(6)]
    solar = [0, 24, 67, 100, 76, 31]
    if forecast_record["scenario"] == "storm":
        solar = [round(x*.35) for x in solar]
    target = [h["critical_kw"]]*6

    def reactive():
        battery = h["battery_initial_kwh"]
        fuel = h["generator_fuel_kwh"]
        generator_started = False
        out = []
        for i in range(6):
            need = max(0, target[i]-grid[i]-solar[i])
            # Reactive policy depletes the battery first and starts the generator later.
            b = min(need, h["battery_max_kw"], battery)
            battery -= b
            need -= b
            if need > 0 and not generator_started:
                generator_started = True  # This hour is lost to reactive startup.
                g = 0
            else:
                g = min(need, h["generator_kw"], fuel) if generator_started else 0
            fuel -= g
            out.append({"hour": i+1, "grid_kwh": grid[i], "solar_kwh": solar[i],
                        "battery_kwh": b, "generator_kwh": g,
                        "unmet_kwh": max(0, need-g)})
        return out

    method = "prepared dispatch heuristic"
    try:
        from scipy.optimize import linprog
        # Variables: battery[6], generator[6], unmet[6]. Solar and grid are fixed.
        n = 6
        costs = [0.02]*n + [0.01]*n + [1.0]*n
        eq = []
        rhs = []
        for i in range(n):
            row = [0.0]*(3*n)
            row[i] = row[n+i] = row[2*n+i] = 1.0
            eq.append(row)
            rhs.append(max(0, target[i]-grid[i]-solar[i]))
        ub = []
        limit = []
        for indices, capacity in [(range(n), h["battery_initial_kwh"]),
                                  (range(n, 2*n), h["generator_fuel_kwh"])]:
            row = [0.0]*(3*n)
            for j in indices: row[j] = 1.0
            ub.append(row); limit.append(capacity)
        bounds = [(0, h["battery_max_kw"])]*n + [(0, h["generator_kw"])]*n + [(0, None)]*n
        result = linprog(costs, A_ub=ub, b_ub=limit, A_eq=eq, b_eq=rhs,
                         bounds=bounds, method="highs")
        if not result.success: raise RuntimeError(result.message)
        optimized = []
        for i in range(n):
            optimized.append({"hour": i+1, "grid_kwh": grid[i], "solar_kwh": solar[i],
                              "battery_kwh": round(result.x[i], 2),
                              "generator_kwh": round(result.x[n+i], 2),
                              "unmet_kwh": round(result.x[2*n+i], 2)})
        method = "SciPy linear program"
    except ImportError:
        battery = h["battery_initial_kwh"]
        fuel = h["generator_fuel_kwh"]
        optimized = []
        for i in range(6):
            need = max(0, target[i]-grid[i]-solar[i])
            g = min(need, h["generator_kw"], fuel)
            fuel -= g; need -= g
            b = min(need, h["battery_max_kw"], battery)
            battery -= b; need -= b
            optimized.append({"hour":i+1,"grid_kwh":grid[i],"solar_kwh":solar[i],
                              "battery_kwh":b,"generator_kwh":g,"unmet_kwh":need})
    baseline = reactive()
    unmet = round(sum(row["unmet_kwh"] for row in optimized), 1)
    baseline_unmet = round(sum(row["unmet_kwh"] for row in baseline), 1)
    return {"method": method, "grid_loss": "simulated local interruption beginning at regional deficit",
            "solar": "simulated", "hours": optimized, "baseline_hours": baseline,
            "critical_demand_kwh": sum(target), "critical_served_kwh": round(sum(target)-unmet, 1),
            "critical_unmet_kwh": unmet, "reactive_unmet_kwh": baseline_unmet,
            "improvement_kwh": round(baseline_unmet-unmet, 1), "provenance": "simulated hospital resources"}
