from pathlib import Path

from oemof import solph
from oemof.visio.energy_system_graph import ESGraphRenderer

scenario = "2050-100-el_eff"

energysystem_path = (
    Path(__file__).resolve().parents[3]
    / "Energy-System-Adlershof"
    / "results"
    / scenario
    / "optimized"
)

file_path = energysystem_path / "energy_system_graph.pdf"

if energysystem_path.exists():
    my_energysystem = solph.EnergySystem()
    my_energysystem.restore(energysystem_path, "es_dump.oemof")

    energysystem_graph = ESGraphRenderer(
        energy_system=my_energysystem, filepath=file_path
    )
    energysystem_graph.render()
elif not energysystem_path.exists():
    raise FileNotFoundError(f"Directory does not exist: {energysystem_path}")
