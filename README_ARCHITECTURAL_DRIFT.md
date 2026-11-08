# Architektonický drift – simulačný experiment

> Prehľad celého repozitára je v hlavnom [README.md](README.md).

Experiment je praktickou prílohou k eseji **„Architektonický drift, ako zabrániť postupnému rozpadu softvérovej architektúry“**. Počas 25 sprintov porovnáva tri spôsoby údržby plánovanej štvorvrstvovej architektúry systému objednávok:

- **NO ARCHITECTURE GOVERNANCE** – tím optimalizuje okamžitú rýchlosť a nekontroluje smer závislostí,
- **PERIODIC REVIEW & REFACTORING** – používa code review, ADR a refactoring každých šesť sprintov,
- **CONTINUOUS ARCHITECTURE GUARDRAILS** – investuje do dependency testov a pravidiel v CI, ktoré väčšinu porušení zastavia ešte pred zlúčením kódu.

Model rozlišuje architektonický drift ako počet aktívnych porušení plánovaných pravidiel a architektonickú eróziu ako rastúci architektonický dlh. Dlh získava malý „úrok“, pretože staré porušenia vedú k ďalším obchádzkam a strate znalosti pôvodného zámeru.

## Spustenie

Závislosti sú spoločné s prvým experimentom:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python architectural_drift_experiment.py
```

Voliteľné parametre:

```bash
python architectural_drift_experiment.py --iterations 25 --seed 73 --output-dir outputs_architectural_drift
```

## Plánovaná architektúra

Príklad používa vrstvy `Presentation`, `Application`, `Domain` a `Infrastructure`. Povolené sú najmä smery `Presentation → Application`, `Application → Domain` a závislosti infraštruktúrnych adaptérov smerom k aplikačným portom a doméne. Priamy prístup UI k databáze alebo závislosť domény od databázového frameworku sú porušenia. Tabuľka modelovaných pravidiel sa exportuje do `architecture_rules.csv`.

## Matematický model

Každý sprint dostane rovnaký dopyt, zložitosť a termínový tlak vo všetkých troch stratégiách. Počet pokusov o architektonickú skratku má Poissonovo rozdelenie:

```text
attempts(t) ~ Poisson(delivered(t) × architecture_pressure × delivery_pressure(t))
introduced(t) ~ Binomial(attempts(t), 1 - prevention_effectiveness)
```

Architektonický dlh sa zvyšuje o zavedené porušenia a v každom sprinte rastie o 2 %:

```text
architecture_debt(t+1) = (architecture_debt(t) + 1.5 × introduced(t)) × 1.02
```

Cena zmeny rastie nelineárne:

```text
change_cost(t) = (base_cost + governance_overhead) × complexity(t)
                 × (1 + debt_drag × architecture_debt(t)^1.18)
```

Relatívny drift index je percentuálny pomer aktívnych porušení k odhadovanému počtu závislostí v rastúcom systéme. Počet chýb závisí od množstva dodanej práce, aktívnych porušení a architektonického dlhu. Všetky náhodné veličiny používajú pevný seed, preto je experiment reprodukovateľný.

## Výstupy

Skript vytvorí kompletný DataFrame po iteráciách, konečnú tabuľku a grafy:

- aktívnych porušení architektúry,
- architektonického dlhu a drift indexu,
- ceny ďalšej zmeny,
- dodaných funkcionalít a chýb,
- citlivosti na refactoring každé 2 až 12 iterácií.

Citlivosť ukazuje kompromis medzi príliš častým refactoringom, ktorý spotrebúva kapacitu, a príliš zriedkavým refactoringom, pri ktorom rastú drift, chyby a cena ďalších zmien. Model je zámerne jednoduchý a jeho parametre nie sú empiricky kalibrované; výsledky preto ilustrujú mechanizmus, ale nedokazujú univerzálnu pravdu.
