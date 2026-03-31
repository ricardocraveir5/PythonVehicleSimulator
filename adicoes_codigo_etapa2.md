# Adições de Código — Etapa 2 (DINAV 2026)

**Autor:** Ricardo Craveiro (1191000@isep.ipp.pt)
**Branch:** `claude/torpedo-parameter-inventory-vtoPN`
**Sessão Claude Code:** `cse_019EH7Fze5noa1tks9nnkYPW`
**Data:** 2026-03-25 (inicial) · 2026-03-28/29 (continuação)

---

## Commit 1 — `feat: torpedo.py — modelo MVC, getters/setters, _recalculate_derived`

**Ficheiro:** `src/python_vehicle_simulator/vehicles/torpedo.py`

### 1.1 Atributos privados no `__init__`

Variáveis que antes eram locais ou públicas foram promovidas a atributos privados com prefixo `_`, para suportar propriedades com validação:

```python
self._L    = 1.6      # length (m)  — private; property in 2B
self._diam = 0.19     # cylinder diameter (m) — private; property in 2B
self._a    = self._L / 2                # semi-axis major
self._b    = self._diam / 2             # semi-axis minor
self._Cd   = 0.42                       # parasitic drag coefficient
self._r44  = 0.3                        # roll inertia factor
self._T_surge    = 20
self._T_sway     = 20
self._T_heave    = self._T_sway         # A7: acoplado a T_sway
self._zeta_roll  = 0.3
self._zeta_pitch = 0.8
self._T_yaw      = 1
self._K_nomoto   = 5.0/20.0
self._T_nomoto   = self._T_yaw          # A8: acoplado a T_yaw
self._r_max      = 5.0 * math.pi / 180
```

Referências de missão também privadas:
```python
self._ref_z   = r_z
self._ref_psi = r_psi
self._ref_n   = r_rpm
self._V_c     = V_current
self._beta_c  = beta_current * self.D2R
```

### 1.2 Propriedades com validação física

**Geometria (com recálculo em cascata):**
```python
@property
def L(self): return self._L

@L.setter
def L(self, valor):
    if valor <= 0:
        raise ValueError("L deve ser > 0")
    if valor <= self._diam:
        raise ValueError("L deve ser maior do que o diâmetro (diam)")
    self._L = valor
    self._a = valor / 2
    self._recalculate_derived()

@property
def diam(self): return self._diam

@diam.setter
def diam(self, valor):
    if valor <= 0:
        raise ValueError("diam deve ser > 0")
    if valor >= self._L:
        raise ValueError("diam deve ser < L")
    self._diam = valor
    self._b = valor / 2
    self._recalculate_derived()

@property
def massa(self):
    return (4/3 * math.pi * self.rho * self._a * self._b**2)
```

**Anomalia A7 — acoplamento T_sway → T_heave:**
```python
@T_sway.setter
def T_sway(self, valor):
    if valor <= 0:
        raise ValueError("T_sway deve ser > 0")
    self._T_sway = valor
    self._T_heave = valor   # ← acoplamento documentado (Fossen 2021)
```

**Anomalia A8 — acoplamento T_yaw → T_nomoto:**
```python
@T_yaw.setter
def T_yaw(self, valor):
    if valor <= 0:
        raise ValueError("T_yaw deve ser > 0")
    self._T_yaw = valor
    self._T_nomoto = valor  # ← acoplamento documentado (Fossen 2021)
```

### 1.3 Métodos de acesso às barbatanas e propulsor

```python
def get_fin_CL(self, index): ...
def set_fin_CL(self, index, valor): ...
def get_fin_area(self, index): ...
def set_fin_area(self, index, valor): ...
def get_fin_position(self, index): ...
def set_fin_position(self, index, valor): ...
def get_thruster_nMax(self): return self.actuators[4].nMax
def set_thruster_nMax(self, valor): ...
```

### 1.4 `_recalculate_derived()`

Recalcula toda a cadeia de parâmetros derivados após mudança de geometria ou coeficientes físicos:

