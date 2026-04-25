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

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QTabWidget,
    QHBoxLayout, QVBoxLayout, QPushButton,
    QStatusBar, QMenuBar, QGroupBox,
    QFormLayout, QDoubleSpinBox, QScrollArea,
    QDialog, QComboBox, QLabel, QDialogButtonBox,
    QMessageBox, QFileDialog,
)

from .torpedo_viz import (SimulationThread, TorpedoStatesWidget,
                          TorpedoVizWidget, TorpedoControlsWidget,
                          ComparativeWidget, Etapa3GraphsWidget)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPalette, QColor


# ---------------------------------------------------------------------------
# Helper: read-only spin-box style
# ---------------------------------------------------------------------------
_READONLY_STYLE = "background-color: #d0d0d0;"


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
        self._btn_reset       = QPushButton("Repor Defaults")
        self._btn_validate    = QPushButton("Validar")
        self._btn_simulate    = QPushButton("Simular")
        self._btn_simulate_ab = QPushButton("Simular A e B (Etapa 3)")
        self._btn_export_csv  = QPushButton("Exportar CSV")
        self._btn_export_csv.setEnabled(False)
        for btn in (self._btn_reset, self._btn_validate, self._btn_simulate,
                    self._btn_simulate_ab, self._btn_export_csv):
            btn_layout.addWidget(btn)
        root_layout.addLayout(btn_layout)

        # Simulation state
        self._sim_duration: float = 20.0   # seconds (overridden by dialog)
        self._sim_thread = None             # SimulationThread instance

        # Etapa 3 A/B run state machine
        self._ab_mode: str | None = None       # None | "A" | "B"
        self._ab_saved_duration: float | None = None

        # ------------------------------------------------------------------
        # Signal → slot connections
        # ------------------------------------------------------------------
        self._controller.params_updated.connect(self._on_params_updated)
        self._controller.validation_error.connect(self._on_validation_error)
        self._controller.simulation_ready.connect(self._on_simulation_ready)
        self._controller.param_dependency_updated.connect(
            self._on_dependency_updated)

        self._btn_reset.clicked.connect(self._controller.reset_to_defaults)
        self._btn_validate.clicked.connect(self._load_params)
        self._btn_simulate.clicked.connect(self._launch_simulation_dialog)
        self._btn_simulate_ab.clicked.connect(self._launch_etapa3_ab_run)
        self._btn_export_csv.clicked.connect(self._export_last_csv)

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

        # Etapa 3 A/B: passo mais fino replica fielmente o script (dt=0.02)
        if self._ab_mode is not None:
            sample_time = 0.02
        else:
            sample_time = 0.05
        N = max(1, int(self._sim_duration / sample_time))

        self._sim_thread = SimulationThread(vehicle, N, sample_time, parent=self)
        self._sim_thread.finished.connect(self._on_simulation_done)
        self._sim_thread.error.connect(self._on_simulation_error)
        self._sim_thread.start()

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
                self._btn_simulate.setEnabled(True)
                self._btn_simulate_ab.setEnabled(True)
                self._btn_reset.setEnabled(True)
                self.statusBar().showMessage(
                    "Etapa 3 concluída — A e B a correr lado a lado em 3D; "
                    "tab Comparação também populada.")
                return

            # Modo normal (single-sim)
            self._btn_simulate.setEnabled(True)
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
            self._btn_simulate.setEnabled(True)
            if self._ab_mode is not None:
                stage = self._ab_mode
                if self._ab_saved_duration is not None:
                    self._sim_duration = self._ab_saved_duration
                    self._ab_saved_duration = None
                self._ab_mode = None
                self._btn_simulate_ab.setEnabled(True)
                self._btn_reset.setEnabled(True)
                self.statusBar().showMessage(
                    f"Erro em Sim {stage}: {msg} — corrida A/B abortada.")
                QMessageBox.warning(self, "Erro na Simulação A/B", msg)
                return
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
    # Internal helpers
    # ----------------------------------------------------------------------

    def _load_params(self):
        """Populate all spin-boxes with current model values."""
        params = self._controller.get_current_params()
        self._on_params_updated(params)
        self.statusBar().showMessage(
            f"Pronto. ({len(params)} parâmetros carregados)")


