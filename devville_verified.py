"""Launch the Dev-Ville GUI with evidence-backed ticket completion semantics."""
import tkinter as tk

from devville import DevVilleApp
from verified_company import VerifiedCompany


class VerifiedDevVilleApp(DevVilleApp):
    """Existing Dev-Ville GUI wired to the verified company runtime."""

    def __init__(self, root: tk.Tk):
        super().__init__(root)
        self.company = VerifiedCompany()
        self.root.title("Dev-Ville - Verified Runtime")
        self.update_ui()


def main() -> None:
    root = tk.Tk()
    VerifiedDevVilleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
