"""
test_etapa3_widget.py — Unit tests for Etapa3GraphsWidget.

Headless tests (QT_QPA_PLATFORM=offscreen) that exercise the new
"Gráficos Etapa 3" widget added in `torpedo_viz.py`.

Author: Ricardo Craveiro (1191000@isep.ipp.pt)
DINAV 2026 — Etapa 3
"""

import os
import sys

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qt_app():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture(scope="module")
def sim_result():
    """Run one short torpedo simulation for all tests in this module."""
    from python_vehicle_simulator.vehicles.torpedo import torpedo
    from python_vehicle_simulator.lib.mainLoop import simulate

    vehicle = torpedo("stepInput")
    N = 200
    sampleTime = 0.05
    simTime, simData = simulate(N, sampleTime, vehicle)
    return simTime, simData


@pytest.fixture()
def widget(qt_app):
    """Fresh Etapa3GraphsWidget for each test."""
    from python_vehicle_simulator.gui.torpedo_viz import Etapa3GraphsWidget
    w = Etapa3GraphsWidget()
    yield w
    w.deleteLater()


# ---------------------------------------------------------------------------
# 1 — Placeholder before any simulation
# ---------------------------------------------------------------------------

def test_etapa3_widget_initial_placeholder(widget):
    """Antes de chamar plot_etapa3() o info-label deve mostrar placeholder."""
    assert "Aguarda" in widget._info.text()


# ---------------------------------------------------------------------------
# 2 — plot_etapa3 creates the expected number of axes
# ---------------------------------------------------------------------------

def test_etapa3_widget_plot_creates_axes(widget, sim_result):
    """plot_etapa3() deve criar 5 subplots + 1 twin axis = 6 axes."""
    simTime, simData = sim_result
    widget.plot_etapa3(simTime, simData, dimU=5)
    assert len(widget._fig.axes) == 6, (
        f"Expected 6 axes (5 subplots + RPM twin), got {len(widget._fig.axes)}")


# ---------------------------------------------------------------------------
# 3 — Depth subplot has inverted y-axis
# ---------------------------------------------------------------------------

def test_etapa3_widget_depth_axis_inverted(widget, sim_result):
    """O subplot de profundidade deve ter o eixo y invertido (z↓)."""
    simTime, simData = sim_result
    widget.plot_etapa3(simTime, simData, dimU=5)

    # O subplot da profundidade tem ylabel a começar com "Profundidade"
    depth_axes = [ax for ax in widget._fig.axes
                  if ax.get_ylabel().startswith("Profundidade")]
    assert depth_axes, "Subplot de profundidade não encontrado"
    ax = depth_axes[0]
    y_lo, y_hi = ax.get_ylim()
    assert y_lo > y_hi, (
        f"Eixo y de profundidade não está invertido: ylim=({y_lo}, {y_hi})")


# ---------------------------------------------------------------------------
# 4 — Trajectory subplot has equal aspect
# ---------------------------------------------------------------------------

def test_etapa3_widget_trajectory_aspect_equal(widget, sim_result):
    """O subplot de trajectória deve ter aspecto 'equal' para preservar escala."""
    simTime, simData = sim_result
    widget.plot_etapa3(simTime, simData, dimU=5)

    traj_axes = [ax for ax in widget._fig.axes
                 if ax.get_title() == "Trajectória 2D"]
    assert traj_axes, "Subplot de trajectória não encontrado"
    aspect = traj_axes[0].get_aspect()
    # Matplotlib devolve 1.0 (float) ou 'equal' (string) consoante a versão
    assert aspect == 1.0 or aspect == 'equal', (
        f"Aspecto da trajectória deveria ser igual, não {aspect!r}")


# ---------------------------------------------------------------------------
# 5 — Actuator subplot has a twin axis for RPM
# ---------------------------------------------------------------------------

def test_etapa3_widget_actuator_has_twin_axis(widget, sim_result):
    """O subplot dos actuadores deve ter um twin axis para o RPM."""
    simTime, simData = sim_result
    widget.plot_etapa3(simTime, simData, dimU=5)

    # Procurar o eixo das deflexões e o twin (RPM)
    fin_axes = [ax for ax in widget._fig.axes
                if ax.get_title() == "Comandos dos actuadores"]
    rpm_axes = [ax for ax in widget._fig.axes
                if ax.get_ylabel().startswith("Rotação")]

    assert fin_axes, "Subplot dos actuadores não encontrado"
    assert rpm_axes, "Twin axis para RPM não encontrado"
    # Os dois axes devem partilhar a mesma posição (twin axis)
    bbox_fin = fin_axes[0].get_position()
    bbox_rpm = rpm_axes[0].get_position()
    assert abs(bbox_fin.x0 - bbox_rpm.x0) < 1e-6
    assert abs(bbox_fin.y0 - bbox_rpm.y0) < 1e-6


