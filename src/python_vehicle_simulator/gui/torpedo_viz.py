"""
torpedo_viz.py — 3D visualisation and state plots for the Torpedo AUV GUI.

Provides:
  SimulationThread    — runs mainLoop.simulate() in a QThread (non-blocking)
  TorpedoVizWidget    — embedded 3D animation; camera follows the torpedo
  TorpedoStatesWidget — embedded static 3×3 state time-series subplots

Dependências: PyQt6, matplotlib (já incluídos em requirements_gui.txt).
Sem novas dependências externas.

Referência: T. I. Fossen, Handbook of Marine Craft Hydrodynamics and Motion
            Control, 2ª ed., Wiley, 2021.
Autor das adições: Ricardo Craveiro (1191000@isep.ipp.pt) — DINAV 2026 Etapa 2
"""

import math

import numpy as np

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from matplotlib import animation
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


# ---------------------------------------------------------------------------
# SimulationThread
# ---------------------------------------------------------------------------

class SimulationThread(QThread):
    """
    Executa mainLoop.simulate() numa thread separada para não bloquear a GUI.

    Sinais
    ------
    finished(simTime, simData) — emitido quando a simulação termina com sucesso
    error(mensagem)            — emitido se ocorrer uma excepção
    """

    finished = pyqtSignal(object, object)
    error    = pyqtSignal(str)

    def __init__(self, vehicle, N: int, sampleTime: float, parent=None):
        super().__init__(parent)
        self._vehicle    = vehicle
        self._N          = N
        self._sampleTime = sampleTime

    def run(self):
        try:
            from python_vehicle_simulator.lib.mainLoop import simulate
            simTime, simData = simulate(self._N, self._sampleTime, self._vehicle)
            self.finished.emit(simTime, simData)
        except Exception as exc:                       # noqa: BLE001
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Geometria do torpedo (frame do corpo → frame NED)
# ---------------------------------------------------------------------------

def _rot_matrix(phi: float, theta: float, psi: float) -> np.ndarray:
    """
    Matriz de rotação ZYX (convenção Fossen): corpo → NED.
    R tal que p_ned = R @ p_body.
    """
    cp, sp = math.cos(phi),   math.sin(phi)
    ct, st = math.cos(theta), math.sin(theta)
    cy, sy = math.cos(psi),   math.sin(psi)
    Rz = np.array([[cy, -sy, 0.0], [sy,  cy, 0.0], [0.0, 0.0, 1.0]])
    Ry = np.array([[ct,  0.0, st], [0.0, 1.0, 0.0], [-st, 0.0, ct]])
    Rx = np.array([[1.0, 0.0,  0.0], [0.0, cp, -sp], [0.0, sp,  cp]])
    return Rz @ Ry @ Rx


def _ellipse_ring(a: float, b: float, x_body: float, n: int = 24) -> np.ndarray:
    """
    Anel de secção elíptica do elipsóide no ponto x_body (frame do corpo).
    Devolve array (3, n+1).
    """
    r = b * math.sqrt(max(0.0, 1.0 - (x_body / a) ** 2))
    th = np.linspace(0.0, 2.0 * math.pi, n + 1)
    return np.vstack([np.full(n + 1, x_body), r * np.cos(th), r * np.sin(th)])


def _build_body_geometry(L: float, diam: float, n_rings: int = 10,
                         n_pts: int = 24) -> list:
    """Secções transversais do corpo (elipsóide) no frame do corpo."""
    a = L / 2
    xs = np.linspace(-a * 0.97, a * 0.97, n_rings)
    return [_ellipse_ring(a, diam / 2, x, n_pts) for x in xs]


def _build_fin_geometry(L: float, diam: float) -> list:
    """
    Quatro barbatanas (rectângulos fechados) no frame do corpo.
    Ordem: topo (-z_b), fundo (+z_b), estibordo (+y_b), bombordo (-y_b).
    """
    a      = L / 2
    b      = diam / 2
    fin_h  = b * 2.8       # envergadura (span)
    fin_c  = a * 0.40      # corda (chord)
    x0     = -a            # raiz da barbatana (cauda)
    x1     = x0 + fin_c    # bordo de fuga

    def _rect(y0, y1, z0, z1):
        pts = np.array([[x0, x1, x1, x0, x0],
                        [y0, y0, y1, y1, y0],
                        [z0, z0, z1, z1, z0]], dtype=float)
        return pts

    return [
        _rect(0.0, 0.0, -b,           -(b + fin_h)),   # topo
        _rect(0.0, 0.0,  b,             b + fin_h),    # fundo
        _rect( b,  b + fin_h, 0.0,  0.0),              # estibordo
        _rect(-b, -(b + fin_h), 0.0, 0.0),             # bombordo
    ]


