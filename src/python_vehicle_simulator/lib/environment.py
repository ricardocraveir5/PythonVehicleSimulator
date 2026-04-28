#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
environment.py — Modelação de correntes oceânicas (Etapa 4).

Define a hierarquia CurrentModel e cinco perfis concretos:
    - ConstantCurrent     (réplica do comportamento actual do torpedo)
    - LinearProfile       (V_c proporcional à profundidade)
    - PowerLawProfile     (lei de potência 1/7, perfil tipo camada-limite)
    - LogarithmicProfile  (perfil logarítmico tipo camada-limite turbulenta)
    - GaussMarkovCurrent  (processo estocástico de Gauss-Markov de 1ª ordem)

Convenção NED: z positivo para baixo, z = 0 corresponde à superfície livre.
Todos os perfis devolvem (V_c, beta_c) em (m/s, rad).

Referência:
    T. I. Fossen, "Handbook of Marine Craft Hydrodynamics and Motion Control",
    2nd ed., Wiley, 2021 — Cap. 10 (Modelling of Environmental Forces).

Autores:
    Ricardo Craveiro (1191000@isep.ipp.pt)
    Afonso Barreiro  (1201126@isep.ipp.pt)
DINAV 2026 — Etapa 4
"""

import math
from abc import ABC, abstractmethod

import numpy as np


# ---------------------------------------------------------------------------
# Classe abstracta
# ---------------------------------------------------------------------------

class CurrentModel(ABC):
    """Interface comum a todos os modelos de corrente oceânica."""

    @abstractmethod
    def get_current(self, z: float, t: float) -> tuple[float, float]:
        """Devolve (V_c, beta_c) à profundidade z (m) e instante t (s).

        Parâmetros
        ----------
        z : float
            Profundidade em metros (NED, positivo para baixo).
        t : float
            Tempo em segundos.

        Devolve
        -------
        tuple[float, float]
            (V_c em m/s, beta_c em radianos).
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Validador auxiliar
# ---------------------------------------------------------------------------

def _validar_beta(beta_c: float) -> None:
    """beta_c deve estar em [-π, π] (mesma convenção do torpedo.py)."""
    if not -math.pi <= beta_c <= math.pi:
        raise ValueError("beta_c deve estar entre -π e π radianos")


# ---------------------------------------------------------------------------
# 1. Corrente constante
# ---------------------------------------------------------------------------

class ConstantCurrent(CurrentModel):
    """Corrente uniforme — V_c e beta_c constantes em z e t.

    Replica o comportamento original de torpedo.py (atributos privados
    _V_c e _beta_c usados em dynamics()).
    """

    def __init__(self, V_c: float, beta_c: float):
        if V_c < 0:
            raise ValueError("V_c deve ser >= 0")
        _validar_beta(beta_c)
        self._V_c = float(V_c)
        self._beta_c = float(beta_c)

    def get_current(self, z: float, t: float) -> tuple[float, float]:
        return self._V_c, self._beta_c


# ---------------------------------------------------------------------------
# 2. Perfil linear
# ---------------------------------------------------------------------------

class LinearProfile(CurrentModel):
    """Perfil linear: V_c(z) = V_surface * (z / z_ref) para z > 0.

    Para z <= 0 (acima ou na superfície) devolve V_c = 0.
    """

    def __init__(self, V_surface: float, z_ref: float, beta_c: float):
        if V_surface < 0:
            raise ValueError("V_surface deve ser >= 0")
        if z_ref <= 0:
            raise ValueError("z_ref deve ser > 0")
        _validar_beta(beta_c)
        self._V_surface = float(V_surface)
        self._z_ref = float(z_ref)
        self._beta_c = float(beta_c)

    def get_current(self, z: float, t: float) -> tuple[float, float]:
        if z <= 0.0:
            return 0.0, self._beta_c
        return self._V_surface * (z / self._z_ref), self._beta_c


# ---------------------------------------------------------------------------
# 3. Perfil em lei de potência (1/7)
# ---------------------------------------------------------------------------

