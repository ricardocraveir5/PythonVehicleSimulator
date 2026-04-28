# Log de Utilização de IA — Etapa 4

- **Aluno:** Ricardo Craveiro (1191000@isep.ipp.pt)
- **Curso:** Mestrado de Sistemas Autónomos — ISEP
- **Unidade:** DINAV — Dinâmica Avançada 2026
- **Professor:** Pedro Barbosa Guedes
- **Ferramenta de IA:** Claude Code (claude-opus-4-7)
  - *Nota:* Modelo actualizado de `claude-opus-4-6` (Etapa 3) para
    `claude-opus-4-7` (versão mais recente com maior capacidade de
    raciocínio para arquitectura multi-camada e coordenação de QThreads).
- **Branch:** `claude/etapa4-correntes-oceanicas-KPtjy`
- **Data:** 2026-04-28

---

## Contexto e Objectivo

A Etapa 4 do trabalho laboratorial DINAV 2026 acrescenta modelação de
correntes oceânicas ao torpedo AUV. O ponto de partida foi o branch
`master` com a Etapa 3 completa + os commits do PR #5 (tab "Gráficos Etapa 3"
+ botão "Simular A e B" com animação 3D dual) — 135 testes passavam.

O objectivo tinha três dimensões:
1. **Modelos físicos** — hierarquia de 5 perfis de corrente com interface
   abstracta comum.
2. **Integração na simulação** — torpedo usa o modelo activo em cada passo
   de `dynamics()`; `mainLoop.simulate()` suporta cancelamento cooperativo.
3. **GUI e análise** — selector, gráficos analíticos dinâmicos, comparações
   automáticas, preview ao vivo. Campanha S0-S5 para o artigo.

---

## Pipeline de Agentes — Sessão (2026-04-28)

O trabalho desta etapa foi planeado em modo Plan e executado em modo
implementação. Cada commit abaixo corresponde a um bloco de trabalho do
agente.

---

### Bloco 1 — `lib/environment.py` (commit `3161c41`)

**Objectivo:** Criar hierarquia `CurrentModel` com 5 perfis.

**Principais decisões:**
- Classe abstracta com método `get_current(z, t) -> (V_c, beta_c)`.
- Constante e perfis determinísticos (Linear, PowerLaw, Logarítmico) sem
  estado. Gauss-Markov com estado interno `_V` e integração Euler.
- Lei 1/7 e Logarítmico partilham `V_surface`/`z_ref` — GUI reutiliza
  os mesmos spinboxes para os dois modelos.
- 25 testes unitários em `test_environment.py` (isolados, sem Qt).

---

### Bloco 2 — `torpedo.py` integração (commit `180e276`)

**Objectivo:** Torpedo usa `CurrentModel` em cada passo de `dynamics()`.

**Implementação:**
- `current_model=None` keyword-only no construtor — retrocompatível.
- `_t_sim` incrementado em `dynamics()` para modelos com estado temporal
  (Gauss-Markov).
- Getters `V_c` / `beta_c` delegam no modelo activo se disponível.
- `current_model_type` em `get_all_params()` para export CSV automático.

---

### Bloco 3 — Fix `beta_c` setter (commit `2953719`)

**Problema:** Setter `beta_c` escrevia em graus internamente, quebrando
o round-trip `get_all_params()` → `set_from_dict()`.

**Correcção:** Setter escrita em radianos (como todos os outros ângulos
internos). 15 novos testes de integração torpedo×CurrentModel em
`test_torpedo_etapa4.py`.

---

### Bloco 4 — GUI selector de corrente (commit `85febc1`)

**Objectivo:** Expor os 5 modelos na GUI com UI adaptativa.

**Implementação:**
- `QComboBox` "Modelo de corrente" com 5 entradas.
- `QStackedWidget`: cada modelo tem o seu painel de spinboxes (ou label
  informativo para Lei 1/7 que partilha os campos do Linear).
- `CurrentProfileWidget`: gráfico `V_c(z)` em NED recalculado a cada
  `params_updated`. Mostra o perfil activo do z=0 ao z=200 m.
- `_view_params()` do controller estende o dict de parâmetros com
  `current_model_selected`, `current_V_c`, `current_beta_c_deg`, etc.
- `get_view_state()` devolve estado completo para pré-preencher o diálogo
  de comparação.

---

### Bloco 5 — Campanha S0-S5 (commit `3c09cf4`)

**Objectivo:** 6 simulações canónicas para o artigo + outputs automáticos.