# ---------------------------------------------------------------------------
# 6 — Re-plot replaces axes (does not accumulate)
# ---------------------------------------------------------------------------

def test_etapa3_widget_replot_replaces_axes(widget, sim_result):
    """Chamar plot_etapa3() múltiplas vezes não acumula axes."""
    simTime, simData = sim_result
    widget.plot_etapa3(simTime, simData, dimU=5)
    n_after_first = len(widget._fig.axes)
    widget.plot_etapa3(simTime, simData, dimU=5)
    widget.plot_etapa3(simTime, simData, dimU=5)
    n_after_third = len(widget._fig.axes)
    assert n_after_first == n_after_third == 6, (
        f"Axes acumularam: {n_after_first} → {n_after_third}")


# ---------------------------------------------------------------------------
# 7 — Info label updates with sample count and duration
# ---------------------------------------------------------------------------

def test_etapa3_widget_info_label_updates(widget, sim_result):
    """O info-label deve mostrar nº de amostras e duração após plot."""
    simTime, simData = sim_result
    widget.plot_etapa3(simTime, simData, dimU=5)
    text = widget._info.text()
    assert str(len(simTime)) in text, (
        f"Nº de amostras ({len(simTime)}) ausente do label: {text!r}")
    assert "duração" in text.lower() or "duracao" in text.lower(), (
        f"Palavra 'duração' ausente do label: {text!r}")


# ---------------------------------------------------------------------------
# 8 — Plotted data matches simData (sampling check)
# ---------------------------------------------------------------------------

def test_etapa3_widget_data_correctness(widget, sim_result):
    """Os dados desenhados na trajectória batem com simData (amostragem)."""
    simTime, simData = sim_result
    widget.plot_etapa3(simTime, simData, dimU=5)

    traj_axes = [ax for ax in widget._fig.axes
                 if ax.get_title() == "Trajectória 2D"]
    ax = traj_axes[0]
    # A primeira linha do plot é a trajectória completa (este vs norte)
    line = ax.lines[0]
    x_data = line.get_xdata()   # este = simData[:, 1]
    y_data = line.get_ydata()   # norte = simData[:, 0]
    np.testing.assert_allclose(x_data, simData[:, 1], atol=1e-9)
    np.testing.assert_allclose(y_data, simData[:, 0], atol=1e-9)


# ---------------------------------------------------------------------------
# 9 — Angular velocities are converted from rad/s to deg/s
# ---------------------------------------------------------------------------

def test_etapa3_widget_angular_velocities_in_degrees(widget, sim_result):
    """Velocidades angulares plotadas em °/s, não em rad/s."""
    simTime, simData = sim_result
    widget.plot_etapa3(simTime, simData, dimU=5)

    ang_axes = [ax for ax in widget._fig.axes
                if ax.get_title() == "Velocidades angulares"]
    assert ang_axes, "Subplot de velocidades angulares não encontrado"
    ax = ang_axes[0]
    # Linha 0 → p (rad/s na simData[:, 9], plotada em °/s)
    line_p = ax.lines[0]
    expected_p_deg = np.rad2deg(simData[:, 9])
    np.testing.assert_allclose(line_p.get_ydata(), expected_p_deg, atol=1e-9)
    # ylabel deve indicar "°/s"
    assert "°" in ax.get_ylabel(), (
        f"ylabel não indica graus: {ax.get_ylabel()!r}")


# ---------------------------------------------------------------------------
# 10 — Handles short simulations (N=2)
# ---------------------------------------------------------------------------

def test_etapa3_widget_handles_short_simulation(widget):
    """plot_etapa3() funciona com simulação muito curta (N=2)."""
    simTime = np.array([[0.0], [0.05]])
    simData = np.zeros((2, 22))
    simData[1, 0] = 0.1   # x_north avança 0.1 m
    simData[1, 6] = 2.0   # u final
    # Não deve lançar excepção
    widget.plot_etapa3(simTime, simData, dimU=5)
    assert len(widget._fig.axes) == 6
