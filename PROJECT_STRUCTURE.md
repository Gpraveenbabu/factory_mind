# FactoryMind — Complete Project Structure

## Overview

FactoryMind is a production-grade industrial AI platform that monitors industrial machines, detects degradation, performs root-cause analysis, enforces safety policies, and executes actions through a controlled tool broker with full audit trails.

The project contains 48 files with 5,354 lines of Python code. All 86 tests pass.

---

## Top-Level Files

### pyproject.toml
**Purpose:** Package configuration and dependency management.
**Contains:**
- Project name (factorymind), version (0.1.0), description, Python requirement (>=3.11)
- Core dependencies: numpy, pandas, scipy, scikit-learn, pydantic, pyyaml
- Optional dependency groups: dev (pytest, ruff, mypy), ml (torch, transformers, mlflow), api (fastapi, uvicorn, sqlalchemy), rag (faiss, sentence-transformers)
- Tool configuration: pytest settings, ruff linting rules, mypy strict type checking
- setuptools package discovery

### Makefile.py
**Purpose:** Build automation commands.
**Contains:** Make targets for install, test, test-cov, lint, format, typecheck, run, train, evaluate, docker-up, demo, clean. Note: saved as Makefile.py by the system, rename to Makefile on your local machine.

### SETUP_GUIDE.md
**Purpose:** Step-by-step guide for setting up and running FactoryMind on a local device.
**Contains:** What was built (10-step explanation), how to run it (prerequisites, virtual environment, install, test, lint, demo), project structure diagram, key design principles, troubleshooting.

### configs/default.yaml
**Purpose:** Central configuration file for the entire platform.
**Contains:**
- Simulation settings: num_machines (100), duration_steps (1000), sampling_interval (60s), seed (42), noise_std (0.5), sensor quality fault probabilities
- Sensor nominal ranges: temperature (65-85 C), vibration (1-4 mm/s), pressure (4.5-6 bar), motor_current (8-14 A), rpm (1450-1550), load (40-70%), coolant_temperature (25-35 C), coolant_flow (8-12 L/min), acoustic_level (65-80 dB)
- Detection thresholds: warn and critical levels for each sensor (e.g., temperature warn=90, critical=100; vibration warn=5.5, critical=8.0)
- Degradation thresholds: early (0.2), developing (0.5), severe (0.75), critical (0.95)
- Policy settings: approval timeout (300s), max concurrent actions (5), auto-shutdown disabled
- Audit settings: SHA-256 hash, file-based chain storage

---

## factorymind/ (Main Python Package)

### factorymind/__init__.py
**Purpose:** Package initialization file. Currently empty — will contain version info and public API exports in future phases.

---

### factorymind/domain/ (Domain Layer)

The domain layer defines the core vocabulary of the entire system. Every other layer depends on these types.

#### domain/__init__.py
Empty package init file.

#### domain/enums.py (140 lines)
**Purpose:** Defines all enumerations used throughout the platform.
**Contains:**
- MachineState: RUNNING, DEGRADING, WARNING, CRITICAL, SHUTDOWN, MAINTENANCE
- HealthState: HEALTHY, EARLY_DEGRADATION, DEVELOPING_FAULT, SEVERE_DEGRADATION, CRITICAL_FAILURE
- FailureMode: NONE, BEARING_DEGRADATION, BEARING_FAILURE, THERMAL_OVERLOAD, COOLING_FAILURE, MECHANICAL_IMBALANCE, MOTOR_OVERLOAD, SENSOR_FAULT
- RiskLevel: LOW, MODERATE, HIGH, SEVERE, CRITICAL
- SensorName: temperature, vibration, pressure, motor_current, rpm, load, coolant_temperature, coolant_flow, acoustic_level
- AnomalyType: THRESHOLD_BREACH, TREND_ANOMALY, CORRELATION_ANOMALY, CONTRADICTION
- AuditEventType: TELEMETRY_RECEIVED, ANOMALY_DETECTED, RCA_PERFORMED, POLICY_DECISION, APPROVAL_REQUESTED, APPROVAL_GRANTED, APPROVAL_DENIED, ACTION_EXECUTED, ACTION_DENIED, CHAIN_VERIFIED, CHAIN_TAMPERED
- ApprovalStatus: PENDING, APPROVED, DENIED, EXPIRED
- ToolName: GET_MACHINE_STATUS, GET_SENSOR_HISTORY, SCHEDULE_INSPECTION, REDUCE_MACHINE_LOAD, SHUTDOWN_MACHINE, REQUEST_HUMAN_APPROVAL
- PolicyDecision: ALLOW, DENY, REQUIRE_APPROVAL
- IncidentStatus: OPEN, INVESTIGATING, MITIGATING, RESOLVED, CLOSED
- ALL_SENSORS: tuple of all 9 sensor name strings

