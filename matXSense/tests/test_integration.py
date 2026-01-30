"""
Integration tests: API + auth flow end-to-end.
Uses FastAPI TestClient; no real HTTP server required.
"""
import sys
import unittest
from pathlib import Path

# Project root on path so "src.backend.main" can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from src.backend.main import app

client = TestClient(app)

# Demo credentials (from auth)
DEMO_USER = "admin"
DEMO_PASSWORD = "demo123"


def _get_token():
    """Login and return Bearer token for API calls."""
    r = client.post(
        "/auth/login",
        data={"username": DEMO_USER, "password": DEMO_PASSWORD},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    return data["access_token"]


def _auth_headers():
    return {"Authorization": f"Bearer {_get_token()}"}


class TestAuthIntegration(unittest.TestCase):
    """Auth: login and protected access."""

    def test_login_success(self):
        r = client.post(
            "/auth/login",
            data={"username": DEMO_USER, "password": DEMO_PASSWORD},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("access_token", data)
        self.assertEqual(data.get("token_type"), "bearer")
        self.assertEqual(data.get("username"), DEMO_USER)

    def test_login_wrong_password(self):
        r = client.post(
            "/auth/login",
            data={"username": DEMO_USER, "password": "wrong"},
        )
        self.assertEqual(r.status_code, 401)

    def test_login_demo_user(self):
        r = client.post(
            "/auth/login",
            data={"username": "demo", "password": DEMO_PASSWORD},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("access_token", r.json())

    def test_api_without_token_returns_401(self):
        r = client.get("/api/sensors")
        self.assertEqual(r.status_code, 401)

    def test_api_with_token_succeeds(self):
        r = client.get("/api/sensors", headers=_auth_headers())
        self.assertEqual(r.status_code, 200)


class TestSensorsIntegration(unittest.TestCase):
    """GET /api/sensors: live sensor simulation."""

    def test_sensors_response_shape(self):
        r = client.get("/api/sensors", headers=_auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("temperature_celsius", data)
        self.assertIn("humidity_percent", data)
        self.assertIn("ph", data)
        self.assertIn("salinity_psu", data)
        self.assertIn("status_temp", data)
        self.assertIn("updated_at", data)

    def test_sensors_with_material_and_environment(self):
        r = client.get(
            "/api/sensors",
            params={"material": "steel", "environment": "coastal"},
            headers=_auth_headers(),
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data["temperature_celsius"], (int, float))
        self.assertIsInstance(data["humidity_percent"], (int, float))


class TestHealthRulIntegration(unittest.TestCase):
    """GET /api/health-rul: health score, RUL (days), risk %."""

    def test_health_rul_response_shape(self):
        r = client.get("/api/health-rul", headers=_auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("health_score", data)
        self.assertIn("rul_days", data)
        self.assertIn("risk_percent", data)
        self.assertIn("source", data)

    def test_health_rul_sensor_driven_when_params_provided(self):
        r = client.get(
            "/api/health-rul",
            params={
                "temperature_celsius": 22,
                "humidity_percent": 60,
                "ph": 7.2,
                "salinity_psu": 34,
            },
            headers=_auth_headers(),
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data.get("source"), "sensor_driven")
        self.assertIsInstance(data["health_score"], (int, float))
        self.assertIsInstance(data["rul_days"], int)
        self.assertIsInstance(data["risk_percent"], (int, float))


class TestPredictIntegration(unittest.TestCase):
    """POST /api/predict: custom material + environment + sensor prediction."""

    def test_predict_response_shape(self):
        r = client.post(
            "/api/predict",
            json={
                "material": "steel",
                "environment": "coastal",
                "temperature_celsius": 24,
                "humidity_percent": 65,
                "ph": 7.0,
                "salinity_psu": 35,
            },
            headers=_auth_headers(),
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("health_score", data)
        self.assertIn("rul_days", data)
        self.assertIn("risk_percent", data)
        self.assertIn("message", data)

    def test_predict_different_material(self):
        r = client.post(
            "/api/predict",
            json={
                "material": "concrete",
                "environment": "urban",
                "temperature_celsius": 20,
                "humidity_percent": 55,
                "ph": 7.5,
                "salinity_psu": 30,
            },
            headers=_auth_headers(),
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertGreaterEqual(data["health_score"], 0)
        self.assertLessEqual(data["health_score"], 100)
        self.assertGreaterEqual(data["rul_days"], 0)


class TestMaterialsIntegration(unittest.TestCase):
    """GET /api/materials: material and environment options."""

    def test_materials_response(self):
        r = client.get("/api/materials", headers=_auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("materials", data)
        self.assertIn("environments", data)
        self.assertIsInstance(data["materials"], list)
        self.assertIsInstance(data["environments"], list)


class TestAlertsIntegration(unittest.TestCase):
    """GET /api/alerts: active alerts."""

    def test_alerts_response(self):
        r = client.get("/api/alerts", headers=_auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data, list)


class TestModelMetricsIntegration(unittest.TestCase):
    """GET /api/model-metrics: 6 bridge models (3 RUL + 3 classifier)."""

    def test_model_metrics_response(self):
        r = client.get("/api/model-metrics", headers=_auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data, list)
        if data:
            first = data[0]
            self.assertIn("model", first)
            self.assertIn("task", first)


class TestPredictionsBridgeIntegration(unittest.TestCase):
    """GET /api/predictions/bridge: RUL predictions (RF, XGBoost, LightGBM)."""

    def test_predictions_bridge_response(self):
        r = client.get("/api/predictions/bridge", headers=_auth_headers())
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data, list)
        if data:
            first = data[0]
            self.assertIn("pred_lgb", first)
            self.assertIn("pred_rf", first)


class TestDegradationTimelineIntegration(unittest.TestCase):
    """GET /api/degradation-timeline: historical + predicted degradation."""

    def test_degradation_timeline_response(self):
        r = client.get(
            "/api/degradation-timeline",
            params={"material": "steel", "environment": "coastal"},
            headers=_auth_headers(),
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("historical", data)
        self.assertIn("prediction", data)


class TestFrontendDelivery(unittest.TestCase):
    """Frontend: index and static assets served correctly."""

    def test_index_returns_html(self):
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        html = r.text
        self.assertIn("MatXSense", html)
        self.assertIn("view-login", html)
        self.assertIn("view-dashboard", html)
        self.assertIn("login-form", html)
        self.assertIn("/static/style.css", html)

    def test_index_contains_dashboard_elements(self):
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        html = r.text
        self.assertIn("Live Sensor Grid", html)
        self.assertIn("Material Health Score", html)
        self.assertIn("temp-value", html)
        self.assertIn("health-value", html)
        self.assertIn("gauge-fill", html)

    def test_static_css_served(self):
        r = client.get("/static/style.css")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.text), 0)

    def test_static_scripts_served(self):
        r = client.get("/static/scripts.js")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.text), 0)
        self.assertIn("API_BASE", r.text)
        self.assertIn("/auth/login", r.text)
        self.assertIn("apiGet", r.text)


class TestFrontendApiFlow(unittest.TestCase):
    """Frontend integration: same API sequence the dashboard uses after login."""

    def test_dashboard_flow_sensors_health_alerts(self):
        """Login -> sensors -> health-rul -> alerts (dashboard tick)."""
        r_login = client.post(
            "/auth/login",
            data={"username": DEMO_USER, "password": DEMO_PASSWORD},
        )
        self.assertEqual(r_login.status_code, 200)
        token = r_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r_sensors = client.get("/api/sensors", headers=headers)
        self.assertEqual(r_sensors.status_code, 200)
        sensors = r_sensors.json()
        self.assertIn("temperature_celsius", sensors)
        self.assertIn("humidity_percent", sensors)
        self.assertIn("ph", sensors)
        self.assertIn("salinity_psu", sensors)
        self.assertIn("updated_at", sensors)

        r_health = client.get("/api/health-rul", headers=headers)
        self.assertEqual(r_health.status_code, 200)
        health = r_health.json()
        self.assertIn("health_score", health)
        self.assertIn("rul_days", health)
        self.assertIn("risk_percent", health)
        self.assertIn("source", health)

        r_alerts = client.get("/api/alerts", headers=headers)
        self.assertEqual(r_alerts.status_code, 200)
        self.assertIsInstance(r_alerts.json(), list)

    def test_dashboard_flow_materials_metrics_timeline(self):
        """Login -> materials -> model-metrics -> degradation-timeline (dashboard init)."""
        r_login = client.post(
            "/auth/login",
            data={"username": "demo", "password": DEMO_PASSWORD},
        )
        self.assertEqual(r_login.status_code, 200)
        token = r_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r_materials = client.get("/api/materials", headers=headers)
        self.assertEqual(r_materials.status_code, 200)
        mat = r_materials.json()
        self.assertIn("materials", mat)
        self.assertIn("environments", mat)
        self.assertIsInstance(mat["materials"], list)
        self.assertIsInstance(mat["environments"], list)

        r_metrics = client.get("/api/model-metrics", headers=headers)
        self.assertEqual(r_metrics.status_code, 200)
        self.assertIsInstance(r_metrics.json(), list)

        r_timeline = client.get(
            "/api/degradation-timeline",
            params={"material": "steel", "environment": "coastal"},
            headers=headers,
        )
        self.assertEqual(r_timeline.status_code, 200)
        tl = r_timeline.json()
        self.assertIn("historical", tl)
        self.assertIn("prediction", tl)

    def test_login_then_sensor_driven_health_rul(self):
        """Frontend passes sensor params to health-rul for sensor_driven source."""
        r_login = client.post(
            "/auth/login",
            data={"username": DEMO_USER, "password": DEMO_PASSWORD},
        )
        self.assertEqual(r_login.status_code, 200)
        token = r_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r_sensors = client.get("/api/sensors", headers=headers)
        self.assertEqual(r_sensors.status_code, 200)
        s = r_sensors.json()

        r_health = client.get(
            "/api/health-rul",
            params={
                "temperature_celsius": s["temperature_celsius"],
                "humidity_percent": s["humidity_percent"],
                "ph": s["ph"],
                "salinity_psu": s["salinity_psu"],
            },
            headers=headers,
        )
        self.assertEqual(r_health.status_code, 200)
        health = r_health.json()
        self.assertEqual(health.get("source"), "sensor_driven")
        self.assertIsInstance(health["health_score"], (int, float))
        self.assertIsInstance(health["rul_days"], int)
        self.assertIsInstance(health["risk_percent"], (int, float))


class TestRootAndDocs(unittest.TestCase):
    """Root and docs (no auth)."""

    def test_root_returns_ok(self):
        r = client.get("/")
        self.assertIn(r.status_code, (200, 304))

    def test_docs_available(self):
        r = client.get("/docs")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
