"""Launch Dev-Ville as Victor's evidence-producing machine-labor runtime."""
import os
import tkinter as tk

from devville import DevVilleApp
from victor_machine_labor import VictorMachineLaborCompany


class VerifiedDevVilleApp(DevVilleApp):
    """Existing Dev-Ville GUI wired to the Victor machine-labor runtime."""

    def __init__(self, root: tk.Tk):
        super().__init__(root)
        chronos_path = os.environ.get("DEVVILLE_CHRONOS_PATH", "chronos/devville.jsonl")
        self.company = VictorMachineLaborCompany(chronos_jsonl_path=chronos_path)
        self.root.title("Dev-Ville - Victor Machine-Labor Runtime")
        self.update_ui()


def main() -> None:
    root = tk.Tk()
    VerifiedDevVilleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