#### domain/models.py (199 lines)
**Purpose:** Defines all data structures (frozen dataclasses) that flow through the system.
**Contains:**
- utc_now(): helper that returns current UTC timestamp
- SensorReading: one sensor value with timestamp and quality flag
- TelemetrySnapshot: all 9 sensor readings at one moment in time, plus machine_id, timestamp, and quality map
- MachineConfig: machine identity (machine_id, model, nominal_rpm, nominal_load, installed_date)
- MachineRuntimeState: live state of a machine (current_step, degradation_score, failure_probability, health, active_failure, failure_progress, machine_state, last_updated)
- Anomaly: detected anomaly (machine_id, timestamp, sensor_name, anomaly_type, severity, value, threshold, message, detector_name)
- FeatureVector: computed features for one snapshot (rolling stats, trends, correlations)
- EvidenceItem: one piece of evidence for RCA (source, description, value, expected, weight)
- RootCauseResult: RCA output (machine_id, timestamp, root_cause, confidence, evidence, health_state, degradation_score)
- PolicyDecisionResult: policy evaluation output (decision, tool_name, machine_id, reason, conditions)
- ApprovalRequest: human approval request (request_id, tool_name, machine_id, actor, timestamp, status, decided_by, decided_at)
- ToolExecutionResult: tool execution output (success, tool_name, machine_id, output, error, approved_by)
- AuditEvent: one event in the audit chain (event_id, timestamp, machine_id, actor, event_type, payload, previous_hash, event_hash)
- Incident: an incident record (incident_id, machine_id, opened_at, status, anomalies, root_cause, actions_taken, resolution)

---

### factorymind/simulation/ (Simulation Layer)

The simulation layer creates a digital twin of an industrial machine. It generates realistic sensor data without real hardware.

#### simulation/__init__.py
Empty package init file.

#### simulation/sensors.py (194 lines)
**Purpose:** Defines sensor specifications and generates correlated sensor readings.
**Contains:**
- NoiseModel: protocol for noise injection strategies
- GaussianNoise: Gaussian noise implementation
- SensorSpec: dataclass capturing each sensor's nominal range, noise model, and failure interaction factors
- DEFAULT_SENSOR_SPECS: dictionary of specs for all 9 sensors
- SensorQualityConfig: configures sensor data quality faults (drift_rate, dropout_prob, stuck_prob, outlier_prob, outlier_factor)
- SensorState: tracks each sensor's running state including drift_bias and stuck flag
- SensorGenerator: main class that produces correlated readings step-by-step. Physics-based correlations: temperature affects vibration, vibration affects motor_current, load drives motor_current, motor_current drives temperature, coolant_flow affects coolant_temperature
- get_sensor_specs(): returns default sensor specifications
- ALL_SENSORS: re-exported from domain.enums for convenience

