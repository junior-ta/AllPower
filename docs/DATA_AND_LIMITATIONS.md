# Data, assumptions and limits

| Input | Current demo | Intended real source | Guardrail |
|---|---|---|---|
| Regional hourly demand | Deterministic simulated series, seed 19 | ERCOT hourly load or EIA-930 | Do not call the current forecast validated on real demand. |
| Supply availability | Simulated 73,700 MW less scenario derating | Timestamped ERCOT adequacy publication | Net generation is not available capacity. |
| Reserve requirement | Simulated 4,800 MW | Operator requirement matching source time | State this assumption visibly. |
| Facility | Fictional Bayou Regional Hospital | Optional real facility only with permission and context | No partnership claim. |
| Critical load | Simulated 420 kW each hour | Site energy plan | Fixed for six-hour demonstration. |
| Battery | 900 kWh nameplate, 720 kWh initial, 240 kW discharge | Site equipment record | Initial usable energy is the constraint. |
| Generator | 330 kW, 1,800 kWh fuel-equivalent budget | Site equipment record | Reactive baseline loses one startup hour. |
| Solar | Simulated hourly curve | Local forecast / meter data | Storm scenario reduces it to 35%. |
| Local grid interruption | Begins at first regional deficit in scenario | Local feeder and outage evidence | This link is illustrative, not a physical forecast. |
| Asset finding | Scripted scenario finding | InsPLAD-trained model, later field inspection | No image model inference currently claimed. |

The regional model forecasts demand, then tests it against assumed supply minus reserve. A regional deficit does not by itself establish that a particular hospital will lose power. The local interruption is a separate scenario bridge. The optimized backup result is modeled energy coverage, not patient outcomes. Battery charge efficiency, solar uncertainty, generator ramping, and network constraints are simplified; these must be modeled before operational use.

The shipped simulation is reproducible. It is not real-world validation. Source files were not downloaded into this workspace because outbound shell networking was unavailable. The data acquisition links and import route are in the README. The image model is not trained or connected in the shipped app. These gaps are visible in the dashboard and pitch.
