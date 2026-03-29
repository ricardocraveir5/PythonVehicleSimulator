# HOWTO — Torpedo AUV GUI (DINAV 2026 Etapa 2)

Guia de instalação, execução e teste da interface gráfica MVC para o torpedo AUV.

**Referência:** T. I. Fossen, *Handbook of Marine Craft Hydrodynamics and Motion Control*, 2nd ed., Wiley, 2021.
**Autor das adições:** Ricardo Craveiro (1191000@isep.ipp.pt) — DINAV 2026 Etapa 2

---

## Pré-requisitos

- Python **≥ 3.10**
- pip

---

## 1. Instalação

```bash
# Clonar o repositório
git clone https://github.com/ricardocraveir5/PythonVehicleSimulator.git
cd PythonVehicleSimulator

# Mudar para o branch da Etapa 2
git checkout claude/torpedo-parameter-inventory-vtoPN
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

A janela abre com dois painéis laterais:

| Painel esquerdo (fixo) | Painel direito (3 tabs) |
|------------------------|------------------------|
| Parâmetros físicos (L, diam, massa, Cd, r44, T_surge) | **Tab "Controladores"** — Profundidade + Rumo SMC |
| Barbatanas (CL de cada uma) | **Tab "Visualização 3D"** — animação 3D com câmara a seguir |
| Propulsor (RPM máx.) | **Tab "Gráficos de Estado"** — 9 subplots (toda a simulação) |

### Botões

| Botão | Acção |
|-------|-------|
| **Repor Defaults** | Restaura todos os parâmetros aos valores de fábrica |
| **Validar** | Recarrega os valores actuais do modelo nos widgets |
| **Simular** | Abre diálogo para configurar e lançar simulação |

### Interacção com widgets

- Editar um valor e premir **Enter** ou sair do campo aplica o valor ao modelo
- Campos **cinzentos** são só de leitura (massa, T_heave, T_nomoto)
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
**"Visualização 3D"** e a simulação corre em background (~2 s para 20 s de
simulação). Quando termina, a animação 3D fica activa e o tab
**"Gráficos de Estado"** fica preenchido com os 9 subplots.

---

## 4. Exemplos de Utilização

### Exemplo 1 — Alterar um parâmetro físico

1. No painel esquerdo, localizar o campo **L** (Comprimento).
2. Clicar no campo, alterar de `1.6` para `2.0` e premir **Enter**.
3. O campo **massa** (cinzento, só de leitura) actualiza automaticamente:
   `31.93 kg → 86.65 kg` — recalculado por `_recalculate_derived()`.
4. Clicar **Validar** para confirmar que todos os campos reflectem o modelo.

### Exemplo 2 — Verificar acoplamento T_sway → T_heave

1. Clicar no tab **"Controladores"** (painel direito).
2. Localizar o campo **T_sway** (Constante de tempo em deriva).
3. Alterar para `30.0` e premir **Enter**.
4. O campo **T_heave** (só de leitura) fica com **fundo azul** e actualiza-se
   automaticamente para `30.0` (acoplamento A7 — Fossen 2021).
5. O acoplamento A8 funciona da mesma forma: **T_yaw → T_nomoto**.

### Exemplo 3 — Introduzir um valor inválido

1. Com **diam = 0.19 m**, tentar definir **L = 0.10 m** e premir **Enter**.
2. A barra de estado mostra: `Erro de validação: L deve ser maior do que o diâmetro`.
3. O campo **L** fica com **fundo vermelho** (`#ffcccc`).
4. Clicar **Repor Defaults** para restaurar todos os valores de fábrica.

### Exemplo 4 — Lançar uma simulação e observar a animação 3D

1. Clicar **Simular**.
2. No diálogo, configurar:
   - Modo: `depthHeadingAutopilot`
   - Profundidade: `20 m`
   - Rumo: `45 °`
   - Duração: `20 s`
3. Clicar **OK** — o painel direito muda para o tab **"Visualização 3D"** e a
   barra de estado mostra "A simular…".
4. Após ~2 s, a animação arranca:
   - O **elipsóide azul** representa o corpo do torpedo
   - As **4 barbatanas** (laranja: vertical, verde: horizontal) rodam com o veículo
   - A **trajectória percorrida** é mostrada a azul (esbatida no fundo: trajectória completa)
   - A **câmara segue o torpedo** — os eixos centram-se na posição actual
   - O título mostra `t`, `ψ`, `z` e `u` em tempo real
5. A animação repete automaticamente (parâmetro `repeat=True`).

### Exemplo 5 — Consultar os gráficos de estado

1. Após a simulação terminar, clicar no tab **"Gráficos de Estado"**.
2. São apresentados 9 subplots em grelha 3×3:

   | Linha | Coluna 1 | Coluna 2 | Coluna 3 |
   |-------|----------|----------|----------|
   | 1 | Norte x (m) | Este y (m) | Profundidade z (m) |
   | 2 | Rolamento φ (°) | Arfagem θ (°) | Guinada ψ (°) |
   | 3 | Avanço u (m/s) | Deriva v (m/s) | Afundamento w (m/s) |

3. Todos os gráficos mostram a simulação completa de uma só vez (eixo x = tempo em s).

### Exemplo 6 — Alterar barbatanas e comparar simulações

1. No painel esquerdo, grupo **Barbatanas**, alterar **fin_CL_0** de `0.5` para `0.8`.
2. Clicar **Simular** com os mesmos parâmetros anteriores.
3. Comparar a guinada ψ no tab **"Gráficos de Estado"** entre as duas simulações.