#### simulation/failures.py (225 lines)
**Purpose:** Defines how each failure mode degrades sensor readings over time.
**Contains:**
- Growth functions: _linear (constant rate), _exponential (accelerating, for bearing wear), _sigmoid (slow then sudden, for thermal runaway), _step (instantaneous, for sudden failures)
- FailureProfile: dataclass defining a failure's affected_sensors, deviation_fn, degradation_fn, description
- _bearing_degradation_deviation: vibration rises exponentially first (scale=20, k=1.5), then temperature, then motor_current, then acoustic_level, then rpm drops
- _bearing_failure_deviation: sudden vibration spike + temperature spike using step functions
- _thermal_overload_deviation: temperature rises sigmoidally, coolant_temperature follows, coolant_flow drops
- _mechanical_imbalance_deviation: vibration increases exponentially, pressure fluctuates
- _motor_overload_deviation: motor_current spikes exponentially first, then temperature, load increases, rpm drops
- _cooling_failure_deviation: coolant_flow drops exponentially, coolant_temperature rises, temperature follows
- _sensor_fault_deviation: returns empty (sensor faults are injected at the sensor layer, not as machine deviations)
- _default_degradation: maps progress [0,1] to degradation_score [0,1]
- _sensor_fault_degradation: always returns 0 (sensor faults do not degrade the machine)
- FAILURE_PROFILES: registry mapping each FailureMode to its FailureProfile
- get_failure_profile(): retrieves a profile by mode

#### simulation/machine.py (182 lines)
**Purpose:** The MachineSimulator combines sensor generation with failure injection to produce a complete digital twin.
**Contains:**
- _health_from_degradation(): maps degradation score to HealthState (0-0.2=healthy, 0.2-0.5=early, 0.5-0.75=developing, 0.75-0.95=severe, 0.95+=critical)
- _machine_state_from_health(): maps HealthState to MachineState
- MachineSimulator: main simulator class with:
  - Config fields: config, seed, noise_std, quality, sampling_interval_s
  - inject_failure(): schedules a failure at a specific step with a ramp period
  - step(): advances one time step, computes failure progress, applies deviations to sensors, returns TelemetrySnapshot
  - run(): runs multiple steps and returns all snapshots
  - reset(): resets to initial state
  - inject_sensor_fault(): injects a stuck-value fault on a specific sensor (for testing sensor fault detection)
  - Properties: runtime (read-only), machine_id

#### simulation/scenarios.py (259 lines)
**Purpose:** Predefined test scenarios with expected outcomes.
**Contains:**
- Scenario: frozen dataclass with machine_config, failure_mode, onset_step, ramp_steps, description, and expected outcomes (expected_anomalies, expected_root_cause, expected_health)
- ScenarioResult: result of running a scenario
- SCENARIOS: list of 11 predefined scenarios:
  1. healthy_machine: no failure, stays healthy
  2. gradual_bearing_degradation: bearing wear over 150 steps
  3. sudden_bearing_failure: rapid bearing seizure
  4. thermal_overload: sigmoidal temperature rise
  5. cooling_failure: coolant flow drops
  6. mechanical_imbalance: vibration increases
  7. motor_overload: current spikes
  8. sensor_dropout: sensor drops readings
  9. sensor_drift: sensor gradually drifts
  10. sensor_stuck: sensor gets stuck at one value
  11. multi_machine_demo: multiple machines for integration testing
- get_scenario(): retrieve a scenario by name
- get_demo_scenario(): returns the main demo scenario

---

### factorymind/ingestion/ (Ingestion Layer)

The ingestion layer receives telemetry, validates it, and buffers it for downstream processing.

#### ingestion/__init__.py
Empty package init file.

#### ingestion/validation.py (117 lines)
**Purpose:** Validates incoming telemetry snapshots before they enter the pipeline.
**Contains:**
- TelemetryValidator: validates snapshots with checks for:
  - Schema completeness: all 9 sensors must be present
  - Range validation: values must be within plausible physical ranges
  - NaN fraction: too many NaNs indicates sensor failure
  - Plausibility: detects contradictory readings (e.g., high RPM but zero current)
- ValidationResult: dataclass with is_valid and errors list
- ValidationError: exception raised when validation fails

