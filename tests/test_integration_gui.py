"""
test_integration_gui.py — Integration tests for TorpedoController + TorpedoGUI.

Agente 5B — DINAV 2026 Etapa 2
Author: Ricardo Craveiro (1191000@isep.ipp.pt)

Runs headlessly (QT_QPA_PLATFORM=offscreen) and covers 6 scenarios:
  1. Startup: widgets load with correct torpedo values
  2. Valid update: params_updated emitted with new value
  3. Invalid update: validation_error emitted for out-of-range value
  4. Dependency A7: T_sway → T_heave auto-update via param_dependency_updated
  5. Prepare simulation: simulation_ready emitted with valid torpedo instance
  6. Reset: params_updated emitted with factory defaults
"""

import os
import sys
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Ensure src is importable when running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(scope="module")
def qt_app():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture()
def mvc(qt_app):
    """Fresh controller + GUI for each test."""
    from PyQt6.QtWidgets import QMessageBox

    from python_vehicle_simulator.gui.torpedo_controller import TorpedoController
    from python_vehicle_simulator.gui.torpedo_gui import TorpedoGUI

    with patch.object(QMessageBox, "warning", staticmethod(lambda *a, **kw: None)), \
         patch.object(QMessageBox, "information", staticmethod(lambda *a, **kw: None)):
        ctrl = TorpedoController()
        gui = TorpedoGUI(ctrl)
        gui.show()
        qt_app.processEvents()
        yield ctrl, gui, qt_app


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 1 — Arranque
# ──────────────────────────────────────────────────────────────────────────────

def test_startup_widgets_load(mvc):
    ctrl, gui, app = mvc
    pw = gui.param_widgets
    assert len(pw) > 0, "No widgets registered"
    assert abs(pw["L"].value()        - 1.6)  < 1e-6
    assert abs(pw["diam"].value()     - 0.19) < 1e-6
    assert abs(pw["fin_CL_0"].value() - 0.5)  < 1e-6


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 2 — Alteração válida
# ──────────────────────────────────────────────────────────────────────────────

def test_valid_update_emits_params_updated(mvc):
    ctrl, gui, app = mvc
    received = []
    ctrl.params_updated.connect(lambda p: received.append(p))
    ctrl.update_param("wn_d", 0.2)
    app.processEvents()
    assert received, "params_updated not emitted"
    assert abs(received[-1].get("wn_d", -1) - 0.2) < 1e-9


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 3 — Alteração inválida
# ──────────────────────────────────────────────────────────────────────────────

def test_invalid_update_emits_validation_error(mvc):
    ctrl, gui, app = mvc
    errors = []
    ctrl.validation_error.connect(lambda m: errors.append(m))
    ctrl.update_param("zeta_d", 0.1)   # < 0.5 → inválido
    app.processEvents()
    assert errors, "validation_error not emitted for zeta_d=0.1"
    assert len(errors[-1]) > 5, f"Error message too short: {errors[-1]!r}"


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 4 — Acoplamento A7: T_sway → T_heave
# ──────────────────────────────────────────────────────────────────────────────

def test_tsway_updates_theave(mvc):
    ctrl, gui, app = mvc
    deps = []
    ctrl.param_dependency_updated.connect(lambda n, v: deps.append((n, v)))
    ctrl.update_param("T_sway", 25.0)
    app.processEvents()
    theave_updates = [(n, v) for n, v in deps if n == "T_heave"]
    assert theave_updates, f"T_heave dependency not emitted. All deps: {deps}"
    assert abs(theave_updates[-1][1] - 25.0) < 1e-9


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 5 — prepare_simulation
# ──────────────────────────────────────────────────────────────────────────────

def test_prepare_simulation_emits_ready(mvc):
    ctrl, gui, app = mvc
    vehicles = []
    ctrl.simulation_ready.connect(lambda v: vehicles.append(v))
    ctrl.prepare_simulation("depthHeadingAutopilot", 30.0, 50.0)
    app.processEvents()
    assert vehicles, "simulation_ready not emitted"
    v = vehicles[-1]
    assert v.controlMode == "depthHeadingAutopilot"
    assert abs(v.ref_z   - 30.0) < 1e-6
    assert abs(v.ref_psi - 50.0) < 1e-6


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 6 — Reset
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# Cenário 7 — Tabs de visualização
# ──────────────────────────────────────────────────────────────────────────────

def test_visualization_tabs_exist(mvc):
    """Painel direito deve ser um QTabWidget com 3 tabs de visualização."""
    from PyQt6.QtWidgets import QTabWidget
    ctrl, gui, app = mvc
    right = gui._right_panel
    assert isinstance(right, QTabWidget), (
        f"Expected QTabWidget, got {type(right).__name__}")
    assert right.count() == 3, f"Expected 3 tabs, got {right.count()}"
    assert right.tabText(0) == "Controladores"
    assert right.tabText(1) == "Visualização 3D"
    assert right.tabText(2) == "Gráficos de Estado"


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 6 — Reset
# ──────────────────────────────────────────────────────────────────────────────

def test_reset_restores_defaults(mvc):
    ctrl, gui, app = mvc
    # First change something
    ctrl.update_param("wn_d", 0.2)
    app.processEvents()

    reset_params = []
    ctrl.params_updated.connect(lambda p: reset_params.append(p))
    ctrl.reset_to_defaults()
    app.processEvents()
    assert reset_params, "params_updated not emitted after reset"
    p = reset_params[-1]
    assert abs(p.get("L", -1) - 1.6) < 1e-6, f"L after reset = {p.get('L')}"


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 8 — K_nomoto e r_max expostos na GUI
# ──────────────────────────────────────────────────────────────────────────────

def test_nomoto_and_rmax_in_gui(mvc):
    """K_nomoto e r_max devem estar registados como widgets na GUI."""
    ctrl, gui, app = mvc
    assert "K_nomoto" in gui.param_widgets, "K_nomoto não encontrado em param_widgets"
    assert "r_max"    in gui.param_widgets, "r_max não encontrado em param_widgets"
    # Devem ter valores válidos (diferentes de zero)
    assert gui.param_widgets["K_nomoto"].value() > 0
    assert gui.param_widgets["r_max"].value() > 0


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 9 — zeta_roll e zeta_pitch expostos na GUI
# ──────────────────────────────────────────────────────────────────────────────

def test_roll_pitch_damping_in_gui(mvc):
    """zeta_roll e zeta_pitch devem estar registados como widgets na GUI."""
    ctrl, gui, app = mvc
    assert "zeta_roll"  in gui.param_widgets, "zeta_roll não encontrado em param_widgets"
    assert "zeta_pitch" in gui.param_widgets, "zeta_pitch não encontrado em param_widgets"
    # Valores predefinidos: 0.3 e 0.8
    assert abs(gui.param_widgets["zeta_roll"].value()  - 0.3) < 1e-6
    assert abs(gui.param_widgets["zeta_pitch"].value() - 0.8) < 1e-6


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 10 — Dependência geométrica: L → massa
# ──────────────────────────────────────────────────────────────────────────────

def test_geometry_dependency_mass(mvc):
    """Aumentar L deve aumentar a massa calculada (_recalculate_derived)."""
    ctrl, gui, app = mvc
    original_mass = ctrl._model.massa
    ctrl.update_param("L", 2.0)   # maior L → maior massa
    app.processEvents()
    new_mass = ctrl._model.massa
    assert new_mass > original_mass, (
        f"Massa devia ter aumentado: {original_mass:.4f} → {new_mass:.4f}"
    )
