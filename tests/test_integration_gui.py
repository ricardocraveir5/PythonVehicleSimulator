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
    """Painel direito deve ser um QTabWidget com 7 tabs (Etapa 4+ adicionou Análise)."""
    from PyQt6.QtWidgets import QTabWidget
    ctrl, gui, app = mvc
    right = gui._right_panel
    assert isinstance(right, QTabWidget), (
        f"Expected QTabWidget, got {type(right).__name__}")
    assert right.count() == 7, f"Expected 7 tabs, got {right.count()}"
    assert right.tabText(0) == "Controladores"
    assert right.tabText(1) == "Visualização 3D"
    assert right.tabText(2) == "Gráficos de Estado"
    assert right.tabText(3) == "Gráficos Etapa 3"
    assert right.tabText(4) == "Sinais de Controlo"
    assert right.tabText(5) == "Comparação"
    assert right.tabText(6) == "Análise"


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
        finished  = pyqtSignal(object, object)
        error     = pyqtSignal(str)
        cancelled = pyqtSignal()  # Etapa 4+ — paridade com o SimulationThread real

        invocations = []
        mode = "success"         # "success" | "error" | "noop"
        error_msg = "boom"

        def __init__(self, vehicle, N, sampleTime, parent=None):
            super().__init__(parent)
            self._vehicle = vehicle
            self._N = N
            self._sampleTime = sampleTime
            self._cancel_flag = False
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

        def cancel(self):
            self._cancel_flag = True

        def is_cancelled(self) -> bool:
            return self._cancel_flag

        def wait(self, timeout_ms: int = 0) -> bool:
            return True

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


# ---------------------------------------------------------------------------
# Etapa 4 — Selector de corrente oceânica + integração CurrentModel na GUI
# ---------------------------------------------------------------------------

def test_current_model_selector_has_five_options(mvc):
    """Combo 'Corrente Oceânica' tem exactamente as 5 opções definidas na spec."""
    _, gui, _ = mvc
    items = [gui._current_model_combo.itemText(i)
             for i in range(gui._current_model_combo.count())]
    assert items == ['Constante', 'Linear', 'Lei 1/7',
                     'Logarítmico', 'Gauss-Markov']


def test_selector_linear_shows_linear_panel(mvc):
    """Mudar selector para 'Linear' expõe widgets current_V_surface/z_ref."""
    from PyQt6.QtWidgets import QDoubleSpinBox
    _, gui, app = mvc
    gui._current_model_combo.setCurrentText('Linear')
    app.processEvents()
    page = gui._current_model_stack.currentWidget()
    spinboxes = page.findChildren(QDoubleSpinBox)
    assert len(spinboxes) >= 2
    assert 'current_V_surface' in gui.param_widgets
    assert 'current_z_ref' in gui.param_widgets


def test_selector_constante_shows_info_label(mvc):
    """Mudar selector para 'Constante' mostra label informativo (sem spinboxes)."""
    from PyQt6.QtWidgets import QDoubleSpinBox, QLabel
    _, gui, app = mvc
    gui._current_model_combo.setCurrentText('Constante')
    app.processEvents()
    page = gui._current_model_stack.currentWidget()
    assert page.findChild(QLabel) is not None
    assert page.findChild(QDoubleSpinBox) is None


def test_prepare_simulation_linear_uses_linear_profile(mvc):
    """prepare_simulation com modelo 'Linear' instancia torpedo com LinearProfile."""
    from python_vehicle_simulator.lib.environment import LinearProfile
    ctrl, gui, app = mvc
    gui._current_model_combo.setCurrentText('Linear')
    app.processEvents()
    vehicles = []
    ctrl.simulation_ready.connect(lambda v: vehicles.append(v))
    ctrl.prepare_simulation('depthHeadingAutopilot', 30.0, 50.0)
    app.processEvents()
    assert vehicles, "simulation_ready não foi emitido"
    assert isinstance(vehicles[-1].current_model, LinearProfile)


def test_v_c_and_beta_c_deg_widgets_exist(mvc):
    """Widgets V_c e beta_c_deg estão em param_widgets com valores válidos."""
    _, gui, _ = mvc
    assert 'V_c' in gui.param_widgets
    assert 'beta_c_deg' in gui.param_widgets
    assert gui.param_widgets['V_c'].value() >= 0.0
    assert -180.0 <= gui.param_widgets['beta_c_deg'].value() <= 180.0


# ---------------------------------------------------------------------------
# Etapa 4+ — Start/Stop, comparações personalizáveis, gráficos analíticos
# ---------------------------------------------------------------------------

def test_simulate_supports_cancellation():
    """mainLoop.simulate() respeita is_cancelled e devolve dados parciais."""
    from python_vehicle_simulator.lib.mainLoop import simulate
    from python_vehicle_simulator.vehicles.torpedo import torpedo as torp

    veh = torp("stepInput")
    counter = {'n': 0}
    def cancel_after_5():
        counter['n'] += 1
        return counter['n'] > 5
    simTime, simData = simulate(N=1000, sampleTime=0.05, vehicle=veh,
                                is_cancelled=cancel_after_5)
    # 5 iterações antes de o flag ser True ⇒ 5 linhas de simData
    assert simData.shape[0] == 5
    assert simTime.shape == (5, 1)