#### ingestion/pipeline.py (153 lines)
**Purpose:** The ingestion pipeline that receives, validates, and buffers telemetry.
**Contains:**
- TelemetryBuffer: a deque-based rolling buffer that keeps the last N snapshots per machine
- IngestionStats: tracks total ingested, rejected, and per-machine counts
- IngestionPipeline: main class that:
  - ingest(): validates a snapshot, adds to buffer, emits events via callbacks
  - get_recent(): returns the last N snapshots for a machine
  - latest(): returns the most recent snapshot for a machine
  - machine_ids: property listing all known machine IDs
  - Designed for Kafka replacement in later phases (callback-based event emission)

---

### factorymind/features/ (Feature Engineering Layer)

Three feature engines transform raw sensor readings into signals that the detector and RCA engine use.

#### features/__init__.py
Empty package init file.

#### features/rolling.py (126 lines)
**Purpose:** Computes rolling statistical features over a sliding window.
**Contains:**
- RollingWindow: deque-based window that computes mean, std, min, max, EWMA (exponentially weighted moving average), and lag features
- RollingFeatureEngine: manages per-sensor rolling windows, produces features like rolling_mean_temperature, rolling_std_vibration, rolling_ewma_motor_current, lag_1_pressure, lag_5_rpm

#### features/temporal.py (125 lines)
**Purpose:** Detects how fast sensor values are changing (trend detection).
**Contains:**
- TrendState: per-sensor trend computation using least-squares linear regression:
  - add(): adds a value to the window
  - slope(): computes least-squares slope (rate of change per step)
  - rate_of_change(): simple (current - oldest) / window_size
  - trend_direction(): returns 'increasing', 'decreasing', or 'stable' based on relative slope threshold (0.005)
  - is_trending(): returns True if relative slope exceeds 0.02
- TemporalFeatureEngine: manages TrendState for all sensors, produces features like vibration_slope, vibration_trend, temperature_rate_of_change

#### features/correlations.py (129 lines)
**Purpose:** Tracks pairs of sensors that normally move together. Detects when one sensor deviates but its partner does not (key for sensor fault detection).
**Contains:**
- CorrelationState: tracks ratio between two sensors, rolling ratio mean, and ratio deviation
- CORRELATION_PAIRS: 4 pairs of normally-correlated sensors:
  - temp_vibration (temperature and vibration)
  - vibration_current (vibration and motor_current)
  - coolant_flow_temp (coolant_flow and coolant_temperature)
  - load_current (load and motor_current)
- CorrelationFeatureEngine: updates correlation states and produces features like temp_vibration_ratio, temp_vibration_ratio_deviation

---

### factorymind/detection/ (Detection Layer)

#### detection/__init__.py
Empty package init file.

#### detection/rules.py (173 lines)
**Purpose:** Rule-based anomaly detector using fixed thresholds.
**Contains:**
- ThresholdConfig: dataclass with warn and critical thresholds for every sensor (temperature_warn=90, temperature_critical=100, vibration_warn=5.5, vibration_critical=8.0, etc.)
- LOW_IS_BAD_SENSORS: set of sensors where low values are the anomaly (pressure, coolant_flow)
- RuleDetector: main detector class that:
  - Maintains internal RollingFeatureEngine and TemporalFeatureEngine per machine
  - detect(): checks each sensor against thresholds, optionally requires trend confirmation
  - Produces Anomaly objects with severity (0.5 for warn, 0.9 for critical) and anomaly type (THRESHOLD_BREACH or TREND_ANOMALY)
  - Can optionally require trend confirmation (a single spike is not enough; the sensor must also be trending)

---

### factorymind/rca/ (Root Cause Analysis Layer)

Deterministic root cause analysis — no LLM in the reasoning loop. Uses fixed confidence weights.

#### rca/__init__.py
Empty package init file.