```python
def _recalculate_derived(self):
    g = 9.81
    self.S    = 0.7 * self._L * self._diam
    self.CD_0 = self._Cd * math.pi * self._b**2 / self.S

    m      = 4/3 * math.pi * self.rho * self._a * self._b**2
    Ix     = (2/5) * m * self._b**2
    Iy     = (1/5) * m * (self._a**2 + self._b**2)
    Iz     = Iy
    MRB_CG = np.diag([m, m, m, Ix, Iy, Iz])
    H_rg   = Hmtrx(self.r_bg)
    self.MRB = H_rg.T @ MRB_CG @ H_rg

    self.W = m * g
    self.B = self.W

    MA_44   = self._r44 * Ix
    e       = math.sqrt(1 - (self._b / self._a)**2)
    # ... k-factors de Lamb ...
    self.MA   = np.diag([m*k1, m*k2, m*k2, MA_44, k_prime*Iy, k_prime*Iy])
    self.M    = self.MRB + self.MA
    self.Minv = np.linalg.inv(self.M)

    dz = self.r_bg[2] - self.r_bb[2]
    self.w_roll  = math.sqrt(self.W * dz / self.M[3][3])
    self.w_pitch = math.sqrt(self.W * dz / self.M[4][4])

    if hasattr(self, 'actuators'):
        for i in range(4):
            self.actuators[i].R[0] = -self._a
```

### 1.5 `get_all_params()` e `set_from_dict()`

```python
def get_all_params(self):
    return {
        'L': self._L, 'diam': self._diam, 'massa': self.massa,
        'Cd': self._Cd, 'r44': self._r44,
        'T_surge': self._T_surge, 'T_sway': self._T_sway,
        'T_heave': self._T_heave, 'zeta_roll': self._zeta_roll,
        'zeta_pitch': self._zeta_pitch, 'T_yaw': self._T_yaw,
        'K_nomoto': self._K_nomoto, 'T_nomoto': self._T_nomoto,
        'r_max': self._r_max, 'ref_z': self._ref_z,
        'ref_psi': self._ref_psi, 'ref_n': self._ref_n,
        'V_c': self._V_c, 'beta_c': self._beta_c,
        'fin_CL': [self.get_fin_CL(i) for i in range(4)],
        'fin_area': [self.get_fin_area(i) for i in range(4)],
        'thruster_nMax': self.get_thruster_nMax(),
        # ... (todos os parâmetros dos controladores)
    }

def set_from_dict(self, params_dict):
    for key, value in params_dict.items():
        try:
            if key in ('massa', 'T_heave', 'T_nomoto'):
                logging.warning("Parâmetro '%s' é read-only e foi ignorado.", key)
            elif hasattr(self, key):
                setattr(self, key, value)
        except ValueError as e:
            raise ValueError(f"Parâmetro '{key}': {str(e)}")
```

---

## Commit 2 — `feat: GUI MVC — torpedo_controller, torpedo_gui, torpedo_viz, main_gui (PyQt6)`

**Ficheiros novos:**
- `src/python_vehicle_simulator/gui/torpedo_controller.py`
- `src/python_vehicle_simulator/gui/torpedo_gui.py`
- `src/python_vehicle_simulator/gui/torpedo_viz.py`
- `src/python_vehicle_simulator/gui/main_gui.py`

### 2.1 `TorpedoController` — 4 sinais Qt

```python
class TorpedoController(QObject):
    params_updated          = pyqtSignal(dict)
    simulation_ready        = pyqtSignal(object)
    validation_error        = pyqtSignal(str)
    param_dependency_updated = pyqtSignal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = torpedo()
        self._last_params = self._model.get_all_params()
```

### 2.2 `update_param()` com despacho especial

```python
def update_param(self, nome, valor):
    try:
        if nome.startswith('fin_CL_'):
            idx = int(nome.split('_')[-1])
            self._model.set_fin_CL(idx, valor)
        elif nome.startswith('fin_area_'):
            idx = int(nome.split('_')[-1])
            self._model.set_fin_area(idx, valor)
        elif nome == 'thruster_nMax':
            self._model.set_thruster_nMax(valor)
        elif nome in ('massa', 'T_heave', 'T_nomoto'):
            self.validation_error.emit(f"[{nome}] Parâmetro é só de leitura.")
            return
        else:
            setattr(self._model, nome, valor)
    except ValueError as e:
        self.validation_error.emit(f"[{nome}] {str(e)}")
        return

    new_params = self._model.get_all_params()
    self.params_updated.emit(new_params)
    self._check_dependencies(new_params)
    self._last_params = new_params
```

### 2.3 `_check_dependencies()` — detecção de acoplamentos

