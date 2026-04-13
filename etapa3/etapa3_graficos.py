#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etapa3_graficos.py — Simulacao comparativa do torpedo AUV para a Etapa 3.

Corre duas simulacoes em modo stepInput (200 s, dt=0.02 s) com parametros
de fabrica (Cd=0.42) e com arrasto reduzido (Cd=0.25), exporta ambas para
CSV via gui.export_results.export_csv, e gera 9 graficos num unico PDF.

O efeito fisico observavel: reduzir Cd diminui CD_0 (= Cd * pi * b^2 / S),
que entra em forceLiftDrag() dentro de dynamics(), reduzindo o arrasto
parasita e aumentando a velocidade terminal em surge. A trajectoria
global, velocidades e profundidade sao afectadas.

Nota: em stepInput, a propulsao esta hardcoded a n = 1525 RPM (Anomalia
A5), e apenas as deflexoes das barbatanas sao controladas por degraus.

Original author: Thor I. Fossen (dinamica do torpedo, simulate(), Fossen 2021)
Additions:       Ricardo Craveiro (1191000@isep.ipp.pt)
DINAV 2026 - Etapa 3
"""

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # backend nao-interactivo - apenas geracao de PDF
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
import numpy as np  # noqa: E402

# -----------------------------------------------------------------------
# Configuracao de caminhos — garantir que python_vehicle_simulator e
# importavel a partir de src/ mesmo correndo o script de outro cwd
# -----------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from python_vehicle_simulator.vehicles.torpedo import torpedo  # noqa: E402
from python_vehicle_simulator.lib.mainLoop import simulate  # noqa: E402
from python_vehicle_simulator.gui.export_results import export_csv  # noqa: E402


# -----------------------------------------------------------------------
# Constantes da simulacao
# -----------------------------------------------------------------------
SAMPLE_TIME = 0.02                                   # dt (s)
DURATION_S = 200.0                                   # duracao total (s)
N_STEPS = int(round(DURATION_S / SAMPLE_TIME))       # = 10000

OUT_DIR = REPO_ROOT / "etapa3"
CSV_A = OUT_DIR / "sim_A_cd042.csv"
CSV_B = OUT_DIR / "sim_B_cd025.csv"
PDF_OUT = OUT_DIR / "etapa3_graficos.pdf"

# Indices das colunas do CSV (layout produzido por export_csv com dimU=5)
#  0  t_s
#  1-3  x, y, z
#  4-6  phi, theta, psi
#  7-9  u, v, w
# 10-12 p, q, r
# 13-17 delta_r_top_cmd, delta_r_bottom_cmd, delta_s_star_cmd,
#       delta_s_port_cmd, n_cmd
# 18-22 delta_r_top_act, delta_r_bottom_act, delta_s_star_act,
#       delta_s_port_act, n_act
COL_T = 0
COL_X, COL_Y, COL_Z = 1, 2, 3
COL_U, COL_V, COL_W = 7, 8, 9
COL_P, COL_Q, COL_R = 10, 11, 12
COL_DELTA_R_TOP_CMD = 13
COL_DELTA_R_BOT_CMD = 14
COL_DELTA_S_STAR_CMD = 15
COL_DELTA_S_PORT_CMD = 16
COL_N_CMD = 17


# -----------------------------------------------------------------------
# Execucao das simulacoes
# -----------------------------------------------------------------------
def run_simulation(cd_value: float):
    """
    Instancia o torpedo em modo stepInput, aplica Cd via setter (que
    valida 0.1..0.5 e recalcula CD_0), corre simulate() e devolve
    (simTime, simData, params).
    """
    vehicle = torpedo("stepInput")

    # Setter Cd - valida e invoca _recalculate_derived() -> CD_0
    vehicle.Cd = cd_value

    print(f"  -> A correr simulacao com Cd = {vehicle.Cd:.3f} "
          f"(CD_0 = {vehicle.CD_0:.6f}) durante {DURATION_S:.0f} s "
          f"({N_STEPS} passos de {SAMPLE_TIME} s) ...")

    sim_time, sim_data = simulate(N=N_STEPS,
                                  sampleTime=SAMPLE_TIME,
                                  vehicle=vehicle)

    return sim_time, sim_data, vehicle.get_all_params()


def load_csv(path: Path) -> np.ndarray:
    """
    Le o CSV exportado ignorando linhas de comentario (# ...) e a linha
    de cabecalho CSV. Devolve matriz (N, 23) com todas as colunas
    numericas.

    Nota: np.loadtxt usa `skiprows` em linhas brutas (antes de filtrar
    comentarios), por isso tem de se contar explicitamente quantas
    linhas de comentario `#` existem + 1 linha de cabecalho CSV.
    """
    with open(path, "r", encoding="utf-8") as f:
        comment_lines = sum(1 for line in f if line.startswith("#"))
    return np.loadtxt(path, delimiter=",", skiprows=comment_lines + 1,
                      comments="#")


# -----------------------------------------------------------------------
# Graficos individuais (PT-PT)
# -----------------------------------------------------------------------
def _grid(ax):
    ax.grid(True, linestyle="--", alpha=0.5)


def plot_trajectoria(data: np.ndarray, titulo: str):
    """Grafico 1/5: trajectoria 2D Norte (y) vs Este (x)."""
    fig, ax = plt.subplots(figsize=(8, 6))
    # Convencao Fossen NED: x = Norte, y = Este. No plot horizontal
    # queremos o Norte no eixo vertical e o Este no eixo horizontal.
    norte = data[:, COL_X]
    este = data[:, COL_Y]
    ax.plot(este, norte, color="tab:blue", linewidth=1.5)
    ax.plot(este[0], norte[0], marker="o", color="green",
            markersize=8, label="Inicio")
    ax.plot(este[-1], norte[-1], marker="s", color="red",
            markersize=8, label="Fim")
    ax.set_xlabel("Este [m]")
    ax.set_ylabel("Norte [m]")
    ax.set_title(titulo)
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(loc="best")
    _grid(ax)
    return fig


def plot_velocidades(data: np.ndarray, titulo: str):
    """
    Grafico 2/6: velocidades lineares (u, v, w) em m/s e velocidades
    angulares (p, q, r) em graus/s, em dois subplots empilhados.
    """
    t = data[:, COL_T]
    fig, (ax_lin, ax_ang) = plt.subplots(2, 1, figsize=(9, 8),
                                         sharex=True)

    ax_lin.plot(t, data[:, COL_U], label="u (surge)", color="tab:blue")
    ax_lin.plot(t, data[:, COL_V], label="v (sway)", color="tab:orange")
    ax_lin.plot(t, data[:, COL_W], label="w (heave)", color="tab:green")
    ax_lin.set_ylabel("Velocidade linear [m/s]")
    ax_lin.set_title(titulo)
    ax_lin.legend(loc="best")
    _grid(ax_lin)

    # Velocidades angulares convertidas de rad/s para graus/s
    ax_ang.plot(t, np.rad2deg(data[:, COL_P]),
                label="p (rolamento)", color="tab:red")
    ax_ang.plot(t, np.rad2deg(data[:, COL_Q]),
                label="q (arfagem)", color="tab:purple")
    ax_ang.plot(t, np.rad2deg(data[:, COL_R]),
                label="r (guinada)", color="tab:brown")
    ax_ang.set_xlabel("Tempo [s]")
    ax_ang.set_ylabel("Velocidade angular [graus/s]")
    ax_ang.legend(loc="best")
    _grid(ax_ang)

    return fig


def plot_actuadores(data: np.ndarray, titulo: str):
    """
    Grafico 3/7: comandos dos 5 actuadores. As 4 deflexoes das fins em
    graus (eixo esquerdo) e RPM do helice (eixo direito).
    """
    t = data[:, COL_T]
    fig, ax_esq = plt.subplots(figsize=(9, 6))

    # Deflexoes das fins (cmd) convertidas de rad para graus
    ax_esq.plot(t, np.rad2deg(data[:, COL_DELTA_R_TOP_CMD]),
                label="delta_r_top", color="tab:blue")
    ax_esq.plot(t, np.rad2deg(data[:, COL_DELTA_R_BOT_CMD]),
                label="delta_r_bottom", color="tab:cyan")
    ax_esq.plot(t, np.rad2deg(data[:, COL_DELTA_S_STAR_CMD]),
                label="delta_s_star", color="tab:orange")
    ax_esq.plot(t, np.rad2deg(data[:, COL_DELTA_S_PORT_CMD]),
                label="delta_s_port", color="tab:red")
    ax_esq.set_xlabel("Tempo [s]")
    ax_esq.set_ylabel("Deflexao das barbatanas [graus]")
    _grid(ax_esq)

    ax_dir = ax_esq.twinx()
    ax_dir.plot(t, data[:, COL_N_CMD],
                label="n (helice)", color="tab:green",
                linestyle="--", linewidth=1.8)
    ax_dir.set_ylabel("Rotacao do helice [RPM]")

    # Legenda combinada dos dois eixos
    linhas_esq, labels_esq = ax_esq.get_legend_handles_labels()
    linhas_dir, labels_dir = ax_dir.get_legend_handles_labels()
    ax_esq.legend(linhas_esq + linhas_dir, labels_esq + labels_dir,
                  loc="best")
    ax_esq.set_title(titulo)
    return fig


def plot_profundidade(data: np.ndarray, titulo: str):
    """Grafico 4/8: profundidade z vs tempo."""
    t = data[:, COL_T]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(t, data[:, COL_Z], color="tab:blue", linewidth=1.5)
    # Eixo invertido: profundidade cresce para baixo no mar
    ax.invert_yaxis()
    ax.set_xlabel("Tempo [s]")
    ax.set_ylabel("Profundidade z [m]")
    ax.set_title(titulo)
    _grid(ax)
    return fig


def plot_comparacao_trajectorias(data_a: np.ndarray,
                                 data_b: np.ndarray):
    """Grafico 9: sobreposicao das trajectorias 2D das duas simulacoes."""
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.plot(data_a[:, COL_Y], data_a[:, COL_X],
            label="Cd=0.42", color="tab:blue", linewidth=1.8)
    ax.plot(data_b[:, COL_Y], data_b[:, COL_X],
            label="Cd=0.25", color="tab:red", linewidth=1.8,
            linestyle="--")
    ax.plot(0, 0, marker="o", color="green",
            markersize=8, label="Inicio comum")
    ax.plot(data_a[-1, COL_Y], data_a[-1, COL_X],
            marker="s", color="tab:blue", markersize=8)
    ax.plot(data_b[-1, COL_Y], data_b[-1, COL_X],
            marker="s", color="tab:red", markersize=8)
    ax.set_xlabel("Este [m]")
    ax.set_ylabel("Norte [m]")
    ax.set_title("Comparacao de trajectorias 2D — efeito de Cd")
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(loc="best")
    _grid(ax)
    return fig


# -----------------------------------------------------------------------
# Orquestrador
# -----------------------------------------------------------------------
def main() -> int:
    print("=" * 72)
    print("Etapa 3 — DINAV 2026: simulacao comparativa Cd=0.42 vs Cd=0.25")
    print("=" * 72)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Directoria de saida: {OUT_DIR}")

    # --- Sim A (fabrica, Cd = 0.42) -----------------------------------
    print("\n[Sim A] Parametros de fabrica (Cd = 0.42)")
    t_a, sd_a, params_a = run_simulation(cd_value=0.42)
    export_csv(CSV_A, t_a, sd_a, params=params_a, dimU=5)
    print(f"  -> CSV escrito: {CSV_A}")

    # --- Sim B (arrasto reduzido, Cd = 0.25) --------------------------
    print("\n[Sim B] Arrasto reduzido (Cd = 0.25)")
    t_b, sd_b, params_b = run_simulation(cd_value=0.25)
    export_csv(CSV_B, t_b, sd_b, params=params_b, dimU=5)
    print(f"  -> CSV escrito: {CSV_B}")

    # --- Releitura via loadtxt ----------------------------------------
    print("\n[Leitura] A recarregar CSVs com numpy.loadtxt...")
    data_a = load_csv(CSV_A)
    data_b = load_csv(CSV_B)
    print(f"  -> Sim A: {data_a.shape}")
    print(f"  -> Sim B: {data_b.shape}")
    print(f"  -> u_final A = {data_a[-1, COL_U]:.4f} m/s   "
          f"u_final B = {data_b[-1, COL_U]:.4f} m/s")

    # --- Geracao do PDF com 9 paginas ---------------------------------
    print(f"\n[PDF] A gerar {PDF_OUT} ...")
    with PdfPages(PDF_OUT) as pdf:
        # Paginas 1-4: Sim A
        figuras = [
            plot_trajectoria(
                data_a,
                "Simulacao A (Cd=0.42) — Trajectoria no plano horizontal"),
            plot_velocidades(
                data_a,
                "Simulacao A (Cd=0.42) — Velocidades no corpo "
                "(lineares e angulares)"),
            plot_actuadores(
                data_a,
                "Simulacao A (Cd=0.42) — Comandos dos actuadores"),
            plot_profundidade(
                data_a,
                "Simulacao A (Cd=0.42) — Profundidade vs tempo"),
            # Paginas 5-8: Sim B
            plot_trajectoria(
                data_b,
                "Simulacao B (Cd=0.25) — Trajectoria no plano horizontal"),
            plot_velocidades(
                data_b,
                "Simulacao B (Cd=0.25) — Velocidades no corpo "
                "(lineares e angulares)"),
            plot_actuadores(
                data_b,
                "Simulacao B (Cd=0.25) — Comandos dos actuadores"),
            plot_profundidade(
                data_b,
                "Simulacao B (Cd=0.25) — Profundidade vs tempo"),
            # Pagina 9: comparacao
            plot_comparacao_trajectorias(data_a, data_b),
        ]
        for fig in figuras:
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

    print(f"  -> PDF escrito: {PDF_OUT}")
    print("\nConcluido com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