#### rca/signatures.py (138 lines)
**Purpose:** Defines the knowledge base of failure signatures that the RCA engine matches against.
**Contains:**
- FailureSignature: frozen dataclass with primary_sensors, secondary_sensors, expected_trends, correlated_pairs, description
- FAILURE_SIGNATURES: registry with signatures for all 7 failure modes:
  - BEARING_DEGRADATION: primary=vibration, secondary=temperature/motor_current/acoustic_level, trends=vibration+temperature+current increasing
  - BEARING_FAILURE: primary=vibration+temperature, secondary=motor_current/acoustic_level/rpm
  - THERMAL_OVERLOAD: primary=temperature+coolant_temperature, secondary=motor_current/acoustic_level, trends include coolant_flow decreasing
  - MECHANICAL_IMBALANCE: primary=vibration, secondary=pressure/motor_current
  - MOTOR_OVERLOAD: primary=motor_current, secondary=temperature/load/rpm, trends include rpm decreasing
  - COOLING_FAILURE: primary=coolant_flow+coolant_temperature, secondary=temperature
  - SENSOR_FAULT: special, detected by correlation anomaly (no primary sensors)
- get_signature(): retrieves a signature by mode
- all_signatures(): returns all signatures except NONE and SENSOR_FAULT

#### rca/evidence.py (158 lines)
**Purpose:** Collects all available evidence for the RCA engine.
**Contains:**
- EvidenceBundle: dataclass holding anomalies, trends, slopes, correlation_deviations, anomalous_sensors, contradiction_pairs, and evidence_items
- EvidenceCollector: maintains TemporalFeatureEngine and CorrelationFeatureEngine per machine:
  - collect(): gathers threshold evidence, trend evidence, correlation evidence, and contradiction detection
  - Contradiction detection: flags when one sensor is anomalous but its correlated partner is normal and not trending (e.g., vibration anomalous but motor_current stable = possible sensor fault)
  - Produces EvidenceItems with weights (threshold=severity, trend=0.6, correlation=0.7, contradiction=0.8)

#### rca/engine.py (202 lines)
**Purpose:** The deterministic RCA engine that matches evidence against failure signatures.
**Contains:**
- RCAEngine: main class that:
  - analyze(): takes a snapshot, anomalies, and degradation_score, returns RootCauseResult
  - Returns healthy (NONE, confidence=1.0) when there are no anomalies
  - Checks for sensor fault first: if anomalous sensor has no consistent trend and there are contradiction pairs, returns SENSOR_FAULT
  - Matches remaining evidence against all failure signatures
  - _match_signature(): computes confidence using fixed weights:
    - Primary sensor anomalous: +0.3 per match
    - Secondary sensor anomalous: +0.15 per match
    - Trend matches expected direction: +0.1 per match
    - Contradiction involving primary sensor: -0.2 penalty
    - Scores clamped to [0, 1]
  - Returns the highest-scoring failure mode if confidence >= 0.3, otherwise NONE
- _health_from_score(): maps degradation score to HealthState
- _make_evidence(): helper to create EvidenceItem

---

### factorymind/policy/ (Policy Layer)

Deterministic safety policy engine. The AI agent cannot bypass this.

#### policy/__init__.py
Empty package init file.

#### policy/permissions.py (101 lines)
**Purpose:** Defines permission levels for each tool.
**Contains:**
- PermissionLevel: enum (SYSTEM, OPERATOR, SUPERVISOR, DENIED)
- ToolPermission: dataclass with level, requires_approval flag, and approval_level
- TOOL_PERMISSIONS: registry mapping each tool to its permission:
  - get_machine_status: SYSTEM (always allowed, read-only)
  - get_sensor_history: SYSTEM (always allowed, read-only)
  - schedule_inspection: SYSTEM (allowed with sufficient degradation)
  - reduce_machine_load: OPERATOR (requires operator approval)
  - shutdown_machine: SUPERVISOR (requires supervisor approval)
  - request_human_approval: SYSTEM (always allowed)
- get_permission(): retrieves permission for a tool
- is_auto_approved(): checks if a tool is auto-approved
- requires_human_approval(): checks if a tool needs human approval

