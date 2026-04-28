"""
torpedo_gui.py — Main window (View) for the Torpedo AUV parameter editor.

Part of the MVC architecture for the torpedo vehicle model.
The View communicates exclusively with the TorpedoController and never
accesses the torpedo Model directly.

Etapa 3 additions: CSV/JSON export, control signal plots, comparative
analysis tab, fin_area widgets, simulation store.

Original author: Thor I. Fossen
Additions:       Ricardo Craveiro (1191000@isep.ipp.pt)
DINAV 2026 — Etapa 2/3
"""

import math

import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QTabWidget,
    QHBoxLayout, QVBoxLayout, QPushButton,
    QStatusBar, QMenuBar, QGroupBox,
    QFormLayout, QDoubleSpinBox, QScrollArea,
    QDialog, QComboBox, QLabel, QDialogButtonBox,
    QMessageBox, QFileDialog, QStackedWidget,
)

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from python_vehicle_simulator.lib.environment import (
    LinearProfile, PowerLawProfile, LogarithmicProfile,
)

from .torpedo_viz import (SimulationThread, TorpedoStatesWidget,
                          TorpedoVizWidget, TorpedoControlsWidget,
                          ComparativeWidget, Etapa3GraphsWidget,
                          DragCurveWidget, ControlResponseWidget)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPalette, QColor


# ---------------------------------------------------------------------------
# Helper: read-only spin-box style
# ---------------------------------------------------------------------------
_READONLY_STYLE = "background-color: #d0d0d0;"


class CurrentProfileWidget(QWidget):
    """
    Etapa 4 — Gráfico estático do perfil V_c(z) para o CurrentModel
    actualmente seleccionado na GUI.

    Convenção NED: z=0 no topo (superfície), z cresce para baixo.
    Altura fixa de 150 px. O método update_plot é ligado ao sinal
    params_updated do controller para refrescar automaticamente.
    """

    _Z_MAX = 100.0  # base do gráfico em metros (NED)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fig = Figure(figsize=(4, 1.5), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)
        self.setFixedHeight(150)

    def update_plot(self, params: dict):
        """Redesenha o perfil V_c(z) consoante params['current_model_selected']."""
        tipo = params.get('current_model_selected', 'Constante')
        beta_c_rad = params.get('beta_c', 0.0)

        self._fig.clear()
        ax = self._fig.add_subplot(111)
        ax.set_xlabel('V_c (m/s)')
        ax.set_ylabel('z (m)')
        ax.grid(True, linestyle=':', alpha=0.5)

        z = np.linspace(0.01, self._Z_MAX, 200)

        if tipo == 'Constante':
            V_c = float(params.get('V_c', 0.0))
            ax.axvline(V_c, color='C0', linewidth=1.5)
            ax.set_xlim(left=-0.05, right=max(0.5, V_c * 1.2 + 0.1))
        elif tipo == 'Linear':
            modelo = LinearProfile(
                params['current_V_surface'], params['current_z_ref'],
                beta_c_rad)
            vs = np.array([modelo.get_current(zi, 0.0)[0] for zi in z])
            ax.plot(vs, z, color='C0', linewidth=1.5)
        elif tipo == 'Lei 1/7':
            modelo = PowerLawProfile(
                params['current_V_surface'], params['current_z_ref'],
                beta_c_rad)
            vs = np.array([modelo.get_current(zi, 0.0)[0] for zi in z])
            ax.plot(vs, z, color='C0', linewidth=1.5)
        elif tipo == 'Logarítmico':
            modelo = LogarithmicProfile(
                V_star=params['current_V_star'], z_0=params['current_z_0'],
                beta_c=beta_c_rad, kappa=params['current_kappa'])
            vs = np.array([modelo.get_current(zi, 0.0)[0] for zi in z])
            ax.plot(vs, z, color='C0', linewidth=1.5)
        elif tipo == 'Gauss-Markov':
            Vc0 = float(params.get('current_Vc0', 0.0))
            sigma = float(params.get('current_sigma', 0.0))
            ax.axvline(Vc0, color='C0', linewidth=1.5,
                       label=f'V_c0 = {Vc0:.2f}')
            if sigma > 0:
                ax.axvspan(Vc0 - sigma, Vc0 + sigma, alpha=0.2, color='C0',
                           label=f'±σ = ±{sigma:.2f}')
            ax.legend(loc='upper right', fontsize='x-small')
            ax.set_xlim(left=Vc0 - max(sigma, 0.1) - 0.05,
                        right=Vc0 + max(sigma, 0.1) + 0.05)

        ax.set_ylim(self._Z_MAX, 0.0)  # z=0 no topo (NED)
        self._canvas.draw_idle()


