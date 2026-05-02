# HOWTO — Torpedo AUV GUI (DINAV 2026)

Guia de instalação, execução e teste da interface gráfica MVC para o torpedo AUV.
Cobre as Etapas 2, 3 e 4 do projecto DINAV 2026.

**Referência:** T. I. Fossen, *Handbook of Marine Craft Hydrodynamics and Motion Control*, 2nd ed., Wiley, 2021.
**Autor das adições:** Ricardo Craveiro (1191000@isep.ipp.pt) — DINAV 2026

---

## Pré-requisitos

- Python **≥ 3.10**
- pip

---

## 1. Instalação

```bash
# Clonar o repositório (branch master — contém todas as etapas)
git clone https://github.com/ricardocraveir5/PythonVehicleSimulator.git
cd PythonVehicleSimulator
```

**(Recomendado) Criar ambiente virtual:**

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (cmd.exe):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Instalar dependências (todas as plataformas):**
```bash
pip install -e .
pip install -r requirements_gui.txt
```

O ficheiro `requirements_gui.txt` instala:
- `PyQt6 >= 6.4.0`
- `numpy >= 1.23.0`
- `matplotlib >= 3.6.0`

---

## 2. Lançar a GUI

**Linux / macOS:**
```bash
python3 -m python_vehicle_simulator.gui.main_gui
# ou directamente:
python3 src/python_vehicle_simulator/gui/main_gui.py
```

**Windows:**
```cmd
python -m python_vehicle_simulator.gui.main_gui
```

A janela abre com dois painéis principais:

| Painel esquerdo (fixo) | Painel direito (7 tabs) |
|------------------------|------------------------|
| Parâmetros físicos (L, diam, massa, Cd, V_c, β_c, r44, T_surge) | **Tab "Controladores"** — Profundidade + Rumo SMC + Corrente Oceânica |
| Barbatanas (CL e área de cada uma) | **Tab "Visualização 3D"** — animação 3D com câmara a seguir |
| Propulsor (RPM máx.) | **Tab "Gráficos de Estado"** — 9 subplots (toda a simulação) |
| | **Tab "Gráficos Etapa 3"** — trajectória, profundidade, velocidades, actuadores |
| | **Tab "Sinais de Controlo"** — comando vs. valor real (6 subplots) |
| | **Tab "Comparação"** — sobreposição de duas simulações em 9 subplots |
| | **Tab "Análise"** — curva de arrasto, resposta analítica, preview ao vivo |

### Botões

| Botão | Acção |
|-------|-------|
| **Repor Defaults** | Restaura todos os parâmetros aos valores de fábrica |
| **Validar** | Recarrega os valores actuais do modelo nos widgets |
| **Simular** | Abre diálogo para configurar e lançar uma simulação |
| **Parar** | Cancela a simulação em curso (activo apenas durante simulação) |
| **Simular A e B (Etapa 3)** | Corre duas simulações seguidas e mostra animação 3D lado a lado |
| **Comparar Sem/Com Corrente** | Corre duas simulações (sem e com corrente) e sobrepõe resultados |
| **Comparar 2 Cenários…** | Abre diálogo para configurar dois cenários totalmente personalizados |
| **Exportar CSV** | Exporta a última simulação para CSV ou JSON (activo após primeira simulação) |

### Interacção com widgets

- Editar um valor e premir **Enter** ou sair do campo aplica o valor ao modelo
- Campos **cinzentos** são só de leitura (massa, T_heave, T_nomoto, κ)
- Campos com **fundo azul** (`#d0e8ff`) foram actualizados automaticamente
  por acoplamento (A7: T_sway → T_heave; A8: T_yaw → T_nomoto)
- Campos com **fundo vermelho** (`#ffcccc`) contêm um valor inválido

---

## 3. Diálogo de Simulação

Clicar **Simular** abre um diálogo com:

