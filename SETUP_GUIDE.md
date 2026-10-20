
# FactoryMind — Project Guide

**An industrial AI platform for equipment monitoring, anomaly detection, root-cause analysis, and controlled operational decision-making.**

FactoryMind is designed around a deterministic industrial decision core. It combines simulated equipment signals, detection logic, root-cause analysis (RCA), policy evaluation, controlled tool execution, and audit records.

The project emphasizes a key engineering principle: **AI can help interpret industrial conditions, but operational actions should pass through explicit policies and controlled execution paths.**

This guide helps developers understand the architecture, run the available functionality, inspect outputs, test the core, and identify future extensions.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Core Concepts](#2-core-concepts)
3. [Architecture](#3-architecture)
4. [Requirements](#4-requirements)
5. [Installation](#5-installation)
6. [Run the Project](#6-run-the-project)
7. [Understand the Outputs](#7-understand-the-outputs)
8. [How the Decision Pipeline Works](#8-how-the-decision-pipeline-works)
9. [Policy and Tool Execution](#9-policy-and-tool-execution)
10. [Auditability](#10-auditability)
11. [Run Tests](#11-run-tests)
12. [Project Structure](#12-project-structure)
13. [Troubleshooting](#13-troubleshooting)
14. [Safety and Limitations](#14-safety-and-limitations)
15. [Roadmap](#15-roadmap)

---

## 1. Project Overview

Industrial environments generate large amounts of telemetry. Engineers need to detect abnormal conditions, understand their likely causes, and decide what action should be taken.

FactoryMind explores how to organize these steps into a testable, auditable software system.

### The problem

A basic monitoring system might report that a machine's temperature has exceeded a threshold. That alone does not answer:

- Is the condition genuinely abnormal?
- What other signals changed at the same time?
- What is the likely root cause?
- Is an intervention permitted?
- Which component requested or approved the action?
- Can the decision be reconstructed later?

FactoryMind separates these responsibilities into individual components.

### Project objectives

- Simulate industrial equipment signals.
- Detect abnormal operating conditions.
- Generate structured root-cause hypotheses.
- Evaluate proposed actions against explicit policies.
- Route permitted actions through a controlled tool broker.
- Record relevant decisions and execution outcomes in an audit chain.
- Provide a foundation for future industrial AI agents.

### Intended users

- Industrial AI and machine-learning developers.
- Software engineers working on industrial monitoring.
- Researchers studying explainable decision pipelines.
- Developers interested in tool-using AI agents with operational controls.
- Engineers building prototypes for predictive maintenance and root-cause analysis.

FactoryMind is a prototype and should not be treated as a certified industrial control system.

---

## 2. Core Concepts

### 2.1 Simulator

The simulator generates equipment signals or operating scenarios so that the pipeline can be exercised without requiring a live industrial machine.

It provides a repeatable way to explore normal and abnormal conditions.

### 2.2 Detection

The detection component evaluates incoming signals and identifies conditions that may require investigation.

Examples of industrial signals include temperature, vibration, pressure, and operating load. The exact signals and detection rules depend on the implementation.

### 2.3 Root-Cause Analysis

Root-cause analysis attempts to explain an observed anomaly by evaluating available evidence.

A useful RCA result should distinguish:

- The detected symptom.
- The supporting evidence.
- The proposed cause or causes.
- Confidence or uncertainty, where implemented.
- The next recommended investigation or action.

A proposed root cause is not automatically proof of the physical cause of a failure.

### 2.4 Policy Engine

The policy engine evaluates whether a proposed action satisfies the project's explicit operational rules.

Policy decisions should be separate from the model's recommendation. A model suggesting an action does not, by itself, authorize that action.

### 2.5 Tool Broker

The tool broker provides a controlled boundary between decision logic and executable tools.

Instead of allowing arbitrary components to execute operations directly, requests can be routed through a defined interface where permissions and validation are applied.

### 2.6 Audit Chain

The audit component records relevant events and decisions so they can be reviewed later.

The goal is to make it possible to trace how a system reached a decision and what happened when a tool request was processed.

---

## 3. Architecture

FactoryMind's core vertical slice follows this conceptual flow:

```text
Industrial Scenario
        |
        v
     Simulator
        |
        v
   Signal / State
        |
        v
    Detection
        |
        v
Root-Cause Analysis
        |
        v
  Policy Evaluation
        |
        v
    Tool Broker
        |
        v
 Controlled Tool Result
        |
        v
    Audit Chain
```

The exact data structures and call order should be confirmed against the current implementation.

### Component responsibilities

| Component | Responsibility |
|---|---|
| Simulator | Produces repeatable equipment scenarios |
| Detection | Identifies abnormal conditions |
| RCA | Analyzes evidence and proposes possible causes |
| Policy | Determines whether a proposed operation is allowed |
| Tool broker | Controls requests to supported tools |
| Audit chain | Records relevant decisions and outcomes |

### Why separate these components?

Separation improves:

- **Testability:** each component can be validated independently.
- **Explainability:** detection evidence and proposed causes can be inspected.
- **Safety:** policy checks can be applied before controlled operations.
- **Maintainability:** components can evolve without requiring a complete rewrite.
- **Traceability:** decisions and execution outcomes can be associated with audit records.

### Deterministic core

The deterministic core is the first priority for FactoryMind.

The objective is to make the operational flow predictable and testable before introducing additional agent services, dashboards, or distributed infrastructure.

This does not mean every external dependency is automatically deterministic. Simulator inputs, configuration, tool responses, and execution environments can still affect results.

---

## 4. Requirements

Use the versions and dependencies specified by the current repository.

Typical requirements for a Python implementation include:

- Python compatible with the project's dependency definitions.
- A virtual environment.
- Git.
- The libraries listed in the repository's dependency files.

The exact minimum Python version, package versions, and optional service requirements should be taken from the actual project configuration rather than guessed.

---

## 5. Installation

### Step 1: Clone the repository

```bash
git clone <YOUR_FACTORYMIND_REPOSITORY_URL>
cd FactoryMind
```

Replace the placeholder with your actual repository URL. Use the repository's actual directory name if it differs.

### Step 2: Create a virtual environment

```bash
python3 -m venv .venv
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### Step 3: Install dependencies

If the repository includes `requirements.txt`:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If the project uses `pyproject.toml` or another dependency manager, follow the installation instructions defined in that file.

### Step 4: Inspect the repository

Before running a command, inspect the available entry points and tests:

```bash
find . -maxdepth 3 -type f | sort
```

Look for:

- A documented demo or example.
- The simulator entry point.
- The main pipeline or orchestration module.
- The policy and tool-broker implementations.
- The audit implementation.
- Test files and configuration files.

The correct command depends on the actual entry point provided by your checkout.

---

## 6. Run the Project

FactoryMind's core workflow is intended to demonstrate the path from an equipment scenario to a controlled, auditable decision.

Because entry-point names and constructor signatures depend on the repository version, use the actual demo script or command documented by the project. Do not assume that a particular CLI or API exists unless it is implemented.

### Recommended first run

1. Activate the virtual environment.
2. Load the project's supported configuration.
3. Run the available simulator or demo.
4. Inspect the generated signals.
5. Review detection results.
6. Inspect the RCA result.
7. Review the policy decision.
8. Inspect the tool-broker outcome.
9. Examine the audit records.
10. Run the test suite.

### What should you look for?

A useful end-to-end demonstration should make the relationship between the stages visible:

- Which input scenario was evaluated?
- Which condition was detected?
- What evidence supported the RCA result?
- What action was proposed?
- Was the action allowed or denied?
- What did the tool broker return?
- What information was recorded in the audit trail?

The exact output fields and successful execution sequence should be verified against the implementation.

---

## 7. Understand the Outputs

The examples in this section are **illustrative schemas**, not captured FactoryMind execution results. Actual field names, values, and serialization depend on the current code.

### 7.1 Simulated equipment state

A simulator may represent a machine's operating conditions using structured telemetry.

Illustrative example:

```json
{
  "equipment_id": "pump-01",
  "temperature_c": 92.4,
  "vibration_mm_s": 8.1,
  "operating_state": "running"
}
```

This example shows the kind of information an industrial scenario could contain. It does not establish that the current simulator emits these exact fields.

### 7.2 Detection result

The detection stage identifies a condition that warrants attention.

Illustrative example:

```json
{
  "anomaly_detected": true,
  "severity": "high",
  "signals": [
    "temperature",
    "vibration"
  ]
}
```

The purpose is to represent a detected condition and its evidence. The actual detection thresholds and severity categories must be taken from the source code or configuration.

### 7.3 Root-cause analysis result

RCA should connect a detected symptom with supporting evidence and a proposed explanation.

Illustrative example:

```json
{
  "suspected_cause": "bearing_degradation",
  "supporting_evidence": [
    "elevated_vibration",
    "increased_temperature"
  ],
  "recommended_action": "inspect_bearing"
}
```

This is an example of a structured RCA result, not a validated diagnosis. Real industrial root-cause analysis requires appropriate sensor data, validation, and engineering review.

### 7.4 Policy decision

The policy stage evaluates a proposed action.

Illustrative example:

```json
{
  "action": "inspect_bearing",
  "decision": "allowed",
  "reason": "action_matches_configured_policy"
}
```

The actual policy may allow, deny, or otherwise classify a request. Use the implemented decision model to determine its exact vocabulary and fields.

### 7.5 Tool-broker result

The broker mediates an operation and returns its outcome.

Illustrative example:

```json
{
  "tool": "maintenance_ticket",
  "status": "completed",
  "operation_id": "op-001"
}
```

This example does not mean FactoryMind currently integrates with a real maintenance-ticket system. Only document a real integration when the corresponding tool is implemented and tested.

### 7.6 Audit record

An audit record can associate an input, decision, action request, or result with a traceable record.

Illustrative example:

```json
{
  "event_type": "policy_decision",
  "action": "inspect_bearing",
  "decision": "allowed",
  "recorded": true
}
```

The actual audit implementation determines the recorded fields and whether it uses hashing, chained records, or another integrity mechanism.

---

## 8. How the Decision Pipeline Works

### Step 1: Generate a scenario

The simulator produces an input state for the pipeline.

For repeatable tests, the same scenario and configuration should produce comparable outputs. If randomness is involved, use the simulator's supported seed mechanism if available.

### Step 2: Detect an abnormal condition

The detection component evaluates the input using the rules or models implemented in the project.

The result should preserve enough evidence for downstream analysis.

### Step 3: Analyze possible causes

RCA evaluates the available evidence and produces a proposed explanation.

Keep the distinction between evidence and hypothesis clear. A detected correlation does not necessarily prove causation.

### Step 4: Propose an action

Based on the condition and RCA result, the system can produce a recommended next step.

Recommendations should remain distinct from execution requests.

### Step 5: Evaluate policy

The policy engine checks whether the requested operation satisfies the configured rules.

A denied action should not proceed to a protected execution path.

### Step 6: Route through the tool broker

Permitted requests are routed through the broker and handled by supported tools.

The broker should validate requests at its boundary instead of relying solely on upstream components to behave correctly.

### Step 7: Record the outcome

Relevant events, policy decisions, and tool outcomes are recorded in the audit mechanism.

The complete trace helps developers understand what happened and investigate unexpected behavior.

---

## 9. Policy and Tool Execution

Policy enforcement is a core design principle of FactoryMind.

### Recommended execution boundary

```text
Recommendation
      |
      v
Policy Evaluation
      |
      +---- Denied ----> Record decision
      |
      v
   Allowed
      |
      v
  Tool Broker
      |
      v
Validate and Execute
      |
      v
Record Outcome
```

This diagram expresses the intended control flow. Verify the precise enforcement sequence in the actual implementation.

### Policy design principles

- Validate requested actions before execution.
- Use explicit allow/deny rules.
- Reject unsupported or malformed requests.
- Apply least-privilege access to tools.
- Keep policy decisions separate from model-generated recommendations.
- Record denials as well as successful operations where supported.
- Treat timeouts and tool failures as distinct from successful execution.

### Tool broker design principles

- Expose a limited set of supported operations.
- Validate tool arguments.
- Avoid unrestricted shell or arbitrary-code execution.
- Handle failures explicitly.
- Return structured outcomes.
- Preserve traceability between the request and its result.

**Important:** Do not connect a prototype broker to live industrial equipment without a separate safety review, authorization design, failure analysis, and appropriate operational safeguards.

---

## 10. Auditability

Auditability helps developers reconstruct a decision after execution.

A useful audit trail should make it possible to identify:

- The relevant scenario or input.
- The detection outcome.
- The RCA result.
- The proposed action.
- The policy decision.
- The tool request and execution outcome.
- Any associated errors.

### Audit integrity

If the implementation uses hash-linked records, the integrity of the chain depends on how records are serialized, hashed, linked, stored, and verified.

A hash chain can make certain modifications detectable, but it does not automatically guarantee:

- Protection against every privileged attacker.
- Durable storage.
- Correct timestamps.
- Confidentiality.
- Authenticity of every event source.
- Correctness of the underlying industrial decision.

Document only the integrity properties that the current code and tests demonstrate.

---

## 11. Run Tests

Run the tests from the repository root using the project's configured test runner.

For a Python project using pytest:

```bash
python -m pytest -v
```

If the project organizes tests in a dedicated directory:

```bash
python -m pytest tests/ -v
```

Use the path that actually exists in your checkout.

### Test the deterministic core

The core vertical slice should have tests for:

- Simulator behavior.
- Detection logic.
- RCA output and evidence handling.
- Policy allow/deny decisions.
- Tool-broker validation and failure handling.
- Audit record creation.
- Audit integrity verification, if implemented.
- End-to-end execution across the core components.

### Verify the result

After running tests, record:

- The command used.
- The number of passed and failed tests.
- Any skipped tests.
- The environment and dependency versions.
- Whether tests exercised only mocks/simulations or external integrations.

Do not publish a fixed test count unless it matches the latest run.

---

## 12. Project Structure

The following is a conceptual structure based on the FactoryMind core architecture. Treat it as an organizational guide rather than an assertion that every path already exists.

```text
FactoryMind/
├── simulator/
│   └── equipment scenarios
├── detection/
│   └── anomaly detection logic
├── rca/
│   └── root-cause analysis
├── policy/
│   └── action authorization rules
├── tool_broker/
│   └── controlled tool execution
├── audit/
│   └── decision and execution records
├── tests/
│   └── unit and integration tests
├── docs/
│   └── PROJECT_GUIDE.md
├── README.md
└── project configuration and dependency files
```

The actual repository may use different paths or combine some components into shared packages.

### Where should a new contributor start?

1. Find the simulator and understand its input format.
2. Follow one scenario through the detection component.
3. Inspect how evidence is passed into RCA.
4. Review policy evaluation and its tests.
5. Inspect the tool-broker boundary.
6. Trace how decisions and results reach the audit mechanism.
7. Run the relevant unit tests before changing a component.

---

## 13. Troubleshooting

### Import errors

**Possible cause:** The package is not installed or the project root is not on Python's import path.

**Try:**

```bash
python -m pip install -e .
```

Use this only if the repository supports editable installation through its packaging configuration.

Otherwise, follow the repository's actual setup instructions.

### Dependencies fail to install

**Possible cause:** Unsupported Python versions, conflicting dependencies, or platform-specific packages.

**Try:**

- Check the Python version required by the project.
- Create a fresh virtual environment.
- Follow the dependency files in the repository.
- Avoid mixing dependencies from unrelated environments.

### The pipeline produces no anomaly

**Possible cause:** The input scenario does not cross the configured thresholds or satisfy the detection rules.

**Try:**

- Inspect the simulator output.
- Check the detection configuration.
- Verify units and expected signal ranges.
- Run a known test scenario.
- Review the detection tests before changing thresholds.

### An action is denied

**Possible cause:** The policy engine rejected the request or the request did not satisfy the configured requirements.

**Try:**

- Inspect the policy decision and reason.
- Check the requested action and its arguments.
- Verify the active policy configuration.
- Do not bypass the policy merely to make the demo succeed.

### Tool execution fails

**Possible cause:** Invalid arguments, an unsupported operation, a timeout, or a tool error.

**Try:**

- Inspect the broker response.
- Verify the tool is registered and supported.
- Confirm request validation.
- Check whether the failure was recorded.
- Test failure paths using safe test doubles.

### Audit verification fails

**Possible cause:** A record was altered, the chain was constructed inconsistently, or serialization/hash inputs differ.

**Try:**

- Inspect the audit verification output.
- Check canonical serialization and record ordering.
- Confirm the same hashing rules are used when creating and verifying records.
- Use a minimal reproducible test.

Do not assume an audit verification failure is harmless.

---

## 14. Safety and Limitations

FactoryMind is a software prototype for industrial AI workflows.

### Current scope

The primary focus is the deterministic core:

- Simulator
- Detection
- Root-cause analysis
- Policy evaluation
- Tool broker
- Audit chain

The exact level of completion for each component should be verified against the current source code and tests.

### Important limitations

- Simulated equipment behavior does not prove performance on real machinery.
- Anomaly detection does not necessarily identify the true physical cause.
- RCA results should be treated as hypotheses unless independently validated.
- Policy rules can be incomplete or incorrectly configured.
- Tool-broker controls require testing against invalid inputs and failure scenarios.
- Audit records do not prove that an underlying decision was correct.
- Prototype software is not a replacement for industrial safety systems or qualified engineering review.

### Before any real deployment

- Validate against representative industrial data.
- Define access controls and authentication.
- Test policy bypass and malformed-request scenarios.
- Review failure modes and recovery behavior.
- Define audit retention, access, and integrity requirements.
- Establish human approval for consequential operations.
- Conduct a safety and security assessment.
- Keep the prototype isolated from live control systems until formally approved.

---

## 15. Roadmap

The checklist distinguishes core functionality from possible future extensions.

### Core deterministic vertical slice

- [x] Equipment simulation
- [x] Detection component
- [x] Root-cause analysis component
- [x] Policy evaluation
- [x] Controlled tool-broker boundary
- [x] Audit-chain component
- [x] Unit and integration testing for the core

**Verification note:** The checked items describe the intended core scope. Confirm the current implementation and latest tests before presenting every item as production-ready.

### Future platform extensions

- [ ] Additional equipment simulators and scenarios
- [ ] Richer detection models and validation datasets
- [ ] Evidence-grounded RCA enhancements
- [ ] Expanded policy rules and authorization controls
- [ ] Additional tool adapters and integrations
- [ ] Monitoring dashboard and operational UI
- [ ] API layer for external clients
- [ ] Persistent storage for events and audit records
- [ ] Metrics, tracing, and observability
- [ ] Containerized deployment and CI/CD
- [ ] Evaluation on representative industrial data
- [ ] Carefully controlled human approval workflows

These are potential extensions, not claims that the corresponding services are already implemented.

---

## Contributing

Contributions are welcome.

Before submitting a change:

1. Read the relevant component and its tests.
2. Keep component interfaces explicit.
3. Add tests for normal and failure cases.
4. Preserve policy enforcement boundaries.
5. Avoid direct tool execution that bypasses the broker.
6. Ensure important decisions and failures remain traceable.
7. Document configuration changes and new outputs.
8. Report what has been tested and what remains unverified.

---

## License

Add the actual project license here. Verify the licensing requirements of dependencies and any external models or datasets before redistributing them.

---

## Summary

FactoryMind is organized around a controlled industrial decision pipeline: simulate, detect, analyze, evaluate policy, execute through a broker, and record the outcome.

Start by running the deterministic core and its tests. Understand the interfaces between components before adding more services or integrating external systems.

The long-term objective is an industrial AI platform that is explainable, testable, auditable, and designed with explicit operational controls.
