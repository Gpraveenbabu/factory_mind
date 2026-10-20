"""Tests for feature engineering (rolling, temporal, correlations)."""

from __future__ import annotations

import math

import pytest

from factorymind.domain.models import MachineConfig, TelemetrySnapshot
from factorymind.features.correlations import CorrelationFeatureEngine
from factorymind.features.rolling import RollingFeatureEngine, RollingWindow
from factorymind.features.temporal import TemporalFeatureEngine, TrendState
from factorymind.simulation.machine import MachineSimulator
from factorymind.simulation.sensors import ALL_SENSORS


class TestRollingWindow:
    def test_empty_window_returns_nan(self):
        w = RollingWindow("temperature", window_size=5)
        assert math.isnan(w.mean())
        assert math.isnan(w.min_val())
        assert math.isnan(w.max_val())

    def test_add_values_and_compute_stats(self):
        w = RollingWindow("temperature", window_size=5)
        for v in [70, 72, 74, 76, 78]:
            w.add(float(v))
        assert w.mean() == pytest.approx(74.0)
        assert w.min_val() == 70.0
        assert w.max_val() == 78.0
        assert w.std() > 0

    def test_window_evicts_old_values(self):
        w = RollingWindow("temperature", window_size=3)
        for v in [70, 72, 74, 76, 78]:
            w.add(float(v))
        # Only last 3 values: 74, 76, 78
        assert w.mean() == pytest.approx(76.0)

    def test_nan_values_skipped(self):
        w = RollingWindow("temperature", window_size=5)
        w.add(70.0)
        w.add(float("nan"))
        w.add(72.0)
        assert len(w) == 2

    def test_lag_features(self):
        w = RollingWindow("temperature", window_size=10)
        for v in range(10):
            w.add(float(v))
        assert w.lag(0) == 9.0
        assert w.lag(1) == 8.0
        assert w.lag(9) == 0.0
        assert math.isnan(w.lag(10))

    def test_ewma(self):
        w = RollingWindow("temperature", window_size=10)
        w.add(100.0)
        assert w.ewma() == 100.0
        w.add(0.0)
        # alpha=0.3: 0.3*0 + 0.7*100 = 70
        assert w.ewma() == pytest.approx(70.0)


class TestRollingFeatureEngine:
    def test_produces_features_for_all_sensors(self, healthy_machine):
        engine = RollingFeatureEngine(list(ALL_SENSORS), window_size=5)
        for _ in range(6):
            snap = healthy_machine.step()
            features = engine.update(snap)
        # Should have features for each sensor
        for sensor in ALL_SENSORS:
            assert f"{sensor}_rolling_mean" in features
            assert f"{sensor}_rolling_std" in features
            assert f"{sensor}_ewma" in features


class TestTemporalFeatures:
    def test_trend_increasing(self):
        state = TrendState("vibration", window_size=5)
        for v in [1, 2, 3, 4, 5]:
            state.add(float(v))
        assert state.slope() > 0
        assert state.trend_direction() == "increasing"

    def test_trend_decreasing(self):
        state = TrendState("vibration", window_size=5)
        for v in [5, 4, 3, 2, 1]:
            state.add(float(v))
        assert state.slope() < 0
        assert state.trend_direction() == "decreasing"

    def test_trend_stable(self):
        state = TrendState("vibration", window_size=5)
        for v in [3, 3, 3, 3, 3]:
            state.add(float(v))
        assert state.trend_direction() == "stable"

    def test_rate_of_change(self):
        state = TrendState("vibration", window_size=5)
        for v in [10, 12, 14, 16, 18]:
            state.add(float(v))
        # (18 - 10) / 5 = 1.6
        assert state.rate_of_change() == pytest.approx(1.6)

    def test_temporal_engine_detects_bearing_trend(self, bearing_degradation_machine):
        engine = TemporalFeatureEngine(list(ALL_SENSORS), window_size=10)
        sim = bearing_degradation_machine
        # Run past onset
        for _ in range(120):
            snap = sim.step()
            features = engine.update(snap)
        # Vibration should be trending up
        assert features["vibration_trend"] == "increasing"


class TestCorrelationFeatures:
    def test_ratio_computation(self):
        engine = CorrelationFeatureEngine(window_size=5)
        from factorymind.domain.models import TelemetrySnapshot
        from datetime import datetime, timezone

        for i in range(6):
            snap = TelemetrySnapshot(
                machine_id="M-1",
                timestamp=datetime(2025, 1, 1, 0, i, tzinfo=timezone.utc),
                readings={
                    "temperature": 75.0 + i,
                    "vibration": 2.5 + i * 0.1,
                    "motor_current": 11.0 + i * 0.2,
                    "load": 55.0,
                    "coolant_flow": 10.0,
                    "coolant_temperature": 30.0,
                },
            )
            features = engine.update(snap)

        # temp_vibration ratio should exist
        assert "temp_vibration_ratio" in features
        assert not math.isnan(features["temp_vibration_ratio"])

    def test_ratio_deviation_near_zero_for_healthy(self, healthy_machine):
        engine = CorrelationFeatureEngine(window_size=10)
        for _ in range(15):
            snap = healthy_machine.step()
            features = engine.update(snap)
        # In healthy operation, ratio deviations should be small
        for key, val in features.items():
            if "ratio_deviation" in key and val == val:
                assert val < 1.0, f"{key} deviation too high: {val}"