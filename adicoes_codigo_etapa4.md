# Adições de Código — Etapa 4 (DINAV 2026)

**Autor:** Ricardo Craveiro (1191000@isep.ipp.pt)
**Branch:** `claude/etapa4-correntes-oceanicas-KPtjy`
**Data:** 2026-04-28
**Ferramenta de IA:** Claude Code (claude-opus-4-7)

---

## Objectivo da Etapa 4

Modelar correntes oceânicas no torpedo AUV e expor todos os controlos na
GUI MVC. Cobriu quatro frentes:

1. **Hierarquia de modelos de corrente** — 5 perfis (Constante, Linear,
   PowerLaw/Lei-1/7, Logarítmico, Gauss-Markov).
2. **Integração física no torpedo** — `current_model=` keyword-arg em
   `torpedo()`, tempo interno `_t_sim`, extracção de V_c/β_c por passo.
3. **GUI extendida** — selector de corrente, gráfico V_c(z), botão "Parar",
   diálogo de comparação personalizável, gráficos analíticos dinâmicos,
   preview ao vivo com debounce.
4. **Campanha de simulações S0-S5** — 6 CSVs + PDF 27 páginas + ficheiro
   de métricas para o artigo.

---

## Ficheiros novos

| Ficheiro | Linhas | Descrição |
|---|---|---|
| `src/.../lib/environment.py` | 234 | Hierarquia `CurrentModel` + 5 perfis |
| `etapa4/etapa4_simulacoes.py` | ~280 | Campanha S0-S5 (script headless) |
| `tests/test_environment.py` | 246 | 25 testes unitários `CurrentModel` |
| `tests/test_torpedo_etapa4.py` | 242 | 15 testes de integração torpedo×current |
| `tests/test_etapa4.py` | 132 | 6 testes da campanha S0-S5 |
| `adicoes_codigo_etapa4.md` | — | Este documento |
| `log_etapa4_ricardo_craveiro.md` | — | Log detalhado da sessão |

## Ficheiros modificados

| Ficheiro | Alterações principais |
|---|---|
| `src/.../lib/mainLoop.py` | + parâmetro `is_cancelled` em `simulate()` |
| `src/.../vehicles/torpedo.py` | + `current_model=` kwarg, `_t_sim`, getters `V_c`/`beta_c`, `current_model_type` em `get_all_params()` |
| `src/.../gui/torpedo_controller.py` | + `build_compare_instance`, `make_no_vs_with_current_cfgs`, `register_comparison_results`, `build_preview_vehicle` |
| `src/.../gui/torpedo_viz.py` | + `SimulationThread.cancel()`, `DragCurveWidget`, `ControlResponseWidget`, `LivePreviewWidget` |
| `src/.../gui/torpedo_gui.py` | + selector de corrente, botão "Parar", `CompareScenariosDialog`, gráficos analíticos, preview ao vivo, `closeEvent` |
| `tests/test_integration_gui.py` | +17 testes (Fase A: 12, Fase B: 5) |

---

## Detalhes de implementação

### 1. Hierarquia `CurrentModel` (`environment.py`)

```
CurrentModel (abstracta)
├── ConstantCurrent(V_c, beta_c_deg)
├── LinearCurrent(V_surface, z_ref, beta_c_deg)
├── PowerLawCurrent(V_surface, z_ref, beta_c_deg)   # lei 1/7
├── LogarithmicCurrent(V_surface, z_ref, beta_c_deg)
└── GaussMarkovCurrent(V_mean, sigma, mu, beta_c_deg)
```

Cada modelo expõe `get_current(z, t) -> (V_c, beta_c)`. O modelo
Gauss-Markov mantém estado interno (integração Euler de 1.ª ordem).

### 2. Integração no torpedo (`torpedo.py`)

- Kwarg `current_model=None` no construtor; retrocompatível (sem arg →
  usa `V_c`/`beta_c` constantes existentes).
- `dynamics()` chama `_current_model.get_current(eta[2], self._t_sim)`
  e incrementa `_t_sim += sampleTime`.
- `current_model_type` em `get_all_params()` para export CSV.
- Setter `beta_c` mantém radianos (round-trip seguro com `get_all_params`).

### 3. Cancelamento cooperativo (`mainLoop.py`)

```python
def simulate(N, sampleTime, vehicle, is_cancelled=None):
    for i in range(0, N+1):
        if is_cancelled is not None and is_cancelled():
            break
        ...
    n_rows = simData.shape[0]
    simTime = (np.arange(n_rows, dtype=float) * sampleTime)[:, None]
    return simTime, simData
```

Devolve dados parciais; assinatura retrocompatível (default `None`).

### 4. `SimulationThread.cancel()` (`torpedo_viz.py`)