```python
def _check_dependencies(self, new_params: dict):
    dependent_keys = ('T_heave', 'T_nomoto', 'massa')
    for key in dependent_keys:
        old = self._last_params.get(key)
        new = new_params.get(key)
        if new != old:
            self.param_dependency_updated.emit(key, float(new))
```

### 2.4 `prepare_simulation()` — instância configurada para mainLoop

```python
def prepare_simulation(self, control_mode, ref_z, ref_psi):
    p = self._model.get_all_params()
    new_instance = torpedo(control_mode, ref_z, ref_psi,
                           p['ref_n'], p['V_c'], beta_c_deg)
    new_instance.set_from_dict(overrides)
    for i, cl   in enumerate(p['fin_CL']):   new_instance.set_fin_CL(i, cl)
    for i, area in enumerate(p['fin_area']): new_instance.set_fin_area(i, area)
    new_instance.set_thruster_nMax(p['thruster_nMax'])
    self.simulation_ready.emit(new_instance)
```

### 2.5 `TorpedoGUI` — QTabWidget com 3 separadores

```python
class TorpedoGUI(QMainWindow):
    def __init__(self, controller: TorpedoController):
        super().__init__()
        self._controller = controller
        self.param_widgets: dict[str, QDoubleSpinBox] = {}

        tabs = QTabWidget()
        tabs.addTab(self._build_tab_params(),  "Parâmetros")
        tabs.addTab(self._build_tab_viz(),     "Visualização 3D")
        tabs.addTab(self._build_tab_states(),  "Estados")
        self.setCentralWidget(tabs)
```

### 2.6 `_add_spinboxes()` — fábrica de QDoubleSpinBox

Cria um `QDoubleSpinBox` por especificação de tuplo e regista em `self.param_widgets`:

```python
def _add_spinboxes(self, layout, specs):
    for nome, label, unidade, vmin, vmax, step, decimals, readonly, tooltip in specs:
        sb = QDoubleSpinBox()
        sb.setRange(vmin, vmax)
        sb.setSingleStep(step)
        sb.setDecimals(decimals)
        sb.setReadOnly(readonly)
        sb.setToolTip(tooltip)
        if unidade:
            sb.setSuffix(f"  {unidade}")
        val = self._controller.get_current_params().get(nome, 0.0)
        sb.setValue(float(val))
        if not readonly:
            sb.valueChanged.connect(
                lambda v, n=nome: self._controller.update_param(n, v))
        layout.addRow(f"{label}:", sb)
        self.param_widgets[nome] = sb
```

### 2.7 `_on_dependency_updated()` — realce azul

```python
def _on_dependency_updated(self, nome: str, valor: float):
    if nome in self.param_widgets:
        w = self.param_widgets[nome]
        w.setValue(valor)
        w.setStyleSheet("background-color: #cce5ff;")
        QTimer.singleShot(2000, lambda: w.setStyleSheet(""))
```

### 2.8 `_on_simulation_done()` — despacho para os dois separadores

```python
def _on_simulation_done(self, simTime, simData):
    p = self._controller.get_current_params()
    self._viz_widget.run_animation(simTime, simData, p['L'], p['diam'])
    self._states_widget.plot_states(simTime, simData)
```

### 2.9 `SimulationThread.run()` — mainLoop em QThread separada

```python
class SimulationThread(QThread):
    finished = pyqtSignal(object, object)
    error    = pyqtSignal(str)

    def run(self):
        try:
            from python_vehicle_simulator.lib.mainLoop import simulate
            simTime, simData = simulate(self._N, self._sampleTime, self._vehicle)
            self.finished.emit(simTime, simData)
        except Exception as exc:
            self.error.emit(str(exc))
```

### 2.10 Geometria 3D — matriz de rotação ZYX (Fossen 2021)

```python
def _rot_matrix(phi, theta, psi) -> np.ndarray:
    """Matriz de rotação ZYX: corpo → NED."""
    cp, sp = math.cos(phi),   math.sin(phi)
    ct, st = math.cos(theta), math.sin(theta)
    cy, sy = math.cos(psi),   math.sin(psi)
    Rz = np.array([[cy, -sy, 0], [sy,  cy, 0], [0, 0, 1]])
    Ry = np.array([[ct,  0, st], [0,   1,  0], [-st, 0, ct]])
    Rx = np.array([[1,   0,  0], [0,  cp, -sp], [0, sp, cp]])
    return Rz @ Ry @ Rx
```

### 2.11 `_build_body_geometry()` e `_build_fin_geometry()`

