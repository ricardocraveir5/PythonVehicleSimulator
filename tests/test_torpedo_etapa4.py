"""
test_torpedo_etapa4.py — Testes de integração da hierarquia CurrentModel
no torpedo.

Cobre:
    - Construtor com e sem `current_model`.
    - Property/setter `current_model` (validação, None, troca).
    - Tempo interno `_t_sim` incrementado em `dynamics()`.
    - Equivalência semântica: legado (current_model=None) vs ConstantCurrent
      com os mesmos V_c e beta_c.
    - Despacho real do perfil em `dynamics()` (LinearProfile a z>0 vs z=0).
    - Chave 'current_model_type' em `get_all_params()`.

Referência:
    T. I. Fossen, "Handbook of Marine Craft Hydrodynamics and Motion Control",
    2nd ed., Wiley, 2021.

Autores:
    Ricardo Craveiro (1191000@isep.ipp.pt)
    Afonso Barreiro  (1201126@isep.ipp.pt)
DINAV 2026 — Etapa 4
"""

import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from python_vehicle_simulator.vehicles.torpedo import torpedo
from python_vehicle_simulator.lib.environment import (
    ConstantCurrent,
    LinearProfile,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def t_legacy():
    """torpedo() sem current_model — caminho legado."""
    return torpedo('depthHeadingAutopilot', 10, 30, 1000, 0.5, 45)


def _make_torpedo_with_model(model):
    """Constrói torpedo com o controlador depthHeadingAutopilot e current_model."""
    return torpedo('depthHeadingAutopilot', 10, 30, 1000, 0.0, 0.0,
                   current_model=model)


def _step(t, eta, nu):
    """Avança um passo de dynamics() e devolve nu_next (cópia)."""
    u_control = t.depthHeadingAutopilot(eta, nu, 0.02)
    nu_next, _ = t.dynamics(eta, nu.copy(), t.u_actual.copy(), u_control, 0.02)
    return nu_next


# ---------------------------------------------------------------------------
# Construtor
# ---------------------------------------------------------------------------

def test_torpedo_sem_args_current_model_none():
    """torpedo() sem argumentos: current_model=None, _t_sim=0.0."""
    t = torpedo()
    assert t.current_model is None
    assert t._t_sim == 0.0


def test_torpedo_construtor_aceita_current_model_keyword():
    """torpedo(current_model=...) passa por keyword e armazena."""
    cm = ConstantCurrent(V_c=0.3, beta_c=0.2)
    t = torpedo(current_model=cm)
    assert t.current_model is cm


def test_torpedo_construtor_rejeita_current_model_invalido():
    """current_model que não é CurrentModel ⇒ ValueError em PT-PT."""
    with pytest.raises(ValueError, match="current_model"):
        torpedo(current_model="nao-e-um-modelo")
    with pytest.raises(ValueError, match="current_model"):
        torpedo(current_model=42)


def test_torpedo_current_model_e_keyword_only():
    """Não deve ser possível passar current_model por posição."""
    with pytest.raises(TypeError):
        # 7.º argumento posicional não existe — current_model é keyword-only.
        torpedo("stepInput", 0, 0, 0, 0, 0, ConstantCurrent(0.1, 0.0))


# ---------------------------------------------------------------------------
# Property current_model
# ---------------------------------------------------------------------------

def test_current_model_setter_aceita_none(t_legacy):
    """Definir current_model = None volta ao caminho legado."""
    t_legacy.current_model = ConstantCurrent(V_c=0.3, beta_c=0.0)
    t_legacy.current_model = None
    assert t_legacy.current_model is None


def test_current_model_setter_aceita_instancia(t_legacy):
    cm = LinearProfile(V_surface=0.4, z_ref=10.0, beta_c=0.1)
    t_legacy.current_model = cm
    assert t_legacy.current_model is cm


def test_current_model_setter_rejeita_invalido(t_legacy):
    with pytest.raises(ValueError, match="current_model"):
        t_legacy.current_model = "invalido"
    with pytest.raises(ValueError, match="current_model"):
        t_legacy.current_model = 3.14


# ---------------------------------------------------------------------------
# Tempo interno _t_sim
# ---------------------------------------------------------------------------

def test_dynamics_incrementa_t_sim(t_legacy):
    """dynamics() incrementa _t_sim em sampleTime a cada chamada."""
    eta = np.zeros(6)
    nu = np.zeros(6)
    assert t_legacy._t_sim == 0.0
    _step(t_legacy, eta, nu)
    assert t_legacy._t_sim == pytest.approx(0.02)
    _step(t_legacy, eta, nu)
    _step(t_legacy, eta, nu)
    assert t_legacy._t_sim == pytest.approx(0.06)


def test_dynamics_t_sim_resistente_a_sampletime_variavel():
    """_t_sim acumula correctamente passos heterogéneos."""
    t = torpedo('depthHeadingAutopilot', 10, 0, 1000, 0.0, 0.0)
    eta = np.zeros(6)
    nu = np.zeros(6)
    u = t.depthHeadingAutopilot(eta, nu, 0.02)
    t.dynamics(eta, nu.copy(), t.u_actual.copy(), u, 0.05)
    t.dynamics(eta, nu.copy(), t.u_actual.copy(), u, 0.10)
    assert t._t_sim == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# Equivalência semântica: legado vs ConstantCurrent
# ---------------------------------------------------------------------------

def test_constant_current_iguala_caminho_legado():
    """torpedo(V_current=V, beta_current=beta) e torpedo(current_model=
    ConstantCurrent(V, beta_rad)) produzem nu_next idêntico após um passo.

    É o teste de regressão que protege a retrocompatibilidade total: o
    caminho legado (sem CurrentModel) e o explícito com ConstantCurrent
    têm de ser numericamente indistinguíveis.
    """
    V_c, beta_c_deg = 0.5, 45.0
    beta_c_rad = beta_c_deg * math.pi / 180

    t_a = torpedo('depthHeadingAutopilot', 10, 30, 1000, V_c, beta_c_deg)
    t_b = torpedo('depthHeadingAutopilot', 10, 30, 1000, 0.0, 0.0,
                  current_model=ConstantCurrent(V_c=V_c, beta_c=beta_c_rad))

    eta = np.array([1.0, 0.5, 5.0, 0.05, 0.02, 0.3])
    nu = np.array([1.5, 0.1, 0.0, 0.01, 0.0, 0.05])

    nu_a = _step(t_a, eta, nu)
    nu_b = _step(t_b, eta, nu)

    np.testing.assert_allclose(nu_a, nu_b, rtol=0.0, atol=1e-12)


def test_dynamics_default_inalterado_apos_etapa4():
    """torpedo() sem current_model continua a executar dynamics() sem erro
    e devolve um vector com forma (6,)."""
    t = torpedo('depthHeadingAutopilot', 10, 30, 1000, 0.0, 0.0)
    eta = np.zeros(6)
    nu = np.zeros(6)
    nu_next = _step(t, eta, nu)
    assert nu_next.shape == (6,)
    assert np.all(np.isfinite(nu_next))


# ---------------------------------------------------------------------------
# Despacho real do perfil em dynamics()
# ---------------------------------------------------------------------------

def test_linear_profile_a_z_zero_iguala_corrente_nula():
    """LinearProfile a z=0 devolve V_c=0 ⇒ resultado idêntico ao de um
    torpedo sem corrente."""
    cm = LinearProfile(V_surface=2.0, z_ref=10.0, beta_c=0.5)
    t_modelado = _make_torpedo_with_model(cm)
    t_sem = torpedo('depthHeadingAutopilot', 10, 30, 1000, 0.0, 0.0)

    eta = np.zeros(6)  # z = eta[2] = 0
    nu = np.zeros(6)

    nu_a = _step(t_modelado, eta, nu)
    nu_b = _step(t_sem, eta, nu)
    np.testing.assert_allclose(nu_a, nu_b, rtol=0.0, atol=1e-12)


def test_linear_profile_a_profundidade_difere_do_caso_sem_corrente():
    """A z=z_ref a corrente é máxima (V_surface) — nu_next deve diferir
    visivelmente de um cenário sem corrente."""
    cm = LinearProfile(V_surface=1.0, z_ref=5.0, beta_c=0.5)
    t_modelado = _make_torpedo_with_model(cm)
    t_sem = torpedo('depthHeadingAutopilot', 10, 30, 1000, 0.0, 0.0)

    eta = np.array([0.0, 0.0, 5.0, 0.0, 0.0, 0.0])  # z = 5 = z_ref
    nu = np.array([1.5, 0.0, 0.0, 0.0, 0.0, 0.0])

    nu_a = _step(t_modelado, eta, nu)
    nu_b = _step(t_sem, eta, nu)
    diff = np.max(np.abs(nu_a - nu_b))
    assert diff > 1e-6, (
        f"LinearProfile a z=z_ref deveria afectar nu_next; diff_max={diff:.2e}")


# ---------------------------------------------------------------------------
# get_all_params()
# ---------------------------------------------------------------------------

def test_get_all_params_inclui_current_model_type_default():
    """Sem current_model, get_all_params() devolve 'ConstantCurrent'."""
    t = torpedo()
    params = t.get_all_params()
    assert 'current_model_type' in params
    assert params['current_model_type'] == 'ConstantCurrent'


def test_get_all_params_devolve_nome_da_classe_concreta():
    """Com current_model definido, devolve o nome da classe concreta."""
    casos = [
        (ConstantCurrent(V_c=0.1, beta_c=0.0), 'ConstantCurrent'),
        (LinearProfile(V_surface=0.5, z_ref=10.0, beta_c=0.0), 'LinearProfile'),
    ]
    for modelo, esperado in casos:
        t = torpedo(current_model=modelo)
        assert t.get_all_params()['current_model_type'] == esperado
