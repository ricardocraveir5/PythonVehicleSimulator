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
    """Fresh controller + GUI for each test, with teardown to free Qt resources."""
    from PyQt6.QtWidgets import QMessageBox

    from python_vehicle_simulator.gui.torpedo_controller import TorpedoController
    from python_vehicle_simulator.gui.torpedo_gui import TorpedoGUI

    with patch.object(QMessageBox, "warning", staticmethod(lambda *a, **kw: None)), \
         patch.object(QMessageBox, "information", staticmethod(lambda *a, **kw: None)):
        ctrl = TorpedoController()
        gui = TorpedoGUI(ctrl)
        gui.show()
        qt_app.processEvents()
        try:
            yield ctrl, gui, qt_app
        finally:
            gui.close()
            gui.deleteLater()
            qt_app.processEvents()


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
    """Painel direito deve ser um QTabWidget com 6 tabs de visualização."""
    from PyQt6.QtWidgets import QTabWidget
    ctrl, gui, app = mvc
    right = gui._right_panel
    assert isinstance(right, QTabWidget), (
        f"Expected QTabWidget, got {type(right).__name__}")
    assert right.count() == 6, f"Expected 6 tabs, got {right.count()}"
    assert right.tabText(0) == "Controladores"
    assert right.tabText(1) == "Visualização 3D"
    assert right.tabText(2) == "Gráficos de Estado"
    assert right.tabText(3) == "Gráficos Etapa 3"
    assert right.tabText(4) == "Sinais de Controlo"
    assert right.tabText(5) == "Comparação"


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


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 11 — Widget Etapa3GraphsWidget está registado na GUI
# ──────────────────────────────────────────────────────────────────────────────

def test_etapa3_widget_registered_in_gui(mvc):
    """O widget Etapa3GraphsWidget deve existir como atributo da GUI."""
    from python_vehicle_simulator.gui.torpedo_viz import Etapa3GraphsWidget
    ctrl, gui, app = mvc
    assert hasattr(gui, "_etapa3_widget"), (
        "_etapa3_widget não existe como atributo da GUI")
    assert isinstance(gui._etapa3_widget, Etapa3GraphsWidget), (
        f"_etapa3_widget tem tipo errado: {type(gui._etapa3_widget).__name__}")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 12 — Tab "Gráficos Etapa 3" está na posição correcta (índice 3)
# ──────────────────────────────────────────────────────────────────────────────

def test_etapa3_tab_position(mvc):
    """A tab 'Gráficos Etapa 3' deve estar no índice 3, entre 'Gráficos de
    Estado' (2) e 'Sinais de Controlo' (4)."""
    ctrl, gui, app = mvc
    right = gui._right_panel
    assert right.tabText(3) == "Gráficos Etapa 3", (
        f"Tab 3 tem texto errado: {right.tabText(3)!r}")
    # Ordem relativa aos vizinhos
    assert right.tabText(2) == "Gráficos de Estado"
    assert right.tabText(4) == "Sinais de Controlo"
    # O widget da tab 3 deve ser o mesmo que o atributo _etapa3_widget
    assert right.widget(3) is gui._etapa3_widget


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 13 — Widget é actualizado após _on_simulation_done
# ──────────────────────────────────────────────────────────────────────────────

def test_etapa3_widget_plotted_after_simulation(mvc):
    """Após _on_simulation_done correr, o widget deve ter os 6 axes renderizados
    (5 subplots + twin axis do RPM) e o info-label actualizado."""
    import numpy as np

    ctrl, gui, app = mvc
    # simData sintético com as 22 colunas esperadas (eta, nu, cmd, actual)
    N = 50
    simTime = np.linspace(0, 2.5, N).reshape(-1, 1)
    simData = np.zeros((N, 22))
    simData[:, 0] = np.linspace(0, 10, N)     # x_north
    simData[:, 1] = np.linspace(0, 5,  N)     # y_east
    simData[:, 2] = np.linspace(0, 3,  N)     # z_depth
    simData[:, 6] = 1.5                        # u (surge)
    simData[:, 16] = 1000.0                    # n_cmd (RPM)

    # Antes de chamar _on_simulation_done o widget tem o placeholder
    assert "Aguarda" in gui._etapa3_widget._info.text()

    gui._on_simulation_done(simTime, simData)
    app.processEvents()

    # Widget deve ter 6 axes após plot
    assert len(gui._etapa3_widget._fig.axes) == 6, (
        f"Widget não foi plotado: {len(gui._etapa3_widget._fig.axes)} axes")
    # Info-label deve ter sido actualizado com nº de amostras
    text = gui._etapa3_widget._info.text()
    assert str(N) in text, (
        f"Info-label não foi actualizado com N={N}: {text!r}")


