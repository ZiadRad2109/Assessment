"""
Main Application Module.

This module initializes the QApplication and executes the main event loop.
"""

from PyQt6.QtWidgets import QApplication
import sys
from .gui import MainWindow


def main():
    """
    Main entry point for the application.

    Instantiates the QApplication and MainWindow, and starts the event loop.

    Calls:
        - `PyQt6.QtWidgets.QApplication`
        - `app.gui.MainWindow`
        - `app.gui.MainWindow.show`
        - `QApplication.exec`

    Called by:
        - `run.py`
    """
    # the main application loop
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
