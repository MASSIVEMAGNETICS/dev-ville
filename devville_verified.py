"""Launch Dev-Ville with sovereign topological Victor as driver."""
import os
import tkinter as tk

from devville import DevVilleApp
from victor_driver_facade import VictorDriverCompanyFacade
from victor_sovereign_driver import VictorSovereignDriver


class VerifiedDevVilleApp(DevVilleApp):
    """Existing Dev-Ville GUI with all mutations routed through Victor."""

    def __init__(self, root: tk.Tk):
        super().__init__(root)
        chronos_path = os.environ.get("DEVVILLE_CHRONOS_PATH", "chronos/devville.jsonl")
        identity_path = os.environ.get("VICTOR_IDENTITY_KEY_PATH", "identity/victor.key")
        self.driver = VictorSovereignDriver(
            chronos_jsonl_path=chronos_path,
            identity_key_path=identity_path,
        )
        self.company = VictorDriverCompanyFacade(self.driver)
        self.root.title("Dev-Ville - Sovereign Victor Driver / Machine-Labor Vehicle")
        self.update_ui()


def main() -> None:
    root = tk.Tk()
    VerifiedDevVilleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
