"""
test_environment.py — Testes unitários da hierarquia CurrentModel.

Cobre as 5 classes concretas e a abstracta. Não depende de Qt nem de torpedo.

Referência:
    T. I. Fossen, "Handbook of Marine Craft Hydrodynamics and Motion Control",
    2nd ed., Wiley, 2021 — Cap. 10.

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

from python_vehicle_simulator.lib.environment import (
    CurrentModel,
    ConstantCurrent,
    LinearProfile,
    PowerLawProfile,
    LogarithmicProfile,
    GaussMarkovCurrent,
)


# ---------------------------------------------------------------------------
# CurrentModel (abstracta)
# ---------------------------------------------------------------------------

def test_current_model_nao_instanciavel():
    """A classe abstracta não deve ser instanciável directamente."""
    with pytest.raises(TypeError):
        CurrentModel()


# ---------------------------------------------------------------------------
# ConstantCurrent
# ---------------------------------------------------------------------------

def test_constant_current_devolve_sempre_o_mesmo():
    """ConstantCurrent é independente de z e t."""
    c = ConstantCurrent(V_c=0.7, beta_c=0.5)
    casos = [(0.0, 0.0), (5.0, 1.5), (-3.0, 100.0), (1000.0, 9999.0)]
    for z, t in casos:
        V_c, beta_c = c.get_current(z, t)
        assert V_c == pytest.approx(0.7)
        assert beta_c == pytest.approx(0.5)


def test_constant_current_rejeita_V_c_negativo():
    with pytest.raises(ValueError, match="V_c"):
        ConstantCurrent(V_c=-0.1, beta_c=0.0)


def test_constant_current_rejeita_beta_fora_de_intervalo():
    with pytest.raises(ValueError, match="beta_c"):
        ConstantCurrent(V_c=0.5, beta_c=4.0)


# ---------------------------------------------------------------------------
# LinearProfile
# ---------------------------------------------------------------------------

@pytest.fixture
def lin():
    return LinearProfile(V_surface=1.0, z_ref=10.0, beta_c=0.0)


def test_linear_profile_em_z_ref_iguala_V_surface(lin):
    V_c, _ = lin.get_current(z=10.0, t=0.0)
    assert V_c == pytest.approx(1.0)


def test_linear_profile_em_superficie_zero(lin):
    V_c, _ = lin.get_current(z=0.0, t=0.0)
    assert V_c == 0.0


def test_linear_profile_acima_de_superficie_zero(lin):
    V_c, _ = lin.get_current(z=-5.0, t=0.0)
    assert V_c == 0.0


def test_linear_profile_meio_caminho(lin):
    V_c, _ = lin.get_current(z=5.0, t=0.0)
    assert V_c == pytest.approx(0.5)


def test_linear_profile_rejeita_z_ref_invalido():
    with pytest.raises(ValueError, match="z_ref"):
        LinearProfile(V_surface=1.0, z_ref=0.0, beta_c=0.0)
    with pytest.raises(ValueError, match="z_ref"):
        LinearProfile(V_surface=1.0, z_ref=-2.0, beta_c=0.0)


# ---------------------------------------------------------------------------
# PowerLawProfile
# ---------------------------------------------------------------------------

@pytest.fixture
def pwr():
    return PowerLawProfile(V_surface=1.0, z_ref=10.0, beta_c=0.0)


def test_power_law_em_z_ref_iguala_V_surface(pwr):
    V_c, _ = pwr.get_current(z=10.0, t=0.0)
    assert V_c == pytest.approx(1.0)


def test_power_law_monotonicamente_crescente(pwr):
    """Para z > 0, (z/z_ref)^(1/7) é estritamente crescente em z."""
    zs = [0.1, 0.5, 1.0, 5.0, 10.0, 20.0, 50.0]
    vs = [pwr.get_current(z, 0.0)[0] for z in zs]
    for i in range(1, len(vs)):
        assert vs[i] > vs[i - 1], f"V_c não crescente em z={zs[i]}"


def test_power_law_em_superficie_zero(pwr):
    assert pwr.get_current(z=0.0, t=0.0)[0] == 0.0
    assert pwr.get_current(z=-1.0, t=0.0)[0] == 0.0


def test_power_law_rejeita_z_ref_invalido():
    with pytest.raises(ValueError, match="z_ref"):
        PowerLawProfile(V_surface=1.0, z_ref=0.0, beta_c=0.0)


# ---------------------------------------------------------------------------
# LogarithmicProfile
# ---------------------------------------------------------------------------

@pytest.fixture
def logp():
    return LogarithmicProfile(V_star=0.05, z_0=0.01, beta_c=0.0)


def test_log_profile_crescente_em_z(logp):
    zs = [0.05, 0.1, 1.0, 10.0, 100.0]
    vs = [logp.get_current(z, 0.0)[0] for z in zs]
    for i in range(1, len(vs)):
        assert vs[i] > vs[i - 1], f"V_c não crescente em z={zs[i]}"


def test_log_profile_em_superficie_zero(logp):
    assert logp.get_current(z=0.0, t=0.0)[0] == 0.0
    assert logp.get_current(z=-1.0, t=0.0)[0] == 0.0


def test_log_profile_V_star_zero():
    """V_star = 0 anula a corrente para qualquer z."""
    p = LogarithmicProfile(V_star=0.0, z_0=0.01, beta_c=0.0)
    for z in [0.01, 1.0, 10.0, 100.0]:
        assert p.get_current(z=z, t=0.0)[0] == 0.0


def test_log_profile_rejeita_z_0_invalido():
    with pytest.raises(ValueError, match="z_0"):
        LogarithmicProfile(V_star=0.05, z_0=0.0, beta_c=0.0)
    with pytest.raises(ValueError, match="z_0"):
        LogarithmicProfile(V_star=0.05, z_0=-0.01, beta_c=0.0)


def test_log_profile_rejeita_kappa_invalido():
    with pytest.raises(ValueError, match="kappa"):
        LogarithmicProfile(V_star=0.05, z_0=0.01, beta_c=0.0, kappa=0.0)
    with pytest.raises(ValueError, match="kappa"):
        LogarithmicProfile(V_star=0.05, z_0=0.01, beta_c=0.0, kappa=-0.1)


# ---------------------------------------------------------------------------
# GaussMarkovCurrent
# ---------------------------------------------------------------------------

def test_gauss_markov_reprodutibilidade_com_seed_fixa():
    """Duas instâncias com a mesma rng_seed produzem sequências idênticas."""
    a = GaussMarkovCurrent(mu=0.5, sigma=0.1, V_c0=0.0, beta_c=0.0,
                           rng_seed=42)
    b = GaussMarkovCurrent(mu=0.5, sigma=0.1, V_c0=0.0, beta_c=0.0,
                           rng_seed=42)
    seq_a, seq_b = [], []
    dt = 0.02
    for k in range(1000):
        t = k * dt
        seq_a.append(a.get_current(z=10.0, t=t)[0])
        seq_b.append(b.get_current(z=10.0, t=t)[0])
    np.testing.assert_allclose(seq_a, seq_b, rtol=0.0, atol=0.0)


def test_gauss_markov_seeds_diferentes_divergem():
    """Sementes distintas ⇒ sequências diferentes (sanity check)."""
    a = GaussMarkovCurrent(mu=0.5, sigma=0.1, V_c0=0.0, beta_c=0.0,
                           rng_seed=1)
    b = GaussMarkovCurrent(mu=0.5, sigma=0.1, V_c0=0.0, beta_c=0.0,
                           rng_seed=2)
    seq_a = [a.get_current(0.0, k * 0.02)[0] for k in range(100)]
    seq_b = [b.get_current(0.0, k * 0.02)[0] for k in range(100)]
    assert seq_a != seq_b


def test_gauss_markov_media_converge_para_zero():
    """Com V_c0=0, a média de longa duração deve estar próxima de 0."""
    p = GaussMarkovCurrent(mu=0.5, sigma=0.1, V_c0=0.0, beta_c=0.0,
                           rng_seed=123)
    valores = []
    dt = 0.02
    n = 5000
    for k in range(n):
        valores.append(p.get_current(z=0.0, t=k * dt)[0])
    # Tolerância folgada para evitar falso positivo por flutuação estocástica.
    media_segunda_metade = float(np.mean(valores[n // 2:]))
    assert abs(media_segunda_metade) < 0.05, (
        f"Média de longa duração = {media_segunda_metade:.4f} (esperada ≈ 0)")


def test_gauss_markov_primeira_chamada_usa_dt_default():
    """Sem ruído (sigma=0) e mu=0, V_c mantém-se em V_c0 ao longo do tempo."""
    p = GaussMarkovCurrent(mu=0.0, sigma=0.0, V_c0=0.3, beta_c=0.0,
                           rng_seed=0)
    V_c, _ = p.get_current(z=0.0, t=0.0)
    assert V_c == pytest.approx(0.3)
    V_c, _ = p.get_current(z=0.0, t=10.0)
    assert V_c == pytest.approx(0.3)


def test_gauss_markov_rejeita_mu_negativo():
    with pytest.raises(ValueError, match="mu"):
        GaussMarkovCurrent(mu=-0.1, sigma=0.1, V_c0=0.0, beta_c=0.0)


def test_gauss_markov_rejeita_sigma_negativo():
    with pytest.raises(ValueError, match="sigma"):
        GaussMarkovCurrent(mu=0.5, sigma=-0.01, V_c0=0.0, beta_c=0.0)


def test_gauss_markov_rejeita_beta_invalido():
    with pytest.raises(ValueError, match="beta_c"):
        GaussMarkovCurrent(mu=0.5, sigma=0.1, V_c0=0.0, beta_c=10.0)
