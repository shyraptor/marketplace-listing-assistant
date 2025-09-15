#!/usr/bin/env python
"""Main entry point for Marketplace Listing Assistant."""

import sys
import tkinter as tk
from tkinter import messagebox

from mla.ui import App

if __name__ == "__main__":
    try:
        app = App()
        if hasattr(app, 'backend') and app.backend.lang:
            app.mainloop()
        # If init failed, error messages were already shown
    except Exception as e:
        # Catch-all for unexpected errors during App init itself
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Critical Startup Error", f"Application failed to initialize:\n{e}")
            root.destroy()
        except Exception as tk_e:
            pass
        sys.exit(1)