# Log de Utilização de IA — Etapa 2

- **Aluno:** Ricardo Craveiro (1191000@isep.ipp.pt)
- **Curso:** Mestrado de Sistemas Autónomos — ISEP
- **Unidade:** DINAV — Dinâmica Avançada 2026
- **Professor:** Pedro Barbosa Guedes
- **Ferramenta de IA:** Claude Code (claude-sonnet-4-6)
- **Session ID:** `cse_019EH7Fze5noa1tks9nnkYPW`
- **Datas:** 2026-03-25 (sessão inicial) · 2026-03-28/29 (sessão de continuação)

---

## Contexto e Objectivo

A Etapa 2 do trabalho laboratorial DINAV 2026 consistiu no desenvolvimento de
uma arquitectura MVC (Model-View-Controller) em Python/PyQt6 para o torpedo AUV
número 10 — um veículo subaquático autónomo inspirado no REMUS 100, modelado
segundo a formalização de Thor I. Fossen (2021).

O ponto de partida foi o ficheiro `torpedo.py` existente no repositório
`ricardocraveir5/PythonVehicleSimulator`. Os objectivos foram:

1. Adicionar getters/setters com validação física ao modelo (`torpedo.py`).
2. Criar um controlador Qt (`TorpedoController`) que medeia entre modelo e vista.
3. Criar uma GUI PyQt6 (`TorpedoGUI`) com duas zonas distintas de parâmetros.
4. Garantir a actualização automática de parâmetros interdependentes (A7, A8).
5. Permitir a configuração e lançamento de simulações com visualização em tempo-real.

---

## Pipeline de Agentes — Sessão Inicial (2026-03-25)

### Agente 1 — Análise do torpedo.py original

**Objectivo:** Ler o ficheiro `torpedo.py` e identificar anomalias,
variáveis locais relevantes e oportunidades de encapsulamento.

**Principais decisões:**
- Identificação de 10 anomalias (A1 a A10).
- A1, A5 e A6 documentadas e preservadas (compatibilidade com `mainLoop.py`).
- A7 (T_heave acoplado a T_sway) e A8 (T_nomoto acoplado a T_yaw) sinalizadas
  para resolução via setters.
- A9 e A10: validação dos parâmetros de referência (`ref_z`, `ref_n`) adicionada.

---

### Agente 2A — Promoção de variáveis locais a atributos privados

**Objectivo:** Transformar variáveis locais do `__init__` em atributos privados
com prefixo `_`, sem alterar o comportamento externo.

**Principais decisões:**
- 24 atributos promovidos: `_L`, `_diam`, `_Cd`, `_r44`, `_T_surge`,
  `_T_sway`, `_T_heave`, `_T_yaw`, `_K_nomoto`, `_T_nomoto`, `_wn_d`,
  `_zeta_d`, `_r_max`, `_lam`, `_phi_b`, `_K_d`, `_K_sigma`, `_wn_d_z`,
  `_Kp_z`, `_T_z`, `_Kp_theta`, `_Kd_theta`, `_Ki_theta`, `_K_w`.
- `_ref_z`, `_ref_psi`, `_ref_n`, `_V_c`, `_beta_c` também promovidos.
- Anomalias A1, A5, A6 comentadas no código com etiqueta DINAV 2026.

---

### Agente 2B — Getters/setters com validação física (Fossen 2021)

**Objectivo:** Implementar propriedades Python (getters/setters) para todos os
atributos privados, com validação dos limites físicos.

**Principais decisões:**
- `L` > 0 e > `diam`; `diam` > 0 e < `L`.
- `Cd` ∈ [0.1, 0.5] — Allen et al. (2000); `r44` ∈ [0.1, 0.5].
- **A7:** setter de `T_sway` actualiza `_T_heave` automaticamente.
- **A8:** setter de `T_yaw` actualiza `_T_nomoto` automaticamente.
- `massa` exposta como propriedade calculada (read-only).
- `zeta_d` ∈ [0.5, 2.0]; `ref_z` ∈ [0, 100] m; `ref_n` ∈ [0, nMax] RPM.
- Todos os `ValueError` em português PT-PT.

---

### Agente 2 (final) — get_all_params / set_from_dict / métodos de fins e propulsor

**Objectivo:** Adicionar os métodos utilitários necessários para o Controller.

