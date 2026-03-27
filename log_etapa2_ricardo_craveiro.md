# Log de Utilização de IA — Etapa 2

- **Aluno:** Ricardo Craveiro (1191000@isep.ipp.pt)
- **Curso:** Mestrado de Sistemas Autónomos — ISEP
- **Unidade:** DINAV — Dinâmica Avançada 2026
- **Professor:** Pedro Barbosa Guedes
- **Ferramenta de prompts:** Claude Sonnet 4.6
- **Ferramenta de execução:** Claude Opus 4.6
- **Data:** 2026-03-25

---

## Contexto e Objectivo

A Etapa 2 do trabalho laboratorial DINAV 2026 consistiu no desenvolvimento de
uma arquitectura MVC (Model-View-Controller) em Python/PyQt6 para o torpedo AUV
número 10 — um veículo subaquático autónomo inspirado no REMUS 100, modelado
segundo a formalização de Thor I. Fossen (2021).

O ponto de partida foi o ficheiro `torpedo.py` existente no repositório
`ricardocraveir5/PythonVehicleSimulator`, branch `etapa2/mvc-torpedo`.
O objectivo foi:

1. Adicionar getters/setters com validação física ao modelo (torpedo.py).
2. Criar um controlador Qt (TorpedoController) que medeia entre modelo e vista.
3. Criar uma GUI PyQt6 (TorpedoGUI) com duas zonas distintas de parâmetros.
4. Garantir a actualização automática de parâmetros interdependentes (A7, A8).
5. Permitir a configuração e lançamento de uma nova instância de simulação.

---

## Pipeline de Agentes

### Agente 1 — Análise do torpedo.py original

**Objectivo:** Ler o ficheiro torpedo.py e identificar todas as anomalias,
variáveis locais relevantes e oportunidades de encapsulamento.

**Principais decisões:**
- Identificação de 10 anomalias (A1 a A10).
- A1, A5 e A6 documentadas e preservadas (compatibilidade com mainLoop.py).
- A7 (T_heave acoplado a T_sway) e A8 (T_nomoto acoplado a T_yaw) sinalizadas
  para resolução via setters.
- A9 e A10: validação dos parâmetros de referência (ref_z, ref_n) adicionada
  ao `__init__`.

**Handoff:**
```
ESTADO: COMPLETO
ANOMALIAS: A1-A10 identificadas e classificadas
```

---

### Agente 2A — Promoção de variáveis locais a atributos privados

**Objectivo:** Transformar variáveis locais do `__init__` em atributos privados
com prefixo `_`, sem alterar o comportamento externo.

**Principais decisões:**
- `_L`, `_diam`, `_Cd`, `_r44`, `_T_surge`, `_T_sway`, `_T_heave`,
  `_T_yaw`, `_K_nomoto`, `_T_nomoto`, `_wn_d`, `_zeta_d`, `_r_max`,
  `_lam`, `_phi_b`, `_K_d`, `_K_sigma`, `_wn_d_z`, `_Kp_z`, `_T_z`,
  `_Kp_theta`, `_Kd_theta`, `_Ki_theta`, `_K_w` promovidos.
- `_ref_z`, `_ref_psi`, `_ref_n`, `_V_c`, `_beta_c` também promovidos.
- Anomalias A1, A5, A6 comentadas no código com etiqueta DINAV 2026.

**Handoff:**
```
ESTADO: COMPLETO
COMMIT: 1df7151
```

---

### Agente 2B — Getters/setters com validação física (Fossen 2021)

**Objectivo:** Implementar propriedades Python (getters/setters) para todos os
atributos privados, com validação dos limites físicos segundo Fossen (2021).

**Principais decisões:**
- `L` > 0, `diam` > 0 e < L.
- `Cd` ∈ [0.1, 0.5] — limite baseado em Allen et al. (2000).
- `r44` ∈ [0.1, 0.5] — factor de inércia em rolamento.
- `T_surge`, `T_sway`, `T_yaw` > 0.
- **A7:** setter de `T_sway` actualiza `_T_heave` automaticamente.
- **A8:** setter de `T_yaw` actualiza `_T_nomoto` automaticamente.
- `T_heave` e `T_nomoto` expostos apenas como getter (sem setter directo).
- `massa` exposta como propriedade calculada (read-only).
- `zeta_d` ∈ [0.5, 2.0] — intervalo de amortecimento relativo estável.
- `ref_z` ∈ [0, 100] m.
- `ref_n` ∈ [0, nMax] RPM.
- Todos os ValueError em português PT-PT.

