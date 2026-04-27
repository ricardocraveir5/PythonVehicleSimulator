"""
torpedo_viz.py — 3D visualisation and state plots for the Torpedo AUV GUI.

Provides:
  SimulationThread       — runs mainLoop.simulate() in a QThread (non-blocking)
  TorpedoVizWidget       — embedded 3D animation; camera follows the torpedo
  TorpedoStatesWidget    — embedded static 3×3 state time-series subplots
  Etapa3GraphsWidget     — gráficos Etapa 3 (trajectória, profundidade,
                           velocidades, actuadores) para a simulação actual
  TorpedoControlsWidget  — control command vs. actual time-series (Etapa 3)
  ComparativeWidget      — overlay two simulation runs for comparison (Etapa 3)

Etapa 4 — As classes deste módulo refletem automaticamente o CurrentModel
activo: a alteração à física em torpedo.dynamics() (ver torpedo.py) propaga-se
para a animação 3D e os gráficos de estado sem qualquer alteração de código
neste ficheiro.

Dependências: PyQt6, matplotlib (já incluídos em requirements_gui.txt).
Sem novas dependências externas.

Referência: T. I. Fossen, Handbook of Marine Craft Hydrodynamics and Motion
            Control, 2ª ed., Wiley, 2021.
Autor das adições: Ricardo Craveiro (1191000@isep.ipp.pt) — DINAV 2026 Etapa 2/3
"""

import math

