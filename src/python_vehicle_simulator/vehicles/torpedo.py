#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
torpedo.py:

    Torpedo-shaped vehicle based on the REMUS 100 platform, with modified
    fin-based control:

	- Includes a new finClass that allows fins to be placed at arbitrary
        locations on the vehicle.
	- Computes the force vector based on the local relative water velocity.
	- Supports actuator dynamics for fin control based on input commands.

    The vehicle is controlled using four fins and a propeller. It has a length
    of 1.6 m, a cylindrical body with a 19 cm diameter, and a total mass of
    31.9 kg. The maximum speed is 2.5 m/s, achieved when the propeller runs at
    1525 RPM in still water (no current).

   torpedo()
       Step input, stern plane, rudder and propeller revolution

    torpedo('depthHeadingAutopilot',z_d,psi_d,n_d,V_c,beta_c)
        z_d:    desired depth (m), positive downwards
        psi_d:  desired yaw angle (deg)
        n_d:    desired propeller revolution (rpm)
        V_c:    current speed (m/s)
        beta_c: current direction (deg)

Methods:

    [nu,u_actual] = dynamics(eta,nu,u_actual,u_control,sampleTime ) returns
        nu[k+1] and u_actual[k+1] using Euler's method. The control input is:

            u_control = [ delta_r_top   rudder angle (rad)
                         delta_r_bottom rudder angle (rad)
                         delta_s_star    stern plane angle (rad)
                         delta_s_port    stern plane angle (rad)
                         n          propeller revolution (rpm) ]

    u = depthHeadingAutopilot(eta,nu,sampleTime)
        Simultaneously control of depth and heading using controllers of
        PID and SMC ype. Propeller rpm is given as a step command.

    u = stepInput(t) generates tail rudder, stern planes and RPM step inputs.

References:

    B. Allen, W. S. Vorus and T. Prestero, "Propulsion system performance
         enhancements on REMUS AUVs," OCEANS 2000 MTS/IEEE Conference and
         Exhibition. Conference Proceedings, 2000, pp. 1869-1873 vol.3,
         doi: 10.1109/OCEANS.2000.882209.
    T. I. Fossen (2021). Handbook of Marine Craft Hydrodynamics and Motion
         Control. 2nd. Edition, Wiley. URL: www.fossen.biz/wiley

