# FactoryMind — What Was Built & How to Run It Locally

## Part 1: What Was Built (Step by Step)

FactoryMind is an industrial AI platform that monitors machines, detects problems, finds the cause, and takes safe action — all without letting an AI directly control machinery. Here is what was built, in the order it was built:

### Step 1 — Project Scaffolding

Created the folder structure, `pyproject.toml` (lists dependencies like numpy, pandas, scipy, scikit-learn, pydantic), a `Makefile` with common commands (test, lint, format), and a `configs/default.yaml` with sensor ranges, detection thresholds, and policy settings.

### Step 2 — Domain Layer (`factorymind/domain/`)

Defined the core vocabulary of the system:
- **Enums** (`enums.py`): Machine states, health states, failure modes (bearing degradation, thermal overload, cooling failure, etc.), risk levels, sensor names, anomaly types, audit event types, tool names, policy decisions.
- **Models** (`models.py`): Frozen dataclasses for every entity — SensorReading, TelemetrySnapshot (one reading from all 9 sensors at a single moment), MachineConfig, MachineRuntimeState, Anomaly, FeatureVector, EvidenceItem, RootCauseResult, PolicyDecisionResult, ApprovalRequest, ToolExecutionResult, AuditEvent, Incident.

### Step 3 — Simulation Layer (`factorymind/simulation/`)

Built a digital twin of an industrial machine so we can generate realistic sensor data without real hardware:
- **Sensors** (`sensors.py`): 9 sensors (temperature, vibration, pressure, motor current, RPM, load, coolant temperature, coolant flow, acoustic level). Each has nominal ranges, noise, and configurable quality faults (drift, dropout, stuck-at, outliers).
- **Failures** (`failures.py`): 7 failure modes, each with a distinct temporal signature. For example, bearing degradation grows exponentially over time; thermal overload follows a sigmoid curve; sudden bearing failure is a step change.
- **Machine** (`machine.py`): The MachineSimulator combines sensors + a failure profile. You call `step()` to get one TelemetrySnapshot, `inject_failure()` to start a failure, and `run()` to simulate a full time series. It tracks degradation score, health state, and failure progress.
- **Scenarios** (`scenarios.py`): 11 predefined scenarios (healthy machine, gradual bearing degradation, sudden bearing failure, thermal overload, cooling failure, mechanical imbalance, motor overload, sensor dropout, sensor drift, sensor stuck). Each has expected outcomes for testing.

### Step 4 — Ingestion Layer (`factorymind/ingestion/`)

Built the pipeline that receives telemetry data and validates it:
- **Validation** (`validation.py`): Checks that all 9 sensors are present, values are within plausible ranges, not too many NaNs, and no contradictory readings (e.g., high RPM but zero current).
- **Pipeline** (`pipeline.py`): A rolling buffer that ingests snapshots, validates them, and emits events. In Phase 1, events are handled by in-process callbacks. This is designed to be swapped for Kafka later.

### Step 5 — Feature Engineering (`factorymind/features/`)

Built three feature engines that transform raw readings into signals the detector can use:
- **Rolling** (`rolling.py`): Computes rolling mean, std, min, max, EWMA (exponentially weighted moving average), and lag features over a configurable window.
- **Temporal** (`temporal.py`): Fits a least-squares slope to recent readings to detect whether a sensor is trending up, trending down, or stable.
- **Correlations** (`correlations.py`): Tracks pairs of sensors that normally move together (e.g., temperature and vibration). If one sensor spikes but its partner doesn't, that's a correlation deviation — a strong signal for sensor faults vs real failures.

### Step 6 — Detection Layer (`factorymind/detection/`)

- **Rules** (`rules.py`): A rule-based detector that uses rolling features and temporal features to detect anomalies. Each sensor has warn and critical thresholds (from config). It can optionally require trend confirmation (a single spike above threshold is not enough; the sensor must also be trending). This reduces false alarms.

