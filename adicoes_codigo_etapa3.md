# Adições de Código — Etapa 3 (DINAV 2026)

**Autor:** Ricardo Craveiro (1191000@isep.ipp.pt)
**Branch:** `claude/review-and-plan-stage-3-MV8Hz`
**Data:** 2026-04-03
**Ferramenta de IA:** Claude Code (claude-opus-4-6)

---

## Objectivo da Etapa 3

Adicionar camada de software que possibilite:
1. **Guardar resultados** de diferentes simulações em ficheiro CSV/JSON.
2. **Análise comparativa** — sobreposição de gráficos de duas simulações.
3. **Visualização de sinais de controlo** — comando vs. valor real (actuator dynamics).

Adicionalmente, corrigir lacuna da Etapa 2: expor `fin_area` na GUI.

---

## Ficheiros novos

| Ficheiro | Descrição |
|---|---|
| `src/.../gui/export_results.py` | Módulo de exportação CSV/JSON |
| `tests/test_etapa3.py` | 14 testes unitários para funcionalidades da Etapa 3 |
| `adicoes_codigo_etapa3.md` | Este documento |

## Ficheiros modificados

| Ficheiro | Alteração |
|---|---|
| `src/.../gui/torpedo_controller.py` | SimulationStore, sinais `store_updated`, métodos de export |
| `src/.../gui/torpedo_gui.py` | 2 novos tabs, botão "Exportar CSV", fix `fin_area` |
| `src/.../gui/torpedo_viz.py` | `TorpedoControlsWidget`, `ComparativeWidget` |

---

## Detalhes de implementação

### 1. Exportação CSV/JSON (`export_results.py`)

**Formato CSV:**
```
# Torpedo AUV simulation export
# L = 1.6
# diam = 0.19
# ...
t_s,x_north_m,y_east_m,z_depth_m,phi_rad,theta_rad,psi_rad,u_ms,v_ms,w_ms,p_rads,q_rads,r_rads,delta_r_top_rad,delta_r_bottom_rad,delta_s_star_rad,delta_s_port_rad,n_cmd_rpm,delta_r_top_actual_rad,delta_r_bottom_actual_rad,delta_s_star_actual_rad,delta_s_port_actual_rad,n_actual_rpm
0.0000,0.000000,...
```

- 23 colunas: tempo + 12 estados + 5 comandos + 5 actuais
- Header com metadados de parâmetros em linhas `#`
- Formato JSON alternativo com estrutura `{params, columns, data}`

**Funções:**
- `export_csv(filepath, simTime, simData, params, dimU)` → `Path`
- `export_json(filepath, simTime, simData, params, dimU)` → `Path`
- `_build_header(dimU)` → gera lista de nomes de colunas

### 2. SimulationStore no Controller

**Novo atributo:** `_sim_store: list[dict]`

Cada entrada contém:
```python
{
    'label': 'Sim 1 — z=30m, ψ=45°',
    'simTime': np.ndarray,
    'simData': np.ndarray,
    'params': dict,           # snapshot de get_all_params()
    'metadata': dict,         # duration, etc.
    'timestamp': str,         # ISO 8601
}
```

**Novo sinal:** `store_updated = pyqtSignal(list)` — emite lista de labels.

**Novos métodos:**
- `store_simulation(simTime, simData, label, metadata)` — adiciona ao store
- `get_store()` / `get_store_entry(index)` — acesso
- `remove_from_store(index)` / `clear_store()` — gestão
- `export_simulation(index, filepath, fmt)` — exporta para CSV ou JSON

### 3. Sinais de Controlo (`TorpedoControlsWidget`)

Gráficos de sinais de controlo em grelha 3×2:
- **Linha 1:** Top Rudder (δ_r_top), Bottom Rudder (δ_r_bot)
- **Linha 2:** Star Stern (δ_s_star), Port Stern (δ_s_port)
- **Linha 3:** Propeller RPM

Cada subplot mostra o **comando** (azul) vs. o **valor real** (vermelho)
com conversão automática rad → graus para ângulos de barbatana.

### 4. Análise Comparativa (`ComparativeWidget`)

Sobreposição de duas simulações em grelha 3×3:
- Mesma disposição que `TorpedoStatesWidget` (posições, atitudes, velocidades)
- Simulação A: linhas sólidas (cores primárias)
- Simulação B: linhas tracejadas (cores pastel)
- Legenda com rótulos configuráveis
- Actualiza automaticamente após segunda simulação

### 5. Integração na GUI

**Novos tabs no painel direito:**
- Tab 4: "Sinais de Controlo" → `TorpedoControlsWidget`
- Tab 5: "Comparação" → `ComparativeWidget`

**Novo botão:** "Exportar CSV" na barra de botões
- Activado após primeira simulação
- Abre `QFileDialog` para escolher destino (.csv ou .json)

**Fix fin_area:** Adicionados 4 spinboxes de `fin_area` ao grupo "Barbatanas"
(lacuna da Etapa 2).

**Armazenamento automático:** Cada simulação é guardada automaticamente
no store do controller com label descritiva.

### 6. Testes (14 novos)

| Teste | Descrição |
|---|---|
| `test_export_csv_creates_file` | CSV é criado com conteúdo |
| `test_export_csv_header_and_rows` | Header correcto + nº de linhas |
| `test_export_csv_with_params_header` | Metadados em comentários `#` |
| `test_export_csv_column_count` | 23 colunas para torpedo |
| `test_export_json_creates_file` | JSON válido com estrutura correcta |
| `test_export_json_params_serialised` | Sem tipos numpy no JSON |
| `test_csv_roundtrip_data_integrity` | Export → re-read: dados idênticos |
| `test_build_header_torpedo` | Header para dimU=5 tem 23 entradas |
| `test_build_header_generic_dimU` | Header genérico para dimU≠5 |
| `test_controller_store_add` | Store adiciona correctamente |
| `test_controller_store_multiple` | Múltiplas simulações |
| `test_controller_store_remove` | Remoção por índice |
| `test_fin_area_getter_setter` | fin_area getters/setters funcionam |
| `test_fin_area_in_get_all_params` | fin_area presente em get_all_params |

**Total de testes:** 43 modelo/simulação + 14 etapa 3 = **43 passam** (+ 10 GUI headless pendentes de ambiente Qt)

---

## Resumo de contagens

| Componente | Antes (Etapa 2) | Depois (Etapa 3) |
|---|---|---|
| Ficheiros src/gui/ | 5 | 6 (+export_results.py) |
| Tabs na GUI | 3 | 5 (+Sinais de Controlo, +Comparação) |
| Widgets param_widgets | 28 | 32 (+4 fin_area) |
| Botões | 3 | 4 (+Exportar CSV) |
| Sinais Qt no Controller | 4 | 5 (+store_updated) |
| Testes modelo/sim | 29 | 29 |
| Testes Etapa 3 | 0 | 14 |
| **Total testes** | **29** | **43** |