**Handoff:**
```
ESTADO: COMPLETO
COMMIT: fe1f69a
```

---

### Agente 2 (final) — get_all_params / set_from_dict / métodos de fins e propulsor

**Objectivo:** Adicionar os métodos utilitários necessários para o Controller:
`get_all_params()`, `set_from_dict()`, `set_fin_CL()`, `get_fin_CL()`,
`set_fin_area()`, `get_fin_area()`, `set_thruster_nMax()`, `get_thruster_nMax()`.

**Principais decisões:**
- `get_all_params()` devolve dicionário completo com 35 chaves.
- `set_from_dict()` ignora silenciosamente `massa`, `T_heave`, `T_nomoto`
  (campos read-only derivados).
- Validação de índice [0–3] nas fins.
- `set_thruster_nMax()` limitado a ]0, 1525] RPM.

**Handoff:**
```
ESTADO: COMPLETO
COMMIT: d00a2e3
```

---

### Agente 3 — torpedo_controller.py

**Objectivo:** Criar a camada Controller do padrão MVC com sinais Qt.

**Principais decisões:**
- `TorpedoController(QObject)` com 4 sinais:
  - `params_updated(dict)` — após alteração bem-sucedida.
  - `simulation_ready(object)` — quando nova instância está pronta.
  - `validation_error(str)` — em caso de ValueError.
  - `param_dependency_updated(str, float)` — quando T_heave ou T_nomoto mudam
    como efeito lateral de um setter.
- `update_param()` faz dispatch especial para `fin_CL_N`, `fin_area_N`,
  `thruster_nMax`; bloqueia `massa`, `T_heave`, `T_nomoto` como read-only.
- `_check_dependencies()` compara snapshot pré e pós setter para detectar
  mudanças em parâmetros dependentes.
- `prepare_simulation()` cria nova instância torpedo() com parâmetros actuais
  + missão, propagando todos os valores via `set_from_dict()`.
- `reset_to_defaults()` recria instância com valores de fábrica.

**Handoff:**
```
ESTADO: COMPLETO
COMMIT: f9d29d2
```

---

### Agente 4A — torpedo_gui.py (estrutura base)

**Objectivo:** Criar a janela principal TorpedoGUI com layout de dois painéis.

**Principais decisões:**
- `TorpedoGUI(QMainWindow)` com splitter horizontal 450+450.
- Painel esquerdo: parâmetros físicos, fins, thruster (QScrollArea).
- Painel direito: controlador de profundidade, controlador de rumo (QScrollArea).
- Barra de botões inferior: "Repor Defaults", "Validar", "Simular".
- `param_widgets: dict[str, QDoubleSpinBox]` como registo central.
- Conexão de todos os sinais do controller aos slots da view.

**Handoff:**
```
ESTADO: COMPLETO
COMMIT: 24c2570
```

---

### Agente 4B — torpedo_gui.py (preenchimento dos painéis)

**Objectivo:** Preencher os grupos de parâmetros com QDoubleSpinBox configurados.

**Principais decisões:**
- Fábrica `_add_spinboxes(form, specs)` partilhada pelos dois painéis.
- 25 widgets registados: L, diam, massa (RO), Cd, r44, fin_CL_0..3,
  thruster_nMax, wn_d_z, Kp_z, T_z, Kp_theta, Kd_theta, Ki_theta, K_w,
  T_heave (RO), wn_d, zeta_d, lam, phi_b, K_d, K_sigma, T_nomoto (RO).
