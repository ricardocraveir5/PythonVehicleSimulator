"""
main_gui.py — Entry point for the Torpedo AUV parameter-editor GUI.

References:
    T. I. Fossen, "Handbook of Marine Craft Hydrodynamics and Motion
    Control", 2nd ed., Wiley, 2021.

Author : Ricardo Craveiro (1191000@isep.ipp.pt)
Project: DINAV 2026 — Etapa 2 (MVC torpedo GUI)
"""

import sys

from PyQt6.QtWidgets import QApplication

from python_vehicle_simulator.gui.torpedo_controller import TorpedoController
from python_vehicle_simulator.gui.torpedo_gui import TorpedoGUI


def main() -> int:
    """Create the Qt application, wire the MVC triad, and enter the event loop."""
    app = QApplication(sys.argv)
    app.setApplicationName("Torpedo AUV — DINAV 2026")
    app.setOrganizationName("ISEP / DINAV")

    controller = TorpedoController()
    window = TorpedoGUI(controller)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
