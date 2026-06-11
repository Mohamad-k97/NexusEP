from pathlib import Path

from nexusep.abbey.simulation.runner import AbbeySimulation


PROJECT_ROOT = Path(__file__).resolve().parents[2]

config_path = PROJECT_ROOT / "nexusep" / "data" / "abbey" / "config" / "abbey_config.jsonc"
output_path = PROJECT_ROOT / "outputs" / "abbey" / "runs" / "abbey_v01_test_08.csv"

sim = AbbeySimulation.initialize(
    config_path=config_path,
    duration_hours=48,
    dt_minutes=1,
)

df = sim.run()
sim.save_csv(output_path)

print(df.head())
print(f"Saved to: {output_path}")