from django.test import TestCase
from django.urls import reverse

from .models import Objective, Scenario, SimulationStep, SituationReport, Unit
from .services import DEFAULT_OBJECTIVES, DEFAULT_UNITS, REPORT_TITLE, bootstrap_active_scenario


class DashboardTests(TestCase):
    def test_bootstrap_creates_full_scenario(self):
        scenario = bootstrap_active_scenario()

        self.assertIsNotNone(scenario.id)
        self.assertTrue(Scenario.objects.exists())

        self.assertGreater(scenario.units.count(), 0)
        self.assertGreater(scenario.events.count(), 0)


class SimulationApiTests(TestCase):
    def test_simulate_step_creates_snapshot_and_map_movement(self):
        scenario = bootstrap_active_scenario()
        initial_positions = {unit.id: (unit.pos_x, unit.pos_y) for unit in scenario.units.all()}

        response = self.client.post(
            reverse("simulator:simulate_step", args=[scenario.id]),
            data={"tempo": 4, "intel_confidence": 70},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertTrue(payload["ok"])
        self.assertIn("event", payload)
        self.assertIn("decision", payload)
        self.assertIn("state", payload)

        state = payload["state"]
        self.assertIn("units", state)
        self.assertIn("kpis", state)
        self.assertIn("risk", state)
        self.assertIn("actions", state)

        scenario.refresh_from_db()
        self.assertEqual(scenario.step_number, 1)
        self.assertEqual(SimulationStep.objects.filter(scenario=scenario).count(), 1)

        moved = False
        for unit in scenario.units.all():
            start = initial_positions[unit.id]
            if start != (unit.pos_x, unit.pos_y):
                moved = True
        self.assertTrue(moved)

    def test_state_endpoint_returns_wrapped_state(self):
        scenario = bootstrap_active_scenario()
        response = self.client.get(reverse("simulator:scenario_state", args=[scenario.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state"]["scenario_id"], scenario.id)
        self.assertIn("error_catalog", payload["state"])
        self.assertIn("supply_sources", payload["state"])
        self.assertIn("index_guides", payload["state"])
        self.assertIn("final_summary", payload["state"])

    def test_resupply_success_updates_units(self):
        scenario = bootstrap_active_scenario()
        weakest_before = min(unit.supply for unit in scenario.units.all())

        response = self.client.post(
            reverse("simulator:resupply", args=[scenario.id]),
            data={"source": "depot"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertIn("Припасы", payload["event"]["title"])

        scenario.refresh_from_db()
        self.assertLess(scenario.reserve_supplies, 120)
        weakest_after = min(unit.supply for unit in scenario.units.all())
        self.assertGreaterEqual(weakest_after, weakest_before)

    def test_generate_report_requires_enough_data(self):
        scenario = bootstrap_active_scenario()
        response = self.client.post(reverse("simulator:generate_report", args=[scenario.id]))

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "REPORT_NOT_ENOUGH_DATA")

    def test_generate_report_completes_report_objective(self):
        scenario = bootstrap_active_scenario()

        for _ in range(2):
            self.client.post(
                reverse("simulator:simulate_step", args=[scenario.id]),
                data={"tempo": 3, "intel_confidence": 72},
                content_type="application/json",
            )

        response = self.client.post(reverse("simulator:generate_report", args=[scenario.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["state"]["report_ready"])

        report_objective = Objective.objects.get(scenario=scenario, sort_order=3)
        self.assertTrue(report_objective.is_completed)
        self.assertEqual(report_objective.progress, 100)

    def test_schedule_objective_completes_when_core_goals_done_in_time(self):
        scenario = bootstrap_active_scenario()
        scenario.step_number = 8
        scenario.save(update_fields=["step_number"])

        SituationReport.objects.create(
            scenario=scenario,
            title=REPORT_TITLE,
            text="Тестовый отчет",
            state="Готово",
            sort_order=99,
        )
        Objective.objects.filter(scenario=scenario, sort_order__in=[0, 1, 3]).update(progress=100, is_completed=True)
        Objective.objects.filter(scenario=scenario, sort_order=2).update(progress=0, is_completed=False)

        response = self.client.post(
            reverse("simulator:resupply", args=[scenario.id]),
            data={"source": "depot"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        schedule_objective = Objective.objects.get(scenario=scenario, sort_order=2)
        self.assertTrue(schedule_objective.is_completed)
        self.assertEqual(schedule_objective.progress, 100)
        self.assertEqual(payload["state"]["status"], Scenario.STATUS_WON)

    def test_resupply_fails_if_reserve_empty(self):
        scenario = bootstrap_active_scenario()
        scenario.reserve_supplies = 0
        scenario.save(update_fields=["reserve_supplies"])

        response = self.client.post(
            reverse("simulator:resupply", args=[scenario.id]),
            data={"source": "depot"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "NO_RESERVE_SUPPLIES")

    def test_complete_operation_requires_objectives(self):
        scenario = bootstrap_active_scenario()
        response = self.client.post(reverse("simulator:complete", args=[scenario.id]))

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "OBJECTIVES_NOT_COMPLETE")

    def test_complete_operation_sets_win_status(self):
        scenario = bootstrap_active_scenario()
        Objective.objects.filter(scenario=scenario).update(progress=100, is_completed=True)

        response = self.client.post(reverse("simulator:complete", args=[scenario.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])

        scenario.refresh_from_db()
        self.assertEqual(scenario.status, Scenario.STATUS_WON)
        self.assertTrue(scenario.end_reason)

    def test_restart_operation_resets_scenario(self):
        scenario = bootstrap_active_scenario()
        Objective.objects.filter(scenario=scenario).update(progress=100, is_completed=True)
        Unit.objects.filter(scenario=scenario).update(readiness=5, supply=3, morale=4, pos_x=95, pos_y=95)
        scenario.status = Scenario.STATUS_LOST
        scenario.end_reason = "test"
        scenario.step_number = 5
        scenario.reserve_supplies = 0
        scenario.weather_index = 88
        scenario.pressure_index = 91
        scenario.save(
            update_fields=[
                "status",
                "end_reason",
                "step_number",
                "reserve_supplies",
                "weather_index",
                "pressure_index",
            ]
        )

        response = self.client.post(reverse("simulator:restart", args=[scenario.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])

        scenario.refresh_from_db()
        self.assertEqual(scenario.status, Scenario.STATUS_ACTIVE)
        self.assertEqual(scenario.step_number, 0)
        self.assertEqual(scenario.step_limit, 18)
        self.assertEqual(scenario.reserve_supplies, 120)
        self.assertEqual(scenario.weather_index, 35)
        self.assertEqual(scenario.pressure_index, 45)

        objectives = list(Objective.objects.filter(scenario=scenario).order_by("sort_order"))
        self.assertEqual([item.text for item in objectives], DEFAULT_OBJECTIVES)
        self.assertTrue(all(item.progress == 0 for item in objectives))
        self.assertTrue(all(item.is_completed is False for item in objectives))

        units = list(Unit.objects.filter(scenario=scenario).order_by("sort_order"))
        self.assertEqual(len(units), len(DEFAULT_UNITS))
        for unit, baseline in zip(units, DEFAULT_UNITS):
            self.assertEqual(unit.name, baseline["name"])
            self.assertEqual(unit.role, baseline["role"])
            self.assertEqual(unit.readiness, baseline["readiness"])
            self.assertEqual(unit.supply, baseline["supply"])
            self.assertEqual(unit.morale, baseline["morale"])
            self.assertEqual(unit.pos_x, baseline["pos_x"])
            self.assertEqual(unit.pos_y, baseline["pos_y"])

    def test_lose_condition_blocks_actions_until_restart(self):
        scenario = bootstrap_active_scenario()
        scenario.step_limit = 1
        scenario.save(update_fields=["step_limit"])

        step_response = self.client.post(
            reverse("simulator:simulate_step", args=[scenario.id]),
            data={"tempo": 5, "intel_confidence": 35},
            content_type="application/json",
        )
        self.assertEqual(step_response.status_code, 200)
        scenario.refresh_from_db()
        self.assertEqual(scenario.status, Scenario.STATUS_LOST)

        blocked_response = self.client.post(
            reverse("simulator:resupply", args=[scenario.id]),
            data={"source": "depot"},
            content_type="application/json",
        )
        self.assertEqual(blocked_response.status_code, 409)
        blocked_payload = blocked_response.json()
        self.assertEqual(blocked_payload["error"]["code"], "SCENARIO_CLOSED")

        restart_response = self.client.post(reverse("simulator:restart", args=[scenario.id]))
        self.assertEqual(restart_response.status_code, 200)
        scenario.refresh_from_db()
        self.assertEqual(scenario.status, Scenario.STATUS_ACTIVE)
