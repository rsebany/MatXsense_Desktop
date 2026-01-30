"""Tests for environmental data simulator."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_generation.environmental_data_simulator import EnvironmentalDataSimulator


class TestEnvironmentalDataSimulator(unittest.TestCase):
    def test_simulator_init(self):
        """Test simulator initialization."""
        start = datetime(2024, 1, 1)
        sim = EnvironmentalDataSimulator(start_date=start, num_days=7, readings_per_day=24)
        self.assertEqual(sim.start_date, start)
        self.assertEqual(sim.num_days, 7)
        self.assertEqual(sim.readings_per_day, 24)
        self.assertEqual(sim.total_readings, 7 * 24)
        self.assertEqual(sim.data, [])

    def test_generate_timestamps(self):
        """Test timestamp generation count and spacing."""
        start = datetime(2024, 1, 1)
        sim = EnvironmentalDataSimulator(start_date=start, num_days=2, readings_per_day=24)
        timestamps = sim.generate_timestamps()
        self.assertEqual(len(timestamps), 48)
        self.assertEqual(timestamps[0], start)
        expected_second = start + timedelta(hours=1)
        self.assertEqual(timestamps[1], expected_second)

    def test_generate_temperature_range(self):
        """Test temperature values are in expected range (with seed)."""
        np.random.seed(42)
        start = datetime(2024, 6, 15)
        sim = EnvironmentalDataSimulator(start_date=start, num_days=1, readings_per_day=24)
        timestamps = sim.generate_timestamps()
        temps = sim.generate_temperature(timestamps)
        self.assertEqual(len(temps), 24)
        for t in temps:
            self.assertIsInstance(t, (int, float))
            self.assertGreaterEqual(t, 10)
            self.assertLessEqual(t, 45)

    def test_generate_humidity_range(self):
        """Test humidity values are clamped 40-90%."""
        np.random.seed(42)
        start = datetime(2024, 1, 1)
        sim = EnvironmentalDataSimulator(start_date=start, num_days=1, readings_per_day=24)
        timestamps = sim.generate_timestamps()
        temps = sim.generate_temperature(timestamps)
        humidity = sim.generate_humidity(temps)
        self.assertEqual(len(humidity), 24)
        for h in humidity:
            self.assertGreaterEqual(h, 40)
            self.assertLessEqual(h, 90)

    def test_generate_ph_range(self):
        """Test pH values are in 6.5-8.5."""
        np.random.seed(42)
        sim = EnvironmentalDataSimulator(
            start_date=datetime(2024, 1, 1), num_days=1, readings_per_day=24
        )
        ph_values = sim.generate_pH()
        self.assertEqual(len(ph_values), 24)
        for p in ph_values:
            self.assertGreaterEqual(p, 6.5)
            self.assertLessEqual(p, 8.5)

    def test_generate_salinity_range(self):
        """Test salinity values are in 30-40 PSU."""
        np.random.seed(42)
        sim = EnvironmentalDataSimulator(
            start_date=datetime(2024, 1, 1), num_days=1, readings_per_day=24
        )
        salinity = sim.generate_salinity()
        self.assertEqual(len(salinity), 24)
        for s in salinity:
            self.assertGreaterEqual(s, 30)
            self.assertLessEqual(s, 40)

    def test_simulate_output_structure(self):
        """Test simulate() returns list of records with expected keys."""
        np.random.seed(42)
        sim = EnvironmentalDataSimulator(
            start_date=datetime(2024, 1, 1), num_days=1, readings_per_day=6
        )
        data = sim.simulate()
        self.assertEqual(len(data), 6)
        required_keys = {"timestamp", "temperature_celsius", "humidity_percent", "pH", "salinity_psu"}
        for record in data:
            self.assertEqual(set(record.keys()), required_keys)
            self.assertIsInstance(record["timestamp"], str)
            self.assertIsInstance(record["temperature_celsius"], (int, float))
            self.assertIsInstance(record["humidity_percent"], (int, float))
            self.assertIsInstance(record["pH"], (int, float))
            self.assertIsInstance(record["salinity_psu"], (int, float))

    def test_simulate_stores_data(self):
        """Test simulate() populates sim.data."""
        np.random.seed(42)
        sim = EnvironmentalDataSimulator(
            start_date=datetime(2024, 1, 1), num_days=1, readings_per_day=4
        )
        result = sim.simulate()
        self.assertIs(result, sim.data)
        self.assertEqual(len(sim.data), 4)


if __name__ == "__main__":
    unittest.main()