**Script `etapa4/etapa4_simulacoes.py`:**
- Backend `Agg` (headless, sem Qt).
- 200 s, 10 000 passos cada.
- 6 CSVs (10 001 linhas + header de parâmetros).
- PDF 27 páginas: 4 por simulação (trajectória 3D, z(t), u(t), V_c(z))
  + 3 páginas comparativas (XY, z(t), u(t)).
- `etapa4_metricas.txt`: desvio horizontal máximo vs S0, RMS de
  profundidade, RMS de deflexão das barbatanas, desvio padrão S5 vs S1.
- 6 testes em `test_etapa4.py`.

---

### Bloco 6 — GUI Fase A: start/stop + comparações (commit `ab08721`)

**Objectivo:** Controlo do ciclo de vida + comparação personalizável +
gráficos analíticos.

**Cancelamento cooperativo:**
- `mainLoop.simulate()` aceita `is_cancelled: Callable[[], bool] = None`.
- `SimulationThread.cancel()` activa `_cancel_flag`; `run()` emite
  `cancelled()` em vez de `finished()`.

**Botão "Parar":**
- Desabilitado por defeito; habilitado ao lançar qualquer simulação.
- Cancela `_sim_thread`, limpa state machines A/B e compare, restaura
  todos os botões via `_restore_buttons_after_sim()`.

**`CompareScenariosDialog`:**
- 2 colunas scrolláveis, pré-preenchidas com o estado actual.
- Cada coluna: título editável + todos os parâmetros relevantes + selector
  de corrente.
- Corre as 2 sims sequencialmente (igual ao A/B da Etapa 3).
- Exporta CSVs automáticos em `etapa4/comparacao_<ts>_A.csv` e `_B.csv`.

**Botão "Comparar Sem/Com Corrente":**
- Atalho para comparação pré-definida: S0 (V_c=0) vs S1 (V_c=0.5,
  ConstantCurrent). Labels automáticos "Sem corrente" / "Com corrente V_c=0.5".

**Gráficos analíticos (`DragCurveWidget`, `ControlResponseWidget`):**
- Sem simulação — calculados analiticamente a partir dos parâmetros.
- Actualizados em tempo real via `params_updated`.
- Colocados numa nova tab "Análise" no painel direito.

---

### Bloco 7 — GUI Fase B: preview ao vivo (commit `accf970`)

**Objectivo:** Simulação curta com debounce que actualiza z(t) e u(t)
sem o utilizador ter de premir "Simular".

**`LivePreviewWidget`:**
- Placeholder inicial com texto informativo.
- `update_from(simTime, simData)`: pinta 2 subplots (z(t), u(t)).
- `show_running()` / `show_disabled()`: feedback visual de estado.

**`controller.build_preview_vehicle()`:**
- Constrói torpedo com parâmetros actuais + current_model activo.
- Reusa `build_compare_instance()`.

**Mecanismo de debounce:**
- `QTimer.setSingleShot(True)` com 800 ms.
- `_on_params_changed_for_preview()`: slot de `params_updated` — cancela
  preview anterior e reinicia o timer.
- `_run_preview()`: slot do timer — cria `SimulationThread` separado
  (N=1000, dt=0.05), liga `finished` a `_on_preview_done`.
- `_on_preview_done()`: chama `_live_preview_widget.update_from()`.

**Limpeza:**
- `_on_live_preview_toggled(False)`: cancela thread + para timer + mostra
  placeholder.
- `closeEvent`: cancela `_sim_thread` e `_preview_thread` ao fechar.

**5 novos testes:**
1. Presença de `LivePreviewWidget` e checkbox na tab "Análise".
2. Toggle off cancela preview em curso e limpa estado.
3. Alteração de params com preview a correr dispara `cancel()`.
4. `_on_preview_done` delega em `LivePreviewWidget.update_from()`.
5. `params_updated` com preview desligado não activa o timer.

---

## Decisões de Arquitectura

### Interface abstracta para correntes

`CurrentModel` com `get_current(z, t)` permite adicionar novos perfis
sem tocar no torpedo ou na GUI — basta registar o novo modelo no
controller. Os modelos com estado (Gauss-Markov) encapsulam o estado
internamente, sem expor `_t_sim` ao exterior.

### `_t_sim` no torpedo vs. no loop

O tempo de simulação é gerido pelo torpedo porque:
- O modelo Gauss-Markov necessita de `t` para integrar V_c(t).
- `mainLoop.py` não sabe qual o modelo activo.
- A torpeda é a única entidade com acesso a `sampleTime` por passo.

### Cancelamento cooperativo em vez de interrompimento forçado