class PowerLawProfile(CurrentModel):
    """Perfil em lei de potência 1/7: V_c(z) = V_surface * (z / z_ref)^(1/7).

    Aproximação clássica de camada-limite turbulenta (Fossen 2021, §10.2).
    Para z <= 0 devolve V_c = 0.
    """

    _EXPOENTE = 1.0 / 7.0

    def __init__(self, V_surface: float, z_ref: float, beta_c: float):
        if V_surface < 0:
            raise ValueError("V_surface deve ser >= 0")
        if z_ref <= 0:
            raise ValueError("z_ref deve ser > 0")
        _validar_beta(beta_c)
        self._V_surface = float(V_surface)
        self._z_ref = float(z_ref)
        self._beta_c = float(beta_c)

    def get_current(self, z: float, t: float) -> tuple[float, float]:
        if z <= 0.0:
            return 0.0, self._beta_c
        return (self._V_surface * (z / self._z_ref) ** self._EXPOENTE,
                self._beta_c)


# ---------------------------------------------------------------------------
# 4. Perfil logarítmico
# ---------------------------------------------------------------------------

class LogarithmicProfile(CurrentModel):
    """Perfil logarítmico: V_c(z) = (V_star / kappa) * ln(max(z, z_0) / z_0).

    Modelo padrão de camada-limite turbulenta sobre fundo rugoso. V_star é a
    velocidade de fricção e z_0 a rugosidade aerodinâmica do fundo. kappa é a
    constante de von Kármán (≈ 0.41). Para z <= 0 devolve V_c = 0.
    """

    def __init__(self,
                 V_star: float,
                 z_0: float,
                 beta_c: float,
                 kappa: float = 0.41):
        if V_star < 0:
            raise ValueError("V_star deve ser >= 0")
        if z_0 <= 0:
            raise ValueError("z_0 deve ser > 0")
        if kappa <= 0:
            raise ValueError("kappa deve ser > 0")
        _validar_beta(beta_c)
        self._V_star = float(V_star)
        self._z_0 = float(z_0)
        self._kappa = float(kappa)
        self._beta_c = float(beta_c)

    def get_current(self, z: float, t: float) -> tuple[float, float]:
        if z <= 0.0:
            return 0.0, self._beta_c
        # O max(z, z_0) garante argumento >= 1 do logaritmo, evitando V_c < 0.
        argumento = max(z, self._z_0) / self._z_0
        V_c = (self._V_star / self._kappa) * math.log(argumento)
        return V_c, self._beta_c


# ---------------------------------------------------------------------------
# 5. Corrente Gauss-Markov (1ª ordem)
# ---------------------------------------------------------------------------

class GaussMarkovCurrent(CurrentModel):
    """Processo de Gauss-Markov de 1ª ordem (Fossen 2021, eq. 10.66):

        dV_c/dt = -mu * V_c + w(t),     w ~ N(0, sigma^2)

    Discretização Euler-Maruyama:
        V_c[k+1] = (1 - mu*dt) * V_c[k] + sigma * sqrt(dt) * randn()

    O passo dt é inferido a partir da diferença entre instantes consecutivos
    passados a get_current(). Na primeira chamada (sem histórico) usa-se
    dt = 0.02 s por defeito. A profundidade z é ignorada — o processo é
    vertical-uniforme.
    """

    _DT_DEFAULT = 0.02  # passo nominal usado na 1.ª chamada

    def __init__(self,
                 mu: float,
                 sigma: float,
                 V_c0: float,
                 beta_c: float,
                 rng_seed: int | None = None):
        if mu < 0:
            raise ValueError("mu deve ser >= 0")
        if sigma < 0:
            raise ValueError("sigma deve ser >= 0")
        _validar_beta(beta_c)
        self._mu = float(mu)
        self._sigma = float(sigma)
        self._beta_c = float(beta_c)
        # Estado interno (gerador isolado garante reprodutibilidade).
        self._V_c = float(V_c0)
        self._t_prev: float | None = None
        self._rng = np.random.default_rng(rng_seed)

    def get_current(self, z: float, t: float) -> tuple[float, float]:
        if self._t_prev is None:
            dt = self._DT_DEFAULT
        else:
            # Não admite passos negativos (se o tempo retroceder, congela).
            dt = max(t - self._t_prev, 0.0)

        ruido = self._rng.standard_normal()
        self._V_c = ((1.0 - self._mu * dt) * self._V_c
                     + self._sigma * math.sqrt(dt) * ruido)
        self._t_prev = t
        return self._V_c, self._beta_c
