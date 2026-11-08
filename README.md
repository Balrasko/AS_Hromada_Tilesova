# Simulačné experimenty k softvérovej architektúre

Repozitár obsahuje dva samostatné, reprodukovateľné experimenty v Pythone. Každý z nich je praktickou prílohou k eseji o softvérovej architektúre. Modely sú zámerne jednoduché a didaktické: ilustrujú mechanizmus a kompromisy, nie sú kalibrované na dáta z reálnych projektov a nemajú slúžiť ako predikcia.

| Experiment | Otázka | Dokumentácia |
|---|---|---|
| **Lean Architecture a technický dlh** | Kedy je akceptovanie technického dlhu súčasťou lean prístupu a kedy je to len výhovorka? | [README_LEAN_ARCHITECTURE.md](README_LEAN_ARCHITECTURE.md) |
| **Architektonický drift** | Ako zabrániť postupnému rozpadu softvérovej architektúry? | [README_ARCHITECTURAL_DRIFT.md](README_ARCHITECTURAL_DRIFT.md) |

## Štruktúra repozitára

```text
.
├── technical_debt_experiment.py       # model: lean / nekontrolovaný / clean dlh, neistota požiadaviek
├── figures.py                         # všetky grafy a diagram k experimentu s technickým dlhom
├── architectural_drift_experiment.py  # model architektonického driftu
├── tests/
│   ├── test_experiment.py             # testy experimentu s technickým dlhom
│   └── test_architectural_drift.py    # testy experimentu s driftom
├── README_LEAN_ARCHITECTURE.md
├── README_ARCHITECTURAL_DRIFT.md
└── requirements.txt                   # spoločné závislosti (NumPy, pandas, Matplotlib)
```

## Inštalácia

Oba experimenty majú spoločné závislosti:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Rýchle spustenie

```bash
# Lean Architecture a technický dlh
python technical_debt_experiment.py   # výsledky do outputs/
python figures.py                     # grafy do figures/

# Architektonický drift
python architectural_drift_experiment.py   # výsledky do outputs_architectural_drift/
```

Parametre jednotlivých skriptov, opis modelov a interpretácia výsledkov sú v príslušnom README. Všetky výstupy sa generujú a nie sú súčasťou repozitára.

## Testy

```bash
python -m unittest discover -s tests
```

Testy overujú reprodukovateľnosť (pevný seed), úplnosť výsledkov a to, že modely vykazujú zamýšľané kompromisy.

## Autori a licencia

Filip Hromada, Johanna Tilešová.
