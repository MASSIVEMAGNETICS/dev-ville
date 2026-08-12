"""Launch the fused Dev-Ville + Victor + MoneyFarm runtime."""
import os
import tkinter as tk

from devville import DevVilleApp
from victor_economic_company import VictorEconomicCompany


class MoneyFarmDevVilleApp(DevVilleApp):
    """Existing Dev-Ville GUI backed by the fused verified/economic runtime."""

    def __init__(self, root: tk.Tk):
        super().__init__(root)
        chronos_path = os.environ.get("DEVVILLE_CHRONOS_PATH", "chronos/devville.jsonl")
        economic_path = os.environ.get("DEVVILLE_MONEYFARM_DB", "state/moneyfarm.sqlite3")
        self.company = VictorEconomicCompany(
            chronos_jsonl_path=chronos_path,
            economic_store_path=economic_path,
        )
        self.root.title("Dev-Ville - Victor Economic Runtime")
        self.update_ui()


def main() -> None:
    root = tk.Tk()
    MoneyFarmDevVilleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