Author:     Braden Meyers
"""
# Modified by: Ricardo Craveiro
#              (1191000@isep.ipp.pt)
# DINAV 2026 — Etapa 2
# Additions: getters/setters with physical
#            validation (Fossen 2021)
# Note: Original anomalias A1, A5, A6
#       documentadas mas preservadas para
#       manter interface base com mainLoop.py

import logging
import numpy as np
import math
from python_vehicle_simulator.lib.control import integralSMC
from python_vehicle_simulator.lib.gnc import crossFlowDrag,forceLiftDrag,Hmtrx,m2c,gvect,ssa
from python_vehicle_simulator.lib.actuator import fin, thruster

# Class Vehicle
class torpedo:
    """
    torpedo()
        Rudder angle, stern plane and propeller revolution step inputs

    torpedo('depthHeadingAutopilot',z_d,psi_d,n_d,V_c,beta_c)
        Depth and heading autopilots

    Inputs:
        z_d:    desired depth, positive downwards (m)
        psi_d:  desired heading angle (deg)
        n_d:    desired propeller revolution (rpm)
        V_c:    current speed (m/s)
        beta_c: current direction (deg)
    """

    def __init__(
        self,
        controlSystem="stepInput",
        r_z = 0,
        r_psi = 0,
        r_rpm = 0,
        V_current = 0,
        beta_current = 0,
    ):

        # Constants
        self.D2R = math.pi / 180        # deg2rad
        self.rho = 1026                 # density of water (kg/m^3)
        g = 9.81                        # acceleration of gravity (m/s^2)

        if controlSystem == "depthHeadingAutopilot":
            self.controlDescription = (
                "Depth and heading autopilots, z_d = "
                + str(r_z)
                + ", psi_d = "
                + str(r_psi)
                + " deg"
                )

        else:
            self.controlDescription = (
                "Step inputs for stern planes, rudder and propeller")
            controlSystem = "stepInput"

        # Reference inputs stored as private attributes (A9: validators added in 2B)
        self._ref_z   = r_z
        self._ref_psi = r_psi
        self._ref_n   = r_rpm
        self._V_c     = V_current
        self._beta_c  = beta_current * self.D2R
        self.controlMode = controlSystem

        # Initialize the AUV model
        self.name = (
            "Torpedo-shaped vehicle based on the REMUS 100 AUV (see 'torpedo100.py' for more details)")
        self._L    = 1.6                # length (m)  — private; property in 2B
        self._diam = 0.19               # cylinder diameter (m) — private; property in 2B

        self.nu = np.array([0, 0, 0, 0, 0, 0], float) # velocity vector
        self.controls = [
            "T Tail rudder (deg)",
            "B Tail rudder (deg)",
            "Star Stern plane (deg)",
            "Port Stern plane (deg)",
            "Propeller revolution (rpm)"
            ]
        self.dimU = len(self.controls)
        self.u_actual = np.zeros(self.dimU, float)    # control input vector

        prop = thruster(self.rho)

        if r_rpm < 0.0 or r_rpm > prop.nMax:
            raise ValueError(
                f"RPM deve estar no intervalo [0, {prop.nMax}]")

        if r_z > 100.0 or r_z < 0.0:
            raise ValueError(
                "Profundidade desejada deve estar entre 0 e 100 m")

        # Hydrodynamics (Fossen 2021, Section 8.4.2)
        self.S = 0.7 * self._L * self._diam  # S = 70% of rectangle L * diam
        self._a = self._L / 2                # semi-axis major (promoted from local var)
        self._b = self._diam / 2             # semi-axis minor (promoted from local var)
        self.r_bg = np.array([0, 0, 0.02], float)    # CG w.r.t. to the CO
        self.r_bb = np.array([0, 0, 0], float)       # CB w.r.t. to the CO

        # Parasitic drag coefficient CD_0, i.e. zero lift and alpha = 0
        # F_drag = 0.5 * rho * Cd * (pi * b^2)
        # F_drag = 0.5 * rho * CD_0 * S
        self._Cd = 0.42                              # from Allen et al. (2000) — promoted
        self.CD_0 = self._Cd * math.pi * self._b**2 / self.S

        # Rigid-body mass matrix expressed in CO
        m = 4/3 * math.pi * self.rho * self._a * self._b**2  # mass of spheriod
        Ix = (2/5) * m * self._b**2                          # moment of inertia
        Iy = (1/5) * m * (self._a**2 + self._b**2)
        Iz = Iy
        MRB_CG = np.diag([ m, m, m, Ix, Iy, Iz ])   # MRB expressed in the CG
        H_rg = Hmtrx(self.r_bg)
        self.MRB = H_rg.T @ MRB_CG @ H_rg           # MRB expressed in the CO

        # Weight and buoyancy
        self.W = m * g
        self.B = self.W

        # Added moment of inertia in roll: A44 = r44 * Ix
        self._r44 = 0.3              # roll inertia factor (promoted from local var)
        MA_44 = self._r44 * Ix

        # Lamb's k-factors
        e = math.sqrt( 1-(self._b/self._a)**2 )
        alpha_0 = ( 2 * (1-e**2)/pow(e,3) ) * ( 0.5 * math.log( (1+e)/(1-e) ) - e )
        beta_0  = 1/(e**2) - (1-e**2) / (2*pow(e,3)) * math.log( (1+e)/(1-e) )

        k1 = alpha_0 / (2 - alpha_0)
        k2 = beta_0  / (2 - beta_0)
        k_prime = pow(e,4) * (beta_0-alpha_0) / (
            (2-e**2) * ( 2*e**2 - (2-e**2) * (beta_0-alpha_0) ) )

        # Added mass system matrix expressed in the CO
        self.MA = np.diag([ m*k1, m*k2, m*k2, MA_44, k_prime*Iy, k_prime*Iy ])

        # Mass matrix including added mass
        self.M = self.MRB + self.MA
        self.Minv = np.linalg.inv(self.M)

        # Natural frequencies in roll and pitch
        self.w_roll = math.sqrt( self.W * ( self.r_bg[2]-self.r_bb[2] ) /
            self.M[3][3] )
        self.w_pitch = math.sqrt( self.W * ( self.r_bg[2]-self.r_bb[2] ) /
            self.M[4][4] )

        S_fin = 0.00665;            # fin area
        CL_delta_r = 0.5            # rudder lift coefficient
        CL_delta_s = 0.7            # stern-plane lift coefficient

        # ANOMALIA A1: portSternFin (angle=0°) é colocada em y=+0.1 m (estibordo)
        # e starSternFin (angle=180°) em y=-0.1 m (bombordo). Os nomes parecem
        # trocados relativamente à posição física calculada.
        # NÃO corrigido para preservar o comportamento original (DINAV 2026, Agente 2).
        portSternFin    = fin(S_fin, CL_delta_s, -self._a, c=0.1, angle=0,   rho=self.rho)
        bottomRudderFin = fin(S_fin, CL_delta_r, -self._a, c=0.1, angle=90,  rho=self.rho)
        starSternFin    = fin(S_fin, CL_delta_s, -self._a, c=0.1, angle=180, rho=self.rho)
        topRudderFin    = fin(S_fin, CL_delta_r, -self._a, c=0.1, angle=270, rho=self.rho)
        self.actuators = [topRudderFin, bottomRudderFin, starSternFin, portSternFin, prop]

        # Low-speed linear damping matrix parameters
        self._T_surge    = 20           # time constant in surge (s)
        self._T_sway     = 20           # time constant in sway (s)
        self._T_heave    = self._T_sway # equal for a cylinder-shaped AUV (A7: coupled)
        self._zeta_roll  = 0.3          # relative damping ratio in roll
        self._zeta_pitch = 0.8          # relative damping ratio in pitch
        self._T_yaw      = 1            # time constant in yaw (s)

        # Feed forward gains (Nomoto gain parameters)
        self._K_nomoto = 5.0/20.0       # K_nomoto = r_max / delta_max
        self._T_nomoto = self._T_yaw    # Time constant in yaw (A8: coupled to T_yaw)

        # Heading autopilot reference model
        self.psi_d  = 0                    # position, velocity and acc. states
        self.r_d    = 0
        self.a_d    = 0
        self._wn_d   = 0.1                 # desired natural frequency
        self._zeta_d = 1                   # desired relative damping ratio
        self._r_max  = 5.0 * math.pi / 180 # maximum yaw rate

        # Heading autopilot (Equation 16.479 in Fossen 2021)
        # sigma = r-r_d + 2*lambda*ssa(psi-psi_d) + lambda^2 * integral(ssa(psi-psi_d))
        # delta = (T_nomoto * r_r_dot + r_r - K_d * sigma
        #       - K_sigma * (sigma/phi_b)) / K_nomoto
        self._lam     = 0.1
        self._phi_b   = 0.1    # boundary layer thickness
        self._K_d     = 0.5    # PID gain
        self._K_sigma = 0.05   # SMC switching gain

        self.e_psi_int = 0     # yaw angle error integral state

        # Depth autopilot
        self._wn_d_z   = 0.02  # desired natural frequency, reference model
        self._Kp_z     = 0.1   # heave proportional gain, outer loop
        self._T_z      = 100.0 # heave integral gain, outer loop
        self._Kp_theta = 5.0   # pitch PID controller
        self._Kd_theta = 2.0
        self._Ki_theta = 0.3
        self._K_w      = 5.0   # optional heave velocity feedback gain

        self.z_int     = 0     # heave position integral state
        self.z_d       = 0     # desired position, LP filter initial state
        self.theta_int = 0     # pitch angle integral state


    # -----------------------------------------------------------------------
    # BLOCO 1 — Parâmetros físicos (getters/setters com validação física)
    # -----------------------------------------------------------------------

    @property
    def L(self): return self._L

    @L.setter
    def L(self, valor):
        if valor <= 0:
            raise ValueError(
                "L deve ser > 0")
        if valor <= self._diam:
            raise ValueError(
                "L deve ser maior do que o diâmetro (diam)")
        self._L = valor
        self._a = valor / 2
        self._recalculate_derived()

    @property
    def diam(self): return self._diam

    @diam.setter
    def diam(self, valor):
        if valor <= 0:
            raise ValueError(
                "diam deve ser > 0")
        if valor >= self._L:
            raise ValueError(
                "diam deve ser < L")
        self._diam = valor
        self._b = valor / 2
        self._recalculate_derived()

    @property
    def massa(self):
        return (4/3 * math.pi * self.rho *
                self._a * self._b**2)

    @property
    def Cd(self): return self._Cd

    @Cd.setter
    def Cd(self, valor):
        if not 0.1 <= valor <= 0.5:
            raise ValueError(
                "Cd deve estar entre 0.1 e 0.5")
        self._Cd = valor
        self._recalculate_derived()

    @property
    def r44(self): return self._r44

    @r44.setter
    def r44(self, valor):
        if not 0.1 <= valor <= 0.5:
            raise ValueError(
                "r44 deve estar entre 0.1 e 0.5")
        self._r44 = valor
        self._recalculate_derived()

    @property
    def T_surge(self): return self._T_surge

    @T_surge.setter
    def T_surge(self, valor):
        if valor <= 0:
            raise ValueError(
                "T_surge deve ser > 0")
        self._T_surge = valor

    @property
    def T_sway(self): return self._T_sway

    @T_sway.setter
    def T_sway(self, valor):
        if valor <= 0:
            raise ValueError(
                "T_sway deve ser > 0")
        self._T_sway = valor
        self._T_heave = valor

    @property
    def T_heave(self): return self._T_heave

    @property
    def zeta_roll(self): return self._zeta_roll

    @zeta_roll.setter
    def zeta_roll(self, valor):
        if not 0.0 <= valor <= 1.0:
            raise ValueError(
                "zeta_roll deve estar entre 0 e 1")
        self._zeta_roll = valor

    @property
    def zeta_pitch(self): return self._zeta_pitch

    @zeta_pitch.setter
    def zeta_pitch(self, valor):
        if not 0.0 <= valor <= 1.0:
            raise ValueError(
                "zeta_pitch deve estar entre 0 e 1")
        self._zeta_pitch = valor

    @property
    def T_yaw(self): return self._T_yaw

    @T_yaw.setter
    def T_yaw(self, valor):
        if valor <= 0:
            raise ValueError(
                "T_yaw deve ser > 0")
        self._T_yaw = valor
        self._T_nomoto = valor

    @property
    def T_nomoto(self): return self._T_nomoto

    # -----------------------------------------------------------------------
    # BLOCO 2 — Parâmetros de referência
    # -----------------------------------------------------------------------

    @property
    def ref_z(self): return self._ref_z

    @ref_z.setter
    def ref_z(self, valor):
        if not 0.0 <= valor <= 100.0:
            raise ValueError(
                "ref_z deve estar entre 0 e 100 m")
        self._ref_z = valor

    @property
    def ref_psi(self): return self._ref_psi

    @ref_psi.setter
    def ref_psi(self, valor):
        self._ref_psi = float(valor)

    @property
    def ref_n(self): return self._ref_n

    @ref_n.setter
    def ref_n(self, valor):
        nMax = self.get_thruster_nMax()
        if not 0.0 <= valor <= nMax:
            raise ValueError(
                f"ref_n deve estar entre 0 e {nMax}")
        self._ref_n = valor

    @property
    def V_c(self): return self._V_c

    @V_c.setter
    def V_c(self, valor):
        if valor < 0:
            raise ValueError(
                "V_c deve ser >= 0")
        self._V_c = valor

    @property
    def beta_c(self): return self._beta_c

    @beta_c.setter
    def beta_c(self, valor):
        if not -180.0 <= valor <= 180.0:
            raise ValueError(
                "beta_c deve estar entre -180 e 180")
        self._beta_c = valor

    # -----------------------------------------------------------------------
    # BLOCO 3 — Métodos de acesso às barbatanas e propulsor
    # -----------------------------------------------------------------------

    def get_fin_CL(self, index):
        if not 0 <= index <= 3:
            raise ValueError(
                "index deve ser entre 0 e 3")
        return self.actuators[index].CL

    def set_fin_CL(self, index, valor):
        if not 0 <= index <= 3:
            raise ValueError(
                "index deve ser entre 0 e 3")
        if not 0.0 <= valor <= 1.0:
            raise ValueError(
                "CL deve estar entre 0.0 e 1.0")
        self.actuators[index].CL = valor

    def get_fin_area(self, index):
        if not 0 <= index <= 3:
            raise ValueError(
                "index deve ser entre 0 e 3")
        return self.actuators[index].area

    def set_fin_area(self, index, valor):
        if not 0 <= index <= 3:
            raise ValueError(
                "index deve ser entre 0 e 3")
        if valor <= 0:
            raise ValueError(
                "area deve ser > 0")
        self.actuators[index].area = valor

    def get_fin_position(self, index):
        if not 0 <= index <= 3:
            raise ValueError(
                "index deve ser entre 0 e 3")
        return self.actuators[index].R[0]

    def set_fin_position(self, index, valor):
        if not 0 <= index <= 3:
            raise ValueError(
                "index deve ser entre 0 e 3")
        if not -self._L <= valor <= 0:
            raise ValueError(
                f"posição deve estar entre "
                f"-{self._L} e 0")
        self.actuators[index].R[0] = valor

    def get_thruster_nMax(self):
        return self.actuators[4].nMax

    def set_thruster_nMax(self, valor):
        if not 0 < valor <= 1525:
            raise ValueError(
                "nMax deve estar entre 0 e 1525 RPM")
        self.actuators[4].nMax = valor

    # -----------------------------------------------------------------------
    # BLOCO 1 — Controlador de profundidade
    # -----------------------------------------------------------------------

    @property
    def wn_d_z(self): return self._wn_d_z

    @wn_d_z.setter
    def wn_d_z(self, valor):
        if valor <= 0:
            raise ValueError(
                "wn_d_z deve ser > 0")
        self._wn_d_z = valor

    @property
    def Kp_z(self): return self._Kp_z

    @Kp_z.setter
    def Kp_z(self, valor):
        if valor <= 0:
            raise ValueError(
                "Kp_z deve ser > 0")
        self._Kp_z = valor

    @property
    def T_z(self): return self._T_z

    @T_z.setter
    def T_z(self, valor):
        if valor <= 0:
            raise ValueError(
                "T_z deve ser > 0")
        self._T_z = valor

    @property
    def Kp_theta(self): return self._Kp_theta

    @Kp_theta.setter
    def Kp_theta(self, valor):
        if valor <= 0:
            raise ValueError(
                "Kp_theta deve ser > 0")
        self._Kp_theta = valor

    @property
    def Kd_theta(self): return self._Kd_theta

    @Kd_theta.setter
    def Kd_theta(self, valor):
        if valor <= 0:
            raise ValueError(
                "Kd_theta deve ser > 0")
        self._Kd_theta = valor

    @property
    def Ki_theta(self): return self._Ki_theta

    @Ki_theta.setter
    def Ki_theta(self, valor):
        if valor < 0:
            raise ValueError(
                "Ki_theta deve ser >= 0")
        self._Ki_theta = valor

    @property
    def K_w(self): return self._K_w

    @K_w.setter
    def K_w(self, valor):
        if valor < 0:
            raise ValueError(
                "K_w deve ser >= 0")
        self._K_w = valor

    # -----------------------------------------------------------------------
    # BLOCO 2 — Controlador de rumo
    # -----------------------------------------------------------------------

    @property
    def wn_d(self): return self._wn_d

    @wn_d.setter
    def wn_d(self, valor):
        if valor <= 0:
            raise ValueError(
                "wn_d deve ser > 0")
        self._wn_d = valor

    @property
    def zeta_d(self): return self._zeta_d

    @zeta_d.setter
    def zeta_d(self, valor):
        if not 0.5 <= valor <= 2.0:
            raise ValueError(
                "zeta_d deve estar entre 0.5 e 2.0")
        self._zeta_d = valor

    @property
    def K_nomoto(self): return self._K_nomoto

    @K_nomoto.setter
    def K_nomoto(self, valor):
        if valor <= 0:
            raise ValueError(
                "K_nomoto deve ser > 0")
        self._K_nomoto = valor

    @property
    def lam(self): return self._lam

    @lam.setter
    def lam(self, valor):
        if valor <= 0:
            raise ValueError(
                "lam deve ser > 0")
        self._lam = valor

    @property
    def phi_b(self): return self._phi_b

    @phi_b.setter
    def phi_b(self, valor):
        if valor <= 0:
            raise ValueError(
                "phi_b deve ser > 0")
        self._phi_b = valor

    @property
    def K_d(self): return self._K_d

    @K_d.setter
    def K_d(self, valor):
        if valor <= 0:
            raise ValueError(
                "K_d deve ser > 0")
        self._K_d = valor

    @property
    def K_sigma(self): return self._K_sigma

    @K_sigma.setter
    def K_sigma(self, valor):
        if valor <= 0:
            raise ValueError(
                "K_sigma deve ser > 0")
        self._K_sigma = valor

    @property
    def r_max(self): return self._r_max

    @r_max.setter
    def r_max(self, valor):
        if valor <= 0:
            raise ValueError(
                "r_max deve ser > 0")
        self._r_max = valor

    # -----------------------------------------------------------------------
    # BLOCO 3 — Métodos utilitários
    # -----------------------------------------------------------------------

    def _recalculate_derived(self):
        """
        Recalcula todos os parâmetros derivados da geometria e das propriedades
        físicas do torpedo, na mesma ordem do __init__.

        Deve ser chamado após qualquer alteração a:
          _L / _diam (via setters L e diam)
          _Cd        (via setter Cd)
          _r44       (via setter r44)

        Referência: Fossen (2021), Capítulo 8.
        Original author: Thor I. Fossen
        Addition: Ricardo Craveiro (1191000@isep.ipp.pt)
        DINAV 2026 — Etapa 2
        """
        g = 9.81

        # Geometria
        self.S    = 0.7 * self._L * self._diam
        self.CD_0 = self._Cd * math.pi * self._b**2 / self.S

        # Matriz de massa rígida
        m     = 4/3 * math.pi * self.rho * self._a * self._b**2
        Ix    = (2/5) * m * self._b**2
        Iy    = (1/5) * m * (self._a**2 + self._b**2)
        Iz    = Iy
        MRB_CG = np.diag([m, m, m, Ix, Iy, Iz])
        H_rg   = Hmtrx(self.r_bg)
        self.MRB = H_rg.T @ MRB_CG @ H_rg

        # Peso e flutuabilidade
        self.W = m * g
        self.B = self.W

        # Massa adicionada (k-factors de Lamb)
        MA_44   = self._r44 * Ix
        e       = math.sqrt(1 - (self._b / self._a)**2)
        alpha_0 = (2 * (1 - e**2) / pow(e, 3)) * (
            0.5 * math.log((1 + e) / (1 - e)) - e)
        beta_0  = (1 / e**2) - (1 - e**2) / (2 * pow(e, 3)) * math.log(
            (1 + e) / (1 - e))
        k1      = alpha_0 / (2 - alpha_0)
        k2      = beta_0  / (2 - beta_0)
        k_prime = pow(e, 4) * (beta_0 - alpha_0) / (
            (2 - e**2) * (2 * e**2 - (2 - e**2) * (beta_0 - alpha_0)))
        self.MA = np.diag([m*k1, m*k2, m*k2, MA_44,
                           k_prime*Iy, k_prime*Iy])

        # Matriz de massa total
        self.M    = self.MRB + self.MA
        self.Minv = np.linalg.inv(self.M)

        # Frequências naturais
        dz = self.r_bg[2] - self.r_bb[2]
        self.w_roll  = math.sqrt(self.W * dz / self.M[3][3])
        self.w_pitch = math.sqrt(self.W * dz / self.M[4][4])

        # Posição longitudinal das barbatanas (na popa = -a)
        if hasattr(self, 'actuators'):
            for i in range(4):
                self.actuators[i].R[0] = -self._a

    def get_all_params(self):
        """
        Devolve dicionário com todos os parâmetros
        actuais — usado pelo Controller.
        Original author: Thor I. Fossen
        Addition: Ricardo Craveiro, DINAV 2026
        """
        return {
            'L': self._L,
            'diam': self._diam,
            'massa': self.massa,
            'Cd': self._Cd,
            'r44': self._r44,
            'T_surge': self._T_surge,
            'T_sway': self._T_sway,
            'T_heave': self._T_heave,
            'zeta_roll': self._zeta_roll,
            'zeta_pitch': self._zeta_pitch,
            'T_yaw': self._T_yaw,
            'K_nomoto': self._K_nomoto,
            'T_nomoto': self._T_nomoto,
            'wn_d': self._wn_d,
            'zeta_d': self._zeta_d,
            'r_max': self._r_max,
            'lam': self._lam,
            'phi_b': self._phi_b,
            'K_d': self._K_d,
            'K_sigma': self._K_sigma,
            'wn_d_z': self._wn_d_z,
            'Kp_z': self._Kp_z,
            'T_z': self._T_z,
            'Kp_theta': self._Kp_theta,
            'Kd_theta': self._Kd_theta,
            'Ki_theta': self._Ki_theta,
            'K_w': self._K_w,
            'ref_z': self._ref_z,
            'ref_psi': self._ref_psi,
            'ref_n': self._ref_n,
            'V_c': self._V_c,
            'beta_c': self._beta_c,
            'fin_CL': [self.get_fin_CL(i)
                       for i in range(4)],
            'fin_area': [self.get_fin_area(i)
                         for i in range(4)],
            'thruster_nMax': self.get_thruster_nMax()
        }

    def set_from_dict(self, params_dict):
        """
        Recebe dicionário e aplica todos os setters
        com validação — usado pelo Controller.
        Lança ValueError com nome do parâmetro
        se validação falhar.
        Original author: Thor I. Fossen
        Addition: Ricardo Craveiro, DINAV 2026
        """
        for key, value in params_dict.items():
            try:
                if key.startswith('fin_CL_'):
                    idx = int(key.split('_')[-1])
                    self.set_fin_CL(idx, value)
                elif key.startswith('fin_area_'):
                    idx = int(key.split('_')[-1])
                    self.set_fin_area(idx, value)
                elif key == 'thruster_nMax':
                    self.set_thruster_nMax(value)
                elif key in ('massa', 'T_heave',
                             'T_nomoto'):
                    logging.warning(
                        "Parâmetro '%s' é read-only e foi ignorado.", key)
                elif hasattr(self, key):
                    setattr(self, key, value)
            except ValueError as e:
                raise ValueError(
                    f"Parâmetro '{key}': {str(e)}")

    def dynamics(self, eta, nu, u_actual, u_control, sampleTime):
        """
        [nu,u_actual] = dynamics(eta,nu,u_actual,u_control,sampleTime) integrates
        the AUV equations of motion using Euler's method.
        """

        # Current velocities
        u_c = self._V_c * math.cos(self._beta_c - eta[5])  # current surge velocity
        v_c = self._V_c * math.sin(self._beta_c - eta[5])  # current sway velocity

        nu_c = np.array([u_c, v_c, 0, 0, 0, 0], float) # current velocity
        Dnu_c = np.array([nu[5]*v_c, -nu[5]*u_c, 0, 0, 0, 0],float) # derivative
        nu_r = nu - nu_c                               # relative velocity
        alpha = math.atan2( nu_r[2], nu_r[0] )         # angle of attack
        U_r = math.sqrt(nu_r[0]**2 + nu_r[1]**2 + nu_r[2]**2)  # relative speed

        # Rigi-body/added mass Coriolis/centripetal matrices expressed in the CO
        CRB = m2c(self.MRB, nu_r)
        CA  = m2c(self.MA, nu_r)

        # CA-terms in roll, pitch and yaw can destabilize the model if quadratic
        # rotational damping is missing. These terms are assumed to be zero
        CA[4][0] = 0     # Quadratic velocity terms due to pitching
        CA[0][4] = 0
        CA[4][2] = 0
        CA[2][4] = 0
        CA[5][0] = 0     # Munk moment in yaw
        CA[0][5] = 0
        CA[5][1] = 0
        CA[1][5] = 0

        C = CRB + CA

        # Dissipative forces and moments
        D = np.diag([
            self.M[0][0] / self._T_surge,
            self.M[1][1] / self._T_sway,
            self.M[2][2] / self._T_heave,
            self.M[3][3] * 2 * self._zeta_roll  * self.w_roll,
            self.M[4][4] * 2 * self._zeta_pitch * self.w_pitch,
            self.M[5][5] / self._T_yaw
            ])

        # Linear surge and sway damping
        D[0][0] = D[0][0] * math.exp(-3*U_r) # vanish at high speed where quadratic
        D[1][1] = D[1][1] * math.exp(-3*U_r) # drag and lift forces dominates

        tau_liftdrag = forceLiftDrag(self._diam, self.S, self.CD_0, alpha, U_r)
        tau_crossflow = crossFlowDrag(self._L, self._diam, self._diam, nu_r)

        # Restoring forces and moments
        g = gvect(self.W, self.B, eta[4], eta[3], self.r_bg, self.r_bb)

        # General force vector
        tau = np.zeros(6,float)
        for i in range(self.dimU):
            tau += self.actuators[i].tau(nu_r, nu)
            u_actual[i] = self.actuators[i].actuate(sampleTime, u_control[i]) # Actuator Dynamics

        # AUV dynamics
        tau_sum = tau + tau_liftdrag + tau_crossflow - np.matmul(C+D,nu_r)  - g
        nu_dot = Dnu_c + np.matmul(self.Minv, tau_sum)


        # Forward Euler integration [k+1]
        nu += sampleTime * nu_dot

        return nu, u_actual


    def stepInput(self, t):
        """
        u_c = stepInput(t) generates step inputs.

        Returns:

            u_control = [ delta_r   rudder angle (rad)
                         delta_s    stern plane angle (rad)
                         n          propeller revolution (rpm) ]
        """
        delta_r =  5 * self.D2R      # rudder angle (rad)
        delta_s = -5 * self.D2R      # stern angle (rad)
        # ANOMALIA A5: n=1525 está hardcoded e ignora self._ref_n.
        # NÃO corrigido para preservar o comportamento original (DINAV 2026, Agente 2).
        n = 1525                     # propeller revolution (rpm)

        if t > 100:
            delta_r = 0

        if t > 50:
            delta_s = 0

        # ANOMALIA A6: sinais de delta_s em posições 2 e 3 são opostos
        # relativamente ao depthHeadingAutopilot. NÃO corrigido para
        # preservar o comportamento original (DINAV 2026, Agente 2).
        u_control = np.array([ delta_r, -delta_r, -delta_s, delta_s, n], float)

        return u_control


    def depthHeadingAutopilot(self, eta, nu, sampleTime):
        """
        [delta_r, delta_s, n] = depthHeadingAutopilot(eta,nu,sampleTime)
        simultaneously control the heading and depth of the AUV using control
        laws of PID type. Propeller rpm is given as a step command.

        Returns:

            u_control = [ delta_r   rudder angle (rad)
                         delta_s    stern plane angle (rad)
                         n          propeller revolution (rpm) ]

        """
        z     = eta[2]              # heave position (depth)
        theta = eta[4]              # pitch angle
        psi   = eta[5]              # yaw angle
        w     = nu[2]               # heave velocity
        q     = nu[4]               # pitch rate
        r     = nu[5]               # yaw rate
        e_psi = psi - self.psi_d    # yaw angle tracking error
        e_r   = r - self.r_d        # yaw rate tracking error
        z_ref   = self._ref_z                   # heave position (depth) setpoint
        psi_ref = self._ref_psi * self.D2R      # yaw angle setpoint

        #######################################################################
        # Propeller command
        #######################################################################
        n = self._ref_n

        #######################################################################
        # Depth autopilot (succesive loop closure)
        #######################################################################
        # LP filtered desired depth command
        self.z_d  = math.exp( -sampleTime * self._wn_d_z ) * self.z_d \
            + ( 1 - math.exp( -sampleTime * self._wn_d_z) ) * z_ref

        # PI controller
        theta_d = self._Kp_z * ( (z - self.z_d) + (1/self._T_z) * self.z_int )
        delta_s = -self._Kp_theta * ssa( theta - theta_d ) - self._Kd_theta * q \
            - self._Ki_theta * self.theta_int - self._K_w * w

        # Euler's integration method (k+1)
        self.z_int     += sampleTime * ( z - self.z_d )
        self.theta_int += sampleTime * ssa( theta - theta_d )

        #######################################################################
        # Heading autopilot (SMC controller)
        #######################################################################

        wn_d   = self._wn_d    # reference model natural frequency
        zeta_d = self._zeta_d  # reference model relative damping factor


        # Integral SMC with 3rd-order reference model
        [delta_r, self.e_psi_int, self.psi_d, self.r_d, self.a_d] = \
            integralSMC(
                self.e_psi_int,
                e_psi, e_r,
                self.psi_d,
                self.r_d,
                self.a_d,
                self._T_nomoto,
                self._K_nomoto,
                wn_d,
                zeta_d,
                self._K_d,
                self._K_sigma,
                self._lam,
                self._phi_b,
                psi_ref,
                self._r_max,
                sampleTime
                )

        u_control = np.array([delta_r, -delta_r, delta_s, -delta_s, n], float)

        return u_control