---

## 5. Executar os Testes

### Testes unitários do modelo (sem Qt)

**Linux / macOS:**
```bash
python3 -m pytest tests/test_torpedo_model.py -v
```

**Windows:**
```cmd
python -m pytest tests\test_torpedo_model.py -v
```

16 testes que verificam:
- Setters de L e diam (validação cruzada, actualização de _a/_b)
- Recalculação de parâmetros derivados (_recalculate_derived)
- Acoplamentos A7 (T_sway → T_heave) e A8 (T_yaw → T_nomoto)
- `set_from_dict` com campos read-only (logging.warning)
- `get_all_params` (completude ≥ 30 chaves)
- `dynamics()` após alteração de parâmetro

### Testes de integração GUI (headless)

**Linux / macOS:**
```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_integration_gui.py -v
```

**Windows (cmd.exe):**
```cmd
set QT_QPA_PLATFORM=offscreen && python -m pytest tests\test_integration_gui.py -v
```

**Windows (PowerShell):**
```powershell
$env:QT_QPA_PLATFORM="offscreen"; python -m pytest tests\test_integration_gui.py -v
```

> **Nota:** Em Windows com ecrã físico activo a variável `QT_QPA_PLATFORM=offscreen` pode ser omitida.

7 cenários de integração que verificam:
1. Arranque: widgets carregam com valores correctos
2. Alteração válida: `params_updated` emitido
3. Alteração inválida: `validation_error` emitido
4. Acoplamento A7: T_sway → T_heave actualizado
5. Preparar simulação: `simulation_ready` com instância válida
6. Reset: valores de fábrica restaurados
7. Tabs de visualização: QTabWidget com 3 tabs correctos
8. K_nomoto e r_max: presentes na GUI com valores válidos
9. zeta_roll e zeta_pitch: presentes com valores padrão (0.3, 0.8)
10. Dependência geométrica: aumentar L aumenta a massa calculada

### Todos os testes

**Linux / macOS:**
```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -v
```

**Windows (cmd.exe):**
```cmd
set QT_QPA_PLATFORM=offscreen && python -m pytest tests\ -v
```

Resultado esperado: **39 passed**.

---

## 6. Verificações rápidas em linha de comando

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

### Verificar recalculação de parâmetros derivados

```bash
python3 -c "
import sys; sys.path.insert(0,'src')
from python_vehicle_simulator.vehicles.torpedo import torpedo
t = torpedo()
m0 = t.massa; t.L = 3.0
print('massa mudou:', m0 != t.massa, f'({m0:.2f} → {t.massa:.2f} kg)')
print('actuador stern em -a:', abs(t.actuators[0].R[0] + t._a) < 1e-9)
"
```

### Verificar validação de modo em prepare_simulation

```bash
python3 -c "
import sys; sys.path.insert(0,'src')
from python_vehicle_simulator.gui.torpedo_controller import TorpedoController
c = TorpedoController()
errs = []
c.validation_error.connect(errs.append)
c.prepare_simulation('modoInvalido', 10.0, 0.0)
print('Mode validation OK:', bool(errs))
print('Mensagem:', errs[0] if errs else '')
"
```

---

## 7. Estrutura dos ficheiros relevantes

```
PythonVehicleSimulator/
├── src/python_vehicle_simulator/
│   ├── vehicles/
│   │   └── torpedo.py          ← Model (getters/setters, _recalculate_derived)
│   └── gui/
│       ├── __init__.py
│       ├── torpedo_controller.py  ← Controller (sinais Qt, prepare_simulation)
│       ├── torpedo_gui.py         ← View (janela PyQt6, 28 widgets, 3 tabs)
│       ├── torpedo_viz.py         ← Visualização (SimulationThread, TorpedoVizWidget, TorpedoStatesWidget)
│       └── main_gui.py            ← Ponto de entrada (QApplication)
├── tests/
│   ├── test_torpedo_model.py      ← 16 testes unitários do model
│   └── test_integration_gui.py   ← 10 testes de integração GUI
├── requirements_gui.txt           ← Dependências da GUI
└── log_etapa2_ricardo_craveiro.md ← Log de utilização de IA
```

---

## 8. Resolução de problemas

| Problema | Causa provável | Solução |
|----------|---------------|---------|
| `ModuleNotFoundError: PyQt6` | PyQt6 não instalado | `pip install PyQt6` |
| `could not connect to display` | Sem servidor X no servidor | `export QT_QPA_PLATFORM=offscreen` (Linux/macOS) para testes headless |
| `QMessageBox` bloqueia em testes | Modal sem interacção | Usar `unittest.mock.patch` para `QMessageBox.warning` e `.information` |
| `AttributeError: 'torpedo' has no 'get_all_params'` | Branch errado | Verificar branch `claude/torpedo-parameter-inventory-vtoPN` |
| ValueError ao fazer reset | diam/L em estado inconsistente | Clicar **Repor Defaults** para restaurar fábrica |
| `'python3' is not recognized` | Windows usa `python` | Usar `python` em vez de `python3` |
| `source: command not found` | `source` é bash-only | Windows cmd: `.venv\Scripts\activate.bat`; PowerShell: `.venv\Scripts\Activate.ps1` |
| `set QT_QPA_PLATFORM` não funciona no PowerShell | Sintaxe diferente | Usar `$env:QT_QPA_PLATFORM="offscreen"` no PowerShell |
| `ValueError: RPM…` ao preparar simulação | RPM fora do intervalo válido | O controller emite `validation_error`; a GUI mostra a mensagem |
