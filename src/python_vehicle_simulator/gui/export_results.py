"""
export_results.py — Export simulation data to CSV or JSON.

Part of the Torpedo AUV GUI — Etapa 3.
Provides functions to serialise simulation results (time-series and
parameter snapshots) for post-processing in MATLAB, Excel or Python.

References:
    T. I. Fossen, "Handbook of Marine Craft Hydrodynamics and Motion
    Control", 2nd ed., Wiley, 2021.

Original author: Thor I. Fossen
Additions:       Ricardo Craveiro (1191000@isep.ipp.pt)
DINAV 2026 — Etapa 3
"""

import csv
import json
import math
from pathlib import Path

import numpy as np


# Column labels that match the simData layout produced by mainLoop.simulate()
# for the torpedo vehicle (dimU = 5).
_STATE_COLS = [
    "x_north_m", "y_east_m", "z_depth_m",
    "phi_rad", "theta_rad", "psi_rad",
    "u_ms", "v_ms", "w_ms",
    "p_rads", "q_rads", "r_rads",
]

_CONTROL_CMD_COLS = [
    "delta_r_top_rad", "delta_r_bottom_rad",
    "delta_s_star_rad", "delta_s_port_rad",
    "n_cmd_rpm",
]

_CONTROL_ACT_COLS = [
    "delta_r_top_actual_rad", "delta_r_bottom_actual_rad",
    "delta_s_star_actual_rad", "delta_s_port_actual_rad",
    "n_actual_rpm",
]


def _build_header(dimU: int) -> list[str]:
    """Build the full CSV header based on vehicle dimU."""
    header = ["t_s"] + _STATE_COLS
    if dimU == 5:
        header += _CONTROL_CMD_COLS + _CONTROL_ACT_COLS
    else:
        header += [f"u_cmd_{i}" for i in range(dimU)]
        header += [f"u_act_{i}" for i in range(dimU)]
    return header


def export_csv(filepath: str | Path,
               simTime: np.ndarray,
               simData: np.ndarray,
               params: dict | None = None,
               dimU: int = 5) -> Path:
    """
    Export simulation results to a CSV file.

    Parameters
    ----------
    filepath : str or Path
        Destination file (will be overwritten if it exists).
    simTime : (N, 1) array
        Time vector from mainLoop.simulate().
    simData : (N, 2*DOF + 2*dimU) array
        State + control data from mainLoop.simulate().
    params : dict, optional
        Model parameter snapshot (from get_all_params()) — written as
        a comment header.
    dimU : int
        Number of control inputs (default 5 for torpedo).

    Returns
    -------
    Path
        The resolved path of the written file.
    """
    filepath = Path(filepath)
    header = _build_header(dimU)
    t = simTime[:, 0] if simTime.ndim == 2 else simTime
    n_cols = min(simData.shape[1], len(header) - 1)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        if params:
            f.write(f"# Torpedo AUV simulation export\n")
            for k, v in params.items():
                f.write(f"# {k} = {v}\n")
            f.write("#\n")

        writer = csv.writer(f)
        writer.writerow(header[:n_cols + 1])
        for i in range(len(t)):
            row = [f"{t[i]:.4f}"] + [f"{simData[i, j]:.6g}"
                                      for j in range(n_cols)]
            writer.writerow(row)

    return filepath.resolve()


def export_json(filepath: str | Path,
                simTime: np.ndarray,
                simData: np.ndarray,
                params: dict | None = None,
                dimU: int = 5) -> Path:
    """
    Export simulation results to a JSON file.

    The JSON structure is::

        {
            "params": { ... },
            "columns": ["t_s", "x_north_m", ...],
            "data": [[0.0, 0.0, ...], ...]
        }

    Parameters
    ----------
    filepath, simTime, simData, params, dimU
        Same as :func:`export_csv`.

    Returns
    -------
    Path
        The resolved path of the written file.
    """
    filepath = Path(filepath)
    header = _build_header(dimU)
    t = simTime[:, 0] if simTime.ndim == 2 else simTime
    n_cols = min(simData.shape[1], len(header) - 1)

    # Convert numpy arrays to plain Python for JSON serialisation
    data_rows = []
    for i in range(len(t)):
        row = [round(float(t[i]), 4)]
        row += [float(simData[i, j]) for j in range(n_cols)]
        data_rows.append(row)

    # Sanitise params (convert numpy types to Python builtins)
    clean_params = {}
    if params:
        for k, v in params.items():
            if isinstance(v, (np.integer, np.floating)):
                clean_params[k] = float(v)
            elif isinstance(v, np.ndarray):
                clean_params[k] = v.tolist()
            elif isinstance(v, list):
                clean_params[k] = [float(x) if isinstance(x, (np.integer, np.floating)) else x for x in v]
            else:
                clean_params[k] = v

    payload = {
        "params": clean_params,
        "columns": header[:n_cols + 1],
        "data": data_rows,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return filepath.resolve()
