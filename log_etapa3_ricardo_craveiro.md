# Log de Utilização de IA — Etapa 3

- **Aluno:** Ricardo Craveiro (1191000@isep.ipp.pt)
- **Curso:** Mestrado de Sistemas Autónomos — ISEP
- **Unidade:** DINAV — Dinâmica Avançada 2026
- **Professor:** Pedro Barbosa Guedes
- **Ferramenta de IA:** Claude Code (claude-opus-4-6)
- **Branch:** `claude/review-and-plan-stage-3-MV8Hz`
- **Data:** 2026-04-03

---

## Contexto e Objectivo

A Etapa 3 do trabalho laboratorial DINAV 2026 acrescenta funcionalidades de
persistência e análise comparativa ao simulador do torpedo AUV:

1. **Exportação CSV/JSON** — guardar resultados de simulações em ficheiro,
   tanto pela GUI como pela CLI (`--csv`, `--json`).
2. **Análise comparativa** — sobreposição de gráficos de duas simulações
   diferentes no mesmo espaço visual.
3. **Visualização de sinais de controlo** — gráficos de comando vs. valor
   real para os 5 actuadores (4 barbatanas + propulsor).
4. **Correcção de lacuna Etapa 2** — exposição de `fin_area` na GUI.

O ponto de partida foi o branch `master` com a Etapa 2 completa (39 testes,
arquitectura MVC funcional).

---

## Pipeline de Agentes — Sessão (2026-04-03)

### Agente 1 — Verificação do estado da Etapa 2

**Objectivo:** Confirmar que o branch `master` contém todas as funcionalidades
da Etapa 2 e que os testes passam.

**Resultado:** 29 testes modelo/simulação confirmados. Branch
`claude/review-and-plan-stage-3-MV8Hz` criado a partir de `master`.

---

### Agente 2 — Planeamento da Etapa 3

**Objectivo:** Definir a arquitectura das novas funcionalidades.

**Principais decisões:**
- **CSV/JSON export** implementado como módulo independente (`export_results.py`)
  sem dependências Qt — reutilizável tanto na GUI como na CLI.
- **SimulationStore** como lista de dicionários no Controller, com sinal
  `store_updated` para notificar a GUI.
- **Formato CSV:** 23 colunas (1 tempo + 12 estados + 5 comandos + 5 actuais),
  header com metadados de parâmetros em linhas `#`.
- **Formato JSON:** estrutura `{params, columns, data}` com sanitização de
  tipos numpy para serialização válida.
- **Sinais de controlo:** grelha 3x2 com conversão automática rad → graus
  para ângulos de barbatana.
- **Análise comparativa:** grelha 3x3 reutilizando `_SPECS` de
  `TorpedoStatesWidget` para consistência visual.

**Decisão do utilizador:**
- Exportação CSV: GUI + CLI (ambas).
- Análise comparativa: estática (sobreposição de gráficos).

---

### Agente 3 — Módulo de exportação (`export_results.py`)

**Objectivo:** Criar módulo de exportação CSV/JSON sem dependências Qt.

**Implementação:**
- `export_csv()`: escreve header com metadados `#`, header CSV, dados com
  formato `:.6g` para precisão adequada.
- `export_json()`: serializa com `_NumpyEncoder` que converte `np.integer`,
  `np.floating`, `np.ndarray` para tipos Python nativos.
- `_build_header()`: gera nomes de colunas — nomes específicos para torpedo
  (dimU=5) e genéricos para outros veículos.

---

### Agente 4 — Widgets de visualização (`torpedo_viz.py`)

**Objectivo:** Adicionar `TorpedoControlsWidget` e `ComparativeWidget`.

**Implementação:**
- `TorpedoControlsWidget`: 5 subplots (4 barbatanas + RPM), cada um com
  linha azul (comando) e linha vermelha (valor real). Conversão rad→deg
  automática para ângulos.
- `ComparativeWidget`: 9 subplots (posições, atitudes, velocidades),
  simulação A em linhas sólidas e simulação B em linhas tracejadas.
  Legenda com rótulos configuráveis.

---

### Agente 5 — Integração GUI e Controller

**Objectivo:** Ligar os novos widgets à GUI existente e adicionar
funcionalidades de store/export ao Controller.

**Implementação no Controller:**
- `store_simulation()`, `get_store()`, `get_store_entry()`,
  `remove_from_store()`, `clear_store()`, `export_simulation()`.
- Sinal `store_updated = pyqtSignal(list)`.

**Implementação na GUI:**
- Tab 4 "Sinais de Controlo" com `TorpedoControlsWidget`.
- Tab 5 "Comparação" com `ComparativeWidget`.
- Botão "Exportar CSV" com `QFileDialog` (suporta `.csv` e `.json`).
- 4 spinboxes de `fin_area` adicionados ao grupo "Barbatanas" (lacuna Etapa 2).
- Armazenamento automático de cada simulação no store.
- Actualização automática do tab de comparação quando ≥2 simulações armazenadas.

---

### Agente 6 — Testes unitários (`test_etapa3.py`)

**Objectivo:** 14 testes cobrindo exportação, store e fin_area.