**Principais decisões:**
- `get_all_params()` devolve dicionário com 35 chaves.
- `set_from_dict()` ignora silenciosamente `massa`, `T_heave`, `T_nomoto`.
- Validação de índice [0–3] nas fins; `set_thruster_nMax()` limitado a ]0, 1525] RPM.

---

### Agente 3 — torpedo_controller.py

**Objectivo:** Criar a camada Controller do padrão MVC com sinais Qt.

**Principais decisões:**
- `TorpedoController(QObject)` com 4 sinais:
  - `params_updated(dict)` — após alteração bem-sucedida.
  - `simulation_ready(object)` — quando nova instância está pronta.
  - `validation_error(str)` — em caso de ValueError.
  - `param_dependency_updated(str, float)` — quando T_heave ou T_nomoto mudam.
- `_check_dependencies()` compara snapshot pré e pós setter para detectar
  mudanças em parâmetros dependentes.
- `prepare_simulation()` cria nova instância `torpedo()` com parâmetros actuais
  + missão, propagando todos os valores via `set_from_dict()`.

---

### Agente 4A/4B/4C — torpedo_gui.py

**Objectivo:** Criar a janela principal `TorpedoGUI` com layout de dois painéis.

**Principais decisões:**
- `TorpedoGUI(QMainWindow)` com splitter horizontal 450+450.
- Painel esquerdo: parâmetros físicos, fins, thruster (`QScrollArea`).
- Painel direito: controlador de profundidade, controlador de rumo.
- `param_widgets: dict[str, QDoubleSpinBox]` como registo central.
- Fábrica `_add_spinboxes()` partilhada; campos RO com fundo cinzento (#d0d0d0).
- `editingFinished` chama `controller.update_param()`; campos RO sem botões.
- Validação visual: fundo vermelho (#ffcccc) em erro; azul (#d0e8ff) em auto-update.

---

### Agente 5A — main_gui.py + requirements_gui.txt

**Objectivo:** Criar o ponto de entrada da aplicação e o ficheiro de dependências.

**Principais decisões:**
- `main_gui.py`: `QApplication` + `TorpedoController` + `TorpedoGUI` + `app.exec()`.
- `requirements_gui.txt`: `PyQt6>=6.4.0`, `numpy>=1.23.0`, `matplotlib>=3.6.0`.

---

### Agente 5B/6 — Testes de integração e revisão crítica

**Objectivo:** Testar 6 cenários de integração headless; verificar conformidade.

**Cenários testados e resultado:** todos passaram à primeira.
Correcção aplicada: botão "Validar" não estava ligado a `_load_params()`.

---

## Sessão de Continuação — 5 Prompts Principais (2026-03-28/29)

### Prompt 1 — Visualização 3D animada do torpedo

> *"Achas que irias conseguir adicionar o torpedo modelado na GUI em movimento?"*

**Resultado:** Criação de `torpedo_viz.py` com:
- `SimulationThread(QThread)` — executa `mainLoop.simulate()` em background,
  emite `finished(simTime, simData)` ou `error(str)`.
- `TorpedoVizWidget` — canvas matplotlib 3D; elipsóide construído por 10
  secções transversais elípticas + 4 barbatanas como rectângulos fechados,
  todos transformados pela matriz de rotação ZYX Euler (corpo → NED).
- **Câmara a seguir o torpedo:** `ax.set_xlim/ylim/zlim` recentrado em cada
  frame na posição instantânea do veículo.
- Diálogo de simulação actualizado com campo "Duração (5–300 s)".
- Painel direito convertido de `QScrollArea` para `QTabWidget` com tab
  "Visualização 3D".

---

### Prompt 2 — Gráficos de estado e câmara a acompanhar

> *"Adiciona também vários plots com as variações de tudo ao longo do tempo.
> Variação de yaw, pitch, aceleração, e todos os outros que aches importante.
> No plot onde o torpedo estiver faz por favor o plot mover-se com o torpedo."*

**Resultado:**
- `TorpedoStatesWidget` — grelha 3×3 com 9 subplots estáticos (simulação
  completa de uma só vez): Norte, Este, Profundidade | φ, θ, ψ (em graus) |
  u, v, w (m/s).
- Tab "Gráficos de Estado" adicionada (3 tabs no total: Controladores |
  Visualização 3D | Gráficos de Estado).
- 36 testes de integração passam.

---

### Prompt 3 — Squash de commits e exemplos no HOWTO

> *"Por favor faz squash a alguns commits de forma a ficar com menos commits
> e ter os commits organizados. Confirma que tudo fica a funcionar correctamente.
> Depois adiciona ao HOWTO exemplos de como navegar a GUI."*

**Resultado:**
- Redução de 18 commits → 3 commits lógicos via `git reset --soft c717e07`
  seguido de commits selectivos + `git push --force-with-lease`.
- `HOWTO.md` enriquecido com 6 exemplos passo-a-passo: alterar parâmetro
  físico, verificar acoplamento A7, valor inválido, simulação 3D, gráficos
  de estado, comparar simulações com barbatanas diferentes.
- Secção "Resolução de problemas" adicionada com erros comuns e soluções.

---

### Prompt 4 — Separar Etapa 2 e Etapa 3 em PRs distintos

> *"Separa a etapa 2 e 3 em PRs diferentes. Põe o da etapa 3 a depender do
> da etapa 2. Não comeces já a trabalhar na etapa 3. Confirma que está tudo
> impecável com a etapa 2. O foco é a etapa 2."*

**Resultado:**
- Decisão arquitectural registada: branch Etapa 3 partirá do branch de Etapa 2
  quando chegar a altura (prazo 12 abril); PR Etapa 3 terá PR Etapa 2 como base.
- Verificação final Etapa 2: 36 testes passam, branch limpo, push feito para
  `claude/torpedo-parameter-inventory-vtoPN`.
- Funcionalidades Etapa 3 (CSV export, gráficos de controlos, análise
  comparativa) planeadas mas não implementadas.

---

### Prompt 5 — Exposição de parâmetros em falta na GUI

> *"Há mais alguma coisa que possas fazer para a etapa 2?"*

**Resultado:** Análise comparativa entre `get_all_params()` e `param_widgets`
identificou 5 parâmetros com getter/setter no modelo mas ausentes da GUI:

| Parâmetro | Grupo GUI | Validação |
|-----------|-----------|-----------|
| `zeta_roll` | Parâmetros Físicos | [0.0, 1.0] |
| `zeta_pitch` | Parâmetros Físicos | [0.0, 1.0] |
| `K_nomoto` | Controlador de Rumo (SMC) | > 0 |
| `r_max` | Controlador de Rumo (SMC) | > 0 (rad/s) |
| `ref_n` | Diálogo de Simulação | [0, nMax] RPM |

3 novos testes adicionados (cenários 8–10): presença de K_nomoto/r_max na GUI,
presença de zeta_roll/pitch com valores correctos, dependência geométrica L→massa.
**Total final: 39 testes passam.**

---

## Anomalias Identificadas e Resolução

| # | Anomalia | Tratamento |
|---|----------|------------|
| A1 | `portSternFin`/`starSternFin`: nomes trocados relativamente à posição física | Documentada; preservada para compatibilidade com `mainLoop.py` |
| A2 | Variáveis de tempo constante eram locais ao `__init__` sem exposição externa | Resolvida: promovidas a atributos privados com propriedades |
| A3 | Parâmetros de autopiloto sem validação de domínio físico | Resolvida: setters com limites Fossen adicionados |
| A4 | `massa` calculada implicitamente sem getter público | Resolvida: propriedade read-only `massa` adicionada |
| A5 | `n=1525` hardcoded em `stepInput()`, ignorando `ref_n` | Documentada; preservada (comportamento original) |
| A6 | Sinais `delta_s` em posições opostas entre `stepInput` e `depthHeadingAutopilot` | Documentada; preservada (comportamento original) |
| A7 | `T_heave` acoplado a `T_sway` apenas no `__init__`, sem propagação dinâmica | Resolvida: setter de `T_sway` actualiza `_T_heave`; controller emite `param_dependency_updated` |
| A8 | `T_nomoto` acoplado a `T_yaw` apenas no `__init__`, sem propagação dinâmica | Resolvida: setter de `T_yaw` actualiza `_T_nomoto`; controller emite `param_dependency_updated` |
| A9 | Sem validação de `ref_z` no `__init__` | Resolvida: setter `ref_z` valida [0, 100] m |
| A10 | Sem validação de `ref_n` no `__init__` | Resolvida: setter `ref_n` valida [0, nMax] RPM |

---

## Decisões de Arquitectura

### Escolha do PyQt6

PyQt6 foi escolhido por:
- Ligação directa ao sistema de sinais/slots Qt, adequado ao padrão MVC.
- `QThread` permite executar `mainLoop.simulate()` sem bloquear a interface.
- `FigureCanvasQTAgg` (matplotlib) embebe animações 3D sem dependências extra.

### Separação MVC estrita

- O **Model** (`torpedo.py`) não importa nem conhece o Controller ou a View.
- A **View** (`torpedo_gui.py`) importa apenas `TorpedoController` e nunca
  acede directamente a `torpedo.py`.
- O **Controller** (`torpedo_controller.py`) importa `torpedo` e expõe uma
  interface de sinais Qt para a View.

### Estratégia de recriação de instância para simulação

`prepare_simulation()` cria uma **nova instância** de `torpedo()` a cada
simulação. Isto garante que os estados internos (integrais, estados de
referência) são inicializados a zero, evitando transientes indesejados.

### Visualização 3D

O torpedo é representado por:
1. 10 secções transversais elípticas (semi-eixos a=L/2, b=diam/2).
2. 4 barbatanas como rectângulos fechados no referencial do corpo.
3. Transformação pela matriz de rotação ZYX Euler → referencial NED.
4. Câmara centrada na posição instantânea (raio de visão = max(5 m, 3·L)).
5. Eixo Z invertido (profundidade positiva para baixo, convenção naval).

### Commits organizados (squash)

O histórico do branch contém 4 commits lógicos desde a base `c717e07`:
1. `feat: torpedo.py — modelo MVC, getters/setters, _recalculate_derived`
2. `feat: GUI MVC — torpedo_controller, torpedo_gui, torpedo_viz, main_gui (PyQt6)`
3. `feat: testes, log, HOWTO e compatibilidade multi-plataforma`
4. `feat: expor K_nomoto, r_max, zeta_roll/pitch e ref_n na GUI`

---

## Estado Final

| Componente | Ficheiro | Estado |
|-----------|---------|--------|
| Model | `torpedo.py` | ✅ 27 getters/setters, `_recalculate_derived`, `get_all_params`, `set_from_dict` |
| Controller | `torpedo_controller.py` | ✅ 4 sinais Qt, `prepare_simulation`, `reset_to_defaults` |
| View | `torpedo_gui.py` | ✅ 2 zonas, 3 tabs, 33 widgets, validação visual, dependências destacadas |
| Visualização | `torpedo_viz.py` | ✅ `SimulationThread`, `TorpedoVizWidget` (3D animado), `TorpedoStatesWidget` (9 subplots) |
| Entrada | `main_gui.py` | ✅ `QApplication` + MVC |
| Testes modelo | `test_torpedo_model.py` | ✅ 16 testes |
| Testes simulação | `test_simulate.py` | ✅ 13 testes |
| Testes integração GUI | `test_integration_gui.py` | ✅ 10 testes |
| **Total** | | **✅ 39 testes passam** |

---

## Notas Finais

### Conformidade com as considerações do enunciado

**1.a — Ferramenta Claude mantida ao longo de todo o trabalho**

Toda a implementação utilizou exclusivamente Claude Code
(claude-sonnet-4-6, session `cse_019EH7Fze5noa1tks9nnkYPW`).
Nenhum outro modelo ou ferramenta de IA foi utilizado.

**1.b — Prompts e respostas registados**

Os 5 prompts mais importantes da sessão de continuação estão documentados
na secção "Sessão de Continuação" deste ficheiro. O histórico completo está
disponível via session ID `cse_019EH7Fze5noa1tks9nnkYPW`.

**1.c — Referências ao autor original Thor I. Fossen mantidas**

Todos os ficheiros criados ou modificados incluem referência a:

> T. I. Fossen, *Handbook of Marine Craft Hydrodynamics and Motion Control*,
> 2nd ed., Wiley, 2021. URL: www.fossen.biz/wiley

---

*Log gerado com Claude Code — session `cse_019EH7Fze5noa1tks9nnkYPW`*
*Sessão inicial: 2026-03-25 · Sessão de continuação: 2026-03-28/29*
*Ricardo Craveiro (1191000@isep.ipp.pt) — DINAV 2026 Etapa 2*
