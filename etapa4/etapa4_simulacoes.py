#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etapa4_simulacoes.py — Simulações canónicas S0-S5 (DINAV 2026, Etapa 4).

Corre 6 simulações de 200 s (10 000 passos a dt=0.02 s) com diferentes
modelos de corrente oceânica, exporta CSVs com snapshot de parâmetros,
gera um PDF multi-página com gráficos e calcula métricas para o artigo.

Configuração:
    Modo:       depthHeadingAutopilot
    Setpoints:  z_d = 30 m, psi_d = 45°, n_d = 1525 RPM
    Posição/atitude inicial: zero

Cenários:
    S0 — ConstantCurrent baseline (V_c = 0)
    S1 — ConstantCurrent (V_c = 0.5 m/s, β_c = 0°)
    S2 — LinearProfile (V_surface = 1.0, z_ref = 50 m)
    S3 — PowerLawProfile (1/7) (V_surface = 1.0, z_ref = 50 m)
    S4 — LogarithmicProfile (V_star = 0.05, z_0 = 0.01, κ = 0.41)
    S5 — GaussMarkovCurrent (μ = 0.1, σ = 0.1, V_c0 = 0.5, seed = 42)

Referência:
    T. I. Fossen, "Handbook of Marine Craft Hydrodynamics and Motion
    Control", 2nd ed., Wiley, 2021 — Cap. 10.

Autores:
    Ricardo Craveiro (1191000@isep.ipp.pt)
    Afonso Barreiro  (1201126@isep.ipp.pt)