| Campo | Descrição | Intervalo |
|-------|-----------|-----------|
| Modo de controlo | `depthHeadingAutopilot` ou `stepInput` | — |
| Profundidade desejada | z_d (positivo para baixo) | 0 – 100 m |
| Rumo desejado | ψ_d | −180 – 180° |
| Duração | Tempo total de simulação | 5 – 300 s |

Ao clicar **OK**, o painel direito muda automaticamente para o tab
**"Visualização 3D"** e a simulação corre em background. Quando termina:
- A animação 3D fica activa
- Os tabs **"Gráficos de Estado"**, **"Gráficos Etapa 3"** e **"Sinais de Controlo"** ficam preenchidos
- O botão **Exportar CSV** fica activo

---

## 4. Modelos de Corrente Oceânica (Etapa 4)

O grupo **"Corrente Oceânica"** na tab **"Controladores"** permite escolher entre 5 perfis:

| Modelo | Parâmetros específicos | Comportamento |
|--------|------------------------|---------------|
| **Constante** | Usa V_c e β_c dos Parâmetros Físicos | Velocidade e direcção fixas |
| **Linear** | V_surface (m/s), z_ref (m) | V_c cresce linearmente com a profundidade |
| **Lei 1/7** | V_surface (m/s), z_ref (m) | V_c cresce com perfil de potência 1/7 |
| **Logarítmico** | V_star (m/s), z_0 (m), κ (fixo 0.41) | Perfil logarítmico de camada limite |
| **Gauss-Markov** | μ (1/s), σ (m/s), V_c0 (m/s), seed | Processo estocástico de 1.ª ordem |

O gráfico **V_c(z)** actualiza-se automaticamente sempre que se altera um parâmetro,
mostrando o perfil de velocidade da corrente em função da profundidade (NED, z positivo para baixo).

### Botões de comparação com corrente

- **Comparar Sem/Com Corrente** — fixa automaticamente 200 s de simulação, corre primeiro
  sem corrente (baseline) e depois com o modelo de corrente activo, exporta dois CSVs em
  `etapa4/comparacao_<timestamp>_A.csv` e `..._B.csv`, e mostra o overlay na tab **"Comparação"**.
- **Comparar 2 Cenários…** — abre o diálogo `CompareScenariosDialog` com duas colunas
  configuráveis (título, Cd, V_c, β_c, z_d, ψ_d, RPM, modelo de corrente).
  Pré-preenche ambas as colunas com os parâmetros actuais.

---

## 5. Tab "Análise" — Gráficos Analíticos e Preview ao Vivo

A tab **"Análise"** contém três widgets que não requerem simulação completa:

| Widget | O que mostra | Quando actualiza |
|--------|--------------|-----------------|
| **Curva de Arrasto** | F_drag(U) = ½·ρ·CD·S·U², U ∈ [0, 3] m/s | A cada mudança de Cd, L ou diam |
| **Resposta do Controlador** | Resposta ao degrau analítica do laço de profundidade (2.ª ordem, wn_d_z e ζ_d) | A cada mudança de parâmetros de controlo |
| **Preview ao Vivo** | z(t) e u(t) de simulação curta (50 s, dt=0.05 s) | A cada mudança de parâmetros, com debounce de 800 ms |

Para activar o **Preview ao Vivo**, marcar a checkbox "Preview ao vivo" no topo do widget.
Ao alterar qualquer parâmetro, o preview cancela automaticamente a simulação anterior antes de recalcular.

---

## 6. Exemplos de Utilização

### Exemplo 1 — Alterar um parâmetro físico

1. No painel esquerdo, localizar o campo **L** (Comprimento).
2. Clicar no campo, alterar de `1.6` para `2.0` e premir **Enter**.
3. O campo **massa** (cinzento, só de leitura) actualiza automaticamente.
4. Clicar **Validar** para confirmar que todos os campos reflectem o modelo.

### Exemplo 2 — Verificar acoplamento T_sway → T_heave

