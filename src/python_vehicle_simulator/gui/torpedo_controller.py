"""
torpedo_controller.py — MVC Controller for the torpedo vehicle model.

Connects the View to the Model (torpedo.py) without either knowing
about the other. Exposes Qt signals for parameter updates, simulation
readiness, validation errors, and dependency notifications.

Original author: Thor I. Fossen
Additions:       Ricardo Craveiro (1191000@isep.ipp.pt)
DINAV 2026 — Etapa 2
"""

from PyQt6.QtCore import QObject, pyqtSignal
from python_vehicle_simulator.vehicles.torpedo import torpedo


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

    params_updated          = pyqtSignal(dict)
    simulation_ready        = pyqtSignal(object)
    validation_error        = pyqtSignal(str)
    param_dependency_updated = pyqtSignal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = torpedo()
        self._last_params = self._model.get_all_params()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_current_params(self):
        """Return a dict with all current model parameters."""
        return self._model.get_all_params()

    def update_param(self, nome, valor):
        """
        Apply *valor* to the parameter *nome* on the Model.

        Special cases:
          - ``fin_CL_N``   → calls set_fin_CL(N, valor)
          - ``fin_area_N`` → calls set_fin_area(N, valor)
          - ``thruster_nMax`` → calls set_thruster_nMax(valor)

        On ValueError  → emits validation_error(message).
        On success     → emits params_updated(full_dict) and
                         calls _check_dependencies().
        """
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
        self.params_updated.emit(new_params)
        self._check_dependencies(new_params)
        self._last_params = new_params

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
                control_mode, ref_z, ref_psi, ref_n, V_c, beta_c_deg
            )

            # Propagate all non-constructor parameters via set_from_dict,
            # skipping keys managed by the constructor itself.
            constructor_keys = {
                'ref_z', 'ref_psi', 'ref_n', 'V_c', 'beta_c',
                'massa', 'T_heave', 'T_nomoto',
                'fin_CL', 'fin_area', 'thruster_nMax',
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

    def reset_to_defaults(self):
        """
        Recreate the internal torpedo instance with factory defaults
        and emit params_updated with the fresh parameter set.
        """
        self._model = torpedo()
        self._last_params = self._model.get_all_params()
        self.params_updated.emit(self._last_params)

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