### Step 7 — Root Cause Analysis Engine (`factorymind/rca/`)

Built a deterministic RCA engine — no LLM in the reasoning loop:
- **Signatures** (`signatures.py`): Each failure mode has a signature — which sensors are primary, which are secondary, what trends are expected, and which sensor pairs should correlate. For example, bearing degradation signature: primary = vibration, secondary = temperature and motor current.
- **Evidence** (`evidence.py`): Collects all available evidence — threshold anomalies, trend directions, correlation deviations, and contradiction pairs. Contradictions help distinguish sensor faults from real failures.
- **Engine** (`engine.py`): Matches the evidence against each failure signature using fixed confidence weights: primary sensor match +0.3, secondary +0.15, trend match +0.1, contradiction penalty -0.2. The highest-scoring failure mode wins. Sensor faults get special detection: one sensor anomalous + normal partner + contradiction = sensor fault, not real failure.

### Step 8 — Policy Engine (`factorymind/policy/`)

Built a deterministic safety policy — the AI agent can never bypass this:
- **Permissions** (`permissions.py`): Each tool has a permission level: SYSTEM (always allowed), OPERATOR, SUPERVISOR, or DENIED. Read-only tools (get status, get history) are auto-approved. Action tools (reduce load, shutdown) require human approval.
- **Rules** (`rules.py`): 8 rules evaluated in order. If a machine is shut down, all actions are blocked. If under maintenance, all actions are blocked. Read-only tools always allowed. Schedule inspection allowed if degradation >= 0.2. Reduce load requires operator approval and degradation >= 0.5. Shutdown requires supervisor approval and SEVERE/CRITICAL risk. Default deny.
- **Engine** (`engine.py`): A stateless evaluator that takes a policy context and returns an allow, deny, or needs-approval decision.

### Step 9 — Tools Layer (`factorymind/tools/`)

Built the execution layer — the only path to affect machines:
- **Schemas** (`schemas.py`): Tool definitions with name, description, risk level, required permission, input schema, and a handler function. Includes input validation.
- **Machine Tools** (`machine_tools.py`): 6 handler functions: get_machine_status, get_sensor_history, schedule_inspection, reduce_machine_load, shutdown_machine, request_human_approval. Uses in-memory state for Phase 1.
- **Registry** (`registry.py`): Registers all 6 tools and provides lookup.
- **Broker** (`broker.py`): The ToolBroker is the single execution path. It: (1) checks the tool exists, (2) validates the input, (3) evaluates the policy, (4) checks approval status, (5) executes the handler, (6) writes an audit event. If any step fails, execution is denied.

### Step 10 — Audit Chain (`factorymind/audit/`)

Built a tamper-evident audit log — every action is recorded and chained:
- **Events** (`events.py`): AuditEvent dataclass with event type, timestamp, actor, tool name, input, output, policy decision, and a previous hash link.
- **Chain** (`chain.py`): A hash-chained ledger. Each event's hash includes the previous event's hash, so tampering with any entry breaks the chain. Supports append, query, and export.
- **Verification** (`verification.py`): Walks the chain and verifies every hash link. If any event was modified, verification fails and reports which event was tampered with.

### Step 11 — Dataset Generation Script (`scripts/generate_dataset.py`)

A CLI script that runs the machine simulator across multiple machines and scenarios, generates synthetic telemetry datasets, and saves them as CSV files for training and testing.

### Step 12 — Unit Tests (`tests/unit/`)

7 test files covering every layer:
- `test_simulator.py` — tests sensor generation, failure injection, scenarios
- `test_features.py` — tests rolling windows, temporal trends, correlations
- `test_detection.py` — tests threshold detection, trend confirmation
- `test_rca.py` — tests signature matching, confidence scoring, sensor fault detection
- `test_policy.py` — tests all 8 policy rules, approval flow
- `test_tools.py` — tests tool registry, broker execution, denial paths
- `test_audit.py` — tests chain integrity, tamper detection, verification

