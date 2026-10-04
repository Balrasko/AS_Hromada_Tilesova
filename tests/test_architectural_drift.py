import unittest

from architectural_drift_experiment import (
    SimulationConfig,
    make_summary,
    run_experiment,
    run_frequency_sensitivity,
)


class ArchitecturalDriftExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = SimulationConfig(iterations=25, seed=73)

    def test_experiment_is_reproducible(self) -> None:
        first = run_experiment(self.config)
        second = run_experiment(self.config)
        self.assertTrue(first.equals(second))

    def test_every_strategy_has_every_iteration(self) -> None:
        results = run_experiment(self.config)
        self.assertEqual(len(results), 3 * self.config.iterations)
        self.assertEqual(results["strategy"].nunique(), 3)
        self.assertTrue((results["active_architecture_violations"] >= 0).all())
        self.assertTrue((results["architecture_debt"] >= 0).all())

    def test_governance_limits_drift_in_typical_run(self) -> None:
        summary = make_summary(run_experiment(self.config))
        unmanaged = summary.loc["NO ARCHITECTURE GOVERNANCE"]
        periodic = summary.loc["PERIODIC REVIEW & REFACTORING"]
        guardrails = summary.loc["CONTINUOUS ARCHITECTURE GUARDRAILS"]

        self.assertGreater(
            unmanaged["active_architecture_violations"],
            periodic["active_architecture_violations"],
        )
        self.assertGreater(
            periodic["final_architecture_debt"],
            guardrails["final_architecture_debt"],
        )
        self.assertGreater(unmanaged["total_defects"], guardrails["total_defects"])

    def test_frequency_sensitivity_contains_all_intervals(self) -> None:
        intervals = (2, 4, 6, 8)
        sensitivity = run_frequency_sensitivity(self.config, intervals)
        self.assertEqual(sensitivity["refactor_interval"].tolist(), list(intervals))
        self.assertTrue((sensitivity["refactoring_count"] >= 0).all())


if __name__ == "__main__":
    unittest.main()