```python
def _build_body_geometry(L, diam, n_rings=10, n_pts=24) -> list:
    """Secções transversais do elipsóide no frame do corpo."""
    a  = L / 2
    xs = np.linspace(-a * 0.97, a * 0.97, n_rings)
    return [_ellipse_ring(a, diam / 2, x, n_pts) for x in xs]

def _build_fin_geometry(L, diam) -> list:
    """Quatro barbatanas (rectângulos) no frame do corpo."""
    a, b   = L / 2, diam / 2
    fin_h  = b * 2.8
    fin_c  = a * 0.40
    x0, x1 = -a, -a + fin_c
    # topo, fundo, estibordo, bombordo
    return [_rect(...), _rect(...), _rect(...), _rect(...)]
```

### 2.12 `TorpedoVizWidget._update()` — câmara segue o torpedo

```python
def _update(fi: int):
    ax.cla()
    ax.plot(x, y, z, 'b-', alpha=0.12, lw=0.7)          # trajectória completa
    ax.plot(x[:fi+1], y[:fi+1], z[:fi+1], 'b-', alpha=0.55, lw=1.8)

    pos = np.array([x[fi], y[fi], z[fi]])
    R   = _rot_matrix(phi[fi], th[fi], psi[fi])

    for ring in body_rings:
        pw = _transform(ring, R, pos)
        ax.plot3D(pw[0], pw[1], pw[2], color='#2e86c1', lw=0.9)

    # Câmara segue o torpedo — limites centrados na posição actual
    ax.set_xlim(x[fi] - view_r, x[fi] + view_r)
    ax.set_ylim(y[fi] - view_r, y[fi] + view_r)
    ax.set_zlim(z[fi] + view_r, z[fi] - view_r)   # z invertido (prof. ↓)
```

### 2.13 `TorpedoStatesWidget.plot_states()` — 9 subplots

```python
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

def plot_states(self, simTime, simData):
    t = simTime[:, 0]
    self._fig.clear()
    axs = self._fig.subplots(3, 3)
    for r, row in enumerate(self._SPECS):
        for c, (col, title, ylabel, to_deg) in enumerate(row):
            sig = simData[:, col]
            if to_deg: sig = np.degrees(sig)
            axs[r][c].plot(t, sig, color=self._COLORS[r][c], lw=1.3)
            axs[r][c].set_title(title, fontsize=8)
    self._canvas.draw()
```

---

## Commit 3 — `feat: testes, log, HOWTO e compatibilidade multi-plataforma`

**Ficheiros modificados/criados:**
- `tests/test_integration_gui.py` (novo)
- `src/python_vehicle_simulator/vehicles/torpedo.py` (fix cross-platform)
- `HOWTO.md` (criado)
- `log_etapa2_ricardo_craveiro.md` (criado)

### 3.1 Fixture MVC e patch QMessageBox

```python
@pytest.fixture
def mvc(qapp):
    ctrl = TorpedoController()
    gui  = TorpedoGUI(ctrl)
    with patch("python_vehicle_simulator.gui.torpedo_gui.QMessageBox") as MockMB:
        MockMB.warning = MagicMock()
        MockMB.critical = MagicMock()
        yield ctrl, gui, qapp
```

### 3.2 Cenários de integração (1–7)

```python
def test_default_params_loaded(mvc):           # parâmetros padrão na GUI
def test_update_param_updates_widget(mvc):     # update_param reflecte no widget
def test_validation_error_on_invalid(mvc):     # valor inválido emite validation_error
def test_dependency_T_sway_updates_T_heave(mvc): # A7: T_sway→T_heave
def test_dependency_T_yaw_updates_T_nomoto(mvc): # A8: T_yaw→T_nomoto
def test_reset_to_defaults(mvc):               # reset restaura valores padrão
def test_prepare_simulation_emits_ready(mvc):  # prepare_simulation emite simulation_ready
```

### 3.3 Fix `sys.exit` → `ValueError` (compatibilidade multi-plataforma)

No `torpedo.__init__`, substituídas as chamadas `sys.exit()` por `raise ValueError(...)`:

```python
# Antes (quebrava testes e GUI):
# sys.exit('RPM fora do intervalo')

# Depois:
if r_rpm < 0.0 or r_rpm > prop.nMax:
    raise ValueError(f"RPM deve estar no intervalo [0, {prop.nMax}]")

if r_z > 100.0 or r_z < 0.0:
    raise ValueError("Profundidade desejada deve estar entre 0 e 100 m")
```