#### policy/rules.py (176 lines)
**Purpose:** Defines 8 policy rules evaluated in strict order.
**Contains:**
- PolicyContext: frozen dataclass with machine_id, machine_state, health_state, degradation_score, root_cause, tool_name, has_approval, approval_level
- 8 policy rule functions:
  1. rule_machine_shutdown_blocks_all: if machine is SHUTDOWN, all actions denied
  2. rule_maintenance_blocks_actions: if machine is under MAINTENANCE, all actions denied
  3. rule_readonly_tools_always_allowed: get_machine_status and get_sensor_history always allowed
  4. rule_schedule_inspection_allowed: schedule_inspection allowed if degradation >= 0.2
  5. rule_reduce_load_requires_approval: reduce_machine_load requires operator approval and degradation >= 0.5
  6. rule_shutdown_requires_supervisor: shutdown_machine requires supervisor approval and SEVERE/CRITICAL risk
  7. rule_request_approval_always_allowed: request_human_approval always allowed
  8. rule_default_deny: if no rule matched, deny by default
- POLICY_RULES: ordered list of all 8 rules (order matters — first match wins)

#### policy/engine.py (66 lines)
**Purpose:** Stateless policy evaluator.
**Contains:**
- PolicyEngine: evaluates a PolicyContext against the 8 rules in order:
  - evaluate(): returns PolicyDecisionResult (ALLOW, DENY, or REQUIRE_APPROVAL)
  - is_allowed(): convenience check for ALLOW
  - is_denied(): convenience check for DENY
  - needs_approval(): convenience check for REQUIRE_APPROVAL

---

### factorymind/tools/ (Tools Layer)

The execution layer. The ToolBroker is the ONLY path to affect machines.

#### tools/__init__.py
Empty package init file.

#### tools/schemas.py (66 lines)
**Purpose:** Defines tool definitions and the handler protocol.
**Contains:**
- ToolHandler: protocol defining the handler function signature (machine_id, params) -> ToolExecutionResult
- ToolDefinition: frozen dataclass with name, description, risk_level, required_permission, input_schema (JSON schema), and handler
- validate_input(): validates input parameters against the JSON schema

#### tools/machine_tools.py (152 lines)
**Purpose:** Implements the 6 tool handler functions.
**Contains:**
- In-memory state: _machine_states, _machine_loads, _inspections_scheduled (dictionaries for Phase 1; will be replaced with database in later phases)
- 6 handler functions:
  - get_machine_status_handler: returns current machine state
  - get_sensor_history_handler: returns recent sensor readings
  - schedule_inspection_handler: schedules an inspection for a machine
  - reduce_machine_load_handler: reduces machine load by a percentage
  - shutdown_machine_handler: shuts down a machine (requires approval)
  - request_human_approval_handler: creates an approval request
- reset_machine_state(): resets in-memory state for testing
- get_machine_state(): returns machine state for testing

#### tools/registry.py (104 lines)
**Purpose:** Central registry for all available tools.
**Contains:**
- ToolRegistry: class that:
  - _register_default_tools(): registers all 6 tools with their definitions
  - register(): adds a custom tool
  - get(): retrieves a tool by name
  - exists(): checks if a tool is registered
  - list_tools(): returns all tool definitions
  - list_tool_names(): returns all tool names

#### tools/broker.py (207 lines)
**Purpose:** The ToolBroker — the ONLY execution path to machines. This is the enforcement point.
**Contains:**
å- ExecutionDenied: exception raised when execution is denied
- ToolBroker: main class that processes execution requests in 6 steps:
  1. Check tool exists in registry
  2. Validate input against schema
  3. Evaluate policy engine (ALLOW, DENY, or REQUIRE_APPROVAL)
  4. Check human approval if required
  5. Execute the tool handler
  6. Record everything to the audit chain
  - If any step fails, ExecutionDenied is raised and the denial is audited
  - Properties: registry, audit_chain
  - Key invariant: no code path exists from the agent to the machine that does not pass through the broker

---

### factorymind/audit/ (Audit Layer)

Tamper-evident audit chain. Every action is recorded and cryptographically linked.

#### audit/__init__.py
Empty package init file.