- Read-only: fundo cinzento (#d0d0d0), sem botões de incremento.
- `editingFinished` dos widgets editáveis chama `controller.update_param()`.

**Handoff:**
```
ESTADO: COMPLETO
COMMIT: 0deb499
```

---

### Agente 4 (4C) — torpedo_gui.py (métodos finais)

**Objectivo:** Implementar os slots de resposta a sinais e o diálogo de simulação.

**Principais decisões:**
- `_on_params_updated()`: percorre param_widgets com blockSignals; distingue
  fin_CL_N (via lista) dos restantes parâmetros directos; limpa fundo azul
  (restaura cinzento em read-only, sem estilo nos editáveis).
- `_on_dependency_updated()`: actualiza widget + aplica `background: #d0e8ff`.
- `_on_validation_error()`: statusbar + QMessageBox.warning.
- `_on_simulation_ready()`: statusbar + QMessageBox.information com modo,
  profundidade e rumo de referência.
- `_launch_simulation_dialog()`: QDialog com QComboBox (modo), dois
  QDoubleSpinBox (z: 0–100 m, ψ: −180–180°), OK/Cancel.
- `_load_params()`: chama `_on_params_updated` com resultado de
  `get_current_params()`.

**Handoff:**
```
ESTADO: COMPLETO
COMMIT: d107f80
```

---

### Agente 5A — main_gui.py + requirements_gui.txt

**Objectivo:** Criar o ponto de entrada da aplicação e o ficheiro de dependências.

**Principais decisões:**
- `main_gui.py`: `QApplication` + `TorpedoController` + `TorpedoGUI` + `app.exec()`.
- `requirements_gui.txt`: `PyQt6>=6.4.0`, `numpy>=1.23.0`, `matplotlib>=3.6.0`.
- Cherry-pick dos commits Agente 2, 3 e 4 para o branch `etapa2/mvc-torpedo`
  (necessário porque o branch local não os continha).

**Handoff:**
```
ESTADO: COMPLETO
COMMIT: eb8ad44
APLICACAO_ARRANCA: SIM
```

---

### Agente 5B — Verificação de cenários de integração

**Objectivo:** Testar 6 cenários de integração com código real em modo headless.

**Cenários testados:**

| # | Cenário | Resultado |
|---|---------|-----------|
| 1 | Arranque: widgets carregam com valores correctos | OK |
| 2 | update_param('wn_d', 0.2) → params_updated | OK |
| 3 | update_param('zeta_d', 0.1) → validation_error | OK |
| 4 | update_param('T_sway', 25.0) → dep_updated('T_heave', 25.0) | OK |
| 5 | prepare_simulation('depthHeadingAutopilot', 30, 50) → sim_ready | OK |
| 6 | reset_to_defaults() → params_updated com defaults | OK |

**Correcções:** Nenhuma — todos os cenários passaram à primeira.
Adicionado ficheiro `tests/test_integration_gui.py` com os testes formalizados.

**Handoff:**
```
ESTADO: COMPLETO
COMMIT: 8b2579f
CENARIOS_OK: 1, 2, 3, 4, 5, 6
CENARIOS_CORRIGIDOS: Nenhum
```

---

### Agente 6 — Revisão crítica

**Objectivo:** Verificar conformidade em 6 dimensões e corrigir problemas encontrados.

**Resultados por dimensão:**

| Dimensão | Resultado | Notas |
|----------|-----------|-------|
| D1 — Arquitectura MVC | APROVADO | Model não importa View; View não acede Model directamente |
| D2 — Validações físicas | APROVADO | Limites Fossen correctos; A7 e A8 propagados; ValueError em PT-PT |
| D3 — Compatibilidade mainLoop | APROVADO | dynamics(), stepInput(), depthHeadingAutopilot() intactos |
| D4 — Qualidade da GUI | PROBLEMA → CORRIGIDO | Botão "Validar" não conectado; ligado a `_load_params()` |
| D5 — Conformidade enunciado | APROVADO | Todos os requisitos implementados |
| D6 — Referências e autoria | PROBLEMA → CORRIGIDO | `gui/__init__.py` vazio; adicionado cabeçalho com Fossen e autor |

**Correcções aplicadas:**
1. `torpedo_gui.py` linha 109: `self._btn_validate.clicked.connect(self._load_params)`.
2. `gui/__init__.py`: adicionado cabeçalho com referência a Fossen e identificação do autor.

**Handoff:**
```
ESTADO: COMPLETO
COMMIT: a415c33
VEREDICTO: PRONTO PARA ENTREGA
```

---

## Anomalias Identificadas e Resolução

| # | Anomalia | Tratamento |
|---|----------|------------|
| A1 | `portSternFin`/`starSternFin`: nomes trocados relativamente à posição física | Documentada; preservada para manter compatibilidade com mainLoop.py |
| A2 | Variáveis de tempo constante (T_surge, T_sway, etc.) eram locais ao `__init__` sem exposição externa | Resolvida: promovidas a atributos privados com propriedades |
| A3 | Parâmetros de autopiloto sem validação de domínio físico | Resolvida: setters com limites Fossen adicionados |
| A4 | `massa` calculada implicitamente em `__init__` sem getter público | Resolvida: propriedade read-only `massa` adicionada |
| A5 | `n=1525` hardcoded em `stepInput()`, ignorando `ref_n` | Documentada; preservada (comportamento original) |
| A6 | Sinais `delta_s` em posições 2 e 3 opostos entre `stepInput` e `depthHeadingAutopilot` | Documentada; preservada (comportamento original) |
| A7 | `T_heave` acoplado a `T_sway` apenas no `__init__`, sem propagação dinâmica | Resolvida: setter de `T_sway` actualiza `_T_heave`; controller emite `param_dependency_updated` |
| A8 | `T_nomoto` acoplado a `T_yaw` apenas no `__init__`, sem propagação dinâmica | Resolvida: setter de `T_yaw` actualiza `_T_nomoto`; controller emite `param_dependency_updated` |
| A9 | Sem validação de `ref_z` no `__init__` | Resolvida: setter `ref_z` valida [0, 100] m |
| A10 | Sem validação de `ref_n` no `__init__` | Resolvida: setter `ref_n` valida [0, nMax] RPM |

---

## Decisões de Arquitectura

### Escolha do PyQt6

O enunciado não especificava framework gráfica. PyQt6 foi escolhido por:
- Ligação directa ao sistema de sinais/slots Qt, adequado ao padrão MVC.
- Disponível em Python >= 3.10.
- Separação clara entre thread de eventos Qt e lógica de domínio.

### Separação MVC estrita

- O **Model** (`torpedo.py`) não importa nem conhece o Controller ou a View.
- A **View** (`torpedo_gui.py`) importa apenas `TorpedoController` e nunca
  acede directamente a `torpedo.py`.
- O **Controller** (`torpedo_controller.py`) importa `torpedo` e expõe uma
  interface de sinais Qt para a View.

Esta separação garante que o Model pode ser testado de forma isolada e que a
View pode ser substituída sem alterar a lógica de domínio.

### Estratégia de recriação de instância para simulação

Em vez de reconfigurar a instância existente, `prepare_simulation()` cria uma
**nova instância** de `torpedo()` com os parâmetros actuais + parâmetros de
missão. Isto garante que os estados internos (integrais, estados de referência)
são inicializados a zero, evitando transientes indesejados no início da simulação.

### Validações físicas implementadas

Todos os limites seguem a formalização de Fossen (2021):
- Coeficiente de arrasto `Cd`: Allen et al. (2000) indica [0.1, 0.5].
- Factor de inércia em rolamento `r44` ∈ [0.1, 0.5].
- Constantes de tempo `T_surge`, `T_sway`, `T_yaw` > 0 s.
- Amortecimento relativo `zeta_d` ∈ [0.5, 2.0] (criticamente amortecido a 1.0).
- Profundidade de referência `ref_z` ∈ [0, 100] m.
- RPM de referência `ref_n` ∈ [0, nMax].

### Uso de branches e commits por agente

Cada agente produziu um ou mais commits com mensagem identificada, permitindo
rastrear individualmente cada decisão de implementação. Os commits foram feitos
no branch `claude/torpedo-parameter-inventory-vtoPN` (único com permissão de
escrita no ambiente de execução), e o PR para `etapa2/mvc-torpedo` foi
solicitado via interface GitHub.

---

## Notas Finais

### Conformidade com as considerações do enunciado

**1.a — Ferramenta Claude mantida ao longo de todo o trabalho**

Toda a pipeline de agentes utilizou exclusivamente as ferramentas Claude
(Sonnet 4.6 para prompts, Opus 4.6 para execução). Nenhum outro modelo ou
ferramenta de IA foi utilizado.

**1.b — Prompts e respostas registados**

Todos os prompts e os respectivos handoffs estão registados na conversa de sessão
Claude (session ID: 019EH7Fze5noa1tks9nnkYPW). Este ficheiro de log documenta
o objectivo, as decisões e o resultado de cada agente. Os ficheiros de código
produzidos contêm nos comentários referências directas às decisões documentadas
neste log.

**1.c — Referências ao autor original Thor I. Fossen mantidas**

Todos os ficheiros criados ou modificados incluem referência explícita a:

> T. I. Fossen, *Handbook of Marine Craft Hydrodynamics and Motion Control*,
> 2nd ed., Wiley, 2021. URL: www.fossen.biz/wiley

A referência está presente em:
- `torpedo.py` (cabeçalho, linha 52–53)
- `torpedo_controller.py` (cabeçalho, linha 8)
- `torpedo_gui.py` (cabeçalho, linha 8)
- `main_gui.py` (cabeçalho, linha 4–7)
- `gui/__init__.py` (cabeçalho, linha 3–6)
- `tests/test_integration_gui.py` (comentário de módulo)

---

## Limitações Conhecidas

### Parâmetros que desencadeiam recalculação completa

Após a implementação de `_recalculate_derived()` (PR #2, Correção 1), os seguintes
setters desencadeiam a recalculação de **todos** os parâmetros geométricos e de
massa (S, CD_0, MRB, MA, M, Minv, W, B, w_roll, w_pitch, posição das barbatanas):

| Setter | Grandezas directamente afectadas | Cascata via `_recalculate_derived()` |
|--------|----------------------------------|-------------------------------------|
| `L`    | `_L`, `_a`                       | Todas (massa, matrizes, frequências, posição fins) |
| `diam` | `_diam`, `_b`                    | Todas (massa, matrizes, frequências, posição fins) |
| `Cd`   | `_Cd`                            | Apenas `CD_0` (mas método completo é chamado) |
| `r44`  | `_r44`                           | `MA`, `M`, `Minv`, `w_roll`, `w_pitch` |

Os setters `T_sway`, `T_yaw`, e todos os ganhos dos controladores **não** chamam
`_recalculate_derived()` pois não afectam a geometria nem as matrizes de massa.

### prepare_simulation() não executa a simulação

O método `prepare_simulation()` do Controller cria uma **nova instância** de
`torpedo()` configurada com os parâmetros actuais e os parâmetros de missão
(modo, profundidade, rumo). Esta instância é emitida via o sinal `simulation_ready`
mas **não executa a simulação**.

A integração com `mainLoop.py` (que recebe a instância e faz a integração
numérica) está prevista para a **Etapa 3**.

### Testes de integração são headless

Os testes em `tests/test_integration_gui.py` correm com
`QT_QPA_PLATFORM=offscreen` — os widgets são criados e os sinais Qt são
disparados, mas **nenhum rendering visual** é efectuado. Erros de layout,
sobreposição de widgets, ou problemas de escala apenas são detectáveis com
uma execução visual real.

### T_heave e T_nomoto são read-only

`T_heave` e `T_nomoto` são **parâmetros derivados**:
- `T_heave` é mantido igual a `T_sway` (acoplamento A7)
- `T_nomoto` é mantido igual a `T_yaw` (acoplamento A8)

Para alterar `T_heave`, alterar `T_sway` (widget editável no painel de
Controlador de Profundidade). Para alterar `T_nomoto`, alterar `T_yaw` (widget
editável no painel de Controlador de Rumo).

### Validações dos modos de controlo

O método `prepare_simulation()` aceita apenas dois modos:
- `'depthHeadingAutopilot'` — controlo simultâneo de profundidade e rumo
- `'stepInput'` — entradas em degrau nos actuadores

Qualquer outro valor resulta em `validation_error` sem criar uma nova instância.

---

*Log gerado pelo Agente LOG — DINAV 2026 Etapa 2*
*Actualizado com PR #2 Corrections (Agentes 5B/6 revisão)*
*Ricardo Craveiro (1191000@isep.ipp.pt)*
