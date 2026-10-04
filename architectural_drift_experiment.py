"""Experiment postupného vzniku architektonického driftu a erózie.

Simulácia porovnáva tri režimy údržby štvorvrstvovej architektúry. Nejde o
predikčný model, ale o reprodukovateľnú ilustráciu vhodnú do akademickej eseje.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib-cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


STRATEGY_ORDER = [
    "NO ARCHITECTURE GOVERNANCE",
    "PERIODIC REVIEW & REFACTORING",
    "CONTINUOUS ARCHITECTURE GUARDRAILS",
]
STRATEGY_COLORS = {
    "NO ARCHITECTURE GOVERNANCE": "#e76f51",
    "PERIODIC REVIEW & REFACTORING": "#2a9d8f",
    "CONTINUOUS ARCHITECTURE GUARDRAILS": "#457b9d",
}

# Zjednodušený príklad pravidiel pre vrstvy systému objednávok. Závislosť
# smie smerovať iba dovnútra; infraštruktúra implementuje porty aplikácie.
ARCHITECTURE_RULES = pd.DataFrame(
    [
        ("Presentation", "Application", True, "UI/API volá aplikačné prípady použitia"),
        ("Application", "Domain", True, "Aplikačná vrstva používa doménový model"),
        ("Infrastructure", "Application", True, "Adaptéry implementujú aplikačné porty"),
        ("Infrastructure", "Domain", True, "Adaptéry mapujú doménové objekty"),
        ("Presentation", "Infrastructure", False, "UI nesmie pristupovať priamo k DB"),
        ("Domain", "Infrastructure", False, "Doména nesmie poznať databázu ani framework"),
        ("Domain", "Presentation", False, "Doména nesmie závisieť od UI/API"),
        ("Application", "Presentation", False, "Aplikácia nesmie závisieť od UI/API"),
    ],
    columns=["source_layer", "target_layer", "allowed", "explanation"],
)


@dataclass(frozen=True)
class SimulationConfig:
    iterations: int = 25
    seed: int = 73
    sprint_capacity: float = 8.0
    min_feature_demand: int = 5
    max_feature_demand: int = 7
    architecture_pressure_per_feature: float = 0.28
    architecture_debt_interest: float = 0.02
    debt_exponent: float = 1.18
    baseline_dependencies: float = 20.0
    dependencies_per_feature: float = 1.25
    defect_fix_time: float = 0.35
    escaped_defect_penalty: float = 0.75


@dataclass(frozen=True)
class GovernanceStrategy:
    name: str
    base_change_cost: float
    governance_time_per_feature: float
    violation_prevention: float
    debt_drag: float
    initial_investments: tuple[float, ...] = ()
    refactor_interval: int | None = None
    refactor_time: float = 0.0
    refactor_fraction: float = 0.0
    min_violations_for_refactor: int = 0
    defect_seed_offset: int = 0


@dataclass(frozen=True)
class ProjectEnvironment:
    feature_demand: np.ndarray
    complexity: np.ndarray
    delivery_pressure: np.ndarray


def default_strategies() -> list[GovernanceStrategy]:
    """Tri režimy od nulovej kontroly po automatizované guardrails."""

    return [
        GovernanceStrategy(
            name="NO ARCHITECTURE GOVERNANCE",
            base_change_cost=0.76,
            governance_time_per_feature=0.0,
            violation_prevention=0.05,
            debt_drag=0.023,
            defect_seed_offset=101,
        ),
        GovernanceStrategy(
            name="PERIODIC REVIEW & REFACTORING",
            base_change_cost=0.87,
            governance_time_per_feature=0.06,
            violation_prevention=0.48,
            debt_drag=0.020,
            initial_investments=(1.0,),
            refactor_interval=6,
            refactor_time=2.4,
            refactor_fraction=0.60,
            min_violations_for_refactor=2,
            defect_seed_offset=202,
        ),
        GovernanceStrategy(
            name="CONTINUOUS ARCHITECTURE GUARDRAILS",
            base_change_cost=0.98,
            governance_time_per_feature=0.08,
            violation_prevention=0.92,
            debt_drag=0.016,
            # Zavedenie ADR šablón, dependency testov a pravidiel v CI.
            initial_investments=(4.0, 3.0, 2.0),
            refactor_interval=5,
            refactor_time=1.2,
            refactor_fraction=0.75,
            min_violations_for_refactor=2,
            defect_seed_offset=303,
        ),
    ]


def create_environment(config: SimulationConfig) -> ProjectEnvironment:
    """Rovnaké požiadavky, zložitosť a termínový tlak pre všetky stratégie."""

    rng = np.random.default_rng(config.seed)
    return ProjectEnvironment(
        feature_demand=rng.integers(
            config.min_feature_demand,
            config.max_feature_demand + 1,
            size=config.iterations,
        ),
        complexity=np.clip(rng.normal(1.0, 0.09, config.iterations), 0.80, 1.20),
        delivery_pressure=rng.uniform(0.80, 1.25, config.iterations),
    )


class ArchitectureSimulator:
    """Diskrétny model vývoja implementovanej architektúry."""

    def __init__(self, config: SimulationConfig, environment: ProjectEnvironment):
        self.config = config
        self.environment = environment

    def _change_cost(
        self,
        strategy: GovernanceStrategy,
        architecture_debt: float,
        complexity: float,
    ) -> float:
        # Governance pridáva malú okamžitú cenu, dlh zvyšuje cenu nelineárne.
        basic_cost = strategy.base_change_cost + strategy.governance_time_per_feature
        debt_multiplier = 1.0 + strategy.debt_drag * architecture_debt**self.config.debt_exponent
        return basic_cost * complexity * debt_multiplier

    def run_strategy(self, strategy: GovernanceStrategy) -> pd.DataFrame:
        rng = np.random.default_rng(self.config.seed + strategy.defect_seed_offset)
        backlog = 0
        delivered_total = 0
        active_violations = 0
        architecture_debt = 0.0
        total_defects = 0
        previous_new_defects = 0
        cumulative_cost = 0.0
        cumulative_development_time = 0.0
        records: list[dict[str, float | int | bool | str]] = []

        for index in range(self.config.iterations):
            iteration = index + 1
            new_demand = int(self.environment.feature_demand[index])
            backlog += new_demand

            investment_time = (
                strategy.initial_investments[index]
                if index < len(strategy.initial_investments)
                else 0.0
            )
            defect_rework_time = min(
                previous_new_defects * self.config.defect_fix_time,
                self.config.sprint_capacity,
            )

            refactoring_performed = False
            refactoring_time = 0.0
            removed_violations = 0
            scheduled_refactor = (
                strategy.refactor_interval is not None
                and iteration % strategy.refactor_interval == 0
            )
            if scheduled_refactor and active_violations >= strategy.min_violations_for_refactor:
                refactoring_performed = True
                refactoring_time = strategy.refactor_time
                removed_violations = max(
                    1,
                    int(np.floor(active_violations * strategy.refactor_fraction)),
                )
                active_violations -= removed_violations
                architecture_debt *= 1.0 - strategy.refactor_fraction

            change_cost = self._change_cost(
                strategy,
                architecture_debt,
                float(self.environment.complexity[index]),
            )
            feature_capacity = max(
                0.0,
                self.config.sprint_capacity
                - investment_time
                - refactoring_time
                - defect_rework_time,
            )
            deliverable = int(np.floor(feature_capacity / change_cost))
            delivered_now = min(backlog, deliverable)
            feature_development_time = delivered_now * change_cost
            backlog -= delivered_now
            delivered_total += delivered_now

            # Každá funkcionalita vytvára príležitosti porušiť smer závislostí.
            expected_attempts = (
                delivered_now
                * self.config.architecture_pressure_per_feature
                * float(self.environment.delivery_pressure[index])
            )
            attempted_violations = int(rng.poisson(expected_attempts))
            prevented_violations = int(
                rng.binomial(attempted_violations, strategy.violation_prevention)
            )
            introduced_violations = attempted_violations - prevented_violations
            active_violations += introduced_violations

            # Staré porušenia získavajú „úrok“: pribúdajú obchádzky, nepriame
            # väzby a strata znalosti pôvodného architektonického zámeru.
            architecture_debt = (
                architecture_debt + 1.5 * introduced_violations
            ) * (1.0 + self.config.architecture_debt_interest)

            dependency_count = (
                self.config.baseline_dependencies
                + delivered_total * self.config.dependencies_per_feature
            )
            drift_index = 100.0 * active_violations / dependency_count
            compliance_score = max(0.0, 100.0 - drift_index)
            maintainability_score = 100.0 * np.exp(-architecture_debt / 45.0)

            expected_defects = delivered_now * (
                0.025 + 0.009 * active_violations + 0.002 * architecture_debt
            )
            new_defects = int(rng.poisson(expected_defects))
            total_defects += new_defects
            previous_new_defects = new_defects

            development_time = (
                investment_time
                + refactoring_time
                + defect_rework_time
                + feature_development_time
            )
            iteration_cost = development_time + new_defects * self.config.escaped_defect_penalty
            cumulative_development_time += development_time
            cumulative_cost += iteration_cost

            records.append(
                {
                    "iteration": iteration,
                    "strategy": strategy.name,
                    "new_feature_demand": new_demand,
                    "backlog_features": backlog,
                    "delivered_this_iteration": delivered_now,
                    "delivered_features": delivered_total,
                    "attempted_violations": attempted_violations,
                    "prevented_violations": prevented_violations,
                    "introduced_violations": introduced_violations,
                    "removed_violations": removed_violations,
                    "active_architecture_violations": active_violations,
                    "architecture_debt": architecture_debt,
                    "drift_index": drift_index,
                    "architecture_compliance_score": compliance_score,
                    "change_cost": change_cost,
                    "maintainability_score": maintainability_score,
                    "new_defects": new_defects,
                    "defect_count": total_defects,
                    "architecture_investment_time": investment_time,
                    "refactoring_time": refactoring_time,
                    "defect_rework_time": defect_rework_time,
                    "feature_development_time": feature_development_time,
                    "development_time": development_time,
                    "cumulative_development_time": cumulative_development_time,
                    "iteration_cost": iteration_cost,
                    "cumulative_cost": cumulative_cost,
                    "refactoring_performed": refactoring_performed,
                }
            )

        return pd.DataFrame(records)


def run_experiment(config: SimulationConfig) -> pd.DataFrame:
    environment = create_environment(config)
    simulator = ArchitectureSimulator(config, environment)
    return pd.concat(
        [simulator.run_strategy(strategy) for strategy in default_strategies()],
        ignore_index=True,
    )


def make_summary(results: pd.DataFrame) -> pd.DataFrame:
    final_rows = results.sort_values("iteration").groupby("strategy", sort=False).tail(1)
    first_six = (
        results[results["iteration"] == 6]
        .set_index("strategy")["delivered_features"]
        .to_dict()
    )
    refactor_count = (
        results.groupby("strategy")["refactoring_performed"].sum().astype(int).to_dict()
    )
    prevented = results.groupby("strategy")["prevented_violations"].sum().to_dict()

    rows: list[dict[str, float | int | str]] = []
    for row in final_rows.itertuples(index=False):
        delivered = int(row.delivered_features)
        rows.append(
            {
                "strategy": row.strategy,
                "features_after_6_iterations": int(first_six[row.strategy]),
                "total_delivered_features": delivered,
                "final_backlog": int(row.backlog_features),
                "active_architecture_violations": int(row.active_architecture_violations),
                "prevented_violations": int(prevented[row.strategy]),
                "final_architecture_debt": row.architecture_debt,
                "final_drift_index": row.drift_index,
                "total_cost": row.cumulative_cost,
                "average_cost_per_feature": row.cumulative_cost / delivered if delivered else np.nan,
                "total_defects": int(row.defect_count),
                "average_change_cost": results.loc[
                    results["strategy"] == row.strategy, "change_cost"
                ].mean(),
                "final_maintainability_score": row.maintainability_score,
                "refactoring_count": int(refactor_count[row.strategy]),
            }
        )

    return pd.DataFrame(rows).set_index("strategy").reindex(STRATEGY_ORDER)


def run_frequency_sensitivity(
    config: SimulationConfig,
    intervals: Iterable[int],
) -> pd.DataFrame:
    """Porovná periodic review stratégiu pri rôznej frekvencii refactoringu."""

    environment = create_environment(config)
    simulator = ArchitectureSimulator(config, environment)
    periodic_template = default_strategies()[1]
    rows: list[dict[str, float | int]] = []
    for interval in intervals:
        strategy = replace(periodic_template, refactor_interval=int(interval))
        result = simulator.run_strategy(strategy)
        final = result.iloc[-1]
        delivered = int(final["delivered_features"])
        rows.append(
            {
                "refactor_interval": int(interval),
                "total_delivered_features": delivered,
                "total_cost": float(final["cumulative_cost"]),
                "average_cost_per_feature": float(final["cumulative_cost"]) / delivered,
                "final_architecture_debt": float(final["architecture_debt"]),
                "final_drift_index": float(final["drift_index"]),
                "total_defects": int(final["defect_count"]),
                "refactoring_count": int(result["refactoring_performed"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _plot_metric(
    results: pd.DataFrame,
    metric: str,
    ylabel: str,
    title: str,
    output_path: Path,
) -> None:
    fig, axis = plt.subplots(figsize=(9, 5.2))
    for strategy in STRATEGY_ORDER:
        subset = results[results["strategy"] == strategy]
        axis.plot(
            subset["iteration"],
            subset[metric],
            label=strategy,
            color=STRATEGY_COLORS[strategy],
            linewidth=2.2,
        )
    axis.set(title=title, xlabel="Iterácia / sprint", ylabel=ylabel)
    axis.grid(alpha=0.25)
    axis.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def create_plots(results: pd.DataFrame, output_dir: Path) -> None:
    plots = [
        (
            "active_architecture_violations",
            "Aktívne porušenia pravidiel",
            "Odklon implementácie od plánovanej architektúry",
            "architecture_violations.png",
        ),
        (
            "architecture_debt",
            "Jednotky architektonického dlhu",
            "Architektonická erózia",
            "architecture_debt.png",
        ),
        ("drift_index", "Drift index [%]", "Relatívny architektonický drift", "drift_index.png"),
        ("change_cost", "Čas na jednu zmenu", "Cena ďalšej zmeny", "change_cost.png"),
        (
            "delivered_features",
            "Kumulatívne funkcionality",
            "Dodané funkcionality",
            "delivered_features.png",
        ),
        ("defect_count", "Kumulatívny počet chýb", "Chyby počas vývoja", "defects.png"),
    ]
    for metric, ylabel, title, filename in plots:
        _plot_metric(results, metric, ylabel, title, output_dir / filename)


def create_sensitivity_plot(sensitivity: pd.DataFrame, output_path: Path) -> None:
    fig, debt_axis = plt.subplots(figsize=(9, 5.2))
    feature_axis = debt_axis.twinx()
    x = sensitivity["refactor_interval"]
    debt_axis.plot(
        x,
        sensitivity["final_architecture_debt"],
        "o-",
        color="#6a4c93",
        linewidth=2,
    )
    feature_axis.plot(
        x,
        sensitivity["total_delivered_features"],
        "s--",
        color="#f4a261",
        linewidth=2,
    )
    debt_axis.set(
        title="Citlivosť na frekvenciu refactoringu",
        xlabel="Refactoring každých N iterácií",
        ylabel="Konečný architektonický dlh",
    )
    feature_axis.set_ylabel("Dodané funkcionality")
    debt_axis.grid(alpha=0.25)
    lines = debt_axis.lines + feature_axis.lines
    debt_axis.legend(
        lines,
        ["Architektonický dlh", "Dodané funkcionality"],
        loc="best",
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def build_interpretation(summary: pd.DataFrame, sensitivity: pd.DataFrame) -> str:
    unmanaged = summary.loc["NO ARCHITECTURE GOVERNANCE"]
    periodic = summary.loc["PERIODIC REVIEW & REFACTORING"]
    guardrails = summary.loc["CONTINUOUS ARCHITECTURE GUARDRAILS"]
    best_balance = sensitivity.loc[sensitivity["average_cost_per_feature"].idxmin()]
    return (
        f"Bez architektonického riadenia tím v prvých šiestich iteráciách dodal "
        f"{int(unmanaged['features_after_6_iterations'])} funkcionalít, no na konci evidoval "
        f"{int(unmanaged['active_architecture_violations'])} aktívnych porušení pravidiel. "
        f"Jeho cena jednej funkcionality dosiahla {unmanaged['average_cost_per_feature']:.2f} "
        f"a backlog {int(unmanaged['final_backlog'])}, pretože drift postupne spomaľoval zmeny. "
        f"Periodické review a refactoring znížili konečný architektonický dlh na "
        f"{periodic['final_architecture_debt']:.1f} pri {int(periodic['total_delivered_features'])} "
        "dodaných funkcionalitách. "
        f"Kontinuálne guardrails skončili s počtom aktívnych porušení "
        f"{int(guardrails['active_architecture_violations'])}, ale v úvodných iteráciách "
        "platili za vytvorenie pravidiel a testov. "
        "Rozdiel medzi stratégiami ukazuje, že samotný pôvodný návrh architektúru neudrží; "
        "dôležitá je spätná väzba počas každej zmeny. "
        f"V sensitivity analysis mala najnižšiu priemernú cenu funkcionality politika "
        f"refactoringu každých {int(best_balance['refactor_interval'])} iterácií, pričom veľmi časté zásahy "
        "spotrebovali kapacitu a zriedkavé zásahy ponechali dlh rásť. "
        "Ide o didaktickú simuláciu zvolených predpokladov, nie o dôkaz univerzálne "
        "optimálnej frekvencie alebo konkrétneho governance procesu."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs_architectural_drift"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 20 <= args.iterations <= 30:
        raise ValueError("Pre experiment zvoľte 20 až 30 iterácií.")

    config = SimulationConfig(iterations=args.iterations, seed=args.seed)
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    results_df = run_experiment(config)
    summary_df = make_summary(results_df)
    sensitivity_df = run_frequency_sensitivity(config, intervals=(2, 3, 4, 5, 6, 8, 10, 12))

    results_df.to_csv(output_dir / "iteration_results.csv", index=False)
    summary_df.to_csv(output_dir / "final_summary.csv")
    sensitivity_df.to_csv(output_dir / "refactoring_frequency_sensitivity.csv", index=False)
    ARCHITECTURE_RULES.to_csv(output_dir / "architecture_rules.csv", index=False)
    create_plots(results_df, output_dir)
    create_sensitivity_plot(sensitivity_df, output_dir / "refactoring_frequency_sensitivity.png")

    interpretation = build_interpretation(summary_df, sensitivity_df)
    (output_dir / "interpretation_sk.txt").write_text(interpretation + "\n", encoding="utf-8")

    display_columns = [
        "iteration",
        "strategy",
        "delivered_features",
        "active_architecture_violations",
        "architecture_debt",
        "drift_index",
        "change_cost",
        "defect_count",
        "cumulative_cost",
        "refactoring_performed",
    ]
    with pd.option_context("display.max_rows", None, "display.width", 180):
        print("\nVÝSLEDKY PO ITERÁCIÁCH (výber stĺpcov)\n")
        print(results_df[display_columns].round(2).to_string(index=False))
        print("\nKONEČNÉ POROVNANIE\n")
        print(summary_df.round(2).to_string())
        print("\nCITLIVOSŤ NA FREKVENCIU REFACTORINGU\n")
        print(sensitivity_df.round(2).to_string(index=False))
    print("\nINTERPRETÁCIA\n")
    print(interpretation)
    print(f"\nVýstupy boli uložené do: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