def _transform(pts: np.ndarray, R: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """Transforma pontos (3, N) do frame do corpo para o frame NED."""
    return R @ pts + pos[:, None]


# ---------------------------------------------------------------------------
# TorpedoVizWidget
# ---------------------------------------------------------------------------

class TorpedoVizWidget(QWidget):
    """
    Visualização 3D animada do torpedo.

    A câmara segue o torpedo: os limites dos eixos são centrados na posição
    actual em cada frame. Chame run_animation() após a simulação terminar.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._fig    = Figure(figsize=(5, 4), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._ax     = self._fig.add_subplot(111, projection='3d')
        self._ani    = None   # manter referência — evita garbage collection

        self._status = QLabel("Aguarda simulação…")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("font-size: 10px; color: #555;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._canvas, stretch=1)
        layout.addWidget(self._status)

        self._ax.text2D(0.5, 0.5, "Aguarda simulação…",
                        ha='center', va='center',
                        transform=self._ax.transAxes,
                        fontsize=11, color='#aaa')
        self._canvas.draw()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_animation(self, simTime: np.ndarray, simData: np.ndarray,
                      L: float, diam: float) -> None:
        """
        Constrói e inicia a animação FuncAnimation a partir dos resultados
        da simulação.

        Parâmetros
        ----------
        simTime : (N, 1) array  — vector de tempo
        simData : (N, ≥12) array — colunas 0:6 = eta, 6:12 = nu
        L, diam : float          — dimensões do torpedo (para geometria)
        """
        if self._ani is not None:
            self._ani.event_source.stop()
            self._ani = None

        N_full = len(simData)
        if N_full < 2:
            return

        # Amostragem reduzida (máx. 200 frames)
        stride = max(1, N_full // 200)
        idx    = np.arange(0, N_full, stride)

        t   = simTime[idx, 0]
        x   = simData[idx, 0]
        y   = simData[idx, 1]
        z   = simData[idx, 2]
        phi = simData[idx, 3]
        th  = simData[idx, 4]
        psi = simData[idx, 5]
        u   = simData[idx, 6]   # velocidade de avanço

        N_frames = len(idx)
        view_r   = max(5.0, L * 4.0)
        a_half   = L / 2.0

        body_rings = _build_body_geometry(L, diam)
        fins       = _build_fin_geometry(L, diam)
        nose_b     = np.array([[a_half], [0.0], [0.0]])

        fin_colors = ['#e67e22', '#e67e22', '#27ae60', '#27ae60']

        def _update(fi: int):
            ax = self._ax
            ax.cla()

            # Trajectória completa (esbatida)
            ax.plot(x, y, z, 'b-', alpha=0.12, lw=0.7, zorder=1)
            # Trajectória percorrida até ao frame actual
            ax.plot(x[:fi + 1], y[:fi + 1], z[:fi + 1],
                    'b-', alpha=0.55, lw=1.8, zorder=2)

            pos = np.array([x[fi], y[fi], z[fi]])
            R   = _rot_matrix(phi[fi], th[fi], psi[fi])

            # Corpo (secções elípticas)
            for ring in body_rings:
                pw = _transform(ring, R, pos)
                ax.plot3D(pw[0], pw[1], pw[2], color='#2e86c1',
                          lw=0.9, alpha=0.75, zorder=3)

            # Barbatanas
            for fin_pts, fc in zip(fins, fin_colors):
                pw = _transform(fin_pts, R, pos)
                ax.plot3D(pw[0], pw[1], pw[2], color=fc,
                          lw=1.6, alpha=0.9, zorder=4)

            # Nariz
            nose_w = _transform(nose_b, R, pos)
            ax.scatter(nose_w[0], nose_w[1], nose_w[2],
                       color='#e74c3c', s=28, zorder=6)

            # Marcador de posição
            ax.scatter([x[fi]], [y[fi]], [z[fi]],
                       color='#1a252f', s=16, zorder=5)

            # Câmara segue o torpedo
            ax.set_xlim(x[fi] - view_r, x[fi] + view_r)
            ax.set_ylim(y[fi] - view_r, y[fi] + view_r)
            ax.set_zlim(z[fi] + view_r, z[fi] - view_r)  # z invertido (prof. ↓)

            ax.set_xlabel("Norte (m)", fontsize=7, labelpad=1)
            ax.set_ylabel("Este (m)",  fontsize=7, labelpad=1)
            ax.set_zlabel("Prof. (m)", fontsize=7, labelpad=1)
            ax.tick_params(labelsize=6)
            ax.set_title(
                f"t = {t[fi]:.1f} s  |  ψ = {math.degrees(psi[fi]):.1f}°"
                f"  |  z = {z[fi]:.1f} m  |  u = {u[fi]:.2f} m/s",
                fontsize=8, pad=3,
            )

            self._status.setText(
                f"Frame {fi + 1}/{N_frames}   "
                f"(x={x[fi]:.1f}, y={y[fi]:.1f}, z={z[fi]:.1f}) m   "
                f"ψ = {math.degrees(psi[fi]):.1f}°"
            )
            return []

        self._ani = animation.FuncAnimation(
            self._fig,
            _update,
            frames=N_frames,
            interval=80,
            blit=False,
            repeat=True,
        )
        self._canvas.draw()


# ---------------------------------------------------------------------------
# TorpedoStatesWidget
# ---------------------------------------------------------------------------

class TorpedoStatesWidget(QWidget):
    """
    Gráficos estáticos (toda a simulação) em grelha 3×3:
      Linha 1 — Posições  (Norte, Este, Profundidade)
      Linha 2 — Atitudes  (Rolamento φ, Arfagem θ, Guinada ψ)
      Linha 3 — Velocidades lineares (Avanço u, Deriva v, Afundamento w)

    Chame plot_states() após a simulação terminar.
    """

    # Paleta de cores por linha
    _COLORS = [
        ['#1f77b4', '#ff7f0e', '#2ca02c'],   # posições
        ['#9467bd', '#8c564b', '#e377c2'],   # atitudes
        ['#d62728', '#17becf', '#bcbd22'],   # velocidades
    ]

    # Especificações dos subplots: (coluna simData, título, ylabel, graus?)
    _SPECS = [
        [(0, "Norte",        "x (m)",   False),
         (1, "Este",         "y (m)",   False),
         (2, "Profundidade", "z (m)",   False)],
        [(3, "Rolamento φ",  "φ (°)",   True),
         (4, "Arfagem θ",    "θ (°)",   True),
         (5, "Guinada ψ",    "ψ (°)",   True)],
        [(6, "Avanço u",     "u (m/s)", False),
         (7, "Deriva v",     "v (m/s)", False),
         (8, "Afundamento w","w (m/s)", False)],
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self._fig    = Figure(figsize=(7, 6), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)

        # Placeholder: eixos visíveis só após plot_states()
        axs = self._fig.subplots(3, 3)
        for ax in axs.flat:
            ax.set_visible(False)

        # Envolve o canvas num QScrollArea para janelas estreitas
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._canvas)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plot_states(self, simTime: np.ndarray, simData: np.ndarray) -> None:
        """
        Renderiza 9 gráficos estáticos com toda a simulação.

        Parâmetros
        ----------
        simTime : (N, 1) array   — vector de tempo (s)
        simData : (N, ≥9) array  — colunas 0:6 eta + 6:12 nu
        """
        t = simTime[:, 0]

        self._fig.clear()
        axs = self._fig.subplots(3, 3)

        for r, row in enumerate(self._SPECS):
            for c, (col, title, ylabel, to_deg) in enumerate(row):
                ax  = axs[r][c]
                sig = simData[:, col]
                if to_deg:
                    sig = np.degrees(sig)

                ax.plot(t, sig, color=self._COLORS[r][c], lw=1.3)
                ax.set_title(title, fontsize=8, pad=3)
                ax.set_ylabel(ylabel, fontsize=7)
                ax.set_xlabel("t (s)", fontsize=7)
                ax.tick_params(labelsize=6)
                ax.grid(True, alpha=0.3, lw=0.5)

        self._fig.tight_layout(pad=1.2)
        self._canvas.draw()
