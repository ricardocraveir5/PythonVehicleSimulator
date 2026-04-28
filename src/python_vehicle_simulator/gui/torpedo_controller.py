"""
torpedo_controller.py — MVC Controller for the torpedo vehicle model.

Connects the View to the Model (torpedo.py) without either knowing
about the other. Exposes Qt signals for parameter updates, simulation
readiness, validation errors, and dependency notifications.

Etapa 3 additions: simulation store, CSV/JSON export, comparative analysis.

Original author: Thor I. Fossen
Additions:       Ricardo Craveiro (1191000@isep.ipp.pt)
DINAV 2026 — Etapa 2/3
"""

import math
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from python_vehicle_simulator.vehicles.torpedo import torpedo
from python_vehicle_simulator.gui.export_results import export_csv, export_json
from python_vehicle_simulator.lib.environment import (
    LinearProfile, PowerLawProfile, LogarithmicProfile, GaussMarkovCurrent,
)


class TorpedoController(QObject):
    """
    MVC Controller for torpedo vehicle parameters and simulation.

    Signals
    -------
    params_updated(dict)
        Emitted after any successful parameter change, carrying the
        full current parameter dictionary.
    simulation_ready(object)
        Emitted when a new torpedo instance is ready to simulate,
        carrying that instance as payload.
    validation_error(str)
        Emitted when a setter raises ValueError; carries the message.
        When triggered from update_param(), the message is prefixed with
        ``[param_name] `` so the View can identify the offending widget.
    param_dependency_updated(str, float)
        Emitted for each dependent parameter that changed as a side
        effect of a setter (e.g. T_heave after T_sway is set).
    """

    # Modos de controlo aceites pelo torpedo
    _VALID_MODES = frozenset({'depthHeadingAutopilot', 'stepInput'})

    params_updated           = pyqtSignal(dict)
    simulation_ready         = pyqtSignal(object)
    validation_error         = pyqtSignal(str)
    param_dependency_updated = pyqtSignal(str, float)
    store_updated            = pyqtSignal(list)        # Etapa 3: list of labels
    # Etapa 4+ — payload (sim_a: dict, sim_b: dict) com simTime, simData,
    # vehicle, label, csv_path e a configuração usada (cfg).
    comparison_ready         = pyqtSignal(dict, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = torpedo()
        self._last_params = self._model.get_all_params()

        # Etapa 3 — simulation store
        self._sim_store: list[dict] = []

        # Etapa 4 — estado do CurrentModel seleccionado na GUI. Não vive no
        # torpedo (que só guarda a instância activa) e é independente das
        # chaves de get_all_params(). Default 'Constante' ⇒ caminho legado.
        self._current_model_state: dict = {
            'current_model_selected': 'Constante',
            'current_V_surface':      0.5,
            'current_z_ref':          10.0,
            'current_V_star':         0.05,
            'current_z_0':            0.01,
            'current_kappa':          0.41,
            'current_mu':             0.5,
            'current_sigma':          0.1,
            'current_Vc0':            0.0,
            'current_seed':           42,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_current_params(self):
        """Return a dict with all current model parameters."""
        return self._model.get_all_params()

    def get_view_state(self) -> dict:
        """
        Etapa 4 — Devolve o snapshot completo para a View: parâmetros do
        torpedo + chaves derivadas (beta_c_deg) + estado da UI (current_*).
        Equivalente ao payload de params_updated, mas em chamada síncrona.
        """
        return self._view_params()

    def update_param(self, nome, valor):
        """
        Apply *valor* to the parameter *nome* on the Model.

        Special cases:
          - ``fin_CL_N``   → calls set_fin_CL(N, valor)
          - ``fin_area_N`` → calls set_fin_area(N, valor)
          - ``thruster_nMax`` → calls set_thruster_nMax(valor)
          - ``beta_c_deg`` → converte de graus para radianos e chama o
            setter ``beta_c`` do modelo (Etapa 4).
          - ``current_*`` / ``current_model_selected`` → estado interno do
            controller, não toca no torpedo (Etapa 4).

        On ValueError  → emits validation_error(message).
        On success     → emits params_updated(full_dict) and
                         calls _check_dependencies().
        """
        # Etapa 4 — beta_c em graus (UX): converte e delega no setter em rad.
        if nome == 'beta_c_deg':
            try:
                self._model.beta_c = float(valor) * (math.pi / 180.0)
            except ValueError as e:
                self.validation_error.emit(f"[{nome}] {str(e)}")
                return
            self._emit_view_params()
            return

        # Etapa 4 — selector e parâmetros do CurrentModel (estado da UI).
        if nome in self._current_model_state:
            self._current_model_state[nome] = (
                int(valor) if nome == 'current_seed' else valor)
            self._emit_view_params()
            return

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
                # read-only derived params — notify caller with param prefix
                self.validation_error.emit(
                    f"[{nome}] Parâmetro é só de leitura.")
                return
            else:
                setattr(self._model, nome, valor)
        except ValueError as e:
            self.validation_error.emit(f"[{nome}] {str(e)}")
            return

        new_params = self._model.get_all_params()
        self.params_updated.emit(self._view_params(new_params))
        self._check_dependencies(new_params)
        self._last_params = new_params

    def _view_params(self, base: dict | None = None) -> dict:
        """
        Etapa 4 — Dict completo para a View: parâmetros do torpedo +
        chaves derivadas (beta_c_deg) + estado da UI (current_*).

        Os consumidores existentes do sinal params_updated continuam a
        receber todas as chaves originais; apenas se acrescentam novas.
        """
        p = dict(base if base is not None else self._model.get_all_params())
        p['beta_c_deg'] = p['beta_c'] * (180.0 / math.pi)
        p.update(self._current_model_state)
        return p

    def _emit_view_params(self):
        """Helper: actualiza _last_params e emite o dict estendido."""
        self._last_params = self._model.get_all_params()
        self.params_updated.emit(self._view_params(self._last_params))

    def _build_current_model(self):
        """
        Etapa 4 — Instancia o CurrentModel correspondente ao estado actual
        da UI. Devolve None para 'Constante' (torpedo cai no caminho legado
        V_c/beta_c constantes).
        """
        s = self._current_model_state
        beta_c_rad = self._model.beta_c
        tipo = s['current_model_selected']
        if tipo == 'Constante':
            return None
        if tipo == 'Linear':
            return LinearProfile(
                s['current_V_surface'], s['current_z_ref'], beta_c_rad)
        if tipo == 'Lei 1/7':
            return PowerLawProfile(
                s['current_V_surface'], s['current_z_ref'], beta_c_rad)
        if tipo == 'Logarítmico':
            return LogarithmicProfile(
                V_star=s['current_V_star'], z_0=s['current_z_0'],
                beta_c=beta_c_rad, kappa=s['current_kappa'])
        if tipo == 'Gauss-Markov':
            return GaussMarkovCurrent(
                mu=s['current_mu'], sigma=s['current_sigma'],
                V_c0=s['current_Vc0'], beta_c=beta_c_rad,
                rng_seed=int(s['current_seed']))
        raise ValueError(
            f"Tipo de modelo de corrente desconhecido: {tipo!r}")

    def prepare_simulation(self, control_mode, ref_z, ref_psi):
        """
        Create a NEW torpedo instance configured with the current
        parameters and the supplied mission settings.

        Parameters
        ----------
        control_mode : str
            ``'depthHeadingAutopilot'`` or ``'stepInput'``.
        ref_z : float
            Desired depth (m), 0–100.
        ref_psi : float
            Desired heading (deg).

        Emits simulation_ready(new_instance) on success, or
        validation_error(message) on failure.
        """
        if control_mode not in self._VALID_MODES:
            self.validation_error.emit(
                f"Modo de controlo inválido: '{control_mode}'. "
                f"Modos aceites: {sorted(self._VALID_MODES)}")
            return

        try:
            p = self._model.get_all_params()
            ref_n = p['ref_n']
            V_c   = p['V_c']
            # beta_c stored in radians internally; expose in degrees for
            # the torpedo() constructor which multiplies by D2R
            beta_c_deg = p['beta_c'] * (180.0 / 3.141592653589793)

            new_instance = torpedo(
                control_mode, ref_z, ref_psi, ref_n, V_c, beta_c_deg,
                current_model=self._build_current_model(),
            )

            # Propagate all non-constructor parameters via set_from_dict,
            # skipping keys managed by the constructor itself.
            constructor_keys = {
                'ref_z', 'ref_psi', 'ref_n', 'V_c', 'beta_c',
                'massa', 'T_heave', 'T_nomoto',
                'fin_CL', 'fin_area', 'thruster_nMax',
                'current_model_type',
            }
            overrides = {
                k: v for k, v in p.items()
                if k not in constructor_keys
            }
            new_instance.set_from_dict(overrides)

            # Restore fin CL, area and thruster nMax individually
            for i, cl in enumerate(p['fin_CL']):
                new_instance.set_fin_CL(i, cl)
            for i, area in enumerate(p['fin_area']):
                new_instance.set_fin_area(i, area)
            new_instance.set_thruster_nMax(p['thruster_nMax'])

        except (ValueError, Exception) as e:
            self.validation_error.emit(
                f"Erro ao preparar simulação: {str(e)}")
            return

        self.simulation_ready.emit(new_instance)

    def prepare_etapa3_simulation(self, cd_value: float):
        """
        Etapa 3 — Prepare a stepInput simulation with a Cd override applied
        only to the NEW torpedo instance; the internal model is never mutated.

        Used by the "Simular A e B (Etapa 3)" GUI button to run a pair of
        simulations (Cd=0.42 then Cd=0.25) without clobbering the Cd value
        currently shown in the Cd spin-box.

        Emits simulation_ready(new_instance) on success, or
        validation_error(message) if cd_value is out of range [0.1, 0.5].
        """
        if not (0.1 <= cd_value <= 0.5):
            self.validation_error.emit(
                f"[Cd] Cd deve estar entre 0.1 e 0.5 (recebido {cd_value}).")
            return

        try:
            p = self._model.get_all_params()
            ref_n = p['ref_n']
            V_c   = p['V_c']
            beta_c_deg = p['beta_c'] * (180.0 / 3.141592653589793)

            new_instance = torpedo(
                "stepInput", 0.0, 0.0, ref_n, V_c, beta_c_deg,
                current_model=self._build_current_model(),
            )

            constructor_keys = {
                'ref_z', 'ref_psi', 'ref_n', 'V_c', 'beta_c',
                'massa', 'T_heave', 'T_nomoto',
                'fin_CL', 'fin_area', 'thruster_nMax',
                'Cd',
                'current_model_type',
            }
            overrides = {
                k: v for k, v in p.items()
                if k not in constructor_keys
            }
            new_instance.set_from_dict(overrides)

            for i, cl in enumerate(p['fin_CL']):
                new_instance.set_fin_CL(i, cl)
            for i, area in enumerate(p['fin_area']):
                new_instance.set_fin_area(i, area)
            new_instance.set_thruster_nMax(p['thruster_nMax'])

            new_instance.Cd = cd_value

        except (ValueError, Exception) as e:
            self.validation_error.emit(
                f"Erro ao preparar simulação Etapa 3: {str(e)}")
            return

        self.simulation_ready.emit(new_instance)

    # ------------------------------------------------------------------
    # Etapa 4+ — Comparação personalizada de 2 cenários
    # ------------------------------------------------------------------

    # Directoria por defeito para exportar CSVs comparativos.
    # Resolução: gui/torpedo_controller.py → gui → python_vehicle_simulator → src → <repo>
    _DEFAULT_COMPARE_DIR = Path(__file__).resolve().parents[3] / 'etapa4'

    def build_compare_instance(self, cfg: dict):
        """
        Etapa 4+ — Constrói uma instância torpedo configurada para uma das
        duas pernas de uma comparação. cfg suporta as chaves:

            - 'label': str  (apenas usado para exibição; ignorado aqui)
            - 'control_mode': 'depthHeadingAutopilot' | 'stepInput'
            - 'ref_z', 'ref_psi', 'ref_n', 'V_c', 'beta_c_deg': overrides
              dos parâmetros do construtor (em graus para psi e beta_c)
            - 'current_model': CurrentModel | None  (já instanciado)
            - 'overrides': dict  (parâmetros extra aplicados via set_from_dict
              após construção e propagação dos params actuais)

        Reusa a mesma lógica de prepare_simulation: parte do snapshot actual
        do modelo e aplica overrides por cima. Devolve a instância (não
        emite simulation_ready — é a GUI que decide quando lançar a thread).
        """
        p = self._model.get_all_params()

        control_mode = cfg.get('control_mode', 'depthHeadingAutopilot')
        if control_mode not in self._VALID_MODES:
            raise ValueError(
                f"Modo de controlo inválido: {control_mode!r}")

        ref_z      = cfg.get('ref_z', p['ref_z'])
        ref_psi    = cfg.get('ref_psi', p['ref_psi'])
        ref_n      = cfg.get('ref_n', p['ref_n'])
        V_c        = cfg.get('V_c', p['V_c'])
        beta_c_deg = cfg.get('beta_c_deg',
                             p['beta_c'] * (180.0 / math.pi))

        veh = torpedo(
            control_mode, ref_z, ref_psi, ref_n, V_c, beta_c_deg,
            current_model=cfg.get('current_model'),
        )

        # Propagar todos os params actuais (excepto chaves do construtor)
        constructor_keys = {
            'ref_z', 'ref_psi', 'ref_n', 'V_c', 'beta_c',
            'massa', 'T_heave', 'T_nomoto',
            'fin_CL', 'fin_area', 'thruster_nMax',
            'current_model_type',
        }
        base = {k: v for k, v in p.items() if k not in constructor_keys}
        veh.set_from_dict(base)

        overrides = cfg.get('overrides') or {}
        if overrides:
            # filtra chaves do construtor para evitar erro/redundância
            safe = {k: v for k, v in overrides.items()
                    if k not in constructor_keys}
            veh.set_from_dict(safe)

        for i, cl in enumerate(p['fin_CL']):
            veh.set_fin_CL(i, cl)
        for i, area in enumerate(p['fin_area']):
            veh.set_fin_area(i, area)
        veh.set_thruster_nMax(p['thruster_nMax'])

        return veh

    def make_no_vs_with_current_cfgs(self) -> tuple[dict, dict]:
        """
        Etapa 4+ — Factory para a comparação pré-definida "Sem vs Com
        Corrente". Os 2 cfgs herdam do estado actual do controller (Cd,
        ganhos, etc.) e diferem apenas no parâmetro V_c.
        """
        cfg_a = {
            'label': 'Sem corrente',
            'V_c': 0.0,
            'beta_c_deg': 0.0,
            'current_model': None,
        }
        cfg_b = {
            'label': 'Com corrente V_c=0.5',
            'V_c': 0.5,
            'beta_c_deg': 0.0,
            'current_model': None,
        }
        return cfg_a, cfg_b

    def register_comparison_results(self, result_a: dict, result_b: dict,
                                    out_dir: Path | None = None):
        """
        Etapa 4+ — Regista 2 resultados de simulação no _sim_store, exporta
        CSVs com nome único (timestamp + sufixo A/B) e emite o sinal
        comparison_ready com os dois resultados (incluindo csv_path).

        Cada result é dict com chaves: 'simTime', 'simData', 'vehicle',
        'label' (e qualquer extra do chamador). Os campos 'csv_path' e
        'metadata' são adicionados aqui.
        """
        if out_dir is None:
            out_dir = self._DEFAULT_COMPARE_DIR
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        for r, suffix in ((result_a, 'A'), (result_b, 'B')):
            csv_path = out_dir / f"comparacao_{ts}_{suffix}.csv"
            export_csv(csv_path, r['simTime'], r['simData'],
                       params=r['vehicle'].get_all_params(), dimU=5)
            r['csv_path'] = csv_path
            self.store_simulation(
                r['simTime'], r['simData'],
                label=r.get('label', f"Comparação {suffix}"),
                metadata={'comparison_ts': ts, 'side': suffix},
            )

        self.comparison_ready.emit(result_a, result_b)

    def reset_to_defaults(self):
        """
        Recreate the internal torpedo instance with factory defaults
        and emit params_updated with the fresh parameter set.
        """
        self._model = torpedo()
        self._emit_view_params()

    # ------------------------------------------------------------------
    # Etapa 3 — Simulation store & export
    # ------------------------------------------------------------------

    def store_simulation(self, simTime, simData, label: str = "",
                         metadata: dict | None = None):
        """
        Add a simulation result to the internal store.

        Parameters
        ----------
        simTime, simData : numpy arrays from mainLoop.simulate()
        label : str — human-readable label
        metadata : dict — optional extra info (control_mode, refs, etc.)
        """
        if not label:
            n = len(self._sim_store) + 1
            label = f"Sim {n}"
        # Etapa 4 — regista o tipo do CurrentModel também na metadata, para
        # facilitar análises e exportações posteriores.
        md = dict(metadata or {})
        md.setdefault('current_model_type',
                      self._current_model_state['current_model_selected'])
        entry = {
            'label': label,
            'simTime': simTime,
            'simData': simData,
            'params': self._model.get_all_params(),
            'metadata': md,
            'timestamp': datetime.now().isoformat(timespec='seconds'),
        }
        self._sim_store.append(entry)
        self.store_updated.emit(self._store_labels())

    def get_store(self) -> list[dict]:
        """Return the full simulation store."""
        return list(self._sim_store)

    def get_store_entry(self, index: int) -> dict | None:
        """Return a single store entry by index, or None."""
        if 0 <= index < len(self._sim_store):
            return self._sim_store[index]
        return None

    def remove_from_store(self, index: int):
        """Remove a simulation by index."""
        if 0 <= index < len(self._sim_store):
            self._sim_store.pop(index)
            self.store_updated.emit(self._store_labels())

    def clear_store(self):
        """Clear all stored simulations."""
        self._sim_store.clear()
        self.store_updated.emit([])

    def export_simulation(self, index: int, filepath: str,
                          fmt: str = "csv") -> Path | None:
        """
        Export a stored simulation to CSV or JSON.

        Parameters
        ----------
        index : int — index in the store
        filepath : str — destination file path
        fmt : 'csv' or 'json'

        Returns
        -------
        Path or None
        """
        entry = self.get_store_entry(index)
        if entry is None:
            self.validation_error.emit("Índice de simulação inválido.")
            return None
        params = entry.get('params')
        fn = export_csv if fmt == "csv" else export_json
        return fn(filepath, entry['simTime'], entry['simData'],
                  params=params)

    def _store_labels(self) -> list[str]:
        return [e['label'] for e in self._sim_store]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_dependencies(self, new_params: dict):
        """
        Detect parameters that changed as side-effects of a setter and
        emit param_dependency_updated for each one.

        Tracked couplings (Fossen 2021):
          A7: T_sway  → T_heave
          A8: T_yaw   → T_nomoto
          geometry: L / diam → massa

        Parameters
        ----------
        new_params : dict
            The freshly retrieved parameter snapshot (post-setter).
            Compared against self._last_params (pre-setter snapshot).
        """
        dependent_keys = ('T_heave', 'T_nomoto', 'massa')

        for key in dependent_keys:
            old = self._last_params.get(key)
            new = new_params.get(key)
            if new != old:
                self.param_dependency_updated.emit(key, float(new))