---

## Commit 4 — `feat: expor K_nomoto, r_max, zeta_roll/pitch e ref_n na GUI`

**Ficheiros modificados:**
- `src/python_vehicle_simulator/gui/torpedo_gui.py`
- `tests/test_integration_gui.py`

### 4.1 `zeta_roll` e `zeta_pitch` no grupo "Físicos"

```python
# Em _build_group_physical(), após T_surge:
('zeta_roll',  'ζ_roll',  '—', 0.0, 1.0, 0.01, 3, False,
 'Amortecimento relativo em rolamento (—)\nLimites: 0.0 – 1.0'),
('zeta_pitch', 'ζ_pitch', '—', 0.0, 1.0, 0.01, 3, False,
 'Amortecimento relativo em arfagem (—)\nLimites: 0.0 – 1.0'),
```

### 4.2 `K_nomoto` e `r_max` no grupo "Controlo de Rumo"

```python
# Em _build_group_heading_ctrl(), após T_yaw:
('K_nomoto', 'K_nomoto', '—',   0.001, 10.0, 0.001, 4, False,
 'Ganho de Nomoto K (—)\nK = r_max / δ_max  (Fossen 2021, §16.3)\nLimites: > 0'),
('r_max',    'r_max',   'rad/s', 0.001, 1.0,  0.001, 4, False,
 'Taxa máxima de guinada permitida (rad/s)\nLimites: > 0  (padrão ≈ 0.087 rad/s = 5 °/s)'),
```

### 4.3 `ref_n` no diálogo de lançamento da simulação

```python
# Em _launch_simulation_dialog(), após sb_psi:
_params = self._controller.get_current_params()
_n_max  = float(_params.get('thruster_nMax', 1525.0))
sb_n = QDoubleSpinBox()
sb_n.setRange(0.0, _n_max)
sb_n.setSingleStep(10.0)
sb_n.setDecimals(0)
sb_n.setSuffix("  RPM")
sb_n.setValue(float(_params.get('ref_n', 0.0)))
layout.addRow("Rotação desejada:", sb_n)

# No bloco accepted:
if dlg.exec() == QDialog.DialogCode.Accepted:
    self._sim_duration = sb_dur.value()
    self._controller.update_param('ref_n', sb_n.value())
    self._controller.prepare_simulation(combo.currentText(),
                                        sb_z.value(), sb_psi.value())
```

### 4.4 Três novos testes (cenários 8–10)

```python
def test_nomoto_and_rmax_in_gui(mvc):
    ctrl, gui, app = mvc
    assert "K_nomoto" in gui.param_widgets
    assert "r_max"    in gui.param_widgets
    assert gui.param_widgets["K_nomoto"].value() > 0
    assert gui.param_widgets["r_max"].value() > 0

def test_roll_pitch_damping_in_gui(mvc):
    ctrl, gui, app = mvc
    assert "zeta_roll"  in gui.param_widgets
    assert "zeta_pitch" in gui.param_widgets
    assert abs(gui.param_widgets["zeta_roll"].value()  - 0.3) < 1e-6
    assert abs(gui.param_widgets["zeta_pitch"].value() - 0.8) < 1e-6

def test_geometry_dependency_mass(mvc):
    ctrl, gui, app = mvc
    original_mass = ctrl._model.massa
    ctrl.update_param("L", 2.0)
    app.processEvents()
    new_mass = ctrl._model.massa
    assert new_mass > original_mass
```

**Total de testes após commit 4: 39 (todos a passar)**

---

## Resumo de ficheiros novos/modificados

| Ficheiro | Tipo | Commit |
|---|---|---|
| `src/.../vehicles/torpedo.py` | Modificado | 1, 3 |
| `src/.../gui/torpedo_controller.py` | Novo | 2 |
| `src/.../gui/torpedo_gui.py` | Novo (modificado em 4) | 2, 4 |
| `src/.../gui/torpedo_viz.py` | Novo | 2 |
| `src/.../gui/main_gui.py` | Novo | 2 |
| `tests/test_integration_gui.py` | Novo (modificado em 4) | 3, 4 |
| `HOWTO.md` | Novo | 3 |
| `log_etapa2_ricardo_craveiro.md` | Novo | 3 |
| `requirements_gui.txt` | Novo | 2 |