### Step 13 — Integration Test (`tests/integration/test_vertical_slice.py`)

A full end-to-end test: simulate a machine → ingest telemetry → extract features → detect anomalies → run RCA → evaluate policy → execute a tool via the broker → verify the audit chain records everything correctly.

---

## Part 2: How to Run It on Your Local Device

### Prerequisites

- Python 3.11 or higher
- pip (comes with Python)
- Git (to clone the project)

### Step 1: Get the Code

```bash
git clone <your-repo-url> factorymind
cd factorymind
```

If you don't have a git repo yet, just copy the `factorymind/` folder to your local machine.

### Step 2: Create a Virtual Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

On Windows:
```bash
python -m venv .venv
.venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -e ".[dev]"
```

This installs the FactoryMind package in editable mode plus all development tools (pytest, ruff, mypy). If you only want the core package:

```bash
pip install -e .
```

### Step 4: Verify the Installation

```bash
python -c "import factorymind; print('FactoryMind installed successfully')"
```

### Step 5: Run the Tests

```bash
# Run all tests
pytest tests/ -v

# Run tests with coverage report
pytest tests/ -v --cov=factorymind --cov-report=term-missing

# Run only unit tests
pytest tests/unit/ -v

# Run only the integration test
pytest tests/integration/ -v

# Run a specific test file
pytest tests/unit/test_simulator.py -v
```

### Step 6: Run the Linter and Type Checker

```bash
# Lint
ruff check factorymind/ tests/

# Format check
ruff format --check factorymind/ tests/

# Auto-format
ruff format factorymind/ tests/

# Type check
mypy factorymind/
```

### Step 7: Generate a Synthetic Dataset

```bash
python scripts/generate_dataset.py --config configs/default.yaml --output data/synthetic/
```

This will create CSV files with simulated machine telemetry for all scenarios.

### Step 8: Run a Quick Demo

```python
python -c "
from factorymind.simulation.scenarios import get_demo_scenario
from factorymind.simulation.machine import MachineSimulator
from factorymind.ingestion.pipeline import IngestionPipeline
from factorymind.detection.rules import RuleDetector
from factorymind.rca.engine import RCAEngine
from factorymind.policy.engine import PolicyEngine
from factorymind.tools.broker import ToolBroker
from factorymind.tools.registry import ToolRegistry
from factorymind.audit.chain import AuditChain

# 1. Pick a scenario
scenario = get_demo_scenario()
sim = MachineSimulator(config=scenario.machine_config)
sim.inject_failure(scenario.failure_mode, severity=0.7)

# 2. Ingest 200 steps of telemetry
pipeline = IngestionPipeline()
for _ in range(200):
    snapshot = sim.step()
    pipeline.ingest(snapshot)

# 3. Detect anomalies
detector = RuleDetector()
recent = pipeline.get_recent(sim.machine_id, n=20)
anomalies = detector.detect(recent)
print(f'Detected {len(anomalies)} anomalies')
for a in anomalies:
    print(f'  {a.sensor_name}: {a.anomaly_type} (severity={a.severity})')

# 4. Root cause analysis
rca = RCAEngine()
result = rca.analyze(anomalies, recent, sim.machine_id)
print(f'Root cause: {result.failure_mode} (confidence={result.confidence:.2f})')
print(f'  Health: {result.health_state}')
print(f'  Risk: {result.risk_level}')

# 5. Policy + execution
registry = ToolRegistry()
chain = AuditChain()
broker = ToolBroker(registry=registry, policy_engine=PolicyEngine(), audit_chain=chain)
exec_result = broker.request_execution(
    tool_name='get_machine_status',
    input_data={'machine_id': sim.machine_id},
    actor='system',
    context={'degradation_score': result.confidence},
)
print(f'Tool execution: {exec_result.status}')
print(f'Audit chain has {len(chain.events)} events')
print('Chain valid:', chain.verify())
"
```