1. Clicar no tab **"Controladores"** (painel direito).
2. Localizar o campo **T_sway** (Constante de tempo em deriva).
3. Alterar para `30.0` e premir **Enter**.
4. O campo **T_heave** (só de leitura) fica com **fundo azul** e actualiza-se
   automaticamente para `30.0` (acoplamento A7 — Fossen 2021).

### Exemplo 3 — Lançar uma simulação e observar a animação 3D

1. Clicar **Simular**.
2. No diálogo, configurar:
   - Modo: `depthHeadingAutopilot`
   - Profundidade: `20 m`
   - Rumo: `45 °`
   - Duração: `20 s`
3. Clicar **OK** — a animação 3D arranca automaticamente:
   - O **elipsóide azul** representa o corpo do torpedo
   - As **4 barbatanas** (laranja: vertical, verde: horizontal) rodam com o veículo
   - A **trajectória percorrida** é mostrada a azul
   - A **câmara segue o torpedo** — os eixos centram-se na posição actual
   - O título mostra `t`, `ψ`, `z` e `u` em tempo real
4. A animação repete automaticamente (`repeat=True`).

### Exemplo 4 — Consultar os gráficos de estado

1. Após a simulação terminar, clicar no tab **"Gráficos de Estado"**.
2. São apresentados 9 subplots em grelha 3×3:

   | Linha | Coluna 1 | Coluna 2 | Coluna 3 |
   |-------|----------|----------|----------|
   | 1 | Norte x (m) | Este y (m) | Profundidade z (m) |
   | 2 | Rolamento φ (°) | Arfagem θ (°) | Guinada ψ (°) |
   | 3 | Avanço u (m/s) | Deriva v (m/s) | Afundamento w (m/s) |

### Exemplo 5 — Visualizar sinais de controlo

1. Após a simulação, clicar no tab **"Sinais de Controlo"**.
2. São apresentados 6 subplots em grelha 3×2:
   - **Linha 1:** Top Rudder (δ_r_top) | Bottom Rudder (δ_r_bot)
   - **Linha 2:** Star Stern (δ_s_star) | Port Stern (δ_s_port)
   - **Linha 3:** Propeller RPM
3. Cada subplot mostra o **comando** (azul) vs. o **valor real** (vermelho).

### Exemplo 6 — Exportar resultados para CSV

1. Após uma simulação, clicar **Exportar CSV**.
2. Na janela de ficheiro, escolher o destino e a extensão (`.csv` ou `.json`).
3. O ficheiro CSV contém 23 colunas: `t_s` + 12 estados + 5 comandos + 5 actuais,
   com metadados de parâmetros em linhas de comentário `#`.

### Exemplo 7 — Comparar duas simulações

1. Correr uma primeira simulação (ex.: Cd=0.42, z_d=20 m).
2. Alterar **Cd** para `0.25` no painel esquerdo.
3. Correr uma segunda simulação com os mesmos parâmetros de controlo.
4. Clicar no tab **"Comparação"** — as duas simulações são sobrepostas em 9 subplots:
   - Simulação A: linhas sólidas
   - Simulação B: linhas tracejadas

### Exemplo 8 — Usar corrente oceânica Gauss-Markov

1. Na tab **"Controladores"**, grupo **"Corrente Oceânica"**, seleccionar **Gauss-Markov**.
2. Configurar: μ=0.01, σ=0.1, V_c0=0.3, seed=42.
3. O gráfico V_c(z) actualiza-se mostrando o perfil estocástico.
4. Clicar **Simular** — a corrente estocástica é aplicada em cada passo de `dynamics()`.
5. Comparar com baseline usando **Comparar Sem/Com Corrente**.

### Exemplo 9 — Preview ao vivo enquanto ajusta parâmetros

1. Clicar no tab **"Análise"** e activar a checkbox **"Preview ao vivo"**.
2. Alterar **Cd** no painel esquerdo — ao fim de 800 ms o preview actualiza
   automaticamente os subplots z(t) e u(t) sem necessidade de clicar Simular.