import numpy as np

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from matplotlib import animation
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec


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
        self._ani    = None   # manter referência — evita garbage collection

        ax = self._fig.add_subplot(111, projection='3d')

        self._status = QLabel("Aguarda simulação…")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("font-size: 10px; color: #555;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._canvas, stretch=1)
        layout.addWidget(self._status)

        ax.text2D(0.5, 0.5, "Aguarda simulação…",
                  ha='center', va='center',
                  transform=ax.transAxes,
                  fontsize=11, color='#aaa')
        self._canvas.draw()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reset_figure(self, n_cols: int) -> list:
        """Clear the Figure and rebuild it with ``n_cols`` side-by-side 3D axes."""
        if self._ani is not None:
            self._ani.event_source.stop()
            self._ani = None
        self._fig.clear()
        gs = GridSpec(1, n_cols, figure=self._fig)
        return [self._fig.add_subplot(gs[0, i], projection='3d')
                for i in range(n_cols)]

    def _draw_torpedo(self, ax, body_rings, fins, nose_b, fin_colors,
                      pos, R, traj_x, traj_y, traj_z, fi, view_r,
                      traj_color: str = 'b') -> None:
        """Render one torpedo (body + fins + trajectory) in ``ax`` at frame ``fi``."""
        ax.cla()
        ax.plot(traj_x, traj_y, traj_z, color=traj_color,
                alpha=0.12, lw=0.7, zorder=1)
        ax.plot(traj_x[:fi + 1], traj_y[:fi + 1], traj_z[:fi + 1],
                color=traj_color, alpha=0.55, lw=1.8, zorder=2)

        for ring in body_rings:
            pw = _transform(ring, R, pos)
            ax.plot3D(pw[0], pw[1], pw[2], color='#2e86c1',
                      lw=0.9, alpha=0.75, zorder=3)
        for fin_pts, fc in zip(fins, fin_colors):
            pw = _transform(fin_pts, R, pos)
            ax.plot3D(pw[0], pw[1], pw[2], color=fc,
                      lw=1.6, alpha=0.9, zorder=4)
        nose_w = _transform(nose_b, R, pos)
        ax.scatter(nose_w[0], nose_w[1], nose_w[2],
                   color='#e74c3c', s=28, zorder=6)
        ax.scatter([pos[0]], [pos[1]], [pos[2]],
                   color='#1a252f', s=16, zorder=5)

        ax.set_xlim(pos[0] - view_r, pos[0] + view_r)
        ax.set_ylim(pos[1] - view_r, pos[1] + view_r)
        ax.set_zlim(pos[2] + view_r, pos[2] - view_r)  # z invertido (prof. ↓)
        ax.set_xlabel("Norte (m)", fontsize=7, labelpad=1)
        ax.set_ylabel("Este (m)",  fontsize=7, labelpad=1)
        ax.set_zlabel("Prof. (m)", fontsize=7, labelpad=1)
        ax.tick_params(labelsize=6)

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
        N_full = len(simData)
        if N_full < 2:
            return

        ax = self._reset_figure(1)[0]

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
            pos = np.array([x[fi], y[fi], z[fi]])
            R   = _rot_matrix(phi[fi], th[fi], psi[fi])
            self._draw_torpedo(ax, body_rings, fins, nose_b, fin_colors,
                               pos, R, x, y, z, fi, view_r, traj_color='b')
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

    def run_dual_animation(self,
                           simTime_A: np.ndarray, simData_A: np.ndarray,
                           simTime_B: np.ndarray, simData_B: np.ndarray,
                           L: float, diam: float,
                           label_A: str = "Simulação A",
                           label_B: str = "Simulação B") -> None:
        """
        Anima dois torpedos lado a lado (A | B), sincronizados no tempo.

        Usado pelo botão "Simular A e B (Etapa 3)". Cada subplot tem a sua
        própria câmara a seguir o respectivo veículo.
        """
        N_A = len(simData_A)
        N_B = len(simData_B)
        if N_A < 2 or N_B < 2:
            return

        ax_A, ax_B = self._reset_figure(2)
        ax_A.set_title(label_A, fontsize=9, pad=4)
        ax_B.set_title(label_B, fontsize=9, pad=4)

        def _sub(simTime, simData):
            stride = max(1, len(simData) // 200)
            idx = np.arange(0, len(simData), stride)
            return {
                't':   simTime[idx, 0],
                'x':   simData[idx, 0],
                'y':   simData[idx, 1],
                'z':   simData[idx, 2],
                'phi': simData[idx, 3],
                'th':  simData[idx, 4],
                'psi': simData[idx, 5],
                'u':   simData[idx, 6],
            }

        A = _sub(simTime_A, simData_A)
        B = _sub(simTime_B, simData_B)
        N_frames = min(len(A['t']), len(B['t']))

        view_r     = max(5.0, L * 4.0)
        a_half     = L / 2.0
        body_rings = _build_body_geometry(L, diam)
        fins       = _build_fin_geometry(L, diam)
        nose_b     = np.array([[a_half], [0.0], [0.0]])
        fin_colors = ['#e67e22', '#e67e22', '#27ae60', '#27ae60']

        def _draw_side(ax, D, fi, traj_color):
            pos = np.array([D['x'][fi], D['y'][fi], D['z'][fi]])
            R   = _rot_matrix(D['phi'][fi], D['th'][fi], D['psi'][fi])
            self._draw_torpedo(ax, body_rings, fins, nose_b, fin_colors,
                               pos, R, D['x'], D['y'], D['z'], fi, view_r,
                               traj_color=traj_color)

        def _update_dual(fi: int):
            _draw_side(ax_A, A, fi, 'C0')
            _draw_side(ax_B, B, fi, 'C1')
            ax_A.set_title(
                f"{label_A}\nt = {A['t'][fi]:.1f} s  |  "
                f"z = {A['z'][fi]:.1f} m  |  u = {A['u'][fi]:.2f} m/s",
                fontsize=8, pad=3,
            )
            ax_B.set_title(
                f"{label_B}\nt = {B['t'][fi]:.1f} s  |  "
                f"z = {B['z'][fi]:.1f} m  |  u = {B['u'][fi]:.2f} m/s",
                fontsize=8, pad=3,
            )
            self._status.setText(
                f"Frame {fi + 1}/{N_frames}   "
                f"A: z={A['z'][fi]:.1f}m, u={A['u'][fi]:.2f}m/s   "
                f"B: z={B['z'][fi]:.1f}m, u={B['u'][fi]:.2f}m/s"
            )
            return []

        self._ani = animation.FuncAnimation(
            self._fig,
            _update_dual,
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


# ---------------------------------------------------------------------------
# Etapa3GraphsWidget  (Etapa 3)
# ---------------------------------------------------------------------------

class Etapa3GraphsWidget(QWidget):
    """
    Gráficos da Etapa 3 — replica dentro da GUI os gráficos gerados pelo
    script ``etapa3/etapa3_graficos.py`` (4 páginas do PDF) para a
    simulação actual.

    Layout (GridSpec 3×2):
      [0, 0] Trajectória 2D no plano horizontal (Norte vs Este)
      [0, 1] Profundidade z vs tempo (eixo z invertido)
      [1, 0] Velocidades lineares (u, v, w) em m/s
      [1, 1] Velocidades angulares (p, q, r) em graus/s
      [2, :] Comandos dos actuadores: deflexões das barbatanas (graus,
             eixo esquerdo) + rotação do propulsor (RPM, eixo direito)

    Mapeamento de colunas da simData para um torpedo (dimU=5):
      0:3   x_north, y_east, z_depth
      3:6   phi, theta, psi
      6:9   u, v, w
      9:12  p, q, r
      12:17 u_control (δ_r_top, δ_r_bot, δ_s_star, δ_s_port, n_cmd)
      17:22 u_actual
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._fig    = Figure(figsize=(8, 7), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)

        # Placeholder: 3×2 empty axes até haver dados
        gs = GridSpec(3, 2, figure=self._fig)
        for r in range(3):
            for c in range(2):
                ax = self._fig.add_subplot(gs[r, c])
                ax.set_visible(False)

        self._info = QLabel("Aguarda simulação…")
        self._info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info.setStyleSheet("font-size: 10px; color: #888;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._canvas)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._info)
        layout.addWidget(scroll, stretch=1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plot_etapa3(self, simTime: np.ndarray, simData: np.ndarray,
                    dimU: int = 5) -> None:
        """
        Renderiza os gráficos da Etapa 3 para a simulação actual.

        Parâmetros
        ----------
        simTime : (N, 1) array — vector de tempo (s)
        simData : (N, 2*DOF + 2*dimU) array — estados + comandos + actuais
        dimU : int — número de entradas de controlo (default 5)
        """
        t = simTime[:, 0]

        DOF = 6
        cmd_start = 2 * DOF   # 12
        # Índices das colunas (layout simData)
        col_x, col_y, col_z = 0, 1, 2
        col_u, col_v, col_w = 6, 7, 8
        col_p, col_q, col_r = 9, 10, 11
        col_delta_r_top  = cmd_start + 0
        col_delta_r_bot  = cmd_start + 1
        col_delta_s_star = cmd_start + 2
        col_delta_s_port = cmd_start + 3
        col_n_cmd        = cmd_start + 4

        self._fig.clear()
        gs = GridSpec(3, 2, figure=self._fig)

        # ── [0, 0] Trajectória 2D (Norte vs Este) ──────────────────────
        ax_traj = self._fig.add_subplot(gs[0, 0])
        norte = simData[:, col_x]
        este  = simData[:, col_y]
        ax_traj.plot(este, norte, color='tab:blue', lw=1.4)
        ax_traj.plot(este[0], norte[0], marker='o', color='green',
                     markersize=7, label='Início')
        ax_traj.plot(este[-1], norte[-1], marker='s', color='red',
                     markersize=7, label='Fim')
        ax_traj.set_xlabel('Este [m]', fontsize=7)
        ax_traj.set_ylabel('Norte [m]', fontsize=7)
        ax_traj.set_title('Trajectória 2D', fontsize=8, pad=3)
        ax_traj.set_aspect('equal', adjustable='datalim')
        ax_traj.legend(fontsize=6, loc='best')
        ax_traj.tick_params(labelsize=6)
        ax_traj.grid(True, linestyle='--', alpha=0.5, lw=0.5)

        # ── [0, 1] Profundidade z vs tempo ─────────────────────────────
        ax_prof = self._fig.add_subplot(gs[0, 1])
        ax_prof.plot(t, simData[:, col_z], color='tab:blue', lw=1.4)
        ax_prof.invert_yaxis()   # profundidade cresce para baixo
        ax_prof.set_xlabel('t [s]', fontsize=7)
        ax_prof.set_ylabel('Profundidade z [m]', fontsize=7)
        ax_prof.set_title('Profundidade vs tempo', fontsize=8, pad=3)
        ax_prof.tick_params(labelsize=6)
        ax_prof.grid(True, linestyle='--', alpha=0.5, lw=0.5)

        # ── [1, 0] Velocidades lineares (u, v, w) ──────────────────────
        ax_vlin = self._fig.add_subplot(gs[1, 0])
        ax_vlin.plot(t, simData[:, col_u], label='u (surge)',
                     color='tab:blue', lw=1.2)
        ax_vlin.plot(t, simData[:, col_v], label='v (sway)',
                     color='tab:orange', lw=1.2)
        ax_vlin.plot(t, simData[:, col_w], label='w (heave)',
                     color='tab:green', lw=1.2)
        ax_vlin.set_xlabel('t [s]', fontsize=7)
        ax_vlin.set_ylabel('Velocidade linear [m/s]', fontsize=7)
        ax_vlin.set_title('Velocidades lineares', fontsize=8, pad=3)
        ax_vlin.legend(fontsize=6, loc='best')
        ax_vlin.tick_params(labelsize=6)
        ax_vlin.grid(True, linestyle='--', alpha=0.5, lw=0.5)

        # ── [1, 1] Velocidades angulares (p, q, r) em °/s ──────────────
        ax_vang = self._fig.add_subplot(gs[1, 1])
        ax_vang.plot(t, np.rad2deg(simData[:, col_p]),
                     label='p (rolamento)', color='tab:red', lw=1.2)
        ax_vang.plot(t, np.rad2deg(simData[:, col_q]),
                     label='q (arfagem)',  color='tab:purple', lw=1.2)
        ax_vang.plot(t, np.rad2deg(simData[:, col_r]),
                     label='r (guinada)',  color='tab:brown', lw=1.2)
        ax_vang.set_xlabel('t [s]', fontsize=7)
        ax_vang.set_ylabel('Velocidade angular [°/s]', fontsize=7)
        ax_vang.set_title('Velocidades angulares', fontsize=8, pad=3)
        ax_vang.legend(fontsize=6, loc='best')
        ax_vang.tick_params(labelsize=6)
        ax_vang.grid(True, linestyle='--', alpha=0.5, lw=0.5)

        # ── [2, :] Actuadores: fins (graus) + n (RPM) em twin axis ─────
        ax_fins = self._fig.add_subplot(gs[2, :])
        ax_fins.plot(t, np.rad2deg(simData[:, col_delta_r_top]),
                     label='δ_r_top',  color='tab:blue',   lw=1.1)
        ax_fins.plot(t, np.rad2deg(simData[:, col_delta_r_bot]),
                     label='δ_r_bot',  color='tab:cyan',   lw=1.1)
        ax_fins.plot(t, np.rad2deg(simData[:, col_delta_s_star]),
                     label='δ_s_star', color='tab:orange', lw=1.1)
        ax_fins.plot(t, np.rad2deg(simData[:, col_delta_s_port]),
                     label='δ_s_port', color='tab:red',    lw=1.1)
        ax_fins.set_xlabel('t [s]', fontsize=7)
        ax_fins.set_ylabel('Deflexão das barbatanas [°]', fontsize=7)
        ax_fins.tick_params(labelsize=6)
        ax_fins.grid(True, linestyle='--', alpha=0.5, lw=0.5)

        ax_rpm = ax_fins.twinx()
        ax_rpm.plot(t, simData[:, col_n_cmd], label='n (hélice)',
                    color='tab:green', lw=1.4, linestyle='--')
        ax_rpm.set_ylabel('Rotação do hélice [RPM]', fontsize=7)
        ax_rpm.tick_params(labelsize=6)

        # Legenda combinada dos dois eixos
        linhas_esq, labels_esq = ax_fins.get_legend_handles_labels()
        linhas_dir, labels_dir = ax_rpm.get_legend_handles_labels()
        ax_fins.legend(linhas_esq + linhas_dir, labels_esq + labels_dir,
                       fontsize=6, loc='best', ncol=5)
        ax_fins.set_title('Comandos dos actuadores', fontsize=8, pad=3)

        duration = float(t[-1] - t[0]) if len(t) > 1 else 0.0
        self._info.setText(
            f"Gráficos Etapa 3 — {len(t)} amostras, "
            f"duração {duration:.1f} s"
        )

        self._fig.tight_layout(pad=1.2)
        self._canvas.draw()


# ---------------------------------------------------------------------------
# TorpedoControlsWidget  (Etapa 3)
# ---------------------------------------------------------------------------

class TorpedoControlsWidget(QWidget):
    """
    Gráficos de sinais de controlo: comando vs. valor real (actuator dynamics).

    Layout: 3 linhas × 2 colunas:
      Linha 1 — Leme de topo (cmd vs actual), Leme de fundo
      Linha 2 — Stern plane estibordo, Stern plane bombordo
      Linha 3 — RPM propulsor, (vazio ou reservado)

    Chame plot_controls() após a simulação terminar.
    """

    _LABELS = [
        ("Top Rudder δ_r_top",    "rad"),
        ("Bottom Rudder δ_r_bot", "rad"),
        ("Star Stern δ_s_star",   "rad"),
        ("Port Stern δ_s_port",   "rad"),
        ("Propeller n",           "RPM"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self._fig    = Figure(figsize=(7, 6), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)

        axs = self._fig.subplots(3, 2)
        for ax in axs.flat:
            ax.set_visible(False)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._canvas)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    def plot_controls(self, simTime: np.ndarray, simData: np.ndarray,
                      dimU: int = 5) -> None:
        """
        Renderiza gráficos de sinais de controlo.

        Parâmetros
        ----------
        simTime : (N, 1) array
        simData : (N, 2*DOF + 2*dimU) array
        dimU : int — número de entradas de controlo (default 5)
        """
        t = simTime[:, 0]
        DOF = 6
        cmd_start = 2 * DOF           # u_control starts at col 12
        act_start = 2 * DOF + dimU    # u_actual starts at col 17

        self._fig.clear()
        axs = self._fig.subplots(3, 2)

        for i in range(dimU):
            r, c = divmod(i, 2)
            ax = axs[r][c]
            label, unit = self._LABELS[i]

            cmd = simData[:, cmd_start + i]
            act = simData[:, act_start + i]

            # Convert rad → deg for fin angles (not RPM)
            if unit == "rad":
                cmd = np.degrees(cmd)
                act = np.degrees(act)
                unit = "°"

            ax.plot(t, cmd, color='#2980b9', lw=1.2, alpha=0.7,
                    label="Comando")
            ax.plot(t, act, color='#e74c3c', lw=1.2, alpha=0.9,
                    label="Actual")
            ax.set_title(label, fontsize=8, pad=3)
            ax.set_ylabel(f"{unit}", fontsize=7)
            ax.set_xlabel("t (s)", fontsize=7)
            ax.tick_params(labelsize=6)
            ax.grid(True, alpha=0.3, lw=0.5)
            ax.legend(fontsize=6, loc='upper right')
            ax.set_visible(True)

        # Hide unused subplot (last slot if dimU is odd)
        if dimU % 2 == 1:
            axs[dimU // 2][1].set_visible(False)

        self._fig.tight_layout(pad=1.2)
        self._canvas.draw()


# ---------------------------------------------------------------------------
# ComparativeWidget  (Etapa 3)
# ---------------------------------------------------------------------------

class ComparativeWidget(QWidget):
    """
    Sobreposição de duas simulações para análise comparativa.

    Mostra grelha 3×3 (mesma disposição que TorpedoStatesWidget) com as
    curvas de ambas as simulações em cores distintas. Inclui legenda com
    os rótulos configuráveis.
    """

    _SPECS = TorpedoStatesWidget._SPECS
    _COLORS_A = ['#1f77b4', '#ff7f0e', '#2ca02c',
                 '#9467bd', '#8c564b', '#e377c2',
                 '#d62728', '#17becf', '#bcbd22']
    _COLORS_B = ['#aec7e8', '#ffbb78', '#98df8a',
                 '#c5b0d5', '#c49c94', '#f7b6d2',
                 '#ff9896', '#9edae5', '#dbdb8d']

    def __init__(self, parent=None):
        super().__init__(parent)

        self._fig    = Figure(figsize=(7, 6), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)

        axs = self._fig.subplots(3, 3)
        for ax in axs.flat:
            ax.set_visible(False)

        self._info = QLabel("Execute duas simulações para comparar.")
        self._info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info.setStyleSheet("font-size: 10px; color: #888;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._canvas)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._info)
        layout.addWidget(scroll, stretch=1)

    def plot_comparison(self,
                        simTime_A: np.ndarray, simData_A: np.ndarray,
                        simTime_B: np.ndarray, simData_B: np.ndarray,
                        label_A: str = "Simulação A",
                        label_B: str = "Simulação B") -> None:
        """
        Renderiza sobreposição de duas simulações.

        Parâmetros
        ----------
        simTime_A, simData_A : arrays da primeira simulação
        simTime_B, simData_B : arrays da segunda simulação
        label_A, label_B : rótulos para a legenda
        """
        tA = simTime_A[:, 0]
        tB = simTime_B[:, 0]

        self._fig.clear()
        axs = self._fig.subplots(3, 3)

        idx = 0
        for r, row in enumerate(self._SPECS):
            for c, (col, title, ylabel, to_deg) in enumerate(row):
                ax = axs[r][c]

                sigA = simData_A[:, col]
                sigB = simData_B[:, col]
                if to_deg:
                    sigA = np.degrees(sigA)
                    sigB = np.degrees(sigB)

                ax.plot(tA, sigA, color=self._COLORS_A[idx], lw=1.3,
                        label=label_A)
                ax.plot(tB, sigB, color=self._COLORS_B[idx], lw=1.3,
                        linestyle='--', label=label_B)
                ax.set_title(title, fontsize=8, pad=3)
                ax.set_ylabel(ylabel, fontsize=7)
                ax.set_xlabel("t (s)", fontsize=7)
                ax.tick_params(labelsize=6)
                ax.grid(True, alpha=0.3, lw=0.5)
                ax.legend(fontsize=5, loc='upper right')
                idx += 1

        self._info.setText(
            f"Comparação: {label_A} vs {label_B}")
        self._fig.tight_layout(pad=1.2)
        self._canvas.draw()