DINAV 2026 — Etapa 4
"""

import logging
import sys
import time
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")  # backend não-interativo — apenas geração de PDF
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 — registo do projecção 3d

# ---------------------------------------------------------------------------
# Setup do path para importar o pacote sem instalação
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from python_vehicle_simulator.vehicles.torpedo import torpedo
from python_vehicle_simulator.lib.mainLoop import simulate
from python_vehicle_simulator.gui.export_results import export_csv
from python_vehicle_simulator.lib.environment import (
    ConstantCurrent, LinearProfile, PowerLawProfile,
    LogarithmicProfile, GaussMarkovCurrent,
)


# ---------------------------------------------------------------------------
# Constantes da campanha de simulações
# ---------------------------------------------------------------------------
SAMPLE_TIME = 0.02
DURATION_S  = 200.0
N_STEPS     = int(round(DURATION_S / SAMPLE_TIME))   # 10 000
REF_Z       = 30.0
REF_PSI_DEG = 45.0
REF_RPM     = 1525
OUT_DIR     = Path(__file__).resolve().parent

log = logging.getLogger("etapa4")


# ---------------------------------------------------------------------------
# Configuração das 6 simulações
# ---------------------------------------------------------------------------
# Cada entrada inclui:
#   - 'csv': nome do ficheiro CSV de saída
#   - 'titulo': descrição humana
#   - 'factory': callable sem argumentos que devolve a CurrentModel (ou None)
#   - 'V_c_init', 'beta_deg_init': valores passados ao construtor torpedo()
#     no caminho legado (S0 e S1). Para S2-S5 ficam a 0 (o current_model
#     domina dynamics() e o V_c/β_c constantes do construtor são ignorados).
SIMS = {
    'S0': {
        'csv': 'sim_S0_baseline.csv',
        'titulo': 'S0 — Baseline V_c = 0 m/s',
        'factory': lambda: None,
        'V_c_init': 0.0,
        'beta_deg_init': 0.0,
    },
    'S1': {
        'csv': 'sim_S1_constante.csv',
        'titulo': 'S1 — ConstantCurrent V_c = 0.5 m/s',
        'factory': lambda: ConstantCurrent(V_c=0.5, beta_c=0.0),
        'V_c_init': 0.5,
        'beta_deg_init': 0.0,
    },
    'S2': {
        'csv': 'sim_S2_linear.csv',
        'titulo': 'S2 — LinearProfile (V_surface=1.0, z_ref=50)',
        'factory': lambda: LinearProfile(
            V_surface=1.0, z_ref=50.0, beta_c=0.0),
        'V_c_init': 0.0,
        'beta_deg_init': 0.0,
    },
    'S3': {
        'csv': 'sim_S3_lei17.csv',
        'titulo': 'S3 — PowerLawProfile 1/7 (V_surface=1.0, z_ref=50)',
        'factory': lambda: PowerLawProfile(
            V_surface=1.0, z_ref=50.0, beta_c=0.0),
        'V_c_init': 0.0,
        'beta_deg_init': 0.0,
    },
    'S4': {
        'csv': 'sim_S4_logaritmico.csv',
        'titulo': 'S4 — LogarithmicProfile (V*=0.05, z_0=0.01, κ=0.41)',
        'factory': lambda: LogarithmicProfile(
            V_star=0.05, z_0=0.01, beta_c=0.0, kappa=0.41),
        'V_c_init': 0.0,
        'beta_deg_init': 0.0,
    },
    'S5': {
        'csv': 'sim_S5_gaussmarkov.csv',
        'titulo': 'S5 — GaussMarkovCurrent (μ=0.1, σ=0.1, V_c0=0.5, seed=42)',
        'factory': lambda: GaussMarkovCurrent(
            mu=0.1, sigma=0.1, V_c0=0.5, beta_c=0.0, rng_seed=42),
        'V_c_init': 0.0,
        'beta_deg_init': 0.0,
    },
}


# ---------------------------------------------------------------------------
# Execução de uma simulação
# ---------------------------------------------------------------------------
def run_simulation(label: str) -> dict:
    """
    Constrói o veículo, corre simulate(), exporta CSV e replica V_c(z) ao
    longo da missão. Devolve dict com chaves:
        simTime, simData, vehicle, csv_path, vc_samples, titulo
    """
    cfg = SIMS[label]
    log.info("[%s] modelo=%s  setpoints z_d=%.1f m, psi_d=%.1f°, n_d=%d RPM",
             label, cfg['titulo'], REF_Z, REF_PSI_DEG, REF_RPM)
    log.info("[%s] início — N=%d passos × dt=%.3f s = %.1f s",
             label, N_STEPS, SAMPLE_TIME, DURATION_S)
    t0 = time.perf_counter()

    cm = cfg['factory']()
    veh = torpedo(
        'depthHeadingAutopilot', REF_Z, REF_PSI_DEG, REF_RPM,
        cfg['V_c_init'], cfg['beta_deg_init'],
        current_model=cm,
    )

    simTime, simData = simulate(N=N_STEPS, sampleTime=SAMPLE_TIME, vehicle=veh)

    csv_path = OUT_DIR / cfg['csv']
    export_csv(csv_path, simTime, simData,
               params=veh.get_all_params(), dimU=5)

    vc_samples = _replicate_vc_samples(
        cfg['factory'], simData, cfg['V_c_init'])

    log.info("[%s] terminou em %.2f s — CSV: %s (%d linhas)",
             label, time.perf_counter() - t0, csv_path.name, len(simTime))
    return {
        'simTime': simTime,
        'simData': simData,
        'vehicle': veh,
        'csv_path': csv_path,
        'vc_samples': vc_samples,
        'titulo': cfg['titulo'],
    }


def _replicate_vc_samples(factory, simData, V_c0_legacy):
    """
    Devolve array (N+1, 2) com [z, V_c] efectivo em cada passo. Cria uma
    nova instância do modelo com a mesma configuração — para S0/S1
    (caminho legado, current_model=None) usa V_c constante igual ao valor
    inicial. Para Gauss-Markov com seed fixa é determinístico.
    """
    cm = factory()
    n = simData.shape[0]
    if cm is None:
        return np.column_stack([simData[:, 2], np.full(n, V_c0_legacy)])
    out = np.zeros((n, 2), dtype=float)
    for i in range(n):
        z = float(simData[i, 2])
        # _t_sim é incrementado no início de dynamics() ⇒ no passo i o
        # modelo de corrente foi consultado em t = (i+1)*dt.
        v_c, _ = cm.get_current(z, (i + 1) * SAMPLE_TIME)
        out[i] = (z, v_c)
    return out


# ---------------------------------------------------------------------------
# Gráficos individuais (4 por simulação)
# ---------------------------------------------------------------------------
def plot_traj_3d(sim, label):
    """(a) Trajectória 3D Norte/Este/z com z invertido (NED)."""
    d = sim['simData']
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection='3d')
    ax.plot(d[:, 0], d[:, 1], d[:, 2], color='C0', linewidth=1.0)
    ax.scatter([d[0, 0]], [d[0, 1]], [d[0, 2]], color='green', s=30,
               label='Início')
    ax.scatter([d[-1, 0]], [d[-1, 1]], [d[-1, 2]], color='red', s=30,
               label='Fim')
    ax.set_xlabel('Norte (m)')
    ax.set_ylabel('Este (m)')
    ax.set_zlabel('z — profundidade (m)')
    ax.invert_zaxis()
    ax.set_title(f"{label} — Trajectória 3D\n{sim['titulo']}")
    ax.legend(loc='upper left', fontsize='small')
    return fig


def plot_z_vs_t(sim, label):
    """(b) Profundidade z(t) com eixo y invertido + linha de setpoint."""
    t = sim['simTime'][:, 0]
    z = sim['simData'][:, 2]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(t, z, color='C0', linewidth=1.2, label='z (m)')
    ax.axhline(REF_Z, color='red', linestyle='--', linewidth=0.9,
               label=f'Setpoint = {REF_Z:.0f} m')
    ax.set_xlabel('Tempo (s)')
    ax.set_ylabel('z — profundidade (m)')
    ax.invert_yaxis()
    ax.set_title(f"{label} — Profundidade ao longo do tempo\n{sim['titulo']}")
    ax.grid(True, linestyle=':', alpha=0.5)
    ax.legend(loc='best', fontsize='small')
    fig.tight_layout()
    return fig


def plot_u_vs_t(sim, label):
    """(c) Velocidade de avanço u(t) (componente surge do nu)."""
    t = sim['simTime'][:, 0]
    u = sim['simData'][:, 6]   # nu[0] = surge
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(t, u, color='C2', linewidth=1.2)
    ax.set_xlabel('Tempo (s)')
    ax.set_ylabel('u — velocidade de avanço (m/s)')
    ax.set_title(f"{label} — Velocidade de avanço\n{sim['titulo']}")
    ax.grid(True, linestyle=':', alpha=0.5)
    fig.tight_layout()
    return fig


def plot_vc_vs_z(sim, label):
    """(d) Perfil V_c(z) efectivo amostrado durante a missão."""
    vc = sim['vc_samples']
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(vc[:, 1], vc[:, 0], s=4, alpha=0.5, color='C3')
    ax.set_xlabel('V_c (m/s)')
    ax.set_ylabel('z — profundidade (m)')
    ax.invert_yaxis()
    ax.set_title(
        f"{label} — Perfil V_c(z) efectivo durante a missão\n{sim['titulo']}")
    ax.grid(True, linestyle=':', alpha=0.5)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Gráficos comparativos (3 páginas)
# ---------------------------------------------------------------------------
def plot_compare_xy(sims):
    """(e) Trajectórias 2D Norte-Este sobrepostas S0-S5."""
    fig, ax = plt.subplots(figsize=(8, 7))
    for label, sim in sims.items():
        d = sim['simData']
        ax.plot(d[:, 1], d[:, 0], linewidth=1.0, label=label)
    ax.set_xlabel('Este (m)')
    ax.set_ylabel('Norte (m)')
    ax.set_aspect('equal', adjustable='datalim')
    ax.set_title('Comparação — Trajectórias horizontais (Norte vs Este)')
    ax.grid(True, linestyle=':', alpha=0.5)
    ax.legend(loc='best', fontsize='small')
    fig.tight_layout()
    return fig


def plot_compare_z_vs_t(sims):
    """(f) z(t) sobreposta S0-S5."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for label, sim in sims.items():
        ax.plot(sim['simTime'][:, 0], sim['simData'][:, 2],
                linewidth=1.0, label=label)
    ax.axhline(REF_Z, color='red', linestyle='--', linewidth=0.9,
               label=f'Setpoint = {REF_Z:.0f} m')
    ax.set_xlabel('Tempo (s)')
    ax.set_ylabel('z (m)')
    ax.invert_yaxis()
    ax.set_title('Comparação — Profundidade z(t)')
    ax.grid(True, linestyle=':', alpha=0.5)
    ax.legend(loc='best', fontsize='small')
    fig.tight_layout()
    return fig