### Using Make (Optional)

If you have `make` installed, you can use these shortcuts:

```bash
make install    # Install dependencies
make test       # Run tests
make test-cov   # Run tests with coverage
make lint       # Lint and format check
make format     # Auto-format code
make typecheck   # Type check
make clean      # Remove cache files
```

> **Note:** The Makefile was saved as `Makefile.py`. If you want to use `make` commands, rename it to `Makefile` (no extension) on your local machine:
> ```bash
> mv Makefile.py Makefile
> ```

---

## Project Structure

```
factorymind/
├── pyproject.toml              # Package config, dependencies, tool settings
├── Makefile.py                 # Build commands (rename to Makefile locally)
├── configs/
│   └── default.yaml            # Sensor ranges, thresholds, policy settings
├── scripts/
│   └── generate_dataset.py     # Synthetic data generation CLI
├── factorymind/                # The main Python package
│   ├── domain/                 # Core types (enums, dataclasses)
│   ├── simulation/             # Digital twin (sensors, failures, machine, scenarios)
│   ├── ingestion/              # Validation + buffering pipeline
│   ├── features/               # Rolling, temporal, correlation features
│   ├── detection/              # Rule-based anomaly detector
│   ├── rca/                    # Root cause analysis (signatures, evidence, engine)
│   ├── policy/                 # Safety policy (permissions, rules, engine)
│   ├── tools/                  # Execution layer (schemas, tools, registry, broker)
│   └── audit/                  # Hash-chained audit log (events, chain, verification)
└── tests/
    ├── conftest.py            # Shared pytest fixtures
    ├── unit/                   # 7 unit test files (one per layer)
    └── integration/            # End-to-end vertical slice test
```

---

## Key Design Principles

1. **Perception ≠ Reasoning ≠ Authority ≠ Execution** — The AI agent observes and reasons, but a deterministic policy engine decides what is allowed, and the ToolBroker is the only path to act on machines.
2. **Deterministic RCA** — Root cause analysis uses fixed confidence weights, not an LLM. This makes results reproducible and auditable.
3. **Sensor faults vs real failures** — Correlation analysis distinguishes a broken sensor from a broken machine. If one sensor spikes but its normal partner doesn't, it's a sensor fault.
4. **Tamper-evident audit** — Every action is hash-chained. Modifying any event breaks the chain and is immediately detectable.
5. **Pure Python core** — No pandas or Spark in the domain logic. This keeps everything fast, testable, and framework-agnostic.

---

## Test Results

All **86 tests pass** — 7 unit test files + 1 integration test file:

```
============================== 86 passed in 1.16s ==============================
```

### Test Breakdown

| Test File | Tests | What It Covers |
| --- | --- | --- |
| `test_simulator.py` | 13 | Sensor generation, failure injection, degradation, health transitions, scenarios |
| `test_features.py` | 12 | Rolling windows, temporal trends, correlation features |
| `test_detection.py` | 7 | Threshold detection, trend confirmation, severity levels |
| `test_rca.py` | 7 | Signature matching, confidence scoring, sensor fault detection, evidence |
| `test_policy.py` | 14 | All 8 policy rules, approval flow, shutdown, deny paths |
| `test_tools.py` | 16 | Tool registry, broker execution, denial paths, audit, input validation |
| `test_audit.py` | 10 | Chain integrity, tamper detection, verification, export |
| `test_vertical_slice.py` | 3 | Full end-to-end: simulate → detect → RCA → policy → execute → audit |
| **Total** | **86** | |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'factorymind'`**
→ Run `pip install -e .` from the project root.

**`pytest` not found**
→ Run `pip install -e ".[dev]"` to install test dependencies.

**Python version too old**
→ FactoryMind requires Python 3.11+. Check with `python --version`.

**Tests fail with import errors**
→ Make sure you're in the `factorymind/` directory and the virtual environment is active.