#### audit/events.py (78 lines)
**Purpose:** Audit event creation and hashing.
**Contains:**
- AuditEventFactory: creates AuditEvent objects with unique UUID4 IDs and UTC timestamps
- compute_event_hash(): computes SHA-256 hash of an event. The hash includes all fields (event_id, timestamp, machine_id, actor, event_type, payload) plus the previous_hash. Including previous_hash creates the chain — modifying any historical event breaks all subsequent hashes.

#### audit/chain.py (142 lines)
**Purpose:** The tamper-evident audit chain.
**Contains:**
- AuditChain: in-memory hash-chained ledger:
  - GENESIS_HASH: 64 zeros (the starting hash for the first event)
  - record(): creates an event, links it to the previous event's hash, computes the SHA-256 hash, and appends to the chain
  - events: property returning read-only copy of all events
  - length: number of events in the chain
  - last_hash: the hash of the most recent event
  - get_events_for_machine(): filter events by machine
  - get_events_by_type(): filter events by type
  - clear(): clears the chain for testing
  - export(): exports all events as dictionaries (for file/database persistence)

#### audit/verification.py (103 lines)
**Purpose:** Verifies the integrity of the audit chain.
**Contains:**
- VerificationResult: dataclass with valid (bool), total_events, broken_at_index, errors list
- ChainVerifier: static methods to verify chain integrity:
  - verify(): walks the entire chain and checks:
    1. Each event's previous_hash matches the previous event's hash
    2. Each event's hash matches the recomputed hash
    3. The genesis event's previous_hash is the genesis constant
    Returns VerificationResult with any errors found
  - verify_event(): verifies a single event against an expected previous hash

---

## scripts/ (Utility Scripts)

### scripts/generate_dataset.py (170 lines)
**Purpose:** CLI tool for generating synthetic industrial datasets.
**Contains:**
- generate_dataset(): creates multiple machines (default 100), injects failures into a fraction of them (default 30%), runs the simulation for a duration (default 1000 steps), and writes three CSV files:
  - telemetry.csv: all sensor readings in long format (machine_id, step, timestamp, 9 sensor values)
  - machine_labels.csv: machine metadata with injected failure mode, onset step, and ramp steps
  - anomaly_labels.csv: ground-truth anomaly labels (is_anomalous, degradation_score, health_state) for each step
- CLI arguments: --machines, --duration, --seed, --output, --failure-fraction
- Uses a random seed for reproducibility

---

## tests/ (Test Suite)

### tests/__init__.py
Empty package init file.

### tests/conftest.py (66 lines)
**Purpose:** Shared pytest fixtures for all tests.
**Contains:**
- sys.path setup to ensure factorymind is importable
- audit_chain fixture: fresh AuditChain for each test
- policy_engine fixture: fresh PolicyEngine
- tool_registry fixture: fresh ToolRegistry
- tool_broker fixture: fresh ToolBroker (combines registry, policy, audit chain)
- healthy_machine fixture: MachineSimulator with no failure (seed=42)
- bearing_degradation_machine fixture: MachineSimulator with bearing degradation injected at step 50, ramp 150 steps

### tests/unit/__init__.py
Empty package init file.

### tests/unit/test_simulator.py (138 lines, 13 tests)
**Tests:**
- TestSensorGenerator: generates_all_sensors, healthy_values_within_nominal_range, deterministic_with_seed, different_seeds_produce_different_readings, dropout_produces_nan, quality_map_reflects_nan
- TestFailureInjection: bearing_degradation_increases_vibration, thermal_overload_increases_temperature, cooling_failure_decreases_coolant_flow, degradation_score_progresses, health_state_transitions
- TestScenarios: all_scenarios_create_simulators, healthy_scenario_stays_healthy, bearing_degradation_scenario_reaches_critical