def test_stop_button_enabled_only_during_simulation(mvc):
    """Antes de qualquer sim, _btn_stop está desactivado."""
    _, gui, _ = mvc
    assert hasattr(gui, '_btn_stop')
    assert gui._btn_stop.text() == 'Parar'
    assert not gui._btn_stop.isEnabled()


def test_stop_button_resets_buttons_when_clicked(mvc):
    """Clicar Parar repõe estado dos botões e limpa flags A/B e compare."""
    ctrl, gui, app = mvc
    # Simular estado de A/B em curso
    gui._ab_mode = "A"
    gui._btn_simulate.setEnabled(False)
    gui._btn_stop.setEnabled(True)
    gui._btn_simulate_ab.setEnabled(False)
    gui._on_stop_clicked()
    app.processEvents()
    assert gui._ab_mode is None
    assert gui._btn_simulate.isEnabled()
    assert not gui._btn_stop.isEnabled()
    assert gui._btn_simulate_ab.isEnabled()


def test_compare_buttons_exist_and_wired(mvc):
    """Etapa 4+ — botões 'Comparar Sem/Com Corrente' e 'Comparar 2 Cenários' existem."""
    _, gui, _ = mvc
    assert hasattr(gui, '_btn_compare_currents')
    assert hasattr(gui, '_btn_compare_custom')
    assert gui._btn_compare_currents.text() == 'Comparar Sem/Com Corrente'
    assert 'Comparar' in gui._btn_compare_custom.text()


def test_make_no_vs_with_current_cfgs_shape():
    """Controller devolve 2 cfgs distintas: sem e com corrente."""
    from python_vehicle_simulator.gui.torpedo_controller import TorpedoController
    ctrl = TorpedoController()
    cfg_a, cfg_b = ctrl.make_no_vs_with_current_cfgs()
    assert cfg_a['V_c'] == 0.0
    assert cfg_b['V_c'] == 0.5
    assert cfg_a['label'] == 'Sem corrente'
    assert 'Com corrente' in cfg_b['label']


def test_build_compare_instance_returns_torpedo(mvc):
    """build_compare_instance constrói uma instância torpedo configurada."""
    from python_vehicle_simulator.vehicles.torpedo import torpedo as torp
    ctrl, _, _ = mvc
    cfg = {'label': 'X', 'control_mode': 'depthHeadingAutopilot',
           'ref_z': 25.0, 'ref_psi': 30.0, 'V_c': 0.3, 'beta_c_deg': 10.0}
    veh = ctrl.build_compare_instance(cfg)
    assert isinstance(veh, torp)
    assert abs(veh.ref_z - 25.0) < 1e-9
    assert abs(veh.V_c - 0.3) < 1e-9


def test_no_vs_with_current_button_creates_two_sims(ab_mvc, tmp_path,
                                                    monkeypatch):
    """Clicar 'Comparar Sem/Com Corrente' produz 2 entradas no _sim_store."""
    ctrl, gui, app, _fake = ab_mvc
    monkeypatch.setattr(ctrl, '_DEFAULT_COMPARE_DIR', tmp_path)
    n_before = len(ctrl.get_store())
    received: list = []
    ctrl.comparison_ready.connect(
        lambda a, b: received.append((a['label'], b['label'])))
    gui._launch_no_vs_with_current()
    app.processEvents()
    n_after = len(ctrl.get_store())
    assert n_after == n_before + 2
    assert len(received) == 1
    assert received[0] == ('Sem corrente', 'Com corrente V_c=0.5')


def test_compare_writes_two_csvs(ab_mvc, tmp_path, monkeypatch):
    """register_comparison_results escreve 2 CSVs num directório dado."""
    ctrl, gui, app, _fake = ab_mvc
    monkeypatch.setattr(ctrl, '_DEFAULT_COMPARE_DIR', tmp_path)
    gui._launch_no_vs_with_current()
    app.processEvents()
    csvs = sorted(tmp_path.glob('comparacao_*_*.csv'))
    assert len(csvs) == 2
    # cada CSV tem header com '# label = ...' (params snapshot)
    for csv_path in csvs:
        content = csv_path.read_text(encoding='utf-8').splitlines()
        assert any(line.startswith('#') for line in content)
        assert any(line.startswith('t_s,') for line in content)


def test_compare_dialog_returns_two_cfgs(mvc):
    """CompareScenariosDialog produz 2 dicts com chaves esperadas."""
    from python_vehicle_simulator.gui.torpedo_gui import CompareScenariosDialog
    _, gui, _ = mvc
    view = gui._controller.get_view_state()
    dlg = CompareScenariosDialog(view, parent=gui)
    cfg_a, cfg_b = dlg.get_cfgs()
    for cfg in (cfg_a, cfg_b):
        assert {'label', 'control_mode', 'ref_z', 'ref_psi',
                'V_c', 'beta_c_deg', 'current_model', 'overrides'} <= set(cfg)
    dlg.close()


