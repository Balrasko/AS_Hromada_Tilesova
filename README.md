# Lean Architecture a technický dlh – simulačný experiment

> Druhý samostatný experiment k téme architektonického driftu je opísaný v
> [README_ARCHITECTURAL_DRIFT.md](README_ARCHITECTURAL_DRIFT.md).

Malý reprodukovateľný experiment porovnáva tri stratégie počas 24 sprintov:

- **LEAN / MANAGED DEBT** – rýchly začiatok, evidovaný dlh a refactoring po prekročení hranice,
- **UNCONTROLLED DEBT** – najlacnejšia počiatočná implementácia bez systematického splácania,
- **CLEAN FROM START** – počiatočná investícia do architektúry a pomalý rast dlhu.

Model je zámerne jednoduchý a didaktický. Nie je kalibrovaný na dáta konkrétnej firmy a nemá slúžiť ako predikcia.

## Spustenie

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python technical_debt_experiment.py
```

Voliteľne možno zmeniť seed, počet iterácií, základnú hranicu splácania a adresár výstupov:

```bash
python technical_debt_experiment.py --seed 42 --iterations 24 --threshold 8 --output-dir outputs
```

Skript vypíše DataFrame po iteráciách, konečné porovnanie, sensitivity analysis a krátku slovenskú interpretáciu. Do priečinka `outputs/` uloží:

- `iteration_results.csv` – kompletný DataFrame pre každú stratégiu a iteráciu,
- `final_summary.csv` – konečné porovnávacie metriky,
- `sensitivity_analysis.csv` – výsledky pre rôzne hranice splácania,
- samostatné PNG grafy dlhu, nákladov, dodaných funkcionalít, ceny zmeny a chýb,
- `sensitivity_analysis.png` a `interpretation_sk.txt`.

## Matematický model

Každý sprint má kapacitu `K = 8` časových jednotiek a rovnaký náhodne vygenerovaný prítok požiadaviek pre všetky stratégie. Cena jednej zmeny v iterácii `t` je

```text
change_cost(t) = base_cost × complexity(t) × (1 + debt_drag × debt(t)^1.25)
```

Počet dodaných funkcionalít je celé minimum z backlogu a kapacity, ktorá zostane po architektonickej práci, refactoringu a oprave chýb:

```text
delivered(t) = min(backlog(t), floor(remaining_capacity(t) / change_cost(t)))
```

Nový dlh je úmerný počtu dodaných funkcionalít, ich zložitosti a miernemu náhodnému tlaku na skratky. Pri managed stratégii sa pred vývojom vykoná refactoring, ak dlh dosiahne zadanú hranicu; refactoring spotrebuje 3,2 jednotky kapacity a odstráni 65 % aktuálneho dlhu. Očakávaný počet chýb je

```text
lambda(t) = delivered(t) × (base_defect_rate + debt_defect_rate × debt(t))
defects(t) ~ Poisson(lambda(t))
```

Seed je pevný (`42`), takže dopyt, zložitosť aj náhodné chyby sú reprodukovateľné. Kumulatívne náklady sú súčtom vývojového času a jednoduchej penalizácie za chyby uniknuté z iterácie. Skóre udržiavateľnosti je pomocný index `100 × exp(-debt / 35)`; nejde o štandardizovanú metriku.

Sensitivity analysis opakuje managed stratégiu s hranicami od 4 do 32. V každom behu zachová rovnaké prostredie aj seed, takže pozorované rozdiely spôsobuje zmena politiky refactoringu, nie iný prítok práce.

## Interpretácia

Typický beh ukazuje, že managed aj uncontrolled stratégia v prvých iteráciách využijú absenciu veľkej vstupnej investície a dodávajú rýchlejšie než clean stratégia. Managed tím však dlh explicitne sleduje a občas obetuje kapacitu na jeho zníženie, takže cena ďalších zmien zostáva v kontrolovanom pásme. Pri uncontrolled stratégii sa po úvodnej výhode nelineárne zvyšuje cena zmeny, počet chýb aj backlog. Clean stratégia má stabilné neskoršie tempo a veľmi nízky dlh, ale nesie náklady architektúry ešte predtým, než sa ich prínos plne prejaví. Preto nemusí byť automaticky najlepšia pri krátkom horizonte alebo vysokej neistote produktu. Výsledky sensitivity analysis zároveň ukazujú, že príliš nízka hranica môže viesť k nadmernému refactoringu, kým príliš vysoká hranica nechá dlh zvyšovať náklady a chyby. Experiment teda ilustruje podmienený trade-off, nie univerzálnu pravdu o optimálnej architektúre.