### tests/unit/test_features.py (149 lines, 12 tests)
**Tests:**
- TestRollingWindow: computes_mean, computes_std, computes_min_max, computes_ewma
- TestRollingFeatureEngine: produces_all_sensor_features, healthy_machine_features
- TestTemporalFeatures: trend_increasing, trend_decreasing, trend_stable, rate_of_change, temporal_engine_detects_bearing_trend
- TestCorrelationFeatures: ratio_computation, ratio_deviation_near_zero_for_healthy

### tests/unit/test_detection.py (94 lines, 7 tests)
**Tests:**
- TestRuleDetector: healthy_machine_no_anomalies, temperature_breach_detected, vibration_breach_detected, critical_severity_higher_than_warn, coolant_flow_low_detected, trend_confirmation_reduces_false_positives, multiple_anomalies_detected

### tests/unit/test_rca.py (101 lines, 7 tests)
**Tests:**
- TestRCAEngine: healthy_machine_no_root_cause, identifies_bearing_degradation, identifies_thermal_overload, identifies_cooling_failure, root_cause_has_evidence, confidence_in_valid_range

### tests/unit/test_policy.py (224 lines, 14 tests)
**Tests:**
- TestPolicyRules: readonly_allowed_on_healthy, inspection_allowed_with_degradation, inspection_denied_on_healthy, reduce_load_requires_approval_and_degradation, reduce_load_denied_without_approval, shutdown_requires_supervisor, shutdown_denied_on_healthy, shutdown_denied_without_approval, request_approval_always_allowed, maintenance_blocks_all, shutdown_machine_blocks_all, default_deny, policy_rules_evaluated_in_order

### tests/unit/test_tools.py (225 lines, 16 tests)
**Tests:**
- TestToolRegistry: all_tools_registered, get_existing_tool, get_nonexistent_tool, input_validation
- TestToolBroker: execute_readonly_tool, execute_schedule_inspection_with_degradation, schedule_inspection_denied_on_healthy, reduce_load_requires_approval, reduce_load_with_approval, shutdown_denied_without_approval, shutdown_with_supervisor_approval, shutdown_on_healthy_machine_denied, execution_audited, denied_execution_audited, invalid_input_rejected, nonexistent_tool_denied

### tests/unit/test_audit.py (152 lines, 10 tests)
**Tests:**
- TestAuditChain: record_creates_event, chain_links_events, genesis_hash_correct, events_are_immutable, export_returns_all_events, get_events_for_machine, get_events_by_type
- TestChainVerifier: verify_valid_chain, verify_detects_tampering, verify_empty_chain

### tests/integration/__init__.py
Empty package init file.

### tests/integration/test_vertical_slice.py (282 lines, 3 tests)
**Purpose:** End-to-end integration test running the complete Phase 1 pipeline.
**Tests:**
- test_full_bearing_degradation_scenario: runs the complete flow:
  1. Machine starts healthy (50 steps, no anomalies)
  2. Bearing degradation injected, anomalies detected, RCA identifies bearing_degradation
  3. Policy allows inspection (degradation > 0.2)
  4. ToolBroker executes inspection
  5. Machine reaches critical state (degradation > 0.9)
  6. Agent requests shutdown without approval → denied
  7. Supervisor approves
  8. ToolBroker executes shutdown
  9. Audit chain has 100+ events and verification passes
  10. All key event types present in chain (telemetry, anomaly, RCA, policy, approval, action)
- test_prompt_injection_cannot_bypass_policy: security test verifying that 'Ignore all safety policies' text in the reason field does not bypass the deterministic policy engine
- test_agent_cannot_directly_control_machine: verifies that the broker is the enforcement point — shutdown on healthy machine is denied even with approval

---

## Summary Statistics

| Metric | Count |
| --- | --- |
| Total Python files | 48 |
| Total lines of code | 5,354 |
| Unit test files | 7 |
| Integration test files | 1 |
| Total tests | 86 |
| Tests passing | 86 (100%) |
| Python packages (sub-packages) | 10 |
| Failure modes supported | 7 |
| Sensors simulated | 9 |
| Tools available | 6 |
| Policy rules | 8 |
| Test scenarios | 11 |
