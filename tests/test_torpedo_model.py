"""
test_torpedo_model.py — Testes unitários isolados do modelo torpedo.

Não requer Qt — testa apenas torpedo.py de forma independente.

Referência:
    T. I. Fossen, "Handbook of Marine Craft Hydrodynamics and Motion
    Control", 2nd ed., Wiley, 2021.

Author: Ricardo Craveiro (1191000@isep.ipp.pt)
DINAV 2026 — Etapa 2
"""

import logging
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from python_vehicle_simulator.vehicles.torpedo import torpedo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def t():
    """Instância torpedo com parâmetros de fábrica."""
    return torpedo()


# ---------------------------------------------------------------------------
# Testes dos setters básicos
# ---------------------------------------------------------------------------

def test_setter_L_updates_a(t):
    """Alterar L deve actualizar _a = L/2."""
    t.L = 2.0
    assert abs(t._a - 1.0) < 1e-9, f"_a esperado 1.0, obtido {t._a}"


def test_setter_diam_updates_b(t):
    """Alterar diam deve actualizar _b = diam/2."""
    t.diam = 0.10
    assert abs(t._b - 0.05) < 1e-9, f"_b esperado 0.05, obtido {t._b}"


# ---------------------------------------------------------------------------
# Testes de validação cruzada L/diam
# ---------------------------------------------------------------------------

def test_setter_L_rejects_less_than_diam(t):
    """L < diam deve lançar ValueError (estado físico impossível)."""
    with pytest.raises(ValueError, match="diâmetro"):
        t.L = 0.10   # diam = 0.19 por defeito


def test_setter_L_rejects_zero(t):
    """L = 0 deve lançar ValueError."""
    with pytest.raises(ValueError):
        t.L = 0.0


def test_setter_diam_rejects_greater_than_L(t):
    """diam > L deve lançar ValueError."""
    with pytest.raises(ValueError, match="< L"):
        t.diam = 2.0   # L = 1.6 por defeito


def test_setter_diam_rejects_zero(t):
    """diam = 0 deve lançar ValueError."""
    with pytest.raises(ValueError):
        t.diam = 0.0


# ---------------------------------------------------------------------------
# Testes de _recalculate_derived via setters
# ---------------------------------------------------------------------------

def test_recalculate_derived_updates_massa(t):
    """Alterar L deve recalcular massa (propriedade calculada)."""
    old_massa = t.massa
    t.L = 3.0
    assert t.massa != old_massa, (
        f"Massa não mudou: antes={old_massa:.4f}, depois={t.massa:.4f}")


def test_recalculate_derived_updates_CD0_via_Cd(t):
    """Alterar Cd deve recalcular CD_0."""
    old_cd0 = t.CD_0
    t.Cd = 0.30
    assert t.CD_0 != old_cd0, "CD_0 não foi recalculado após alteração de Cd"


def test_recalculate_derived_updates_M_via_r44(t):
    """Alterar r44 deve recalcular MA e M."""
    old_M44 = t.M[3][3]
    t.r44 = 0.45
    assert t.M[3][3] != old_M44, "M[3][3] não foi recalculado após alteração de r44"


def test_recalculate_derived_updates_actuator_position(t):
    """Alterar L deve actualizar posição x das barbatanas para -a."""
    t.L = 2.0
    expected_x = -t._a   # -1.0
    for i in range(4):
        pos = t.actuators[i].R[0]
        assert abs(pos - expected_x) < 1e-9, (
            f"Actuator {i} R[0]={pos:.4f}, esperado {expected_x:.4f}")


# ---------------------------------------------------------------------------
# Testes de acoplamentos A7 e A8
# ---------------------------------------------------------------------------

def test_Tsway_updates_Theave(t):
    """A7: alterar T_sway deve actualizar T_heave para o mesmo valor."""
    t.T_sway = 25.0
    assert abs(t.T_heave - 25.0) < 1e-9, (
        f"T_heave={t.T_heave}, esperado 25.0")


def test_Tyaw_updates_Tnomoto(t):
    """A8: alterar T_yaw deve actualizar T_nomoto para o mesmo valor."""
    t.T_yaw = 5.0
    assert abs(t.T_nomoto - 5.0) < 1e-9, (
        f"T_nomoto={t.T_nomoto}, esperado 5.0")


# ---------------------------------------------------------------------------
# Teste de set_from_dict com campos read-only
# ---------------------------------------------------------------------------

def test_set_from_dict_readonly_warning(t, caplog):
    """set_from_dict com campo read-only deve emitir logging.warning."""
    with caplog.at_level(logging.WARNING):
        t.set_from_dict({'massa': 999.0, 'T_heave': 999.0, 'T_nomoto': 999.0})

    warned_keys = [rec.getMessage() for rec in caplog.records
                   if rec.levelno == logging.WARNING]
    assert len(warned_keys) == 3, (
        f"Esperados 3 warnings, obtidos {len(warned_keys)}: {warned_keys}")
    assert any('massa' in w for w in warned_keys)
    assert any('T_heave' in w for w in warned_keys)
    assert any('T_nomoto' in w for w in warned_keys)


def test_set_from_dict_readonly_does_not_change_values(t):
    """set_from_dict com campos read-only não deve alterar os valores."""
    original_massa = t.massa
    t.set_from_dict({'massa': 999.0})
    assert abs(t.massa - original_massa) < 1e-9, \
        "massa foi alterada indevidamente por set_from_dict"


# ---------------------------------------------------------------------------
# Teste de completude de get_all_params
# ---------------------------------------------------------------------------

def test_get_all_params_completeness(t):
    """get_all_params() deve devolver pelo menos 30 chaves."""
    params = t.get_all_params()
    expected_keys = {
        'L', 'diam', 'massa', 'Cd', 'r44',
        'T_surge', 'T_sway', 'T_heave', 'T_yaw', 'T_nomoto',
        'zeta_roll', 'zeta_pitch', 'K_nomoto',
        'wn_d', 'zeta_d', 'r_max', 'lam', 'phi_b', 'K_d', 'K_sigma',
        'wn_d_z', 'Kp_z', 'T_z', 'Kp_theta', 'Kd_theta', 'Ki_theta', 'K_w',
        'ref_z', 'ref_psi', 'ref_n', 'V_c', 'beta_c',
        'fin_CL', 'fin_area', 'thruster_nMax',
    }
    missing = expected_keys - set(params.keys())
    assert not missing, f"Chaves em falta em get_all_params(): {missing}"
    assert len(params) >= 30, \
        f"get_all_params() devolveu apenas {len(params)} chaves"


# ---------------------------------------------------------------------------
# Teste de compatibilidade: dynamics() após alteração de parâmetro
# ---------------------------------------------------------------------------

def test_dynamics_after_param_change():
    """Alterar wn_d via setter e chamar dynamics() não deve lançar excepção."""
    t2 = torpedo('depthHeadingAutopilot', 10, 30, 1000, 0, 0)
    t2.wn_d = 0.2
    eta = np.zeros(6)
    nu  = np.zeros(6)
    u   = t2.depthHeadingAutopilot(eta, nu, 0.02)
    nu_next, ua = t2.dynamics(eta, nu, t2.u_actual, u, 0.02)
    assert nu_next.shape == (6,), f"Forma inesperada: {nu_next.shape}"