```python
def cancel(self):
    self._cancel_flag = True
# run() emite cancelled() em vez de finished() se _cancel_flag
```

### 5. GUI — selector de corrente e gráfico V_c(z)

- `QComboBox` com 5 opções; `QStackedWidget` com painel por modelo
  (spinboxes específicos de cada perfil).
- `CurrentProfileWidget`: gráfico estático V_c(z) em NED (z positivo
  para baixo), pintado sempre que `params_updated` emite.
- Spinboxes `V_c` e `beta_c_deg` movidos para grupo "Parâmetros Físicos"
  como override de baseline.

### 6. Botão "Parar" + state machine

- `_btn_stop` desabilitado por defeito; habilitado ao lançar simulação.
- Chama `_sim_thread.cancel()` + cancela state machines A/B e compare.
- `_restore_buttons_after_sim()` extraído do `_on_simulation_done` para
  reutilização pelo botão e pelos slots de cancelamento.

### 7. `CompareScenariosDialog`

Diálogo modal com 2 colunas scrolláveis:
- Cada coluna tem: título editável, Cd, V_c, beta_c_deg, ref_z, ref_psi,
  ref_n, selector de corrente + spinboxes de `current_*`.
- Pré-preenche com os parâmetros actuais (ambas as colunas iguais).
- Devolve `(cfg_a, cfg_b)` para `_run_compare()`.

Fluxo de comparação:
1. GUI guarda duração do utilizador, fixa 200 s, entra em `_compare_mode = "A"`.
2. Ao terminar A, lança B automaticamente.
3. Ao terminar B, chama `controller.register_comparison_results()` que
   exporta 2 CSVs em `etapa4/comparacao_<ts>_A/B.csv` e emite `comparison_ready`.
4. Slot `_on_comparison_ready` pinta `ComparativeWidget` + animação 3D dual.

### 8. Gráficos analíticos (`DragCurveWidget`, `ControlResponseWidget`)

- **DragCurveWidget**: `F_drag(U) = 0.5·ρ·CD_0·S·U²`, U ∈ [0, 3] m/s.
  Actualiza com mudanças em Cd, L, diam.
- **ControlResponseWidget**: resposta degrau analítica do laço de
  profundidade (modelo de 2.ª ordem com `wn_d_z` e `zeta_d`).
- Ambos ligados a `params_updated` — custo zero (sem simular).

### 9. Live Preview — Fase B (`LivePreviewWidget`)

- 2 subplots: z(t) e u(t), actualizados com simulações curtas de
  50 s, dt=0.05 (1000 passos, ~0.5 s de CPU).
- Checkbox "Preview ao vivo" na tab "Análise".
- Debounce de 800 ms via `QTimer.setSingleShot(True)`.
- Alteração de parâmetro com preview em curso: cancela a actual antes
  de reiniciar o timer.
- `closeEvent` cancela `_sim_thread` e `_preview_thread` ao fechar.

### 10. Campanha S0-S5 (`etapa4_simulacoes.py`)

| Cenário | Modelo | V_c (m/s) |
|---|---|---|
| S0 | Sem corrente (baseline) | 0.0 |
| S1 | Constante | 0.5 |
| S2 | Linear | 0.0 → 0.5 |
| S3 | Lei 1/7 (Power Law) | superfície 0.5 |
| S4 | Logarítmico | superfície 0.5 |
| S5 | Gauss-Markov | média 0.3, σ 0.1 |

Outputs: 6 CSVs, 1 PDF de 27 páginas, 1 ficheiro de métricas.

---

## Resumo de testes

| Ficheiro | Testes | Etapa |
|---|---|---|
| `test_simulate.py` | 4 | 1 |
| `test_torpedo_model.py` | 25 | 1/2 |
| `test_etapa3.py` | 14 | 3 |
| `test_etapa3_widget.py` | 13 | 3+ |
| `test_environment.py` | 25 | 4 |
| `test_torpedo_etapa4.py` | 15 | 4 |
| `test_etapa4.py` | 6 | 4 |
| `test_integration_gui.py` | 48 | 2/3/4 |
| **Total** | **152** | |

---

## Resumo de contagens

| Componente | Antes (Etapa 3+) | Depois (Etapa 4) |
|---|---|---|
| Tabs na GUI | 5 | 7 (+Análise, inclui LivePreview) |
| Modelos de corrente | 0 | 5 |
| Botões simulação | 2 | 4 (+Parar, +Sem/Com Corrente, +Comparar 2 Cenários) |
| Widgets analíticos | 0 | 3 (Drag, ControlResponse, LivePreview) |
| Sinais Qt no Controller | 5 | 7 (+`comparison_ready`, + sinais de corrente) |
| Testes totais | 135 | **152** |