def plot_compare_u_vs_t(sims):
    """(g) u(t) sobreposta S0-S5."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for label, sim in sims.items():
        ax.plot(sim['simTime'][:, 0], sim['simData'][:, 6],
                linewidth=1.0, label=label)
    ax.set_xlabel('Tempo (s)')
    ax.set_ylabel('u (m/s)')
    ax.set_title('Comparação — Velocidade de avanço u(t)')
    ax.grid(True, linestyle=':', alpha=0.5)
    ax.legend(loc='best', fontsize='small')
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Geração do PDF multi-página
# ---------------------------------------------------------------------------
def gerar_pdf(sims: dict, pdf_path: Path):
    """
    Compõe o PDF com 4 páginas por simulação + 3 páginas comparativas.
    Total: 6×4 + 3 = 27 páginas.
    """
    log.info("A gerar %s ...", pdf_path.name)
    individuais = (plot_traj_3d, plot_z_vs_t, plot_u_vs_t, plot_vc_vs_z)
    comparativas = (plot_compare_xy, plot_compare_z_vs_t, plot_compare_u_vs_t)

    with PdfPages(pdf_path) as pdf:
        for label, sim in sims.items():
            for fn in individuais:
                fig = fn(sim, label)
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)
        for fn in comparativas:
            fig = fn(sims)
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
    log.info("PDF gerado: %s", pdf_path)


# ---------------------------------------------------------------------------
# Métricas comparativas
# ---------------------------------------------------------------------------
def compute_metrics(sims: dict) -> dict:
    """
    Para cada Si calcula:
      - desvio_xy_max_m: máximo desvio horizontal vs S0
      - rms_z_vs_setpoint_m: RMS de (z - REF_Z)
      - rms_deflexao_media_deg: RMS da média das 4 deflexões (graus).
        Nota: as barbatanas do torpedo operam em pares simétricos
        (top vs bottom, star vs port) — por isso a média das 4 anula-se
        e este valor é tipicamente ~0. Mantido por fidelidade à spec.
      - rms_deflexao_individual_med_deg: média dos 4 RMS individuais
        (graus) — métrica complementar fisicamente significativa.
    Para S5 acrescenta:
      - std_xy_vs_S1_m: desvio padrão da distância horizontal vs S1
    """
    s0 = sims['S0']['simData']
    metricas: dict = {}
    for label, sim in sims.items():
        d = sim['simData']
        diff_xy = np.sqrt((d[:, 0] - s0[:, 0]) ** 2 +
                          (d[:, 1] - s0[:, 1]) ** 2)
        # Colunas 17-20 = u_actual das 4 barbatanas, em radianos
        defl_deg = np.rad2deg(d[:, 17:21])
        defl_mean = defl_deg.mean(axis=1)
        rms_individual = np.sqrt((defl_deg ** 2).mean(axis=0))
        metricas[label] = {
            'desvio_xy_max_m':                 float(diff_xy.max()),
            'rms_z_vs_setpoint_m':             float(np.sqrt(np.mean(
                                                    (d[:, 2] - REF_Z) ** 2))),
            'rms_deflexao_media_deg':          float(np.sqrt(np.mean(
                                                    defl_mean ** 2))),
            'rms_deflexao_individual_med_deg': float(rms_individual.mean()),
        }

    # S5 vs S1: variabilidade horizontal induzida pela componente estocástica
    d1 = sims['S1']['simData']
    d5 = sims['S5']['simData']
    metricas['S5']['std_xy_vs_S1_m'] = float(np.std(np.sqrt(
        (d5[:, 0] - d1[:, 0]) ** 2 + (d5[:, 1] - d1[:, 1]) ** 2)))
    return metricas


def write_metrics_file(metricas: dict, path: Path):
    """Escrita simples linha-a-linha em PT-PT."""
    log.info("A escrever %s ...", path.name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write("DINAV 2026 — Etapa 4 — Métricas (vs S0; S5 também vs S1)\n")
        f.write("=" * 64 + "\n\n")
        for label in SIMS:  # ordem fixa S0..S5
            m = metricas[label]
            f.write(f"{SIMS[label]['titulo']}\n")
            f.write(f"  Desvio máximo horizontal vs S0 (m): "
                    f"{m['desvio_xy_max_m']:.4f}\n")
            f.write(f"  Erro RMS de profundidade vs setpoint (m): "
                    f"{m['rms_z_vs_setpoint_m']:.4f}\n")
            f.write(f"  RMS deflexão média das 4 barbatanas (°): "
                    f"{m['rms_deflexao_media_deg']:.6f}\n")
            f.write(f"  Média dos RMS individuais das 4 barbatanas (°): "
                    f"{m['rms_deflexao_individual_med_deg']:.4f}\n")
            if 'std_xy_vs_S1_m' in m:
                f.write(f"  Desvio padrão horizontal vs S1 (m): "
                        f"{m['std_xy_vs_S1_m']:.4f}\n")
            f.write("\n")
    log.info("Métricas escritas: %s", path)


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------
def main():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(message)s',
        datefmt='%H:%M:%S',
    )
    log.info("Etapa 4 — DINAV 2026: a iniciar 6 simulações em %s", OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sims = {label: run_simulation(label) for label in SIMS}

    pdf_path = OUT_DIR / 'etapa4_graficos.pdf'
    gerar_pdf(sims, pdf_path)

    metricas = compute_metrics(sims)
    write_metrics_file(metricas, OUT_DIR / 'etapa4_metricas.txt')

    log.info("Concluído. Outputs em %s", OUT_DIR)


if __name__ == '__main__':
    main()
