"""Panel base class."""

import tkinter as tk
from tkinter import ttk


class Panel(ttk.Frame):
    title = "Panel"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.build_ui()

    def build_ui(self) -> None:
        raise NotImplementedError

    def on_state_reset(self) -> None:
        """Called when source changes — sync widgets to default state."""
        pass