def test_drag_curve_widget_reacts_to_Cd_change(mvc):
    """DragCurveWidget tem update_plot ligada a params_updated; a curva muda
    quando Cd muda (verificado pela primeira linha do plot)."""
    ctrl, gui, app = mvc
    ax_before = gui._drag_curve_widget._fig.axes
    line_before = ax_before[0].lines[0].get_ydata().copy() if ax_before else None
    ctrl.update_param('Cd', 0.30)
    app.processEvents()
    ax_after = gui._drag_curve_widget._fig.axes
    line_after = ax_after[0].lines[0].get_ydata()
    assert line_before is not None
    # Cd diminuiu ⇒ força de arrasto diminuiu para mesmo U
    import numpy as np
    assert np.max(line_after) < np.max(line_before)


def test_control_response_widget_reacts_to_wn_change(mvc):
    """ControlResponseWidget repinta quando wn_d_z muda — a curva é diferente."""
    ctrl, gui, app = mvc
    line_before = gui._control_response_widget._fig.axes[0].lines[0]\
        .get_ydata().copy()
    ctrl.update_param('wn_d_z', 1.5)
    app.processEvents()
    line_after = gui._control_response_widget._fig.axes[0].lines[0].get_ydata()
    import numpy as np
    # Frequência maior ⇒ subida mais rápida ⇒ diferença significativa entre curvas
    assert np.max(np.abs(line_after - line_before)) > 0.05


def test_analise_tab_present_with_two_widgets(mvc):
    """Tab 'Análise' existe e contém DragCurveWidget e ControlResponseWidget."""
    from python_vehicle_simulator.gui.torpedo_viz import (
        DragCurveWidget, ControlResponseWidget)
    _, gui, _ = mvc
    right = gui._right_panel
    idx = next(i for i in range(right.count())
               if right.tabText(i) == 'Análise')
    page = right.widget(idx)
    assert page.findChild(DragCurveWidget) is not None
    assert page.findChild(ControlResponseWidget) is not None


# ──────────────────────────────────────────────────────────────────────────────
# Etapa 4+ Fase B — Live preview (simulação curta com debounce)
# ──────────────────────────────────────────────────────────────────────────────

def test_live_preview_widget_in_analise_tab(mvc):
    """LivePreviewWidget e checkbox de live preview existem na tab Análise."""
    from python_vehicle_simulator.gui.torpedo_viz import LivePreviewWidget
    _, gui, _ = mvc
    right = gui._right_panel
    idx = next(i for i in range(right.count())
               if right.tabText(i) == 'Análise')
    page = right.widget(idx)
    assert page.findChild(LivePreviewWidget) is not None
    assert hasattr(gui, '_chk_live_preview')
    assert gui._chk_live_preview.isChecked() is False
    assert gui._preview_enabled is False


def test_live_preview_toggle_off_cancels_running_preview(mvc):
    """Desactivar a checkbox cancela qualquer preview em curso e limpa estado."""
    from unittest.mock import MagicMock
    _, gui, _ = mvc
    gui._chk_live_preview.setChecked(True)
    assert gui._preview_enabled is True
    fake = MagicMock()
    fake.isRunning.return_value = True
    gui._preview_thread = fake
    gui._chk_live_preview.setChecked(False)
    assert gui._preview_enabled is False
    assert fake.cancel.called
    assert gui._preview_thread is None


def test_preview_cancelled_when_params_change_during_run(mvc):
    """Quando params mudam com preview a correr, a actual é cancelada e o
    debounce timer é reiniciado para arrancar uma nova com o estado fresco."""
    from unittest.mock import MagicMock
    _, gui, _ = mvc
    gui._preview_enabled = True
    fake_thread = MagicMock()
    fake_thread.isRunning.return_value = True
    gui._preview_thread = fake_thread
    gui._on_params_changed_for_preview({'Cd': 0.30})
    assert fake_thread.cancel.called
    assert gui._preview_timer.isActive()


def test_on_preview_done_delegates_to_widget(mvc):
    """_on_preview_done chama LivePreviewWidget.update_from(simTime, simData)."""
    from unittest.mock import MagicMock
    import numpy as np
    _, gui, _ = mvc
    spy = MagicMock()
    gui._live_preview_widget.update_from = spy
    simTime = np.linspace(0, 1, 5).reshape(-1, 1)
    simData = np.zeros((5, 24))
    gui._on_preview_done(simTime, simData)
    spy.assert_called_once()


def test_params_change_with_preview_disabled_does_not_start_timer(mvc):
    """Sem preview activa, alterações de params não devem despoletar o timer."""
    ctrl, gui, app = mvc
    gui._preview_enabled = False
    gui._preview_timer.stop()
    ctrl.update_param('Cd', 0.31)
    app.processEvents()
    assert gui._preview_timer.isActive() is False
