
import unittest
import pandas as pd
from app import simulate


def sample_vehicles():
    return pd.DataFrame([
        {
            "id": 1,
            "owner": "driver",
            "vehicle": "EV-101",
            "arrival": 8,
            "departure": 17,
            "energy": 20.0,
            "max_kw": 6.6,
        },
        {
            "id": 2,
            "owner": "driver",
            "vehicle": "EV-102",
            "arrival": 8,
            "departure": 17,
            "energy": 20.0,
            "max_kw": 6.6,
        },
    ])


class TestChargeWiseScheduler(unittest.TestCase):

    def test_smart_schedule_respects_site_power_limit(self):
        power, _, _, _, _ = simulate(
            sample_vehicles(),
            site_limit=10,
            smart=True,
        )
        self.assertLessEqual(max(power), 10 + 1e-9)

    def test_energy_requirements_are_met_when_feasible(self):
        vehicles = sample_vehicles()
        _, delivered, remaining, _, _ = simulate(
            vehicles,
            site_limit=20,
            smart=True,
        )

        for vehicle_id in vehicles["id"]:
            vehicle_id = int(vehicle_id)
            self.assertAlmostEqual(
                remaining[vehicle_id], 0.0, places=6
            )
            self.assertAlmostEqual(
                delivered[vehicle_id], 20.0, places=6
            )


if __name__ == "__main__":
    unittest.main()
