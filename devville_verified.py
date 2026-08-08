"""Launch Dev-Ville with Victor as driver and Dev-Ville as vehicle."""
import os
import tkinter as tk

from devville import DevVilleApp
from victor_driver import VictorDriver
from victor_driver_facade import VictorDriverCompanyFacade


class VerifiedDevVilleApp(DevVilleApp):
    """Existing Dev-Ville GUI with all mutations routed through Victor."""

    def __init__(self, root: tk.Tk):
        super().__init__(root)
        chronos_path = os.environ.get("DEVVILLE_CHRONOS_PATH", "chronos/devville.jsonl")
        self.driver = VictorDriver(chronos_jsonl_path=chronos_path)
        self.company = VictorDriverCompanyFacade(self.driver)
        self.root.title("Dev-Ville - Victor Driver / Machine-Labor Vehicle")
        self.update_ui()


def main() -> None:
    root = tk.Tk()
    VerifiedDevVilleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
