"""
test_engine.py - Autonomy Engine v1.2
23 test cases covering all decision paths, charter modes, warn-gate, and integration.
"""

import sys
import unittest
from pathlib import Path

# Direct path import - autonomy-engine dir contains all modules
AE_DIR = Path(__file__).parent
sys.path.insert(0, str(AE_DIR))

import charter
import decision
import recurrence
import integrate


# Decision Router Tests

class TestDecisionRouter(unittest.TestCase):

    def test_execute_tag_acts(self):
        task = {"title": "Send weekly digest", "tags": ["EXECUTE"]}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "ACT")

    def test_execute_with_skip_in_title_still_acts(self):
        # Regression: warn-gate must NOT block EXECUTE tasks
        task = {"title": "Skip the report this week", "tags": ["EXECUTE"]}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "ACT")

    def test_execute_with_refuse_in_title_still_acts(self):
        task = {"title": "Refuse outdated entries cleanup", "tags": ["EXECUTE"]}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "ACT")

    def test_verify_tag_defers(self):
        task = {"title": "Check the deploy", "tags": ["VERIFY"]}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "DEFER")

    def test_new_tag_defers(self):
        task = {"title": "New feature idea", "tags": ["NEW"]}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "DEFER")

    def test_project_tag_defers(self):
        task = {"title": "Implement transactions", "tags": ["PROJECT"]}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "DEFER")

    def test_plan_tag_proposes(self):
        task = {"title": "Plan Q3 strategy", "tags": ["PLAN"]}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "PROPOSE")

    def test_pending_tag_acts(self):
        task = {"title": "Send follow-up email", "tags": ["PENDING"]}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "ACT")

    def test_financial_keyword_defers(self):
        task = {"title": "Review invoice from AWS", "tags": []}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "DEFER")

    def test_irreversible_keyword_defers(self):
        task = {"title": "Delete old log files", "tags": []}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "DEFER")

    def test_wrong_assignee_defers(self):
        task = {"title": "Book a meeting", "tags": [], "people": {"assignedTo": "Justs Ceplis"}}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "DEFER")

    def test_no_tags_defaults_act(self):
        task = {"title": "Write a blog post draft", "tags": []}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "ACT")

    def test_financial_overrides_execute(self):
        # Safety: financial check runs before EXECUTE trust
        task = {"title": "Process contract payment", "tags": ["EXECUTE"]}
        r = decision.route(task)
        self.assertEqual(r["verdict"], "DEFER")


# Charter Verifier Tests

class TestCharterVerifier(unittest.TestCase):

    def test_normal_task_aligned(self):
        task = {"title": "Send weekly digest", "tags": []}
        r = charter.check(task, mode="solo")
        self.assertTrue(r["aligned"])
        self.assertEqual(r["blockers"], [])

    def test_vericity_in_solo_mode_allowed(self):
        task = {"title": "Analyse Vericity listings", "tags": []}
        r = charter.check(task, mode="solo")
        self.assertTrue(r["aligned"])
        self.assertNotIn("vericity_solo", r["blockers"])

    def test_vericity_in_joint_mode_blocked(self):
        task = {"title": "Push Vericity update", "tags": []}
        r = charter.check(task, mode="joint")
        self.assertFalse(r["aligned"])
        self.assertIn("vericity_solo", r["blockers"])

    def test_warn_gate_skip_is_warning_not_block(self):
        task = {"title": "Skip the onboarding", "tags": []}
        r = charter.check(task, mode="solo")
        self.assertTrue(r["aligned"])
        self.assertEqual(r["blockers"], [])
        self.assertIn("automate_never_refuse", r["warnings"])

    def test_warn_gate_ignore_is_warning_not_block(self):
        task = {"title": "Ignore the daily report", "tags": []}
        r = charter.check(task, mode="solo")
        self.assertTrue(r["aligned"])
        self.assertIn("automate_never_refuse", r["warnings"])

    def test_info_tenets_always_present(self):
        task = {"title": "Routine sync task", "tags": []}
        r = charter.check(task, mode="solo")
        # Tenets 1, 2, 4, 5 are info-level (always)
        self.assertEqual(len(r["info"]), 4)


# Integration Tests

class TestIntegration(unittest.TestCase):

    def test_execute_skip_routes_act_not_defer(self):
        # Regression: warn-gate must not block EXECUTE tasks in full pipeline
        tasks = [{"title": "Skip old task", "tags": ["EXECUTE"]}]
        result = integrate.triage_tasks(tasks, mode="solo", record_patterns=False)
        self.assertEqual(len(result["ACT"]), 1)
        self.assertEqual(len(result["DEFER"]), 0)

    def test_verify_prefiltered_to_defer(self):
        tasks = [{"title": "Verify the build", "tags": ["VERIFY"]}]
        result = integrate.triage_tasks(tasks, mode="solo", record_patterns=False)
        self.assertEqual(len(result["DEFER"]), 1)

    def test_charter_block_defers(self):
        tasks = [{"title": "Push Vericity hotfix", "tags": []}]
        result = integrate.triage_tasks(tasks, mode="joint", record_patterns=False)
        self.assertEqual(len(result["DEFER"]), 1)
        self.assertIn("Charter block", result["DEFER"][0]["reason"])

    def test_mixed_tasks(self):
        tasks = [
            {"title": "Send weekly digest", "tags": ["EXECUTE"]},
            {"title": "Check the new signup flow", "tags": ["VERIFY"]},
            {"title": "Plan Q3 roadmap", "tags": ["PLAN"]},
            {"title": "Delete old backups", "tags": []},
        ]
        result = integrate.triage_tasks(tasks, mode="solo", record_patterns=False)
        self.assertEqual(len(result["ACT"]), 1)
        self.assertEqual(len(result["PROPOSE"]), 1)
        self.assertEqual(len(result["DEFER"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