`QThread.terminate()` deixa o estado partilhado (numpy arrays) corrupto.
O padrão cooperativo (`_cancel_flag` verificado no início de cada iteração)
garante dados consistentes e permite devolver dados parciais úteis.

### Two preview threads isolated from main simulation thread

O `_preview_thread` é completamente separado do `_sim_thread`. O botão
"Simular" não é afectado pela preview em curso (são dois objetos Qt
independentes). O risco de condição de corrida é mitigado pelo modelo de
debounce: apenas um preview thread corre de cada vez.

### CSVs automáticos com timestamp

Cada comparação escreve 2 ficheiros com `<timestamp>` no nome para evitar
colisões. O utilizador pode correr múltiplas comparações numa sessão sem
perder resultados anteriores.

---

## Ficheiros Criados e Modificados

### Ficheiros novos

| Ficheiro | Linhas | Descrição |
|---|---|---|
| `src/.../lib/environment.py` | 234 | Hierarquia CurrentModel |
| `etapa4/etapa4_simulacoes.py` | ~280 | Campanha S0-S5 headless |
| `tests/test_environment.py` | 246 | 25 testes CurrentModel |
| `tests/test_torpedo_etapa4.py` | 242 | 15 testes integração |
| `tests/test_etapa4.py` | 132 | 6 testes campanha |
| `adicoes_codigo_etapa4.md` | ~130 | Documentação técnica |
| `log_etapa4_ricardo_craveiro.md` | — | Este ficheiro |

### Ficheiros modificados

| Ficheiro | +Linhas aprox. | Alterações |
|---|---|---|
| `src/.../lib/mainLoop.py` | +8 | `is_cancelled` em `simulate()` |
| `src/.../vehicles/torpedo.py` | +80 | `current_model=`, `_t_sim`, getters, `current_model_type` |
| `src/.../gui/torpedo_controller.py` | +130 | `build_compare_instance`, `make_no_vs_with_current_cfgs`, `register_comparison_results`, `build_preview_vehicle`, `get_view_state` |
| `src/.../gui/torpedo_viz.py` | +260 | `cancel()`, `DragCurveWidget`, `ControlResponseWidget`, `LivePreviewWidget` |
| `src/.../gui/torpedo_gui.py` | +550 | selector corrente, `CompareScenariosDialog`, botão Parar, gráficos analíticos, live preview, `closeEvent` |
| `tests/test_integration_gui.py` | +165 | 17 novos testes (Fase A: 12, Fase B: 5) |

---

## Estado Final

| Componente | Estado |
|---|---|
| Hierarquia `CurrentModel` (5 modelos) | Funcional |
| Integração torpedo × corrente | Funcional |
| `simulate()` cancelável | Funcional |
| GUI selector de corrente | Funcional |
| Gráfico V_c(z) dinâmico | Funcional |
| Botão "Parar" | Funcional |
| Comparação personalizável (diálogo) | Funcional |
| Comparação pré-definida Sem/Com Corrente | Funcional |
| CSVs automáticos de comparações | Funcional |
| `DragCurveWidget` analítico | Funcional |
| `ControlResponseWidget` analítico | Funcional |
| `LivePreviewWidget` (preview ao vivo) | Funcional |
| Campanha S0-S5 + PDF + métricas | Funcional |
| **Testes anteriores (Etapa 1/2/3)** | **135 passam** |
| **Testes novos Etapa 4** | **+17 GUI (+5 Fase B)** |
| **Testes modelo/ambiente/campanha** | **46 passam** |
| **Total** | **152 passam** |

---

## Notas Finais

### Conformidade com as considerações do enunciado

**1.a — Ferramenta Claude mantida ao longo de todo o trabalho**

Toda a implementação utilizou exclusivamente Claude Code. A versão foi
actualizada de `claude-opus-4-6` para `claude-opus-4-7` nesta etapa.

**1.b — Prompts e respostas registados**

As decisões de arquitectura e o pipeline de blocos estão documentados
neste ficheiro. O histórico completo está disponível via sessão Claude Code.

**1.c — Referências ao autor original mantidas**

Todos os ficheiros criados ou modificados incluem referência a:

> T. I. Fossen, *Handbook of Marine Craft Hydrodynamics and Motion Control*,
> 2nd ed., Wiley, 2021. URL: www.fossen.biz/wiley

---

*Log gerado com Claude Code — claude-opus-4-7*
*Data: 2026-04-28*
*Ricardo Craveiro (1191000@isep.ipp.pt) — DINAV 2026 Etapa 4*