**Testes implementados:**
- CSV: criação de ficheiro, header/linhas, metadados `#`, contagem de colunas.
- JSON: criação, serialização de params (sem tipos numpy).
- Round-trip: CSV export → numpy reload → comparação (`atol=1e-3`).
- Header builder: torpedo (dimU=5, 23 colunas) e genérico (dimU=3, 19 colunas).
- Store: adição, múltiplas entradas, remoção por índice.
- fin_area: getter/setter e presença em `get_all_params()`.

**Erro encontrado e corrigido:** Tolerância do round-trip inicialmente a
`1e-5` falhava para valores RPM grandes (e.g. 999.0234375 truncado a
999.023 pelo formato `:.6g`). Corrigido para `atol=1e-3`.

---

### Agente 7 — CLI `--csv` / `--json` (`main.py`)

**Objectivo:** Adicionar flags de linha de comando para exportação.

**Implementação:**
- `_parse_args()` com `argparse`: flags `--csv FILE` e `--json FILE`.
- `parse_known_args()` para não quebrar argumentos existentes.
- Após `simulate()`, exporta automaticamente se flags presentes.
- `hasattr(vehicle, 'get_all_params')` para compatibilidade com veículos
  que não têm esse método.

---

## Decisões de Arquitectura

### Módulo de exportação independente

`export_results.py` não importa Qt, PyQt6 ou qualquer componente GUI.
Isto permite:
- Reutilização na CLI (`main.py --csv`) sem carregar PyQt6.
- Testes unitários sem ambiente gráfico.
- Extensibilidade futura (e.g. exportação HDF5).

### SimulationStore no Controller (não no Model)

O store é responsabilidade do Controller porque:
- O Model (`torpedo.py`) é uma entidade de domínio puro — não deve guardar
  histórico de simulações.
- O Controller já gere o ciclo de vida das simulações.
- O sinal `store_updated` integra-se naturalmente com os sinais Qt existentes.

### Formato CSV com metadados

O header `#` no CSV permite:
- Reprodutibilidade: os parâmetros da simulação estão no próprio ficheiro.
- Compatibilidade: `numpy.loadtxt(comments='#')` ignora automaticamente.
- Legibilidade: um utilizador pode abrir o CSV e ver os parâmetros usados.

### Tolerância no round-trip test

O formato `:.6g` oferece 6 dígitos significativos, suficiente para análise
de engenharia mas não para reprodução bit-a-bit. A tolerância de `1e-3`
é adequada para valores na ordem das centenas (RPM).

---

## Ficheiros Criados e Modificados

### Ficheiros novos

| Ficheiro | Linhas | Descrição |
|----------|--------|-----------|
| `src/.../gui/export_results.py` | ~167 | Módulo de exportação CSV/JSON |
| `tests/test_etapa3.py` | ~264 | 14 testes unitários Etapa 3 |
| `adicoes_codigo_etapa3.md` | ~155 | Documentação de adições de código |
| `log_etapa3_ricardo_craveiro.md` | — | Este ficheiro |

### Ficheiros modificados

| Ficheiro | Alterações |
|----------|-----------|
| `src/.../gui/torpedo_controller.py` | +90 linhas: SimulationStore, export, sinal `store_updated` |
| `src/.../gui/torpedo_gui.py` | +96 linhas: 2 tabs, botão exportar, fin_area spinboxes |
| `src/.../gui/torpedo_viz.py` | +198 linhas: `TorpedoControlsWidget`, `ComparativeWidget` |
| `src/.../main.py` | +20 linhas: `argparse`, flags `--csv`/`--json` |

---

## Estado Final

| Componente | Estado |
|-----------|--------|
| Exportação CSV | Funcional (GUI + CLI) |
| Exportação JSON | Funcional (GUI + CLI) |
| SimulationStore | Funcional (auto-store + gestão) |
| Sinais de Controlo | Funcional (5 actuadores, cmd vs actual) |
| Análise Comparativa | Funcional (sobreposição 3x3) |
| fin_area na GUI | Corrigido (4 spinboxes) |
| CLI `--csv`/`--json` | Funcional |
| **Testes modelo/sim** | **29 passam** |
| **Testes Etapa 3** | **14 passam** |
| **Total** | **43 testes passam** |

---

## Notas Finais

### Conformidade com as considerações do enunciado

**1.a — Ferramenta Claude mantida ao longo de todo o trabalho**

Toda a implementação utilizou exclusivamente Claude Code (claude-opus-4-6).
Nenhum outro modelo ou ferramenta de IA foi utilizado.

**1.b — Prompts e respostas registados**

Os agentes e decisões estão documentados neste ficheiro. O histórico
completo está disponível via a sessão Claude Code.

**1.c — Referências ao autor original Thor I. Fossen mantidas**

Todos os ficheiros criados ou modificados incluem referência a:

> T. I. Fossen, *Handbook of Marine Craft Hydrodynamics and Motion Control*,
> 2nd ed., Wiley, 2021. URL: www.fossen.biz/wiley

---

*Log gerado com Claude Code — claude-opus-4-6*
*Data: 2026-04-03*
*Ricardo Craveiro (1191000@isep.ipp.pt) — DINAV 2026 Etapa 3*