3. Clicar **Parar** a qualquer momento para cancelar um preview em curso.

### Exemplo 10 — Comparar 2 cenários personalizados

1. Clicar **Comparar 2 Cenários…**.
2. No diálogo, a coluna A está pré-preenchida com os parâmetros actuais.
3. Na coluna B alterar, por exemplo, Cd de `0.42` para `0.25` e o modelo de
   corrente de `Constante` para `Linear`.
4. Clicar **OK** — as duas simulações correm sequencialmente (200 s cada) e
   os resultados são sobrepostos na tab **"Comparação"** e exportados como CSV.

---

## 7. Executar os Testes

### Testes unitários do modelo (sem Qt)

**Linux / macOS:**
```bash
python3 -m pytest tests/test_torpedo_model.py tests/test_simulate.py tests/test_environment.py tests/test_etapa3.py -v
```

**Windows:**
```cmd
python -m pytest tests\test_torpedo_model.py tests\test_simulate.py tests\test_environment.py tests\test_etapa3.py -v
```

### Testes de integração GUI (headless)

**Linux / macOS:**
```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_integration_gui.py tests/test_etapa3_widget.py -v
```

**Windows (cmd.exe):**
```cmd
set QT_QPA_PLATFORM=offscreen && python -m pytest tests\test_integration_gui.py tests\test_etapa3_widget.py -v
```

**Windows (PowerShell):**
```powershell
$env:QT_QPA_PLATFORM="offscreen"; python -m pytest tests\test_integration_gui.py tests\test_etapa3_widget.py -v
```

> **Nota:** Em Windows com ecrã físico activo a variável `QT_QPA_PLATFORM=offscreen` pode ser omitida.

### Todos os testes

**Linux / macOS:**
```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -v
```

**Windows (cmd.exe):**
```cmd
set QT_QPA_PLATFORM=offscreen && python -m pytest tests\ -v
```

Resultado esperado: **152 passed**, distribuídos por 8 ficheiros:

| Ficheiro | Testes | Âmbito |
|----------|--------|--------|
| `test_simulate.py` | 4 | Etapa 1 — loop de simulação |
| `test_torpedo_model.py` | 25 | Etapas 1/2 — modelo torpedo |
| `test_etapa3.py` | 14 | Etapa 3 — exportação CSV/JSON, store |
| `test_etapa3_widget.py` | 13 | Etapa 3+ — widgets GUI headless |
| `test_environment.py` | 25 | Etapa 4 — `CurrentModel` (5 perfis) |
| `test_torpedo_etapa4.py` | 15 | Etapa 4 — torpedo × corrente |
| `test_etapa4.py` | 6 | Etapa 4 — campanha S0-S5 |
| `test_integration_gui.py` | 48 | Etapas 2/3/4 — integração GUI headless |

---

## 8. Verificações rápidas em linha de comando

> **Nota Windows:** substituir `python3` por `python` em todos os comandos abaixo.

### Verificar validação cruzada L/diam

```bash
python3 -c "
import sys; sys.path.insert(0,'src')
from python_vehicle_simulator.vehicles.torpedo import torpedo
t = torpedo()
try:
    t.L = 0.10   # diam=0.19 → deve falhar
    print('FAIL: sem ValueError')
except ValueError as e:
    print('OK:', e)
"
```

### Verificar modelo de corrente Linear

```bash
python3 -c "
import sys; sys.path.insert(0,'src')
from python_vehicle_simulator.lib.environment import LinearProfile
from python_vehicle_simulator.vehicles.torpedo import torpedo
m = LinearProfile(V_surface=0.5, z_ref=50.0, beta_c_deg=0.0)
t = torpedo(current_model=m)
V_c, beta_c = t.V_c, t.beta_c
print(f'V_c={V_c:.4f} m/s  beta_c={beta_c:.4f} rad')
"
```

### Verificar recalculação de parâmetros derivados

