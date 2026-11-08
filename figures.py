"""Všetky grafy k experimentu (esej aj prezentácia) v jednom priečinku.

Grafy sú kompaktné a bez nadpisov: v eseji ich nesie popis obrázka, na slajde
nadpis slajdu. Vďaka 300 DPI sa dajú na slajde zväčšiť bez straty kvality.

Okrem hlavného behu skript počíta:
* opakovanie experimentu cez veľa seedov (robustnosť namiesto jedného behu),
* kontrolný scenár MANAGED BEZ SPLÁCANIA (rovnaké parametre ako managed, bez refactoringu),
* neistotu požiadaviek a cenu prerobenia vopred navrhnutej architektúry,
* citlivosť hranice splácania naprieč seedmi,
* diagram jedného sprintu.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib-cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.ticker import FuncFormatter

from technical_debt_experiment import (
    ProjectSimulator,
    SimulationConfig,
    StrategyConfig,
    create_environment,
    default_strategies,
    run_experiment,
)

MANAGED = "LEAN / MANAGED DEBT"
UNCONTROLLED = "UNCONTROLLED DEBT"
CLEAN = "CLEAN FROM START"
NO_REPAYMENT = "MANAGED BEZ SPLÁCANIA"
MAIN_ORDER = [MANAGED, UNCONTROLLED, CLEAN]

# Farby sú pevne priradené stratégii a overené na farbosleposť. Žltá a tyrkysová
# majú nižší kontrast, preto majú čiary aj rôzne typy čiar a grafy legendu.
COLORS = {
    MANAGED: "#2a78d6",
    UNCONTROLLED: "#eb6834",
    CLEAN: "#1baf7a",
    NO_REPAYMENT: "#eda100",
}
LINESTYLES = {MANAGED: "-", UNCONTROLLED: "--", CLEAN: "-.", NO_REPAYMENT: ":"}
SHORT_LABELS = {
    MANAGED: "Lean / riadený dlh",
    UNCONTROLLED: "Nekontrolovaný dlh",
    CLEAN: "Clean od začiatku",
    NO_REPAYMENT: "Riadený bez splácania",
}

WHITE = "#ffffff"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#8a8985"
GRID = "#e6e5e0"
DIVERGING_LOW = "#2a78d6"  # lean lacnejší
DIVERGING_MID = "#f0efec"
DIVERGING_HIGH = "#e34948"  # clean lacnejší
DPI = 300

SINGLE = (3.4, 2.6)  # polovica šírky A4 (dva grafy vedľa seba)
WIDE = (6.4, 2.8)  # celá šírka A4


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": WHITE,
            "axes.facecolor": WHITE,
            "savefig.facecolor": WHITE,
            "axes.edgecolor": INK_MUTED,
            "axes.labelcolor": INK_SECONDARY,
            "axes.labelsize": 8,
            "axes.titlesize": 8.5,
            "axes.titlecolor": INK,
            "axes.titlelocation": "left",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": INK_SECONDARY,
            "ytick.color": INK_SECONDARY,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.5,
            "legend.frameon": False,
            "font.size": 8,
            "lines.linewidth": 1.6,
        }
    )


def _comma(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


COMMA_AXIS = FuncFormatter(lambda v, _: f"{round(v, 2):g}".replace(".", ","))


def _save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, dpi=DPI, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Výpočty
# ---------------------------------------------------------------------------


def no_repayment_strategy() -> StrategyConfig:
    return replace(default_strategies()[0], name=NO_REPAYMENT, repayment_threshold=None)


def run_final_metrics(
    seeds: range,
    strategies: list[StrategyConfig],
    **config_overrides: float,
) -> pd.DataFrame:
    """Konečné metriky každej stratégie pre každý seed."""

    records = []
    for seed in seeds:
        config = SimulationConfig(seed=seed, **config_overrides)
        simulator = ProjectSimulator(config, create_environment(config))
        for strategy in strategies:
            result = simulator.run_strategy(strategy)
            last = result.iloc[-1]
            new_features = int(last["new_features_delivered"])
            records.append(
                {
                    "seed": seed,
                    "strategy": strategy.name,
                    "new_features_delivered": new_features,
                    "rework_features_delivered": int(last["rework_features_delivered"]),
                    "final_backlog": int(last["backlog_features"]),
                    "final_technical_debt": float(last["technical_debt"]),
                    "total_defects": int(last["defect_count"]),
                    "total_cost": float(last["cumulative_cost"]),
                    "cost_per_new_feature": (
                        float(last["cumulative_cost"]) / new_features if new_features else np.nan
                    ),
                    "redesign_time": float(last["cumulative_redesign_time"]),
                    "refactoring_count": int(result["refactoring_performed"].sum()),
                    **config_overrides,
                }
            )
    return pd.DataFrame(records)


def summarize(frame: pd.DataFrame, by: list[str], metric: str) -> pd.DataFrame:
    grouped = frame.groupby(by, sort=False)[metric]
    return pd.DataFrame(
        {"mean": grouped.mean(), "p10": grouped.quantile(0.10), "p90": grouped.quantile(0.90)}
    ).reset_index()


# ---------------------------------------------------------------------------
# Grafy
# ---------------------------------------------------------------------------


def plot_baseline_metric(
    results: pd.DataFrame,
    metric: str,
    ylabel: str,
    path: Path,
    demand: np.ndarray | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=SINGLE)
    if demand is not None:
        ax.plot(np.arange(1, len(demand) + 1), np.cumsum(demand), color=INK_MUTED,
                linewidth=1.0, linestyle=(0, (1.5, 2)), label="Kumulatívny dopyt")
    for name in MAIN_ORDER:
        data = results[results["strategy"] == name]
        ax.plot(data["iteration"], data[metric], color=COLORS[name],
                linestyle=LINESTYLES[name], label=SHORT_LABELS[name])
    ax.set(xlabel="Sprint", ylabel=ylabel)
    ax.set_xlim(1, results["iteration"].max())
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(COMMA_AXIS)
    ax.legend(loc="upper left")
    _save(fig, path)


def plot_ablation(frame: pd.DataFrame, path: Path) -> None:
    order = [MANAGED, CLEAN, NO_REPAYMENT, UNCONTROLLED]
    stats = summarize(frame, ["strategy"], "cost_per_new_feature").set_index("strategy").loc[order]
    fig, ax = plt.subplots(figsize=SINGLE)
    y = np.arange(len(order))[::-1]
    for yi, name in zip(y, order):
        row = stats.loc[name]
        ax.plot([row["p10"], row["p90"]], [yi, yi], color=COLORS[name], linewidth=4,
                alpha=0.35, solid_capstyle="round")
        ax.plot([row["mean"]], [yi], "o", color=COLORS[name], markersize=6.5,
                markeredgecolor=WHITE, markeredgewidth=1.2)
        ax.annotate(_comma(row["mean"]), xy=(row["p90"], yi), xytext=(5, 0),
                    textcoords="offset points", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(y, [SHORT_LABELS[n].replace(" bez ", "\nbez ") for n in order], color=INK)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(1.2, stats["p90"].max() + 0.35)
    ax.set_ylim(-0.6, len(order) - 0.4)
    ax.set_xlabel("Náklady na funkcionalitu")
    ax.xaxis.set_major_formatter(COMMA_AXIS)
    _save(fig, path)


def plot_volatility(frame: pd.DataFrame, factors: list[float], path: Path) -> None:
    fig, axes = plt.subplots(1, len(factors), figsize=WIDE, sharey=True)
    for ax, factor in zip(axes, factors):
        subset = frame[frame["redesign_cost_factor"] == factor]
        stats = summarize(subset, ["strategy", "requirement_volatility"], "cost_per_new_feature")
        for name in MAIN_ORDER:
            s = stats[stats["strategy"] == name].sort_values("requirement_volatility")
            x = s["requirement_volatility"] * 100
            ax.fill_between(x, s["p10"], s["p90"], color=COLORS[name], alpha=0.12, linewidth=0)
            ax.plot(x, s["mean"], color=COLORS[name], linestyle=LINESTYLES[name],
                    label=SHORT_LABELS[name])
        ax.set_title(f"Prerobenie architektúry stojí {factor:g}× jej návrh")
        ax.set_xlabel("Pravdepodobnosť zmeny požiadaviek (%)")
        ax.set_xlim(0, 50)
    axes[0].set_ylabel("Náklady na novú funkcionalitu")
    axes[0].yaxis.set_major_formatter(COMMA_AXIS)
    axes[0].legend(loc="upper left")
    fig.tight_layout(w_pad=1.5)
    _save(fig, path)


def plot_break_even(matrix: pd.DataFrame, path: Path) -> None:
    """Heatmapa rozdielu nákladov lean − clean (záporné = lean lacnejší)."""

    fig, ax = plt.subplots(figsize=(5.2, 2.9))
    cmap = LinearSegmentedColormap.from_list("div", [DIVERGING_LOW, DIVERGING_MID, DIVERGING_HIGH])
    limit = float(np.nanmax(np.abs(matrix.values)))
    image = ax.imshow(matrix.values, cmap=cmap, norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit),
                      aspect="auto", origin="lower")
    ax.set_xticks(range(matrix.shape[1]), [f"{v * 100:.0f} %" for v in matrix.columns])
    ax.set_yticks(range(matrix.shape[0]), [f"{v:g}×".replace(".", ",") for v in matrix.index])
    ax.set_xticks(np.arange(-0.5, matrix.shape[1]), minor=True)
    ax.set_yticks(np.arange(-0.5, matrix.shape[0]), minor=True)
    ax.grid(which="minor", color=WHITE, linewidth=2)
    ax.grid(which="major", visible=False)
    ax.tick_params(which="both", length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix.values[i, j]
            ax.text(j, i, _comma(value) if value < 0 else "+" + _comma(value),
                    ha="center", va="center", fontsize=7.5,
                    color=INK if abs(value) < limit * 0.6 else WHITE)
    ax.set(xlabel="Pravdepodobnosť zmeny požiadaviek v sprinte",
           ylabel="Cena prerobenia\narchitektúry")
    bar = fig.colorbar(image, ax=ax, fraction=0.05, pad=0.02)
    bar.outline.set_visible(False)
    bar.ax.tick_params(length=0, labelsize=7)
    bar.set_ticks([-limit, 0, limit], labels=["lean\nlacnejší", "0", "clean\nlacnejší"])
    _save(fig, path)


def plot_threshold(frame: pd.DataFrame, path: Path) -> None:
    cost = summarize(frame, ["repayment_threshold"], "cost_per_new_feature")
    refactor = frame.groupby("repayment_threshold")["refactoring_count"].mean().reset_index()
    color = COLORS[MANAGED]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=WIDE, gridspec_kw={"width_ratios": [1.5, 1]})
    ax.fill_between(cost["repayment_threshold"], cost["p10"], cost["p90"], color=color,
                    alpha=0.15, linewidth=0)
    ax.plot(cost["repayment_threshold"], cost["mean"], "o-", color=color, markersize=4.5,
            markeredgecolor=WHITE, markeredgewidth=1)
    ax.set_title("Náklady na funkcionalitu")
    ax.set_xlabel("Hranica dlhu pre refactoring")
    ax.yaxis.set_major_formatter(COMMA_AXIS)
    ax2.bar(refactor["repayment_threshold"].astype(int).astype(str), refactor["refactoring_count"],
            color=color, width=0.7)
    ax2.set_title("Počet refactoringov za 24 sprintov")
    ax2.set_xlabel("Hranica dlhu")
    ax2.grid(axis="x", visible=False)
    fig.tight_layout(w_pad=2)
    _save(fig, path)


# ---------------------------------------------------------------------------
# Diagram sprintu
# ---------------------------------------------------------------------------

DIAGRAM_SIZE = (12.8, 7.2)  # 16:9, priamo na slajd
BOX_FILL = "#f0efec"
BOX_EDGE = "#b9b8b2"
ARROW = "#52514e"


def _box(ax, x, y, w, h, title, body, edge=BOX_EDGE, lw=1.4, dashed=False, fill=BOX_FILL):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.18",
            facecolor=fill, edgecolor=edge, linewidth=lw,
            linestyle=(0, (4, 3)) if dashed else "-",
        )
    )
    if title:
        ax.text(x + 0.2, y + h - 0.25, title, ha="left", va="top", fontsize=14.5,
                fontweight="bold", color=INK)
    ax.text(x + 0.2, y + h - (0.8 if title else 0.25), body, ha="left", va="top",
            fontsize=11.5, color=INK_SECONDARY, linespacing=1.45)


def _arrow(ax, start, end, rad=0.0, dashed=False, color=ARROW, lw=1.8):
    ax.add_patch(
        FancyArrowPatch(
            start, end,
            arrowstyle="-|>", mutation_scale=16,
            connectionstyle=f"arc3,rad={rad}",
            color=color, linewidth=lw,
            linestyle=(0, (4, 3)) if dashed else "-",
            shrinkA=2, shrinkB=2,
        )
    )


def _chip(ax, x, y, color, text):
    ax.add_patch(FancyBboxPatch((x, y - 0.13), 0.26, 0.26, boxstyle="round,pad=0,rounding_size=0.05",
                                facecolor=color, edgecolor="none"))
    ax.text(x + 0.42, y, text, ha="left", va="center", fontsize=12.5, color=INK)


def plot_sprint_diagram(path: Path) -> None:
    """Diagram jedného sprintu; kroky zodpovedajú poradiu výpočtu v run_strategy."""

    fig = plt.figure(figsize=DIAGRAM_SIZE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(0.4, 8.45, "Čo sa deje v jednom sprinte simulácie", fontsize=22,
            fontweight="bold", color=INK, va="center")

    # Hlavný tok: päť krokov zľava doprava.
    y, h, w, gap, x0 = 3.75, 2.25, 2.85, 0.25, 0.35
    xs = [x0 + i * (w + gap) for i in range(5)]
    _box(ax, xs[0], y, w, h, "1  Backlog",
         "nové požiadavky (4–6)\n+ prerábky po zmene\n   požiadaviek")
    _box(ax, xs[1], y, w, h, "2  Réžia sprintu",
         "z kapacity 8 jednotiek:\n• architektúra vopred\n• oprava chýb\n• prerobenie architektúry")
    _box(ax, xs[2], y, w, h, "3  Refactoring?",
         "ak dlh ≥ hranica (8):\n−3,2 jednotky kapacity\n−65 % dlhu",
         edge=COLORS[MANAGED], lw=2.4)
    _box(ax, xs[3], y, w, h, "4  Vývoj",
         "zvyšná kapacita\n÷ cena zmeny\n= dodané funkcionality")
    _box(ax, xs[4], y, w, h, "5  Dôsledky",
         "nový dlh\n(úmerný dodanej práci)\nnové chyby\n(rastú s dlhom)")
    for i in range(4):
        _arrow(ax, (xs[i] + w, y + h / 2), (xs[i + 1], y + h / 2))

    # Neistota požiadaviek (voliteľné rozšírenie modelu).
    ux, uy, uw, uh = xs[0], 6.55, xs[1] + w - xs[0], 1.15
    _box(ax, ux, uy, uw, uh, "",
         "Zmena požiadaviek (s pravdepodobnosťou p):\nčasť práce sa prerába, časť architektúry neplatí",
         dashed=True, fill=WHITE)
    _arrow(ax, (xs[0] + w * 0.5, uy), (xs[0] + w * 0.5, y + h), dashed=True)
    _arrow(ax, (xs[1] + w * 0.5, uy), (xs[1] + w * 0.5, y + h), dashed=True)

    # Vzorec ceny zmeny.
    fx, fw = xs[3], xs[4] + w - xs[3]
    _box(ax, fx, 6.55, fw, 1.15, "",
         "cena zmeny = $c_0$ · zložitosť · (1 + $k$ · dlh$^{1,25}$)\n"
         "→ čím väčší dlh, tým drahšia každá zmena",
         fill=WHITE)
    _arrow(ax, (xs[3] + w * 0.5, 6.55), (xs[3] + w * 0.5, y + h))

    # Spätné väzby do ďalšieho sprintu: pravouhlé cesty v rôznych výškach,
    # bližší cieľ = vyššia úroveň a ľavejší začiatok, takže sa nekrížia.
    loops = [
        (xs[4] + w * 0.15, xs[3] + w * 0.30, 2.95, "dlh zdražuje\nďalšie zmeny"),
        (xs[4] + w * 0.45, xs[2] + w * 0.50, 2.1, "dlh rozhoduje o refactoringu"),
        (xs[4] + w * 0.75, xs[1] + w * 0.50, 1.4, "chyby sa opravujú v ďalšom sprinte"),
    ]
    for sx, tx, level, label in loops:
        ax.plot([sx, sx, tx, tx], [y, level, level, level + 0.05], color=ARROW, linewidth=1.8,
                solid_joinstyle="round", solid_capstyle="round")
        _arrow(ax, (tx, level), (tx, y))
        ax.text((sx + tx) / 2, level + 0.08, label, ha="center", va="bottom", fontsize=12,
                color=INK, linespacing=1.2)

    # Čím sa stratégie líšia.
    ax.text(0.4, 0.45, "Stratégie:", fontsize=12.5, fontweight="bold", color=INK, va="center")
    _chip(ax, 1.75, 0.45, COLORS[MANAGED], "Lean: krok 3 pri dlhu ≥ 8")
    _chip(ax, 5.95, 0.45, COLORS[CLEAN], "Clean: architektúra v kroku 2 (sprinty 1–4)")
    _chip(ax, 11.45, 0.45, COLORS[UNCONTROLLED], "Nekontrolovaný: krok 3 nikdy")

    fig.savefig(path, dpi=DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=200, help="Počet seedov pre opakované behy.")
    parser.add_argument("--output-dir", type=Path, default=Path("figures"))
    args = parser.parse_args()
    out: Path = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    seeds = range(args.seeds)
    _style()

    # 1–3: hlavný beh (seed 42, bez neistoty) – zodpovedá tabuľke v eseji.
    config = SimulationConfig(seed=42)
    baseline = run_experiment(config)
    plot_baseline_metric(baseline, "technical_debt", "Technický dlh (jednotky)",
                         out / "01_technicky_dlh.png")
    plot_baseline_metric(baseline, "change_cost", "Čas na jednu zmenu", out / "02_cena_zmeny.png")
    plot_baseline_metric(baseline, "delivered_features", "Dodané funkcionality",
                         out / "03_dodane_funkcionality.png",
                         demand=create_environment(config).feature_demand)

    # 4: kontrolný scenár – rovnaké parametre, iba bez splácania.
    ablation = run_final_metrics(seeds, default_strategies() + [no_repayment_strategy()])
    plot_ablation(ablation, out / "04_ablacia_splacania.png")

    # 5: neistota požiadaviek pre dve ceny prerobenia architektúry.
    volatility = pd.concat(
        [
            run_final_metrics(seeds, default_strategies(), requirement_volatility=v,
                              redesign_cost_factor=f)
            for f in (1.0, 2.0)
            for v in [round(v, 2) for v in np.arange(0.0, 0.51, 0.05)]
        ],
        ignore_index=True,
    )
    plot_volatility(volatility, [1.0, 2.0], out / "05_neistota_poziadaviek.png")

    # 6: mapa – kedy sa lean oplatí viac než clean.
    pair = [default_strategies()[0], default_strategies()[2]]
    cells = {}
    for f in (0.0, 1.0, 1.5, 2.0, 3.0, 4.0):
        for v in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
            frame = run_final_metrics(seeds, pair, requirement_volatility=v, redesign_cost_factor=f)
            wide = frame.pivot(index="seed", columns="strategy", values="cost_per_new_feature")
            cells[(f, v)] = float((wide[MANAGED] - wide[CLEAN]).mean())
    matrix = pd.Series(cells).unstack()
    plot_break_even(matrix, out / "06_kedy_sa_oplati_lean.png")

    # 7: citlivosť hranice splácania naprieč seedmi.
    managed = default_strategies()[0]
    frames = []
    for t in (4, 6, 8, 10, 12, 15, 18, 24, 32):
        frame = run_final_metrics(seeds, [replace(managed, repayment_threshold=float(t))])
        frame["repayment_threshold"] = float(t)
        frames.append(frame)
    threshold = pd.concat(frames, ignore_index=True)
    plot_threshold(threshold, out / "07_hranica_splacania.png")

    # 8: diagram jedného sprintu.
    plot_sprint_diagram(out / "08_sprint_diagram.png")

    print("ABLÁCIA (priemer cez seedy)")
    print(ablation.groupby("strategy")[["new_features_delivered", "cost_per_new_feature",
                                        "total_defects"]].mean().round(2).to_string())
    print("\nLEAN − CLEAN (riadky: cena prerobenia, stĺpce: volatilita)")
    print(matrix.round(3).to_string())
    print(f"\nGrafy uložené do: {out.resolve()}")


if __name__ == "__main__":
    main()
