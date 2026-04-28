"""
test_etapa4.py — Testes da campanha de simulações S0-S5.

Cobre os 5 cenários do script etapa4/etapa4_simulacoes.py ao nível dos
modelos isolados (rápido) e valida o número de linhas dos 6 CSVs gerados
(corre a campanha completa uma única vez via fixture session-scoped, com
cache em disco — em corridas subsequentes reutiliza os CSVs existentes).

Referência:
    T. I. Fossen, "Handbook of Marine Craft Hydrodynamics and Motion
    Control", 2nd ed., Wiley, 2021.

Autores:
    Ricardo Craveiro (1191000@isep.ipp.pt)
    Afonso Barreiro  (1201126@isep.ipp.pt)
DINAV 2026 — Etapa 4
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "etapa4"))

from python_vehicle_simulator.lib.environment import (
    ConstantCurrent, LinearProfile, PowerLawProfile,
    LogarithmicProfile, GaussMarkovCurrent,
)


# ---------------------------------------------------------------------------
# Testes de modelo isolados (rápidos)
# ---------------------------------------------------------------------------

def test_S0_constant_current_zero_em_todos_os_instantes():
    """S0: ConstantCurrent(0,0) devolve V_c=0 para qualquer (z, t)."""
    cm = ConstantCurrent(V_c=0.0, beta_c=0.0)
    casos = [(0.0, 0.0), (30.0, 1.5), (100.0, 200.0), (-5.0, 50.0)]
    for z, t in casos:
        V_c, beta_c = cm.get_current(z, t)
        assert V_c == 0.0
        assert beta_c == 0.0


def test_S2_linear_profile_em_z_ref_50m_iguala_V_surface():
    """S2: LinearProfile(1.0, 50, 0).get_current(50, 0) ≈ 1.0 m/s (tol 1%)."""
    V_c, _ = LinearProfile(V_surface=1.0, z_ref=50.0,
                           beta_c=0.0).get_current(50.0, 0.0)
    assert abs(V_c - 1.0) <= 0.01


def test_S3_power_law_monotonicamente_crescente_de_1_a_100():
    """S3: PowerLawProfile com z ∈ [1, 100] m é estritamente crescente."""
    p = PowerLawProfile(V_surface=1.0, z_ref=50.0, beta_c=0.0)
    zs = np.linspace(1.0, 100.0, 50)
    vs = [p.get_current(z, 0.0)[0] for z in zs]
    for i in range(1, len(vs)):
        assert vs[i] > vs[i - 1], (
            f"V_c não é crescente em z={zs[i]:.2f}: {vs[i]:.4f} <= {vs[i-1]:.4f}")


def test_S4_log_profile_positivo_em_1m_e_crescente_em_10m():
    """S4: LogarithmicProfile tem V_c(1) > 0 e V_c(10) > V_c(1)."""
    p = LogarithmicProfile(V_star=0.05, z_0=0.01, beta_c=0.0, kappa=0.41)
    v1 = p.get_current(1.0, 0.0)[0]
    v10 = p.get_current(10.0, 0.0)[0]
    assert v1 > 0.0
    assert v10 > v1


def test_S5_gauss_markov_seed42_primeira_chamada_reprodutivel():
    """S5: GaussMarkovCurrent com seed=42 produz a mesma primeira amostra
    quando reinstanciado (reprodutibilidade entre execuções)."""
    a = GaussMarkovCurrent(mu=0.1, sigma=0.1, V_c0=0.5, beta_c=0.0,
                           rng_seed=42)
    b = GaussMarkovCurrent(mu=0.1, sigma=0.1, V_c0=0.5, beta_c=0.0,
                           rng_seed=42)
    out_a = a.get_current(30.0, 0.02)
    out_b = b.get_current(30.0, 0.02)
    assert out_a == out_b


# ---------------------------------------------------------------------------
# Validação dos 6 CSVs gerados (fixture session-scoped com cache em disco)
# ---------------------------------------------------------------------------

def _count_data_lines(path: Path) -> int:
    """Conta linhas de dados (ignora comentários '#' e a linha de header)."""
    n = 0
    with open(path, encoding='utf-8') as f:
        for line in f:
            if line.startswith('#'):
                continue
            if line.startswith('t_s'):
                continue
            if line.strip():
                n += 1
    return n


@pytest.fixture(scope='session')
def csvs_etapa4():
    """
    Garante que os 6 CSVs existem com 10001 linhas. Lento (~minutos) na
    primeira corrida; reutiliza os ficheiros em corridas seguintes.
    """
    import etapa4_simulacoes as e4

    paths = {label: e4.OUT_DIR / cfg['csv'] for label, cfg in e4.SIMS.items()}
    needs_run = [
        label for label, p in paths.items()
        if (not p.exists()) or _count_data_lines(p) != 10001
    ]
    if needs_run:
        e4.OUT_DIR.mkdir(parents=True, exist_ok=True)
        for label in e4.SIMS:
            if label in needs_run:
                e4.run_simulation(label)
    return paths


def test_csv_files_have_10001_data_rows(csvs_etapa4):
    """Cada um dos 6 CSVs tem exactamente 10 001 linhas de dados."""
    for label, p in csvs_etapa4.items():
        assert p.exists(), f"CSV {label} em falta: {p}"
        n = _count_data_lines(p)
        assert n == 10001, f"{label}: linhas={n} (esperado 10001) — {p}"