```bash
python3 -c "
import sys; sys.path.insert(0,'src')
from python_vehicle_simulator.vehicles.torpedo import torpedo
t = torpedo()
m0 = t.massa; t.L = 3.0
print('massa mudou:', m0 != t.massa, f'({m0:.2f} → {t.massa:.2f} kg)')
"
```

---

## 9. Estrutura dos ficheiros relevantes

```
PythonVehicleSimulator/
├── src/python_vehicle_simulator/
│   ├── vehicles/
│   │   └── torpedo.py              ← Model (getters/setters, current_model, _recalculate_derived)
│   ├── lib/
│   │   ├── environment.py          ← CurrentModel + 5 perfis de corrente (Etapa 4)
│   │   └── mainLoop.py             ← simulate() com suporte a cancelamento cooperativo
│   └── gui/
│       ├── __init__.py
│       ├── export_results.py       ← Exportação CSV/JSON (Etapa 3)
│       ├── torpedo_controller.py   ← Controller (sinais Qt, SimulationStore, correntes)
│       ├── torpedo_gui.py          ← View (janela PyQt6, 7 tabs, 8 botões)
│       ├── torpedo_viz.py          ← Widgets de visualização (3D, estados, controlo, comparação, análise)
│       └── main_gui.py             ← Ponto de entrada (QApplication)
├── tests/
│   ├── test_simulate.py            ← 4 testes — loop de simulação
│   ├── test_torpedo_model.py       ← 25 testes — modelo torpedo
│   ├── test_etapa3.py              ← 14 testes — exportação e store
│   ├── test_etapa3_widget.py       ← 13 testes — widgets Etapa 3
│   ├── test_environment.py         ← 25 testes — CurrentModel
│   ├── test_torpedo_etapa4.py      ← 15 testes — torpedo × corrente
│   ├── test_etapa4.py              ← 6 testes — campanha S0-S5
│   └── test_integration_gui.py     ← 48 testes — integração GUI headless
├── etapa4/                         ← Scripts e outputs da campanha S0-S5
├── requirements_gui.txt            ← Dependências da GUI (PyQt6, numpy, matplotlib)
├── adicoes_codigo_etapa2.md        ← Documentação técnica Etapa 2
├── adicoes_codigo_etapa3.md        ← Documentação técnica Etapa 3
└── adicoes_codigo_etapa4.md        ← Documentação técnica Etapa 4
```

---

## 10. Resolução de problemas

| Problema | Causa provável | Solução |
|----------|---------------|---------|
| `ModuleNotFoundError: PyQt6` | PyQt6 não instalado | `pip install PyQt6` |
| `could not connect to display` | Sem servidor X no servidor | `export QT_QPA_PLATFORM=offscreen` (Linux/macOS) para testes headless |
| `QMessageBox` bloqueia em testes | Modal sem interacção | Usar `unittest.mock.patch` para `QMessageBox.warning` e `.information` |
| `ValueError ao fazer reset` | diam/L em estado inconsistente | Clicar **Repor Defaults** para restaurar fábrica |
| `'python3' is not recognized` | Windows usa `python` | Usar `python` em vez de `python3` |
| `source: command not found` | `source` é bash-only | Windows cmd: `.venv\Scripts\activate.bat`; PowerShell: `.venv\Scripts\Activate.ps1` |
| `set QT_QPA_PLATFORM` não funciona no PowerShell | Sintaxe diferente | Usar `$env:QT_QPA_PLATFORM="offscreen"` no PowerShell |
| `ValueError: RPM…` ao preparar simulação | RPM fora do intervalo válido | O controller emite `validation_error`; a GUI mostra a mensagem na barra de estado |
| Preview ao vivo não actualiza | Checkbox desmarcada ou parâmetro não propagado | Verificar checkbox "Preview ao vivo" e premir **Enter** após editar o campo |
| Simulação não cancela | Thread em estado bloqueado | Fechar e reabrir a janela; `closeEvent` cancela todas as threads activas |
