import unittest

from technical_debt_experiment import (
    SimulationConfig,
    make_summary,
    run_experiment,
    run_sensitivity_analysis,
)


class ExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = SimulationConfig(iterations=24, seed=42)

    def test_experiment_is_reproducible(self) -> None:
        first = run_experiment(self.config)
        second = run_experiment(self.config)
        self.assertTrue(first.equals(second))

    def test_result_has_every_strategy_and_iteration(self) -> None:
        results = run_experiment(self.config)
        self.assertEqual(len(results), 3 * self.config.iterations)
        self.assertEqual(results["strategy"].nunique(), 3)
        self.assertTrue((results["technical_debt"] >= 0).all())
        self.assertTrue((results["delivered_features"] >= 0).all())

    def test_typical_run_exhibits_intended_trade_off(self) -> None:
        summary = make_summary(run_experiment(self.config))
        managed = summary.loc["LEAN / MANAGED DEBT"]
        uncontrolled = summary.loc["UNCONTROLLED DEBT"]
        clean = summary.loc["CLEAN FROM START"]

        self.assertGreater(
            managed["features_after_6_iterations"],
            clean["features_after_6_iterations"],
        )
        self.assertGreater(
            uncontrolled["final_technical_debt"],
            managed["final_technical_debt"],
        )
        self.assertGreater(uncontrolled["total_defects"], clean["total_defects"])

    def test_sensitivity_analysis_covers_all_thresholds(self) -> None:
        thresholds = (4, 8, 12, 20)
        sensitivity = run_sensitivity_analysis(self.config, thresholds)
        self.assertEqual(sensitivity["repayment_threshold"].tolist(), list(thresholds))
        self.assertTrue((sensitivity["refactoring_count"] >= 0).all())


if __name__ == "__main__":
    unittest.main()