# ──────────────────────────────────────────────────────────────────────────────
# Etapa 3 A/B button — controller unit tests
# ──────────────────────────────────────────────────────────────────────────────

def test_prepare_etapa3_simulation_emits_ready_with_cd_override(qt_app):
    from python_vehicle_simulator.gui.torpedo_controller import TorpedoController
    ctrl = TorpedoController()
    vehicles = []
    ctrl.simulation_ready.connect(lambda v: vehicles.append(v))
    ctrl.prepare_etapa3_simulation(0.25)
    qt_app.processEvents()
    assert len(vehicles) == 1, "simulation_ready not emitted exactly once"
    v = vehicles[0]
    assert abs(v.Cd - 0.25) < 1e-9
    assert v.controlMode == "stepInput"


def test_prepare_etapa3_simulation_does_not_mutate_model_cd(qt_app):
    from python_vehicle_simulator.gui.torpedo_controller import TorpedoController
    ctrl = TorpedoController()
    ctrl.update_param("Cd", 0.42)
    qt_app.processEvents()
    updates = []
    ctrl.params_updated.connect(lambda p: updates.append(p))
    ctrl.prepare_etapa3_simulation(0.25)
    qt_app.processEvents()
    assert abs(ctrl.get_current_params()["Cd"] - 0.42) < 1e-9
    assert not updates, "params_updated should NOT be emitted"


def test_prepare_etapa3_simulation_rejects_out_of_range_cd(qt_app):
    from python_vehicle_simulator.gui.torpedo_controller import TorpedoController
    ctrl = TorpedoController()
    errors = []
    ready = []
    ctrl.validation_error.connect(lambda m: errors.append(m))
    ctrl.simulation_ready.connect(lambda v: ready.append(v))
    ctrl.prepare_etapa3_simulation(0.05)
    qt_app.processEvents()
    assert errors, "validation_error not emitted for Cd=0.05"
    assert not ready, "simulation_ready should not fire on validation error"


def test_prepare_etapa3_simulation_preserves_user_edited_params(qt_app):
    from python_vehicle_simulator.gui.torpedo_controller import TorpedoController
    ctrl = TorpedoController()
    ctrl.update_param("L", 2.0)
    qt_app.processEvents()
    vehicles = []
    ctrl.simulation_ready.connect(lambda v: vehicles.append(v))
    ctrl.prepare_etapa3_simulation(0.3)
    qt_app.processEvents()
    assert abs(vehicles[0].L - 2.0) < 1e-6


# ──────────────────────────────────────────────────────────────────────────────
# Etapa 3 A/B button — GUI integration tests with a fake SimulationThread
# ──────────────────────────────────────────────────────────────────────────────

def _make_fake_sim_thread_class():
    """Create an isolated fake SimulationThread class per test fixture."""
    import numpy as np
    from PyQt6.QtCore import QObject, pyqtSignal

    class _FakeSimThread(QObject):
        finished = pyqtSignal(object, object)
        error    = pyqtSignal(str)

        invocations = []
        mode = "success"         # "success" | "error" | "noop"
        error_msg = "boom"

        def __init__(self, vehicle, N, sampleTime, parent=None):
            super().__init__(parent)
            self._vehicle = vehicle
            self._N = N
            self._sampleTime = sampleTime
            _FakeSimThread.invocations.append(
                {"vehicle": vehicle, "N": N, "sampleTime": sampleTime})

        def start(self):
            if _FakeSimThread.mode == "noop":
                return
            if _FakeSimThread.mode == "error":
                self.error.emit(_FakeSimThread.error_msg)
                return
            N = max(2, self._N)
            simTime = np.linspace(
                0.0, N * self._sampleTime, N).reshape(-1, 1)
            simData = np.zeros((N, 22))
            simData[:, 0] = np.linspace(0.0, 10.0, N)   # x
            simData[:, 6] = 1.5                          # u (surge)
            simData[:, 16] = 1000.0                      # n_cmd (RPM)
            self.finished.emit(simTime, simData)

        def isRunning(self):
            return False

    return _FakeSimThread


