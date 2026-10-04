"""Reprodukovateľná simulácia troch prístupov k technickému dlhu.

Model nie je predikčný nástroj. Je to malý experiment určený na ilustráciu
trade-offu medzi rýchlosťou dodania, kvalitou a dlhodobou udržateľnosťou.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

# Lokálna cache odstráni závislosť od zapisovateľného domovského adresára.
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib-cache"))

import matplotlib

# Skript tak vie ukladať grafy aj na serveri bez grafického prostredia.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


STRATEGY_ORDER = ["LEAN / MANAGED DEBT", "UNCONTROLLED DEBT", "CLEAN FROM START"]
STRATEGY_COLORS = {
    "LEAN / MANAGED DEBT": "#2a9d8f",
    "UNCONTROLLED DEBT": "#e76f51",
    "CLEAN FROM START": "#457b9d",
}


@dataclass(frozen=True)
class SimulationConfig:
    """Spoločné parametre experimentu."""

    iterations: int = 24
    seed: int = 42
    sprint_capacity: float = 8.0
    min_feature_demand: int = 4
    max_feature_demand: int = 6
    debt_exponent: float = 1.25
    defect_fix_time: float = 0.35
    escaped_defect_penalty: float = 0.75


@dataclass(frozen=True)
class StrategyConfig:
    """Parametre, ktorými sa stratégie zámerne odlišujú."""

    name: str
    base_change_cost: float
    debt_drag: float
    debt_per_feature: float
    base_defect_rate: float
    debt_defect_rate: float
    architecture_investments: tuple[float, ...] = ()
    repayment_threshold: float | None = None
    refactoring_time: float = 0.0
    repayment_fraction: float = 0.0
    defect_seed_offset: int = 0


@dataclass(frozen=True)
class ProjectEnvironment:
    """Rovnaký prítok práce a rovnaká zložitosť pre všetky stratégie."""

    feature_demand: np.ndarray
    complexity: np.ndarray
    shortcut_pressure: np.ndarray


def default_strategies(repayment_threshold: float = 8.0) -> list[StrategyConfig]:
    """Vráti tri scenáre použité v hlavnom experimente."""

    return [
        StrategyConfig(
            name="LEAN / MANAGED DEBT",
            base_change_cost=0.90,
            debt_drag=0.018,
            debt_per_feature=0.55,
            base_defect_rate=0.05,
            debt_defect_rate=0.008,
            repayment_threshold=repayment_threshold,
            refactoring_time=3.2,
            repayment_fraction=0.65,
            defect_seed_offset=101,
        ),
        StrategyConfig(
            name="UNCONTROLLED DEBT",
            base_change_cost=0.75,
            debt_drag=0.025,
            debt_per_feature=0.75,
            base_defect_rate=0.07,
            debt_defect_rate=0.012,
            defect_seed_offset=202,
        ),
        StrategyConfig(
            name="CLEAN FROM START",
            base_change_cost=1.20,
            debt_drag=0.006,
            debt_per_feature=0.04,
            base_defect_rate=0.025,
            debt_defect_rate=0.003,
            # Čas investovaný do architektúry v prvých štyroch iteráciách.
            architecture_investments=(5.0, 4.0, 3.0, 2.0),
            defect_seed_offset=303,
        ),
    ]


def create_environment(config: SimulationConfig) -> ProjectEnvironment:
    """Vygeneruje reprodukovateľné externé podmienky projektu."""

    rng = np.random.default_rng(config.seed)
    return ProjectEnvironment(
        feature_demand=rng.integers(
            config.min_feature_demand,
            config.max_feature_demand + 1,
            size=config.iterations,
        ),
        complexity=np.clip(rng.normal(1.0, 0.08, config.iterations), 0.80, 1.20),
        shortcut_pressure=rng.uniform(0.90, 1.10, config.iterations),
    )


class ProjectSimulator:
    """Diskrétny model projektu s jedným časovým krokom na iteráciu."""

    def __init__(self, config: SimulationConfig, environment: ProjectEnvironment):
        self.config = config
        self.environment = environment

    def _change_cost(self, strategy: StrategyConfig, debt: float, complexity: float) -> float:
        """Cena jednej priemernej zmeny rastie nelineárne s dlhom."""

        debt_multiplier = 1.0 + strategy.debt_drag * debt**self.config.debt_exponent
        return strategy.base_change_cost * complexity * debt_multiplier

    def run_strategy(self, strategy: StrategyConfig) -> pd.DataFrame:
        """Odbehne jednu stratégiu a vráti záznam za každú iteráciu."""

        if len(self.environment.feature_demand) != self.config.iterations:
            raise ValueError("Dĺžka prostredia sa nezhoduje s počtom iterácií.")

        rng = np.random.default_rng(self.config.seed + strategy.defect_seed_offset)
        debt = 0.0
        backlog = 0
        delivered_total = 0
        defect_total = 0
        previous_new_defects = 0
        cumulative_development_time = 0.0
        cumulative_cost = 0.0
        rows: list[dict[str, float | int | str | bool]] = []

        for index in range(self.config.iterations):
            iteration = index + 1
            incoming_demand = int(self.environment.feature_demand[index])
            backlog += incoming_demand

            architecture_time = (
                strategy.architecture_investments[index]
                if index < len(strategy.architecture_investments)
                else 0.0
            )

            # Oprava chýb z predošlej iterácie spotrebuje čas aktuálneho sprintu.
            defect_rework_time = min(
                previous_new_defects * self.config.defect_fix_time,
                self.config.sprint_capacity,
            )

            refactoring_performed = False
            refactoring_time = 0.0
            debt_repaid = 0.0
            if (
                strategy.repayment_threshold is not None
                and debt >= strategy.repayment_threshold
            ):
                refactoring_performed = True
                refactoring_time = strategy.refactoring_time
                debt_repaid = debt * strategy.repayment_fraction
                debt -= debt_repaid

            change_cost = self._change_cost(
                strategy,
                debt,
                float(self.environment.complexity[index]),
            )
            feature_capacity = max(
                0.0,
                self.config.sprint_capacity
                - architecture_time
                - refactoring_time
                - defect_rework_time,
            )
            capacity_limited_features = int(np.floor(feature_capacity / change_cost))
            delivered_now = min(backlog, capacity_limited_features)
            feature_development_time = delivered_now * change_cost
            backlog -= delivered_now
            delivered_total += delivered_now

            # Skratky vytvárajú dlh úmerný množstvu dodanej práce. CLEAN má
            # malú, nie nulovú sadzbu: ani dobrá architektúra neeliminuje dlh.
            debt_added = (
                delivered_now
                * strategy.debt_per_feature
                * float(self.environment.complexity[index])
                * float(self.environment.shortcut_pressure[index])
            )
            debt += debt_added

            # Počet chýb je Poissonova veličina; seed zaručuje reprodukovateľnosť.
            expected_defects = delivered_now * (
                strategy.base_defect_rate + strategy.debt_defect_rate * debt
            )
            new_defects = int(rng.poisson(expected_defects))
            defect_total += new_defects
            previous_new_defects = new_defects

            development_time = (
                architecture_time
                + refactoring_time
                + defect_rework_time
                + feature_development_time
            )
            project_cost = development_time + new_defects * self.config.escaped_defect_penalty
            cumulative_development_time += development_time
            cumulative_cost += project_cost
            maintainability_score = 100.0 * np.exp(-debt / 35.0)

            rows.append(
                {
                    "iteration": iteration,
                    "strategy": strategy.name,
                    "new_feature_demand": incoming_demand,
                    "backlog_features": backlog,
                    "delivered_this_iteration": delivered_now,
                    "delivered_features": delivered_total,
                    "technical_debt": debt,
                    "debt_added": debt_added,
                    "debt_repaid": debt_repaid,
                    "refactoring_performed": refactoring_performed,
                    "architecture_time": architecture_time,
                    "refactoring_time": refactoring_time,
                    "defect_rework_time": defect_rework_time,
                    "feature_development_time": feature_development_time,
                    "development_time": development_time,
                    "cumulative_development_time": cumulative_development_time,
                    "new_defects": new_defects,
                    "defect_count": defect_total,
                    "change_cost": change_cost,
                    "maintainability_score": maintainability_score,
                    "iteration_cost": project_cost,
                    "cumulative_cost": cumulative_cost,
                }
            )

        return pd.DataFrame(rows)


def run_experiment(
    config: SimulationConfig,
    repayment_threshold: float = 8.0,
) -> pd.DataFrame:
    """Spustí všetky stratégie nad rovnakým prostredím."""

    environment = create_environment(config)
    simulator = ProjectSimulator(config, environment)
    frames = [
        simulator.run_strategy(strategy)
        for strategy in default_strategies(repayment_threshold)
    ]
    return pd.concat(frames, ignore_index=True)


def make_summary(results: pd.DataFrame) -> pd.DataFrame:
    """Vytvorí konečnú porovnávaciu tabuľku."""

    final_rows = results.sort_values("iteration").groupby("strategy", sort=False).tail(1)
    first_six = (
        results[results["iteration"] == 6]
        .set_index("strategy")["delivered_features"]
        .to_dict()
    )
    refactor_counts = (
        results.groupby("strategy")["refactoring_performed"].sum().astype(int).to_dict()
    )
    records: list[dict[str, float | int | str]] = []
    for row in final_rows.itertuples(index=False):
        delivered = int(row.delivered_features)
        records.append(
            {
                "strategy": row.strategy,
                "features_after_6_iterations": int(first_six[row.strategy]),
                "total_delivered_features": delivered,
                "final_backlog": int(row.backlog_features),
                "final_technical_debt": row.technical_debt,
                "total_development_time": row.cumulative_development_time,
                "total_cost": row.cumulative_cost,
                "average_cost_per_feature": row.cumulative_cost / delivered if delivered else np.nan,
                "total_defects": int(row.defect_count),
                "average_change_cost": results.loc[
                    results["strategy"] == row.strategy, "change_cost"
                ].mean(),
                "final_maintainability_score": row.maintainability_score,
                "refactoring_count": refactor_counts[row.strategy],
            }
        )

    summary = pd.DataFrame(records).set_index("strategy")
    return summary.reindex(STRATEGY_ORDER)


def run_sensitivity_analysis(
    config: SimulationConfig,
    thresholds: Iterable[float],
) -> pd.DataFrame:
    """Mení iba hranicu splácania; ostatné podmienky a seed zostávajú rovnaké."""

    environment = create_environment(config)
    simulator = ProjectSimulator(config, environment)
    managed_template = default_strategies()[0]
    records: list[dict[str, float | int]] = []

    for threshold in thresholds:
        strategy = replace(managed_template, repayment_threshold=float(threshold))
        result = simulator.run_strategy(strategy)
        last = result.iloc[-1]
        delivered = int(last["delivered_features"])
        records.append(
            {
                "repayment_threshold": float(threshold),
                "total_delivered_features": delivered,
                "total_cost": float(last["cumulative_cost"]),
                "average_cost_per_feature": (
                    float(last["cumulative_cost"]) / delivered if delivered else np.nan
                ),
                "final_technical_debt": float(last["technical_debt"]),
                "total_defects": int(last["defect_count"]),
                "refactoring_count": int(result["refactoring_performed"].sum()),
            }
        )

    return pd.DataFrame(records)


def _plot_metric(
    results: pd.DataFrame,
    metric: str,
    ylabel: str,
    title: str,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for strategy in STRATEGY_ORDER:
        data = results[results["strategy"] == strategy]
        ax.plot(
            data["iteration"],
            data[metric],
            label=strategy,
            color=STRATEGY_COLORS[strategy],
            linewidth=2.2,
        )
    ax.set(title=title, xlabel="Iterácia / sprint", ylabel=ylabel)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def create_strategy_plots(results: pd.DataFrame, output_dir: Path) -> None:
    """Uloží päť samostatných grafov požadovaných zadaním."""

    plots = [
        ("technical_debt", "Jednotky dlhu", "Vývoj technického dlhu", "technical_debt.png"),
        ("cumulative_cost", "Kumulatívne náklady", "Kumulatívne náklady projektu", "cumulative_cost.png"),
        ("delivered_features", "Počet funkcionalít", "Kumulatívne dodané funkcionality", "delivered_features.png"),
        ("change_cost", "Čas na jednu zmenu", "Cena ďalšej zmeny", "change_cost.png"),
        ("defect_count", "Kumulatívny počet chýb", "Vývoj počtu chýb", "defects.png"),
    ]
    for metric, ylabel, title, filename in plots:
        _plot_metric(results, metric, ylabel, title, output_dir / filename)


def create_sensitivity_plot(sensitivity: pd.DataFrame, output_path: Path) -> None:
    """Dve osi ukazujú cenu aj výstup pri rôznych hraniciach refactoringu."""

    fig, cost_axis = plt.subplots(figsize=(9, 5.2))
    feature_axis = cost_axis.twinx()
    x = sensitivity["repayment_threshold"]
    cost_axis.plot(x, sensitivity["total_cost"], "o-", color="#6a4c93", linewidth=2)
    feature_axis.plot(
        x,
        sensitivity["total_delivered_features"],
        "s--",
        color="#f4a261",
        linewidth=2,
    )
    cost_axis.set(
        title="Citlivosť MANAGED DEBT na hranicu splácania",
        xlabel="Debt repayment threshold",
        ylabel="Celkové náklady",
    )
    feature_axis.set_ylabel("Dodané funkcionality")
    cost_axis.grid(alpha=0.25)
    lines = cost_axis.lines + feature_axis.lines
    cost_axis.legend(lines, ["Celkové náklady", "Dodané funkcionality"], loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def build_interpretation(summary: pd.DataFrame, sensitivity: pd.DataFrame) -> str:
    """Vygeneruje krátky text založený na skutočnom výstupe behu."""

    managed = summary.loc["LEAN / MANAGED DEBT"]
    uncontrolled = summary.loc["UNCONTROLLED DEBT"]
    clean = summary.loc["CLEAN FROM START"]
    best_threshold_row = sensitivity.loc[sensitivity["total_cost"].idxmin()]
    return (
        f"V prvých šiestich iteráciách dodal managed prístup "
        f"{int(managed['features_after_6_iterations'])} funkcionalít, kým clean prístup "
        f"{int(clean['features_after_6_iterations'])}, pretože časť jeho kapacity spotrebovala "
        "počiatočná architektúra. "
        f"Na konci experimentu dosiahol managed prístup {int(managed['total_delivered_features'])} "
        f"dodaných funkcionalít pri dlhu {managed['final_technical_debt']:.1f}. "
        f"Nekontrolovaný dlh síce začínal s najnižšou cenou zmeny, ale skončil s dlhom "
        f"{uncontrolled['final_technical_debt']:.1f}, {int(uncontrolled['total_defects'])} chybami "
        f"a backlogom {int(uncontrolled['final_backlog'])} funkcionalít. "
        f"Clean stratégia ukončila simuláciu s dlhom {clean['final_technical_debt']:.1f} a "
        f"{int(clean['total_defects'])} chybami, zaplatila však vstupnú architektonickú investíciu. "
        "Výsledok tak neoznačuje jednu stratégiu za univerzálne najlepšiu: managed dlh vymieňa "
        "časť čistoty za skoršiu spätnú väzbu, zatiaľ čo clean riešenie kupuje stabilitu vopred. "
        f"V sensitivity analysis mala v tomto konkrétnom behu najnižšie celkové náklady hranica "
        f"{best_threshold_row['repayment_threshold']:.0f}, čo ilustruje, že príliš častý aj príliš "
        "neskorý refactoring môže byť nevýhodný. "
        "Simulácia je zámerne zjednodušená ilustrácia mechanizmu a nie empirický dôkaz "
        "univerzálneho pravidla pre reálne projekty."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=24, help="Počet iterácií (predvolene 24).")
    parser.add_argument("--seed", type=int, default=42, help="Seed generátora náhodných čísel.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=8.0,
        help="Základná hranica splácania pre MANAGED DEBT.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Adresár pre CSV, grafy a interpretáciu.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 20 <= args.iterations <= 30:
        raise ValueError("Pre tento experiment zvoľte 20 až 30 iterácií.")
    if args.threshold <= 0:
        raise ValueError("Hranica splácania musí byť kladná.")

    config = SimulationConfig(iterations=args.iterations, seed=args.seed)
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    results_df = run_experiment(config, repayment_threshold=args.threshold)
    summary_df = make_summary(results_df)
    sensitivity_df = run_sensitivity_analysis(
        config,
        thresholds=(4, 6, 8, 10, 12, 15, 18, 24, 32),
    )

    results_df.to_csv(output_dir / "iteration_results.csv", index=False)
    summary_df.to_csv(output_dir / "final_summary.csv")
    sensitivity_df.to_csv(output_dir / "sensitivity_analysis.csv", index=False)
    create_strategy_plots(results_df, output_dir)
    create_sensitivity_plot(sensitivity_df, output_dir / "sensitivity_analysis.png")

    interpretation = build_interpretation(summary_df, sensitivity_df)
    (output_dir / "interpretation_sk.txt").write_text(interpretation + "\n", encoding="utf-8")

    display_columns = [
        "iteration",
        "strategy",
        "technical_debt",
        "development_time",
        "cumulative_cost",
        "delivered_features",
        "defect_count",
        "change_cost",
        "maintainability_score",
        "refactoring_performed",
    ]
    with pd.option_context("display.max_rows", None, "display.width", 180):
        print("\nVÝSLEDKY PO ITERÁCIÁCH (výber stĺpcov)\n")
        print(results_df[display_columns].round(2).to_string(index=False))
        print("\nKONEČNÉ POROVNANIE\n")
        print(summary_df.round(2).to_string())
        print("\nSENSITIVITY ANALYSIS\n")
        print(sensitivity_df.round(2).to_string(index=False))
    print("\nINTERPRETÁCIA\n")
    print(interpretation)
    print(f"\nVýstupy boli uložené do: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