class CompareScenariosDialog(QDialog):
    """
    Etapa 4+ — Diálogo modal para configurar 2 cenários de simulação
    lado a lado. Cada coluna tem rótulo editável e overrides minimalistas
    (Cd, V_c, β_c em graus, ref_z, ref_psi) + selector de modelo de
    corrente (Constante / com perfil pré-definido).

    O propósito é deixar o utilizador comparar variações sem reconfigurar
    a GUI principal — todos os outros parâmetros (ganhos, geometria, etc.)
    são herdados do estado actual do controller.
    """

    _CURRENT_OPTIONS = ['Constante', 'Linear', 'Lei 1/7',
                        'Logarítmico', 'Gauss-Markov']

    # Mapeamento "tipo" → instância de CurrentModel a partir das chaves
    # actuais do view_state. Reproduz a lógica de
    # TorpedoController._build_current_model em modo simplificado.
    @staticmethod
    def _build_model_from(tipo: str, view: dict, V_c_override: float,
                          beta_c_deg_override: float):
        from python_vehicle_simulator.lib.environment import (
            LinearProfile, PowerLawProfile, LogarithmicProfile,
            GaussMarkovCurrent,
        )
        beta_c_rad = float(beta_c_deg_override) * (math.pi / 180.0)
        if tipo == 'Constante':
            return None  # caminho legado V_c/β_c
        if tipo == 'Linear':
            return LinearProfile(view['current_V_surface'],
                                 view['current_z_ref'], beta_c_rad)
        if tipo == 'Lei 1/7':
            return PowerLawProfile(view['current_V_surface'],
                                   view['current_z_ref'], beta_c_rad)
        if tipo == 'Logarítmico':
            return LogarithmicProfile(
                V_star=view['current_V_star'], z_0=view['current_z_0'],
                beta_c=beta_c_rad, kappa=view['current_kappa'])
        if tipo == 'Gauss-Markov':
            return GaussMarkovCurrent(
                mu=view['current_mu'], sigma=view['current_sigma'],
                V_c0=view['current_Vc0'], beta_c=beta_c_rad,
                rng_seed=int(view['current_seed']))
        return None

    def __init__(self, view_state: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Comparar 2 Cenários")
        self.setMinimumSize(640, 380)
        self._view = dict(view_state)

        outer = QVBoxLayout(self)
        cols = QHBoxLayout()
        outer.addLayout(cols)

        self._col_a_widgets = self._build_column(cols, "A", "Cenário A")
        self._col_b_widgets = self._build_column(cols, "B", "Cenário B")

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Correr Comparação")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

    def _build_column(self, parent_layout: QHBoxLayout, suffix: str,
                       default_label: str) -> dict:
        """Cria a coluna A ou B; devolve dict de widgets para leitura."""
        box = QGroupBox(f"Cenário {suffix}")
        form = QFormLayout(box)

        label_edit = QDoubleSpinBox()  # placeholder; substituído por QLineEdit
        # Usamos QComboBox editável só para evitar acrescentar QLineEdit ao
        # import; aceita texto livre.
        from PyQt6.QtWidgets import QLineEdit
        label_edit = QLineEdit(default_label)
        form.addRow("Rótulo:", label_edit)

        # Overrides numéricos
        sb_cd = QDoubleSpinBox()
        sb_cd.setRange(0.1, 0.5); sb_cd.setSingleStep(0.01)
        sb_cd.setDecimals(3); sb_cd.setValue(self._view.get('Cd', 0.42))
        form.addRow("Cd:", sb_cd)

        sb_z = QDoubleSpinBox()
        sb_z.setRange(0.0, 100.0); sb_z.setSingleStep(1.0)
        sb_z.setDecimals(2); sb_z.setValue(self._view.get('ref_z', 30.0))
        form.addRow("ref_z (m):", sb_z)

        sb_psi = QDoubleSpinBox()
        sb_psi.setRange(-360.0, 360.0); sb_psi.setSingleStep(1.0)
        sb_psi.setDecimals(1)
        ref_psi_deg = self._view.get('ref_psi', 0.0)
        sb_psi.setValue(ref_psi_deg)
        form.addRow("ref_psi (°):", sb_psi)

        sb_vc = QDoubleSpinBox()
        sb_vc.setRange(0.0, 5.0); sb_vc.setSingleStep(0.01)
        sb_vc.setDecimals(3); sb_vc.setValue(self._view.get('V_c', 0.0))
        form.addRow("V_c (m/s):", sb_vc)

        sb_beta = QDoubleSpinBox()
        sb_beta.setRange(-180.0, 180.0); sb_beta.setSingleStep(1.0)
        sb_beta.setDecimals(1)
        sb_beta.setValue(self._view.get('beta_c_deg', 0.0))
        form.addRow("β_c (°):", sb_beta)

        cb_model = QComboBox()
        cb_model.addItems(self._CURRENT_OPTIONS)
        current_type = self._view.get('current_model_selected', 'Constante')
        if current_type in self._CURRENT_OPTIONS:
            cb_model.setCurrentText(current_type)
        form.addRow("Modelo de corrente:", cb_model)

        parent_layout.addWidget(box)
        return {
            'label':    label_edit,
            'cd':       sb_cd,
            'z':        sb_z,
            'psi':      sb_psi,
            'vc':       sb_vc,
            'beta':     sb_beta,
            'model':    cb_model,
        }

    def _read_cfg(self, w: dict) -> dict:
        V_c = float(w['vc'].value())
        beta = float(w['beta'].value())
        tipo = w['model'].currentText()
        cm = self._build_model_from(tipo, self._view, V_c, beta)
        return {
            'label':       w['label'].text() or 'Cenário',
            'control_mode': 'depthHeadingAutopilot',
            'ref_z':       float(w['z'].value()),
            'ref_psi':     float(w['psi'].value()),
            'V_c':         V_c,
            'beta_c_deg':  beta,
            'current_model': cm,
            'overrides':   {'Cd': float(w['cd'].value())},
        }

    def get_cfgs(self) -> tuple[dict, dict]:
        return self._read_cfg(self._col_a_widgets), \
               self._read_cfg(self._col_b_widgets)


class TorpedoGUI(QMainWindow):
    """
    Main window for the Torpedo AUV parameter editor.

    Parameters
    ----------
    controller : TorpedoController
        The MVC controller that mediates between this View and the
        torpedo Model.
    parent : QWidget, optional
        Parent widget (default None).
    """

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._controller = controller

        # ------------------------------------------------------------------
        # Window chrome
        # ------------------------------------------------------------------
        self.setWindowTitle("Torpedo AUV — DINAV 2026")
        self.setMinimumSize(900, 600)

        # ------------------------------------------------------------------
        # Menu bar
        # ------------------------------------------------------------------
        menubar: QMenuBar = self.menuBar()
        menubar.addMenu("Ficheiro")
        menubar.addMenu("Simulação")
        menubar.addMenu("Ajuda")

        # ------------------------------------------------------------------
        # Status bar
        # ------------------------------------------------------------------
        self.statusBar().showMessage("Pronto.")

        # ------------------------------------------------------------------
        # Central widget: splitter + button row
        # ------------------------------------------------------------------
        root_widget = QWidget()
        root_layout = QVBoxLayout(root_widget)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)
        self.setCentralWidget(root_widget)

        # Widget registry — must exist before panel builders run
        self.param_widgets: dict = {}

        # Horizontal splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._left_panel  = self._build_left_panel()
        self._right_panel = self._build_right_panel()
        self._splitter.addWidget(self._left_panel)
        self._splitter.addWidget(self._right_panel)
        self._splitter.setSizes([450, 450])
        root_layout.addWidget(self._splitter, stretch=1)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._btn_reset            = QPushButton("Repor Defaults")
        self._btn_validate         = QPushButton("Validar")
        self._btn_simulate         = QPushButton("Simular")
        self._btn_stop             = QPushButton("Parar")
        self._btn_stop.setEnabled(False)
        self._btn_simulate_ab      = QPushButton("Simular A e B (Etapa 3)")
        # Etapa 4+ — comparações com modelo de corrente
        self._btn_compare_currents = QPushButton("Comparar Sem/Com Corrente")
        self._btn_compare_custom   = QPushButton("Comparar 2 Cenários…")
        self._btn_export_csv       = QPushButton("Exportar CSV")
        self._btn_export_csv.setEnabled(False)
        for btn in (self._btn_reset, self._btn_validate, self._btn_simulate,
                    self._btn_stop, self._btn_simulate_ab,
                    self._btn_compare_currents, self._btn_compare_custom,
                    self._btn_export_csv):
            btn_layout.addWidget(btn)
        root_layout.addLayout(btn_layout)

        # Simulation state
        self._sim_duration: float = 20.0   # seconds (overridden by dialog)
        self._sim_thread = None             # SimulationThread instance

        # Etapa 3 A/B run state machine
        self._ab_mode: str | None = None       # None | "A" | "B"
        self._ab_saved_duration: float | None = None

        # Etapa 4+ — state machine para comparações personalizadas
        self._compare_mode: str | None = None  # None | "A" | "B"
        self._compare_cfgs: list[dict] | None = None
        self._compare_results: list[dict] | None = None
        self._compare_saved_duration: float | None = None

        # ------------------------------------------------------------------
        # Signal → slot connections
        # ------------------------------------------------------------------
        self._controller.params_updated.connect(self._on_params_updated)
        self._controller.validation_error.connect(self._on_validation_error)
        self._controller.simulation_ready.connect(self._on_simulation_ready)
        self._controller.param_dependency_updated.connect(
            self._on_dependency_updated)
        # Etapa 4 — gráfico V_c(z) actualiza-se a cada params_updated
        self._controller.params_updated.connect(
            self._current_profile_widget.update_plot)
        # Etapa 4+ — gráficos analíticos dinâmicos (sem simular)
        self._controller.params_updated.connect(
            self._drag_curve_widget.update_plot)
        self._controller.params_updated.connect(
            self._control_response_widget.update_plot)

        self._btn_reset.clicked.connect(self._controller.reset_to_defaults)
        self._btn_validate.clicked.connect(self._load_params)
        self._btn_simulate.clicked.connect(self._launch_simulation_dialog)
        self._btn_stop.clicked.connect(self._on_stop_clicked)
        self._btn_simulate_ab.clicked.connect(self._launch_etapa3_ab_run)
        self._btn_compare_currents.clicked.connect(
            self._launch_no_vs_with_current)
        self._btn_compare_custom.clicked.connect(
            self._launch_compare_dialog)
        self._btn_export_csv.clicked.connect(self._export_last_csv)
        # Etapa 4+ — sinal do controller quando 2 sims comparativas terminam
        self._controller.comparison_ready.connect(self._on_comparison_ready)

        # ------------------------------------------------------------------
        # Initial parameter load
        # ------------------------------------------------------------------
        self._load_params()

    # ----------------------------------------------------------------------
    # Panel builders
    # ----------------------------------------------------------------------

    def _build_left_panel(self) -> QWidget:
        """Left splitter zone: physical params, fins, thruster."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(self._build_group_physical())
        layout.addWidget(self._build_group_fins())
        layout.addWidget(self._build_group_thruster())
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _build_right_panel(self) -> QTabWidget:
        """Right splitter zone: tabbed — controllers, 3D animation, state plots."""
        tabs = QTabWidget()

        # ── Tab 1: Controladores (depth + heading) ──────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._build_group_depth_ctrl())
        layout.addWidget(self._build_group_heading_ctrl())
        layout.addWidget(self._build_group_current_model())
        layout.addStretch()
        scroll.setWidget(container)
        tabs.addTab(scroll, "Controladores")

        # ── Tab 2: Visualização 3D (animada, câmara segue torpedo) ──────────
        self._viz_widget = TorpedoVizWidget()
        tabs.addTab(self._viz_widget, "Visualização 3D")

        # ── Tab 3: Gráficos de Estado (estáticos, simulação completa) ───────
        self._states_widget = TorpedoStatesWidget()
        tabs.addTab(self._states_widget, "Gráficos de Estado")

        # ── Tab 4: Gráficos Etapa 3 (trajectória, profundidade,
        #    velocidades, actuadores — mesmos do etapa3_graficos.py) ────────
        self._etapa3_widget = Etapa3GraphsWidget()
        tabs.addTab(self._etapa3_widget, "Gráficos Etapa 3")

        # ── Tab 5: Sinais de Controlo (Etapa 3) ───────────────────────────
        self._controls_widget = TorpedoControlsWidget()
        tabs.addTab(self._controls_widget, "Sinais de Controlo")

        # ── Tab 6: Análise Comparativa (Etapa 3) ──────────────────────────
        self._comparative_widget = ComparativeWidget()
        tabs.addTab(self._comparative_widget, "Comparação")

        # ── Tab 7: Análise analítica (Etapa 4+) ───────────────────────────
        # Widgets que reagem em tempo real a alterações de parâmetros, sem
        # precisar de simular: curva de arrasto e resposta degrau analítica.
        analise = QWidget()
        analise_layout = QVBoxLayout(analise)
        analise_layout.setContentsMargins(4, 4, 4, 4)
        self._drag_curve_widget = DragCurveWidget()
        self._control_response_widget = ControlResponseWidget()
        analise_layout.addWidget(self._drag_curve_widget)
        analise_layout.addWidget(self._control_response_widget)
        tabs.addTab(analise, "Análise")

        return tabs

    # -- GroupBox 1: Physical parameters ------------------------------------

    def _build_group_physical(self) -> QGroupBox:
        box = QGroupBox("Parâmetros Físicos")
        form = QFormLayout(box)

        specs = [
            # (key, label, unit, min, max, step, decimals, readonly, tooltip)
            ('L',       'L',       'm',   0.01, 100.0,   0.01, 3, False,
             'Comprimento total do veículo (m)\nLimites: 0.01 – 100.0 m  (deve ser > diam)'),
            ('diam',    'diam',    'm',   0.01,  10.0,   0.01, 3, False,
             'Diâmetro do cilindro (m)\nLimites: 0.01 – 10.0 m  (deve ser < L)'),
            ('massa',   'massa',   'kg',   0.0,  1e6,    0.01, 4, True,
             'Massa esféroide calculada — só de leitura\nDepende de L e diam  (Fossen 2021, §8.4)'),
            ('Cd',      'Cd',      '—',    0.1,   0.5,  0.01, 3, False,
             'Coeficiente de arrasto parasítico (—)\nLimites: 0.1 – 0.5  (Allen et al., 2000)'),
            ('r44',     'r44',     '—',    0.1,   0.5,  0.01, 3, False,
             'Factor de inércia em rolamento (—)\nLimites: 0.1 – 0.5'),
            ('T_surge', 'T_surge', 's',   0.01, 1000.0,  1.0, 2, False,
             'Constante de tempo em avanço (s)\nLimites: 0.01 – 1000.0 s'),
            ('zeta_roll',  'ζ_roll',  '—', 0.0, 1.0, 0.01, 3, False,
             'Amortecimento relativo em rolamento (—)\nLimites: 0.0 – 1.0'),
            ('zeta_pitch', 'ζ_pitch', '—', 0.0, 1.0, 0.01, 3, False,
             'Amortecimento relativo em arfagem (—)\nLimites: 0.0 – 1.0'),
            # Etapa 4 — corrente oceânica (V_c, β_c). β_c convertido em
            # graus pelo controller para coerência com o construtor torpedo().
            ('V_c',         'V_c',  'm/s',     0.0,   5.0, 0.01, 3, False,
             'Velocidade da corrente oceânica (m/s)\nLimites: 0.0 – 5.0 m/s'),
            ('beta_c_deg',  'β_c',  '°',    -180.0, 180.0, 1.0,  1, False,
             'Direcção da corrente (°) — convertida para radianos no controller\n'
             'Limites: -180 – 180°'),
        ]
        self._add_spinboxes(form, specs)
        return box

    # -- GroupBox 2: Fins ----------------------------------------------------

    def _build_group_fins(self) -> QGroupBox:
        box = QGroupBox("Barbatanas")
        form = QFormLayout(box)

        fin_labels = [
            'Top Rudder',
            'Bottom Rudder',
            'Star Stern',
            'Port Stern',
        ]
        specs_cl = [
            (f'fin_CL_{i}', f'CL {fin_labels[i]}', '—', 0.0, 1.0, 0.01, 3,
             False,
             f'Coeficiente de sustentação da barbatana {fin_labels[i]} (—)\n'
             f'Limites: 0.0 – 1.0')
            for i in range(4)
        ]
        self._add_spinboxes(form, specs_cl)

        # Etapa 3: expose fin_area (was missing in Etapa 2)
        specs_area = [
            (f'fin_area_{i}', f'Área {fin_labels[i]}', 'm²',
             0.001, 0.1, 0.001, 5, False,
             f'Área da barbatana {fin_labels[i]} (m²)\n'
             f'Limites: 0.001 – 0.1 m²')
            for i in range(4)
        ]
        self._add_spinboxes(form, specs_area)
        return box

    # -- GroupBox 3: Thruster ------------------------------------------------

    def _build_group_thruster(self) -> QGroupBox:
        box = QGroupBox("Propulsor")
        form = QFormLayout(box)

        specs = [
            ('thruster_nMax', 'n_max', 'RPM', 1.0, 1525.0, 1.0, 0, False,
             'Rotação máxima do propulsor (RPM)\nLimites: 1 – 1525 RPM'),
        ]
        self._add_spinboxes(form, specs)
        return box

    # -- GroupBox 4: Depth controller ----------------------------------------

    def _build_group_depth_ctrl(self) -> QGroupBox:
        box = QGroupBox("Controlador de Profundidade")
        form = QFormLayout(box)

        specs = [
            ('T_sway',   'T_sway',   's',     0.01, 1000.0, 1.0,  2, False,
             'Constante de tempo em deriva (s) — actualiza T_heave automaticamente (acoplamento A7)\nLimites: 0.01 – 1000.0 s'),
            ('wn_d_z',   'ωn_d_z',   'rad/s', 0.001, 10.0, 0.001, 4, False,
             'Frequência natural do modelo de referência de profundidade (rad/s)\nLimites: 0.001 – 10.0 rad/s'),
            ('Kp_z',     'Kp_z',     '—',     1e-4, 100.0, 0.01, 4, False,
             'Ganho proporcional — malha exterior de profundidade (—)\nLimites: > 0'),
            ('T_z',      'T_z',      's',      0.01, 1e4,   1.0,  2, False,
             'Constante de tempo integral — malha exterior de profundidade (s)\nLimites: 0.01 – 10000 s'),
            ('Kp_theta', 'Kp_θ',     '—',     1e-4, 100.0, 0.1,  3, False,
             'Ganho proporcional — controlador PID de arfagem (—)\nLimites: > 0'),
            ('Kd_theta', 'Kd_θ',     '—',     1e-4, 100.0, 0.1,  3, False,
             'Ganho derivativo — controlador PID de arfagem (—)\nLimites: > 0'),
            ('Ki_theta', 'Ki_θ',     '—',     0.0,  100.0, 0.01, 3, False,
             'Ganho integral — controlador PID de arfagem (—)\nLimites: ≥ 0'),
            ('K_w',      'K_w',      '—',     0.0,  100.0, 0.1,  3, False,
             'Ganho de realimentação de velocidade em heave (—)\nLimites: ≥ 0'),
            ('T_heave',  'T_heave',  's',      0.01, 1000.0, 1.0, 2, True,
             'Constante de tempo em heave (s) — só de leitura (acoplado a T_sway, A7)'),
        ]
        self._add_spinboxes(form, specs)
        return box

    # -- GroupBox 5: Heading controller (SMC) --------------------------------

    def _build_group_heading_ctrl(self) -> QGroupBox:
        box = QGroupBox("Controlador de Rumo (SMC)")
        form = QFormLayout(box)

        specs = [
            ('T_yaw',    'T_yaw',   's',     0.01, 1000.0, 1.0,  2, False,
             'Constante de tempo em guinada (s) — actualiza T_nomoto automaticamente (acoplamento A8)\nLimites: 0.01 – 1000.0 s'),
            ('K_nomoto', 'K_nomoto', '—',   0.001, 10.0,  0.001, 4, False,
             'Ganho de Nomoto K (—)\nK = r_max / δ_max  (Fossen 2021, §16.3)\nLimites: > 0'),
            ('r_max',    'r_max',   'rad/s', 0.001, 1.0,  0.001, 4, False,
             'Taxa máxima de guinada permitida (rad/s)\nLimites: > 0  (padrão ≈ 0.087 rad/s = 5 °/s)'),
            ('wn_d',    'ωn_d',    'rad/s', 0.001, 10.0,  0.001, 4, False,
             'Frequência natural do modelo de referência de rumo (rad/s)\nLimites: 0.001 – 10.0 rad/s'),
            ('zeta_d',  'ζd',      '—',     0.5,   2.0,   0.01,  3, False,
             'Amortecimento relativo desejado (—)\nLimites: 0.5 – 2.0  (1.0 = criticamente amortecido)'),
            ('lam',     'λ',       '—',     1e-4,  10.0,  0.001, 4, False,
             'Parâmetro SMC λ (—)\nLimites: > 0'),
            ('phi_b',   'φb',      '—',     1e-4,  10.0,  0.001, 4, False,
             'Espessura da camada limite SMC φb (—)\nLimites: > 0'),
            ('K_d',     'K_d',     '—',     1e-4, 100.0,  0.01,  3, False,
             'Ganho PID do controlador SMC (—)\nLimites: > 0'),
            ('K_sigma',  'K_σ',    '—',     1e-4, 100.0,  0.001, 4, False,
             'Ganho de comutação SMC (—)\nLimites: > 0'),
            ('T_nomoto', 'T_nomoto','s',     0.01, 1000.0, 1.0,   2, True,
             'Constante de tempo de Nomoto (s) — só de leitura (acoplado a T_yaw, A8)'),
        ]
        self._add_spinboxes(form, specs)
        return box

    # -- GroupBox 6: Corrente Oceânica (Etapa 4) ----------------------------

    def _build_group_current_model(self) -> QGroupBox:
        """
        Etapa 4 — Selector do modelo de corrente + parâmetros específicos
        em QStackedWidget + gráfico estático V_c(z).
        """
        box = QGroupBox("Corrente Oceânica")
        outer = QVBoxLayout(box)
        outer.setSpacing(6)

        # Combo + label no topo
        top_form = QFormLayout()
        top_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._current_model_combo = QComboBox()
        self._current_model_combo.addItems([
            'Constante', 'Linear', 'Lei 1/7', 'Logarítmico', 'Gauss-Markov',
        ])
        self._current_model_combo.setToolTip(
            'Tipo de modelo de corrente oceânica aplicado em torpedo.dynamics()')
        top_form.addRow("Tipo de modelo:", self._current_model_combo)
        outer.addLayout(top_form)

        # Stack com 5 páginas (uma por modelo)
        self._current_model_stack = QStackedWidget()

        # Página 0 — Constante (apenas label informativo)
        page_const = QWidget()
        const_layout = QVBoxLayout(page_const)
        const_layout.setContentsMargins(8, 4, 8, 4)
        const_layout.addWidget(QLabel(
            "Usar V_c e β_c dos Parâmetros Físicos."))
        self._current_model_stack.addWidget(page_const)

        # Página 1 — Linear
        page_lin = QWidget()
        form_lin = QFormLayout(page_lin)
        self._add_spinboxes(form_lin, [
            ('current_V_surface', 'V_surface', 'm/s', 0.0, 5.0, 0.01, 3, False,
             'Velocidade na superfície (m/s)\nLimites: 0.0 – 5.0'),
            ('current_z_ref',    'z_ref',     'm',   0.1, 500.0, 1.0, 2, False,
             'Profundidade de referência (m)\nLimites: 0.1 – 500.0'),
        ])
        self._current_model_stack.addWidget(page_lin)

        # Página 2 — Lei 1/7: partilha os parâmetros (V_surface, z_ref) com
        # a página Linear (mesmas keys no controller). A UI evita duplicar
        # widgets — só mostra um label informativo.
        page_pow = QWidget()
        pow_layout = QVBoxLayout(page_pow)
        pow_layout.setContentsMargins(8, 4, 8, 4)
        pow_layout.addWidget(QLabel(
            "Usa os mesmos parâmetros (V_surface, z_ref) da página 'Linear'.\n"
            "A diferença é apenas a função de cálculo:\n"
            "  Linear: V_c = V_surface · (z / z_ref)\n"
            "  Lei 1/7: V_c = V_surface · (z / z_ref)^(1/7)"))
        self._current_model_stack.addWidget(page_pow)

        # Página 3 — Logarítmico
        page_log = QWidget()
        form_log = QFormLayout(page_log)
        self._add_spinboxes(form_log, [
            ('current_V_star', 'V_star', 'm/s',   0.0,  1.0, 0.001, 4, False,
             'Velocidade de fricção V* (m/s)\nLimites: 0.0 – 1.0'),
            ('current_z_0',    'z_0',    'm',     0.001, 10.0, 0.001, 4, False,
             'Rugosidade aerodinâmica do fundo z_0 (m)\nLimites: 0.001 – 10.0'),
            ('current_kappa',  'κ',      '—',     0.0,  1.0,  0.01,  2, True,
             'Constante de von Kármán (—) — só de leitura, fixo em 0.41'),
        ])
        self._current_model_stack.addWidget(page_log)

        # Página 4 — Gauss-Markov
        page_gm = QWidget()
        form_gm = QFormLayout(page_gm)
        self._add_spinboxes(form_gm, [
            ('current_mu',    'μ',     '1/s',   0.0,    1.0,    0.01,  3, False,
             'Inverso do tempo de correlação μ (1/s)\nLimites: 0.0 – 1.0'),
            ('current_sigma', 'σ',     'm/s',   0.0,    1.0,    0.001, 4, False,
             'Desvio padrão do ruído σ (m/s)\nLimites: 0.0 – 1.0'),
            ('current_Vc0',   'V_c0',  'm/s',   0.0,    5.0,    0.01,  3, False,
             'Velocidade inicial V_c0 (m/s)\nLimites: 0.0 – 5.0'),
            ('current_seed',  'seed',  '—',     0.0,  9999.0,   1.0,   0, False,
             'Semente do gerador aleatório (int 0–9999)'),
        ])
        self._current_model_stack.addWidget(page_gm)

        outer.addWidget(self._current_model_stack)

        # Gráfico estático V_c(z)
        self._current_profile_widget = CurrentProfileWidget()
        outer.addWidget(self._current_profile_widget)

        # Inicializar valores nos spinboxes a partir do estado actual do
        # controller (defaults da Etapa 4) — é seguro porque param_widgets
        # já está preenchido pelo _add_spinboxes acima.
        defaults = self._controller.get_view_state()
        for key in ('current_V_surface', 'current_z_ref',
                    'current_V_star', 'current_z_0', 'current_kappa',
                    'current_mu', 'current_sigma', 'current_Vc0',
                    'current_seed'):
            if key in self.param_widgets and key in defaults:
                self.param_widgets[key].blockSignals(True)
                self.param_widgets[key].setValue(float(defaults[key]))
                self.param_widgets[key].blockSignals(False)

        # Ligações: combo → stack + controller
        self._current_model_combo.currentIndexChanged.connect(
            self._on_current_model_changed)

        return box

    def _on_current_model_changed(self, idx: int):
        """Etapa 4 — handler do combo: muda página e propaga ao controller."""
        self._current_model_stack.setCurrentIndex(idx)
        self._controller.update_param(
            'current_model_selected',
            self._current_model_combo.itemText(idx))

    # ----------------------------------------------------------------------
    # Shared spin-box factory
    # ----------------------------------------------------------------------

    def _add_spinboxes(self, form: QFormLayout, specs: list):
        """
        Create one QDoubleSpinBox per spec and register it in
        self.param_widgets.

        specs item: (key, label, unit, min, max, step, decimals,
                     readonly, tooltip)
        """
        for key, label, unit, lo, hi, step, dec, readonly, tip in specs:
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setSingleStep(step)
            sb.setDecimals(dec)
            if unit and unit != '—':
                sb.setSuffix(f'  {unit}')
            sb.setToolTip(tip)
            sb.setMinimumWidth(120)

            if readonly:
                sb.setReadOnly(True)
                sb.setStyleSheet(_READONLY_STYLE)
                sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            else:
                # Emit update only when editing is finished (focus lost / Enter)
                _key = key   # capture for closure
                sb.editingFinished.connect(
                    lambda _sb=sb, _k=_key:
                        self._controller.update_param(_k, _sb.value())
                )

            self.param_widgets[key] = sb
            form.addRow(label, sb)

    # ----------------------------------------------------------------------
    # Slots
    # ----------------------------------------------------------------------

    def _on_params_updated(self, params: dict):
        """Refresh every widget from the updated params dict."""
        for key, sb in self.param_widgets.items():
            sb.blockSignals(True)
            try:
                if key.startswith('fin_CL_'):
                    idx = int(key.split('_')[-1])
                    cl_list = params.get('fin_CL', [])
                    if idx < len(cl_list):
                        sb.setValue(float(cl_list[idx]))
                elif key.startswith('fin_area_'):
                    idx = int(key.split('_')[-1])
                    area_list = params.get('fin_area', [])
                    if idx < len(area_list):
                        sb.setValue(float(area_list[idx]))
                elif key in params:
                    sb.setValue(float(params[key]))
            finally:
                sb.blockSignals(False)

        # Restore normal background on all widgets (clear dependency highlight)
        for sb in self.param_widgets.values():
            if sb.isReadOnly():
                sb.setStyleSheet(_READONLY_STYLE)
            else:
                sb.setStyleSheet("")

        self.statusBar().showMessage(
            f"Parâmetros actualizados ({len(params)} valores).")

    def _on_validation_error(self, msg: str):
        """Show validation error in statusbar and highlight the offending widget.

        The controller prefixes messages with ``[param_name] `` when the
        error is associated with a specific parameter.  This method parses
        that prefix, highlights the corresponding widget in red (#ffcccc),
        and shows a clean message (without the prefix) in the statusbar and
        in the QMessageBox warning dialog.

        The red highlight is cleared automatically the next time
        ``_on_params_updated`` fires (which resets all non-readonly styles).
        """
        # Parse optional [param_name] prefix
        param_name  = None
        display_msg = msg
        if msg.startswith('['):
            end = msg.find(']')
            if end > 0:
                param_name  = msg[1:end]
                display_msg = msg[end + 1:].strip()

        self.statusBar().showMessage(f"Erro de validação: {display_msg}")

        # Highlight the offending widget
        if param_name and param_name in self.param_widgets:
            sb = self.param_widgets[param_name]
            if not sb.isReadOnly():
                sb.setStyleSheet("background-color: #ffcccc;")

        QMessageBox.warning(self, "Erro de Validação", display_msg)

    def _on_simulation_ready(self, vehicle):
        """Inicia a simulação em background e muda para o tab de visualização."""
        # Mudar para o tab 3D antes de começar
        self._right_panel.setCurrentIndex(1)

        ctrl_mode = getattr(vehicle, 'controlMode', '—')
        self.statusBar().showMessage(
            f"A simular… (modo '{ctrl_mode}', {int(self._sim_duration)} s)")
        self._btn_simulate.setEnabled(False)
        self._btn_stop.setEnabled(True)            # Etapa 4+ — botão Parar activo

        # Etapa 3 A/B e Etapa 4+ compare: passo fino replica os scripts (dt=0.02)
        if self._ab_mode is not None or self._compare_mode is not None:
            sample_time = 0.02
        else:
            sample_time = 0.05
        N = max(1, int(self._sim_duration / sample_time))

        self._sim_thread = SimulationThread(vehicle, N, sample_time, parent=self)
        self._sim_thread.finished.connect(self._on_simulation_done)
        self._sim_thread.error.connect(self._on_simulation_error)
        self._sim_thread.cancelled.connect(self._on_simulation_cancelled)
        self._sim_thread.start()

    def _restore_buttons_after_sim(self):
        """Etapa 4+ — Repõe estado de botões após simulação (sucesso/erro/cancel)."""
        self._btn_simulate.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_simulate_ab.setEnabled(True)
        self._btn_compare_currents.setEnabled(True)
        self._btn_compare_custom.setEnabled(True)
        self._btn_reset.setEnabled(True)

    def _on_stop_clicked(self):
        """
        Etapa 4+ — Cancela a simulação em curso (e, se a meio, qualquer
        sequência A/B ou comparação personalizada). Reabilita os botões
        e devolve o foco à tab Controladores.
        """
        if self._sim_thread is not None and self._sim_thread.isRunning():
            self._sim_thread.cancel()
            self._sim_thread.wait(2000)
        # Limpar state machine A/B
        if self._ab_mode is not None:
            self._ab_mode = None
            if self._ab_saved_duration is not None:
                self._sim_duration = self._ab_saved_duration
                self._ab_saved_duration = None
        # Limpar state machine de comparação personalizada
        if self._compare_mode is not None:
            self._compare_mode = None
            self._compare_cfgs = None
            self._compare_results = None
            if self._compare_saved_duration is not None:
                self._sim_duration = self._compare_saved_duration
                self._compare_saved_duration = None
        self._restore_buttons_after_sim()
        self._right_panel.setCurrentIndex(0)
        self.statusBar().showMessage(
            "Simulação cancelada — pronto para nova configuração.")

    def _on_simulation_cancelled(self):
        """Slot do sinal cancelled — apenas garante UI restaurada."""
        try:
            self._restore_buttons_after_sim()
        except RuntimeError:
            pass

    def _on_simulation_done(self, simTime, simData):
        """Recebe os dados da simulação e actualiza os widgets de visualização."""
        try:
            self._btn_export_csv.setEnabled(True)
            params = self._controller.get_current_params()
            L    = params.get('L',    1.6)
            diam = params.get('diam', 0.19)

            # Tab 2 — animação 3D
            self._viz_widget.run_animation(simTime, simData, L, diam)
            # Tab 3 — gráficos de estado
            self._states_widget.plot_states(simTime, simData)
            # Tab 4 — gráficos Etapa 3 (trajectória, prof., velocidades, act.)
            self._etapa3_widget.plot_etapa3(simTime, simData, dimU=5)
            # Tab 5 — sinais de controlo (Etapa 3)
            self._controls_widget.plot_controls(simTime, simData, dimU=5)

            # Etapa 4+ — state machine compare (intercepta antes de armazenar
            # via store_simulation: o controller faz isso em
            # register_comparison_results no fim das duas pernas).
            if self._compare_mode is not None:
                self._handle_compare_step(simTime, simData)
                return

            # Etapa 3 — store simulation for comparison / export
            if self._ab_mode == "A":
                label = "Sim A — Cd=0.42 (Etapa 3)"
            elif self._ab_mode == "B":
                label = "Sim B — Cd=0.25 (Etapa 3)"
            else:
                n_sim = len(self._controller.get_store()) + 1
                label = (f"Sim {n_sim} — "
                         f"z={params.get('ref_z', 0):.0f}m, "
                         f"ψ={params.get('ref_psi', 0):.0f}°")
            self._controller.store_simulation(
                simTime, simData, label=label,
                metadata={'duration': self._sim_duration})

            # Tab 6 — comparative overlay (if ≥ 2 simulations stored)
            store = self._controller.get_store()
            if len(store) >= 2:
                a, b = store[-2], store[-1]
                self._comparative_widget.plot_comparison(
                    a['simTime'], a['simData'],
                    b['simTime'], b['simData'],
                    label_A=a['label'], label_B=b['label'])

            # ── A/B state machine ──────────────────────────────────────────
            if self._ab_mode == "A":
                self._ab_mode = "B"
                self.statusBar().showMessage(
                    "Sim A concluída. A correr Sim B (Cd=0.25, stepInput, 200 s)…")
                self._controller.prepare_etapa3_simulation(0.25)
                return
            if self._ab_mode == "B":
                # Substitui a animação single de B pela dupla (A | B)
                a, b = store[-2], store[-1]
                self._viz_widget.run_dual_animation(
                    a['simTime'], a['simData'],
                    b['simTime'], b['simData'],
                    L, diam,
                    label_A=a['label'], label_B=b['label'])
                self._right_panel.setCurrentIndex(1)   # "Visualização 3D"
                if self._ab_saved_duration is not None:
                    self._sim_duration = self._ab_saved_duration
                    self._ab_saved_duration = None
                self._ab_mode = None
                self._restore_buttons_after_sim()
                self.statusBar().showMessage(
                    "Etapa 3 concluída — A e B a correr lado a lado em 3D; "
                    "tab Comparação também populada.")
                return

            # Modo normal (single-sim)
            self._btn_simulate.setEnabled(True)
            self._btn_stop.setEnabled(False)
            n_steps = len(simData)
            x_f, y_f, z_f = simData[-1, 0], simData[-1, 1], simData[-1, 2]
            self.statusBar().showMessage(
                f"Simulação concluída — {n_steps} amostras  |  "
                f"Posição final: ({x_f:.1f}, {y_f:.1f}, {z_f:.1f}) m  |  "
                f"[{len(store)} sim. guardadas]")
        except RuntimeError:
            pass   # widget já destruído (p.ex. durante teardown de testes)

    def _on_simulation_error(self, msg: str):
        """Trata erros da thread de simulação."""
        try:
            if self._ab_mode is not None:
                stage = self._ab_mode
                if self._ab_saved_duration is not None:
                    self._sim_duration = self._ab_saved_duration
                    self._ab_saved_duration = None
                self._ab_mode = None
                self._restore_buttons_after_sim()
                self.statusBar().showMessage(
                    f"Erro em Sim {stage}: {msg} — corrida A/B abortada.")
                QMessageBox.warning(self, "Erro na Simulação A/B", msg)
                return
            if self._compare_mode is not None:
                stage = self._compare_mode
                if self._compare_saved_duration is not None:
                    self._sim_duration = self._compare_saved_duration
                    self._compare_saved_duration = None
                self._compare_mode = None
                self._compare_cfgs = None
                self._compare_results = None
                self._restore_buttons_after_sim()
                self.statusBar().showMessage(
                    f"Erro em Cenário {stage}: {msg} — comparação abortada.")
                QMessageBox.warning(self, "Erro na Comparação", msg)
                return
            self._restore_buttons_after_sim()
            self.statusBar().showMessage(f"Erro na simulação: {msg}")
            QMessageBox.warning(self, "Erro na Simulação", msg)
        except RuntimeError:
            pass

    def _on_dependency_updated(self, nome: str, valor: float):
        """Highlight the dependent widget in light blue and update statusbar."""
        sb = self.param_widgets.get(nome)
        if sb is not None:
            sb.blockSignals(True)
            sb.setValue(float(valor))
            sb.blockSignals(False)
            sb.setStyleSheet("background-color: #d0e8ff;")
            QTimer.singleShot(2000, lambda w=sb: w.setStyleSheet(""))

        self.statusBar().showMessage(
            f"{nome} actualizado automaticamente para {valor:.4g}")

    def _export_last_csv(self):
        """Export the most recent simulation to CSV via file dialog."""
        store = self._controller.get_store()
        if not store:
            QMessageBox.warning(self, "Exportar",
                                "Nenhuma simulação para exportar.")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Exportar Simulação",
            "simulacao_torpedo.csv",
            "CSV (*.csv);;JSON (*.json);;Todos (*)")
        if not filepath:
            return
        fmt = "json" if filepath.endswith(".json") else "csv"
        idx = len(store) - 1
        result = self._controller.export_simulation(idx, filepath, fmt=fmt)
        if result:
            self.statusBar().showMessage(
                f"Exportado: {result.name}  ({fmt.upper()})")

    def _launch_simulation_dialog(self):
        """Open a modal dialog to configure and launch simulation."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Configurar Simulação")
        dlg.setMinimumWidth(320)

        layout = QFormLayout(dlg)

        # Control mode selector
        combo = QComboBox()
        combo.addItems(["depthHeadingAutopilot", "stepInput"])
        layout.addRow("Modo de controlo:", combo)

        # Depth reference
        sb_z = QDoubleSpinBox()
        sb_z.setRange(0.0, 100.0)
        sb_z.setDecimals(1)
        sb_z.setSuffix("  m")
        sb_z.setValue(float(
            self._controller.get_current_params().get('ref_z', 0.0)))
        layout.addRow("Profundidade desejada:", sb_z)

        # Heading reference
        sb_psi = QDoubleSpinBox()
        sb_psi.setRange(-180.0, 180.0)
        sb_psi.setDecimals(1)
        sb_psi.setSuffix("  °")
        sb_psi.setValue(float(
            self._controller.get_current_params().get('ref_psi', 0.0)))
        layout.addRow("Rumo desejado:", sb_psi)

        # Propeller RPM reference
        _params = self._controller.get_current_params()
        _n_max = float(_params.get('thruster_nMax', 1525.0))
        sb_n = QDoubleSpinBox()
        sb_n.setRange(0.0, _n_max)
        sb_n.setSingleStep(10.0)
        sb_n.setDecimals(0)
        sb_n.setSuffix("  RPM")
        sb_n.setValue(float(_params.get('ref_n', 0.0)))
        layout.addRow("Rotação desejada:", sb_n)

        # Duration
        sb_dur = QDoubleSpinBox()
        sb_dur.setRange(5.0, 300.0)
        sb_dur.setSingleStep(5.0)
        sb_dur.setDecimals(0)
        sb_dur.setValue(self._sim_duration)
        sb_dur.setSuffix("  s")
        layout.addRow("Duração:", sb_dur)

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addRow(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._sim_duration = sb_dur.value()
            self._controller.update_param('ref_n', sb_n.value())
            self._controller.prepare_simulation(
                combo.currentText(),
                sb_z.value(),
                sb_psi.value(),
            )

    def _launch_etapa3_ab_run(self):
        """Etapa 3 — corre Sim A (Cd=0.42) e Sim B (Cd=0.25) em sequência."""
        thread_busy = (self._sim_thread is not None
                       and self._sim_thread.isRunning())
        if self._ab_mode is not None or thread_busy:
            QMessageBox.information(
                self, "Simulação em curso",
                "Já existe uma simulação a correr — aguarde pelo fim.")
            return

        self._btn_simulate.setEnabled(False)
        self._btn_simulate_ab.setEnabled(False)
        self._btn_reset.setEnabled(False)

        self._ab_saved_duration = self._sim_duration
        self._sim_duration = 200.0
        self._ab_mode = "A"

        self.statusBar().showMessage(
            "A correr Sim A (Cd=0.42, stepInput, 200 s)…")
        self._controller.prepare_etapa3_simulation(0.42)

    # ----------------------------------------------------------------------
    # Etapa 4+ — Comparações personalizadas e pré-definidas
    # ----------------------------------------------------------------------

    def _launch_no_vs_with_current(self):
        """Atalho para a comparação pré-definida sem corrente vs com corrente."""
        thread_busy = (self._sim_thread is not None
                       and self._sim_thread.isRunning())
        if (self._ab_mode is not None or self._compare_mode is not None
                or thread_busy):
            QMessageBox.information(
                self, "Simulação em curso",
                "Já existe uma simulação a correr — aguarde pelo fim.")
            return
        cfg_a, cfg_b = self._controller.make_no_vs_with_current_cfgs()
        self._run_compare(cfg_a, cfg_b)

    def _launch_compare_dialog(self):
        """Abre o diálogo modal de configuração e dispara a comparação."""
        thread_busy = (self._sim_thread is not None
                       and self._sim_thread.isRunning())
        if (self._ab_mode is not None or self._compare_mode is not None
                or thread_busy):
            QMessageBox.information(
                self, "Simulação em curso",
                "Já existe uma simulação a correr — aguarde pelo fim.")
            return
        # Pré-preencher com o estado actual do controller (ambos iguais)
        view = self._controller.get_view_state()
        dialog = CompareScenariosDialog(view, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cfg_a, cfg_b = dialog.get_cfgs()
        self._run_compare(cfg_a, cfg_b)

    def _run_compare(self, cfg_a: dict, cfg_b: dict):
        """
        Etapa 4+ — Inicia a state machine de comparação personalizada.
        Corre cfg_a primeiro; ao terminar, dispara cfg_b. No fim, chama
        controller.register_comparison_results para guardar/exportar/emitir.
        """
        self._btn_simulate.setEnabled(False)
        self._btn_simulate_ab.setEnabled(False)
        self._btn_compare_currents.setEnabled(False)
        self._btn_compare_custom.setEnabled(False)
        self._btn_reset.setEnabled(False)

        self._compare_saved_duration = self._sim_duration
        self._sim_duration = 200.0
        self._compare_mode = "A"
        self._compare_cfgs = [cfg_a, cfg_b]
        self._compare_results = []

        self.statusBar().showMessage(
            f"Comparação: a correr Cenário A — '{cfg_a.get('label', 'A')}'…")
        try:
            veh = self._controller.build_compare_instance(cfg_a)
        except ValueError as e:
            QMessageBox.warning(self, "Configuração inválida", str(e))
            self._compare_mode = None
            self._compare_cfgs = None
            self._compare_results = None
            self._restore_buttons_after_sim()
            return
        self._on_simulation_ready(veh)

    def _handle_compare_step(self, simTime, simData):
        """Avança a state machine de comparação (chamado de _on_simulation_done)."""
        cfgs = self._compare_cfgs or []
        results = self._compare_results
        idx = 0 if self._compare_mode == "A" else 1
        if results is None or idx >= len(cfgs):
            return
        cfg = cfgs[idx]
        result = {
            'simTime': simTime,
            'simData': simData,
            'vehicle': self._sim_thread._vehicle if self._sim_thread else None,
            'label': cfg.get('label', f"Cenário {self._compare_mode}"),
            'cfg': cfg,
        }
        results.append(result)

        if self._compare_mode == "A":
            # Dispara Cenário B
            self._compare_mode = "B"
            self.statusBar().showMessage(
                f"Cenário A concluído — a correr Cenário B "
                f"'{cfgs[1].get('label', 'B')}'…")
            try:
                veh_b = self._controller.build_compare_instance(cfgs[1])
            except ValueError as e:
                QMessageBox.warning(self, "Configuração inválida", str(e))
                self._compare_mode = None
                self._compare_cfgs = None
                self._compare_results = None
                self._restore_buttons_after_sim()
                return
            self._on_simulation_ready(veh_b)
            return

        # Cenário B terminou — registar e emitir comparison_ready
        if self._compare_saved_duration is not None:
            self._sim_duration = self._compare_saved_duration
            self._compare_saved_duration = None
        self._compare_mode = None
        result_a, result_b = results[0], results[1]
        self._compare_cfgs = None
        self._compare_results = None
        self._controller.register_comparison_results(result_a, result_b)

    def _on_comparison_ready(self, result_a: dict, result_b: dict):
        """
        Etapa 4+ — Recebe ambos os resultados de uma comparação personalizada
        e popula os widgets visuais (animação 3D dual + ComparativeWidget).
        """
        try:
            params = self._controller.get_current_params()
            L = params.get('L', 1.6)
            diam = params.get('diam', 0.19)

            self._comparative_widget.plot_comparison(
                result_a['simTime'], result_a['simData'],
                result_b['simTime'], result_b['simData'],
                label_A=result_a['label'], label_B=result_b['label'])

            self._viz_widget.run_dual_animation(
                result_a['simTime'], result_a['simData'],
                result_b['simTime'], result_b['simData'],
                L, diam,
                label_A=result_a['label'], label_B=result_b['label'])

            self._right_panel.setCurrentIndex(1)  # Visualização 3D
            self._restore_buttons_after_sim()
            self._btn_export_csv.setEnabled(True)
            csv_a = result_a.get('csv_path')
            csv_b = result_b.get('csv_path')
            self.statusBar().showMessage(
                f"Comparação concluída — '{result_a['label']}' vs "
                f"'{result_b['label']}'. CSVs: "
                f"{csv_a.name if csv_a else '?'}, "
                f"{csv_b.name if csv_b else '?'}")
        except RuntimeError:
            pass  # widget destruído (teardown de testes)

    # ----------------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------------

    def _load_params(self):
        """Populate all spin-boxes with current model values."""
        # Etapa 4 — usa get_view_state() para incluir beta_c_deg + current_*
        params = self._controller.get_view_state()
        self._on_params_updated(params)
        self._current_profile_widget.update_plot(params)
        # Etapa 4+ — primeira pintura dos gráficos analíticos
        self._drag_curve_widget.update_plot(params)
        self._control_response_widget.update_plot(params)
        self.statusBar().showMessage(
            f"Pronto. ({len(params)} parâmetros carregados)")