@pytest.fixture()
def ab_mvc(qt_app):
    from unittest.mock import patch
    from PyQt6.QtWidgets import QMessageBox

    from python_vehicle_simulator.gui.torpedo_controller import TorpedoController
    from python_vehicle_simulator.gui import torpedo_gui as tg
    from python_vehicle_simulator.gui.torpedo_gui import TorpedoGUI

    fake_cls = _make_fake_sim_thread_class()

    with patch.object(QMessageBox, "warning", staticmethod(lambda *a, **kw: None)), \
         patch.object(QMessageBox, "information", staticmethod(lambda *a, **kw: None)), \
         patch.object(tg, "SimulationThread", fake_cls):
        ctrl = TorpedoController()
        gui = TorpedoGUI(ctrl)
        gui.show()
        qt_app.processEvents()
        try:
            yield ctrl, gui, qt_app, fake_cls
        finally:
            gui.close()
            gui.deleteLater()
            qt_app.processEvents()


def test_ab_button_exists_and_wired(ab_mvc):
    ctrl, gui, app, _fake = ab_mvc
    assert hasattr(gui, "_btn_simulate_ab")
    assert gui._btn_simulate_ab.text() == "Simular A e B (Etapa 3)"


def test_ab_button_disables_all_sim_buttons_during_run(ab_mvc):
    ctrl, gui, app, fake_cls = ab_mvc
    fake_cls.mode = "noop"   # Sim A starts but never emits finished
    gui._launch_etapa3_ab_run()
    app.processEvents()
    assert gui._ab_mode == "A"
    assert not gui._btn_simulate.isEnabled()
    assert not gui._btn_simulate_ab.isEnabled()
    assert not gui._btn_reset.isEnabled()


def test_ab_button_runs_two_sims_with_etapa3_labels(ab_mvc):
    ctrl, gui, app, _fake = ab_mvc
    gui._launch_etapa3_ab_run()
    app.processEvents()
    store = ctrl.get_store()
    assert len(store) == 2, f"expected 2 sims, got {len(store)}"
    assert store[0]["label"] == "Sim A — Cd=0.42 (Etapa 3)"
    assert store[1]["label"] == "Sim B — Cd=0.25 (Etapa 3)"


def test_ab_button_switches_to_3d_tab_on_completion(ab_mvc):
    ctrl, gui, app, _fake = ab_mvc
    gui._launch_etapa3_ab_run()
    app.processEvents()
    assert gui._right_panel.currentIndex() == 1
    assert gui._ab_mode is None
    assert gui._btn_simulate.isEnabled()
    assert gui._btn_simulate_ab.isEnabled()
    assert gui._btn_reset.isEnabled()


def test_ab_button_uses_200s_10000_steps(ab_mvc):
    ctrl, gui, app, fake_cls = ab_mvc
    gui._launch_etapa3_ab_run()
    app.processEvents()
    calls = fake_cls.invocations
    assert len(calls) == 2, f"expected 2 SimulationThread invocations, got {len(calls)}"
    for c in calls:
        assert c["N"] == 10000
        assert abs(c["sampleTime"] - 0.02) < 1e-9


def test_ab_button_error_in_sim_a_does_not_launch_sim_b(ab_mvc):
    ctrl, gui, app, fake_cls = ab_mvc
    fake_cls.mode = "error"
    saved = gui._sim_duration
    gui._launch_etapa3_ab_run()
    app.processEvents()
    assert len(fake_cls.invocations) == 1, "Sim B should not have been launched"
    assert gui._ab_mode is None
    assert gui._btn_simulate.isEnabled()
    assert gui._btn_simulate_ab.isEnabled()
    assert gui._btn_reset.isEnabled()
    assert gui._sim_duration == saved


def test_ab_button_does_not_change_user_cd_widget_value(ab_mvc):
    ctrl, gui, app, _fake = ab_mvc
    ctrl.update_param("Cd", 0.40)
    app.processEvents()
    gui._launch_etapa3_ab_run()
    app.processEvents()
    assert abs(gui.param_widgets["Cd"].value() - 0.40) < 1e-9
    assert abs(ctrl.get_current_params()["Cd"] - 0.40) < 1e-9


def test_ab_button_restores_sim_duration_after_run(ab_mvc):
    ctrl, gui, app, _fake = ab_mvc
    gui._sim_duration = 20.0
    gui._launch_etapa3_ab_run()
    app.processEvents()
    assert gui._sim_duration == 20.0
    assert gui._ab_saved_duration is None


def test_ab_button_triggers_dual_animation(ab_mvc):
    ctrl, gui, app, _fake = ab_mvc
    calls = []
    original = gui._viz_widget.run_dual_animation

    def _spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    gui._viz_widget.run_dual_animation = _spy
    gui._launch_etapa3_ab_run()
    app.processEvents()
    assert len(calls) == 1
    _args, kwargs = calls[0]
    assert kwargs["label_A"] == "Sim A — Cd=0.42 (Etapa 3)"
    assert kwargs["label_B"] == "Sim B — Cd=0.25 (Etapa 3)"
