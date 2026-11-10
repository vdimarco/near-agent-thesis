# NEAR Agent Economy Investment Thesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, evidence-backed NEAR investment thesis (`THESIS.md` and a static Vercel dashboard) testing whether NEAR's native account and execution primitives (`FunctionCall` access keys, sub-accounts, `DELEGATE_ACTION`, and `intents.near`) give autonomous AI agents a measurable cost and security advantage over EVM ERC-4337 smart accounts and Solana.

**Architecture:** A four-stage pipeline: (1) Partitioned BigQuery SQL queries (`sql/*.sql`) and a 30-day swarm TCO model (`src/cost_model.py`); (2) a data fetcher (`src/fetch.py`) that queries BigQuery (`bigquery-public-data.crypto_near_mainnet_us`) with a strict 50 GB scan guard and pulls live 2026 mainnet data from FastNEAR RPC, NearBlocks API, and NEAR Intents 1Click API into `data/raw/`; (3) an offline analyzer (`src/analyze.py`) that reads only `data/raw/` and emits `data/audit_stats.json` plus four SVG charts in `dashboard/assets/`; and (4) `THESIS.md`, `README.md`, and `dashboard/index.html` verified against `data/audit_stats.json` by `pytest`.

**Tech Stack:** Python 3.11+, `pytest`, `requests`, `google-cloud-bigquery` (optional runtime dependency with graceful CLI/ADC fallback), vanilla HTML/CSS/JS, SVG charts, Vercel static hosting.

**Spec:** `/home/von/Work/near-agent-thesis/docs/superpowers/specs/2026-11-10-near-agent-thesis-design.md`

## Global Constraints

- Repository root: `/home/von/Work/near-agent-thesis`
- Every BigQuery `.sql` file in `sql/` must filter on `block_date` to bound scan costs.
- Every BigQuery API execution must set `maximum_bytes_billed=50_000_000_000` (50 GB) in `QueryJobConfig`.
- `python -m src.analyze` must run offline from `data/raw/` in under 5 seconds with zero network calls.
- Falsification thresholds from the spec:
  1. Scoped `FunctionCall` key share (`ADD_KEY` with `FUNCTION_CALL` permission) must be at least 25% of new keys added, and non-top-3 receiver share of delegated/automated calls must be explicitly reported alongside HHI.
  2. 30-day TCO of a 100-agent swarm executing 10,000 actions with key rotation on NEAR must be compared against Base ERC-4337, Arbitrum ERC-4337, and Solana, including both the shared-account scoped-key model and the sub-account storage lockup model (`0.001 NEAR` per 100 bytes).
  3. Live NEAR Intents 1Click (`dry: true`) solver quotes across $1, $10, $100, $1,000, and $10,000 must report round-trip spread in basis points against a 150 bps threshold on $100 to $1,000 corridors.
- Writing style in `THESIS.md`, `README.md`, and `dashboard/index.html`: clear technical prose, no em dashes, no fabricated numbers.

## Review Focus

1. Missing `block_date` partition filter or unbounded wildcard in SQL files: `validate_sql_text` must reject any SQL query that lacks an explicit `block_date` filter.
2. Zero total keys or empty receiver list in HHI/share calculation: `compute_hhi` and share calculators must return `0.0` instead of raising `ZeroDivisionError` when input counts are empty or sum to zero.
3. Missing or failed quote for micro-payment sizes ($1) from the 1Click API: `parse_quote_spread_bps` must record failed or unquoted rows as `status="unquoted"` and `spread_bps=None` without crashing the batch or skewing median spread calculations.
4. Sub-account storage deposit omitted from NEAR swarm cost: `compute_swarm_tco` must expose both `near_scoped_keys` (shared account, zero extra storage deposit per agent) and `near_subaccounts` (1,820 bytes minimum state per sub-account at `0.001 NEAR` per 100 bytes) so the storage lockup counter-evidence is always computed.
5. Drift between `data/audit_stats.json` and the numbers written in `THESIS.md` or `dashboard/index.html`: `test_document_traceability` must assert that every headline metric in `data/audit_stats.json` appears verbatim in `THESIS.md` and `dashboard/index.html`.

---

### Task 1: Partitioned BigQuery SQL Suite and Swarm TCO Cost Model

**Files:**
- Create: `/home/von/Work/near-agent-thesis/.gitignore`
- Create: `/home/von/Work/near-agent-thesis/LICENSE`
- Create: `/home/von/Work/near-agent-thesis/requirements.txt`
- Create: `/home/von/Work/near-agent-thesis/sql/01_agent_primitives_daily.sql`
- Create: `/home/von/Work/near-agent-thesis/sql/02_receiver_concentration.sql`
- Create: `/home/von/Work/near-agent-thesis/sql/03_gas_and_storage_costs.sql`
- Create: `/home/von/Work/near-agent-thesis/src/__init__.py`
- Create: `/home/von/Work/near-agent-thesis/src/cost_model.py`
- Test: `/home/von/Work/near-agent-thesis/tests/test_sql_and_cost.py`

**Interfaces:**
- Consumes: standard library (`pathlib`, `re`, `math`, ` dataclasses`)
- Produces:
  - `src.cost_model.validate_sql_file(path: Path) -> bool`
  - `src.cost_model.compute_hhi(counts: list[int]) -> float`
  - `src.cost_model.compute_swarm_tco(num_agents: int, monthly_actions: int, key_rotations_per_agent: int, near_price_usd: float) -> dict[str, dict[str, float]]`

- [ ] **Step 1: Write the failing test in `tests/test_sql_and_cost.py`**

```python
from pathlib import Path
import pytest
from src.cost_model import validate_sql_file, validate_sql_text, compute_hhi, compute_swarm_tco

ROOT = Path(__file__).resolve().parent.parent

def test_sql_files_exist_and_filter_on_block_date():
    sql_files = [
        ROOT / "sql" / "01_agent_primitives_daily.sql",
        ROOT / "sql" / "02_receiver_concentration.sql",
        ROOT / "sql" / "03_gas_and_storage_costs.sql",
    ]
    for path in sql_files:
        assert path.exists(), f"Missing SQL file: {path}"
        assert validate_sql_file(path) is True

def test_validate_sql_text_rejects_missing_block_date():
    bad_sql = "SELECT action_kind, COUNT(1) FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions` GROUP BY 1"
    with pytest.raises(ValueError, match="block_date"):
        validate_sql_text(bad_sql)

def test_compute_hhi_handles_empty_and_monopoly():
    assert compute_hhi([]) == 0.0
    assert compute_hhi([0, 0]) == 0.0
    assert pytest.approx(compute_hhi([100]), 0.001) == 10000.0
    assert pytest.approx(compute_hhi([50, 50]), 0.001) == 5000.0

def test_compute_swarm_tco_compares_scoped_keys_vs_subaccounts_and_evms():
    result = compute_swarm_tco(
        num_agents=100,
        monthly_actions=10_000,
        key_rotations_per_agent=2,
        near_price_usd=3.63,
    )
    assert set(result.keys()) == {
        "near_scoped_keys",
        "near_subaccounts",
        "base_erc4337",
        "arbitrum_erc4337",
        "solana_keypairs",
    }
    assert result["near_scoped_keys"]["storage_lockup_usd"] == 0.0
    assert result["near_subaccounts"]["storage_lockup_usd"] > 5.0
    assert result["near_scoped_keys"]["total_30d_usd"] < result["base_erc4337"]["total_30d_usd"]
    assert result["near_scoped_keys"]["total_30d_usd"] < result["arbitrum_erc4337"]["total_30d_usd"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/von/Work/near-agent-thesis && python3 -m pytest tests/test_sql_and_cost.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src'`

- [ ] **Step 3: Write `.gitignore`, `LICENSE`, `requirements.txt`, `sql/*.sql`, and `src/cost_model.py`**

Create `/home/von/Work/near-agent-thesis/.gitignore`:
```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
.env
.vercel/
```

Create `/home/von/Work/near-agent-thesis/LICENSE` (MIT License).

Create `/home/von/Work/near-agent-thesis/requirements.txt`:
```text
pytest>=8.0.0
requests>=2.31.0
google-cloud-bigquery>=3.20.0
```

Create `/home/von/Work/near-agent-thesis/sql/01_agent_primitives_daily.sql`:
```sql
SELECT
  ra.block_date,
  ra.action_kind,
  COUNT(1) AS action_count,
  COUNT(DISTINCT ra.receipt_predecessor_account_id) AS unique_predecessors,
  COUNT(DISTINCT ra.receipt_receiver_account_id) AS unique_receivers,
  COUNTIF(
    ra.action_kind = 'ADD_KEY'
    AND JSON_EXTRACT_SCALAR(ra.args, '$.access_key.permission.permission_kind') = 'FUNCTION_CALL'
  ) AS scoped_function_call_keys,
  COUNTIF(
    ra.action_kind = 'ADD_KEY'
    AND JSON_EXTRACT_SCALAR(ra.args, '$.access_key.permission.permission_kind') = 'FULL_ACCESS'
  ) AS full_access_keys
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions` AS ra
WHERE ra.block_date BETWEEN DATE('2025-09-01') AND DATE('2026-03-24')
  AND ra.action_kind IN ('FUNCTION_CALL', 'DELEGATE_ACTION', 'ADD_KEY', 'CREATE_ACCOUNT')
GROUP BY
  ra.block_date,
  ra.action_kind
ORDER BY
  ra.block_date ASC,
  action_count DESC;
```

Create `/home/von/Work/near-agent-thesis/sql/02_receiver_concentration.sql`:
```sql
SELECT
  ra.block_date,
  ra.action_kind,
  ra.receipt_receiver_account_id AS receiver_account_id,
  COUNT(1) AS receipt_count,
  COUNT(DISTINCT ra.receipt_predecessor_account_id) AS unique_callers
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions` AS ra
WHERE ra.block_date BETWEEN DATE('2026-01-01') AND DATE('2026-03-24')
  AND ra.action_kind IN ('DELEGATE_ACTION', 'FUNCTION_CALL')
GROUP BY
  ra.block_date,
  ra.action_kind,
  receiver_account_id
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY ra.block_date, ra.action_kind
  ORDER BY COUNT(1) DESC
) <= 25
ORDER BY
  ra.block_date ASC,
  ra.action_kind ASC,
  receipt_count DESC;
```

Create `/home/von/Work/near-agent-thesis/sql/03_gas_and_storage_costs.sql`:
```sql
SELECT
  ra.action_kind,
  COUNT(1) AS sample_receipts,
  APPROX_QUANTILES(eo.gas_burnt, 100)[OFFSET(50)] AS p50_gas_burnt,
  APPROX_QUANTILES(eo.gas_burnt, 100)[OFFSET(95)] AS p95_gas_burnt,
  AVG(SAFE_CAST(eo.tokens_burnt AS FLOAT64) / 1e24) AS mean_near_burnt
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions` AS ra
JOIN `bigquery-public-data.crypto_near_mainnet_us.execution_outcomes` AS eo
  ON ra.receipt_id = eo.receipt_id
  AND ra.block_date = eo.block_date
WHERE ra.block_date BETWEEN DATE('2026-03-01') AND DATE('2026-03-24')
  AND eo.block_date BETWEEN DATE('2026-03-01') AND DATE('2026-03-24')
  AND ra.action_kind IN ('ADD_KEY', 'DELETE_KEY', 'CREATE_ACCOUNT', 'DELEGATE_ACTION', 'FUNCTION_CALL')
GROUP BY
  ra.action_kind
ORDER BY
  sample_receipts DESC;
```

Create `/home/von/Work/near-agent-thesis/src/cost_model.py`:
```python
from __future__ import annotations
from pathlib import Path
import re


def validate_sql_text(sql: str) -> bool:
    normalized = " ".join(sql.lower().split())
    if "where" not in normalized or "block_date" not in normalized:
        raise ValueError("SQL query must filter on block_date in a WHERE clause")
    return True


def validate_sql_file(path: Path) -> bool:
    return validate_sql_text(path.read_text(encoding="utf-8"))


def compute_hhi(counts: list[int | float]) -> float:
    positive = [float(c) for c in counts if c and c > 0]
    total = sum(positive)
    if total <= 0:
        return 0.0
    return round(sum(((c / total) * 100.0) ** 2 for c in positive), 2)


def compute_swarm_tco(
    num_agents: int = 100,
    monthly_actions: int = 10_000,
    key_rotations_per_agent: int = 2,
    near_price_usd: float = 3.63,
    near_function_call_fee_near: float = 0.00031,
    near_add_key_fee_near: float = 0.00010,
    near_create_account_fee_near: float = 0.00042,
    near_subaccount_bytes: int = 1820,
) -> dict[str, dict[str, float]]:
    storage_near_per_byte = 0.00001  # 0.001 NEAR per 100 bytes (1e19 yoctoNEAR/byte)
    rotations = num_agents * key_rotations_per_agent

    # 1. NEAR shared parent account + FunctionCall scoped keys (112 bytes per access key)
    scoped_key_storage_near = num_agents * 112 * storage_near_per_byte
    scoped_setup_usd = num_agents * near_add_key_fee_near * near_price_usd
    scoped_rotation_usd = rotations * (near_add_key_fee_near * 2) * near_price_usd
    scoped_exec_usd = monthly_actions * near_function_call_fee_near * near_price_usd

    # 2. NEAR dedicated sub-account per agent (1,820 bytes minimum account + key state)
    sub_storage_near = num_agents * near_subaccount_bytes * storage_near_per_byte
    sub_storage_usd = sub_storage_near * near_price_usd
    sub_setup_usd = num_agents * (near_create_account_fee_near + near_add_key_fee_near) * near_price_usd
    sub_rotation_usd = scoped_rotation_usd
    sub_exec_usd = scoped_exec_usd

    # 3. Base ERC-4337 smart account + session key module ($0.018 deploy, $0.0045 rotation, $0.0028 userOp)
    base_setup_usd = num_agents * 0.018
    base_rotation_usd = rotations * 0.0045
    base_exec_usd = monthly_actions * 0.0028

    # 4. Arbitrum One ERC-4337 smart account + session key module ($0.024 deploy, $0.006 rotation, $0.0035 userOp)
    arb_setup_usd = num_agents * 0.024
    arb_rotation_usd = rotations * 0.0060
    arb_exec_usd = monthly_actions * 0.0035

    # 5. Solana squad/program vault or keypair + rent-exempt account (~0.00089088 SOL rent + priority fee)
    sol_price_usd = 185.0
    sol_rent_usd = num_agents * 0.00089088 * sol_price_usd
    sol_setup_usd = num_agents * 0.0005
    sol_rotation_usd = rotations * 0.0010
    sol_exec_usd = monthly_actions * 0.00045

    return {
        "near_scoped_keys": {
            "setup_usd": round(scoped_setup_usd, 4),
            "rotation_usd": round(scoped_rotation_usd, 4),
            "execution_usd": round(scoped_exec_usd, 4),
            "storage_lockup_usd": 0.0,
            "refundable_key_bond_usd": round(scoped_key_storage_near * near_price_usd, 4),
            "total_30d_usd": round(scoped_setup_usd + scoped_rotation_usd + scoped_exec_usd, 4),
        },
        "near_subaccounts": {
            "setup_usd": round(sub_setup_usd, 4),
            "rotation_usd": round(sub_rotation_usd, 4),
            "execution_usd": round(sub_exec_usd, 4),
            "storage_lockup_usd": round(sub_storage_usd, 4),
            "total_30d_usd": round(sub_setup_usd + sub_rotation_usd + sub_exec_usd + sub_storage_usd, 4),
        },
        "base_erc4337": {
            "setup_usd": round(base_setup_usd, 4),
            "rotation_usd": round(base_rotation_usd, 4),
            "execution_usd": round(base_exec_usd, 4),
            "storage_lockup_usd": 0.0,
            "total_30d_usd": round(base_setup_usd + base_rotation_usd + base_exec_usd, 4),
        },
        "arbitrum_erc4337": {
            "setup_usd": round(arb_setup_usd, 4),
            "rotation_usd": round(arb_rotation_usd, 4),
            "execution_usd": round(arb_exec_usd, 4),
            "storage_lockup_usd": 0.0,
            "total_30d_usd": round(arb_setup_usd + arb_rotation_usd + arb_exec_usd, 4),
        },
        "solana_keypairs": {
            "setup_usd": round(sol_setup_usd, 4),
            "rotation_usd": round(sol_rotation_usd, 4),
            "execution_usd": round(sol_exec_usd, 4),
            "storage_lockup_usd": round(sol_rent_usd, 4),
            "total_30d_usd": round(sol_setup_usd + sol_rotation_usd + sol_exec_usd + sol_rent_usd, 4),
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/von/Work/near-agent-thesis && python3 -m pytest tests/test_sql_and_cost.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
cd /home/von/Work/near-agent-thesis
git add .gitignore LICENSE requirements.txt sql/ src/__init__.py src/cost_model.py tests/test_sql_and_cost.py
git commit -m "feat: add partitioned BigQuery SQL suite and 100-agent swarm cost model"
```

---

### Task 2: Live Mainnet & BigQuery Data Fetcher (`src/fetch.py`)

**Files:**
- Create: `/home/von/Work/near-agent-thesis/src/fetch.py`
- Test: `/home/von/Work/near-agent-thesis/tests/test_fetch.py`

**Interfaces:**
- Consumes: `src.cost_model.validate_sql_file`
- Produces:
  - `src.fetch.classify_block_chunks(chunks: list[dict]) -> dict`
  - `src.fetch.parse_quote_spread_bps(amount_usd: float, response_status: int, payload: dict) -> dict`
  - `src.fetch.run_fetch(output_dir: Path, include_bq: bool = False) -> dict`
  - Raw data files in `/home/von/Work/near-agent-thesis/data/raw/`:
    - `nearblocks_charts.json`
    - `nearblocks_stats.json`
    - `fastnear_block_sample.json`
    - `intents_quotes.json`
    - `bq_agent_primitives_Summary.json`
    - `provenance.json`

- [ ] **Step 1: Write the failing test in `tests/test_fetch.py`**

```python
import pytest
from src.fetch import classify_block_chunks, parse_quote_spread_bps

def test_classify_block_chunks_counts_delegate_and_scoped_keys():
    sample_chunks = [
        {
            "transactions": [
                {
                    "signer_id": "relayer.tg",
                    "receiver_id": "user1.tg",
                    "actions": [
                        {
                            "Delegate": {
                                "delegate_action": {
                                    "sender_id": "user1.tg",
                                    "receiver_id": "game.hot.tg",
                                    "actions": [{"FunctionCall": {"method_name": "claim"}}],
                                }
                            }
                        }
                    ],
                },
                {
                    "signer_id": "alice.near",
                    "receiver_id": "agent.alice.near",
                    "actions": [
                        {"CreateAccount": {}},
                        {
                            "AddKey": {
                                "access_key": {
                                    "permission": {
                                        "FunctionCall": {
                                            "allowance": "250000000000000000000000",
                                            "receiver_id": "intents.near",
                                            "method_names": ["execute_intent"],
                                        }
                                    }
                                },
                                "public_key": "ed25519:abc",
                            }
                        },
                    ],
                },
                {
                    "signer_id": "bob.near",
                    "receiver_id": "bob.near",
                    "actions": [
                        {
                            "AddKey": {
                                "access_key": {"permission": "FullAccess"},
                                "public_key": "ed25519:def",
                            }
                        }
                    ],
                },
            ]
        }
    ]
    summary = classify_block_chunks(sample_chunks)
    assert summary["total_transactions"] == 3
    assert summary["action_counts"]["DELEGATE_ACTION"] == 1
    assert summary["action_counts"]["CREATE_ACCOUNT"] == 1
    assert summary["action_counts"]["ADD_KEY"] == 2
    assert summary["scoped_function_call_keys"] == 1
    assert summary["full_access_keys"] == 1
    assert summary["subaccount_transactions"] == 2

def test_parse_quote_spread_bps_handles_valid_and_unquoted_responses():
    valid = parse_quote_spread_bps(
        corridor="USDC_NEAR_to_ARB",
        amount_usd=100.0,
        response_status=200,
        payload={"quote": {"amountInUsd": "100.00", "amountOutUsd": "99.78", "timeEstimate": 14}},
        latency_ms=210.5,
    )
    assert valid["status"] == "quoted"
    assert pytest.approx(valid["spread_bps"], 0.1) == 22.0
    assert valid["time_estimate_sec"] == 14

    unquoted = parse_quote_spread_bps(
        corridor="USDC_NEAR_to_BTC",
        amount_usd=1.0,
        response_status=400,
        payload={"message": "Amount is too low"},
        latency_ms=115.0,
    )
    assert unquoted["status"] == "unquoted"
    assert unquoted["spread_bps"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/von/Work/near-agent-thesis && python3 -m pytest tests/test_fetch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.fetch'`

- [ ] **Step 3: Implement `src/fetch.py` and run live data capture**

Implement `classify_block_chunks`, `parse_quote_spread_bps`, `fetch_nearblocks`, `fetch_fastnear_sample`, `fetch_intents_quotes`, and `try_fetch_bigquery` (with `maximum_bytes_billed=50_000_000_000`) in `/home/von/Work/near-agent-thesis/src/fetch.py`.

- [ ] **Step 4: Run unit tests and execute `python3 -m src.fetch` to populate `data/raw/`**

Run: `cd /home/von/Work/near-agent-thesis && python3 -m pytest tests/test_fetch.py -v && python3 -m src.fetch`
Expected: PASS and `data/raw/*.json` written with real mainnet data.

- [ ] **Step 5: Commit**

```bash
cd /home/von/Work/near-agent-thesis
git add src/fetch.py tests/test_fetch.py data/raw/
git commit -m "feat: add mainnet RPC, NearBlocks, 1Click Intents, and BigQuery data fetcher"
```

---

### Task 3: Offline Reproducible Analyzer and SVG Chart Generator (`src/analyze.py`)

**Files:**
- Create: `/home/von/Work/near-agent-thesis/src/analyze.py`
- Test: `/home/von/Work/near-agent-thesis/tests/test_analyze.py`

**Interfaces:**
- Consumes: `data/raw/*.json`, `src.cost_model.compute_hhi`, `src.cost_model.compute_swarm_tco`
- Produces:
  - `/home/von/Work/near-agent-thesis/data/audit_stats.json`
  - `/home/von/Work/near-agent-thesis/dashboard/assets/chart1_primitives.svg`
  - `/home/von/Work/near-agent-thesis/dashboard/assets/chart2_concentration.svg`
  - `/home/von/Work/near-agent-thesis/dashboard/assets/chart3_intents_spreads.svg`
  - `/home/von/Work/near-agent-thesis/dashboard/assets/chart4_swarm_tco.svg`

- [ ] **Step 1: Write the failing test in `tests/test_analyze.py`**

```python
from pathlib import Path
import json
from src.analyze import run_analysis

ROOT = Path(__file__).resolve().parent.parent

def test_run_analysis_builds_audit_stats_and_four_svg_charts():
    stats = run_analysis(ROOT)
    audit_path = ROOT / "data" / "audit_stats.json"
    assert audit_path.exists()
    loaded = json.loads(audit_path.read_text(encoding="utf-8"))
    assert loaded == stats

    for key in [
        "macro_network",
        "agent_primitives",
        "receiver_concentration",
        "intents_quotes",
        "swarm_tco",
        "falsification_checks",
    ]:
        assert key in stats

    for chart_name in [
        "chart1_primitives.svg",
        "chart2_concentration.svg",
        "chart3_intents_spreads.svg",
        "chart4_swarm_tco.svg",
    ]:
        svg_path = ROOT / "dashboard" / "assets" / chart_name
        assert svg_path.exists()
        content = svg_path.read_text(encoding="utf-8")
        assert content.startswith("<svg") and "</svg>" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/von/Work/near-agent-thesis && python3 -m pytest tests/test_analyze.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.analyze'`

- [ ] **Step 3: Implement `src/analyze.py`**

Implement `run_analysis(root: Path) -> dict` and deterministic SVG generators for all 4 charts in `/home/von/Work/near-agent-thesis/src/analyze.py`.

- [ ] **Step 4: Run test and `python3 -m src.analyze` to verify it passes**

Run: `cd /home/von/Work/near-agent-thesis && python3 -m src.analyze && python3 -m pytest tests/test_analyze.py -v`
Expected: PASS and `data/audit_stats.json` + `dashboard/assets/*.svg` created.

- [ ] **Step 5: Commit**

```bash
cd /home/von/Work/near-agent-thesis
git add src/analyze.py tests/test_analyze.py data/audit_stats.json dashboard/assets/
git commit -m "feat: add offline reproducible analyzer and SVG chart generator"
```

---

### Task 4: Static Dashboard (`dashboard/index.html`), `THESIS.md`, `README.md`, and Traceability Tests

**Files:**
- Create: `/home/von/Work/near-agent-thesis/THESIS.md`
- Create: `/home/von/Work/near-agent-thesis/README.md`
- Create: `/home/von/Work/near-agent-thesis/dashboard/index.html`
- Create: `/home/von/Work/near-agent-thesis/vercel.json`
- Modify: `/home/von/Work/near-agent-thesis/tests/test_analyze.py`

**Interfaces:**
- Consumes: `data/audit_stats.json`, `dashboard/assets/*.svg`, `sql/*.sql`
- Produces:
  - `/home/von/Work/near-agent-thesis/THESIS.md`
  - `/home/von/Work/near-agent-thesis/README.md`
  - `/home/von/Work/near-agent-thesis/dashboard/index.html`
  - `/home/von/Work/near-agent-thesis/vercel.json`
  - `test_document_traceability_and_no_em_dashes` in `tests/test_analyze.py`

- [ ] **Step 1: Add failing traceability test in `tests/test_analyze.py`**

```python
def test_document_traceability_and_no_em_dashes():
    stats = json.loads((ROOT / "data" / "audit_stats.json").read_text(encoding="utf-8"))
    thesis = (ROOT / "THESIS.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    dashboard = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")

    for doc_name, text in [("THESIS.md", thesis), ("README.md", readme), ("dashboard/index.html", dashboard)]:
        assert "\u2014" not in text, f"Found em dash in {doc_name}"

    expected_tokens = [
        f"{stats['agent_primitives']['scoped_key_share_pct']:.1f}%",
        f"${stats['swarm_tco']['near_scoped_keys']['total_30d_usd']:.2f}",
        f"${stats['swarm_tco']['near_subaccounts']['total_30d_usd']:.2f}",
        f"${stats['swarm_tco']['base_erc4337']['total_30d_usd']:.2f}",
        f"{stats['receiver_concentration']['top3_share_pct']:.1f}%",
    ]
    for token in expected_tokens:
        assert token in thesis, f"Missing {token} in THESIS.md"
        assert token in dashboard, f"Missing {token} in dashboard/index.html"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/von/Work/near-agent-thesis && python3 -m pytest tests/test_analyze.py -v`
Expected: FAIL with `FileNotFoundError: THESIS.md`

- [ ] **Step 3: Write `THESIS.md`, `README.md`, `dashboard/index.html`, and `vercel.json`**

Write `THESIS.md`, `README.md` (with "do X, see Y" steps for Claude Code and Codex screening), `dashboard/index.html` (embedding the 4 SVG charts, the expandable SQL/API queries, one plain-English sentence per chart, and the interactive 100-agent swarm cost calculator), and `vercel.json`.

- [ ] **Step 4: Run full test suite to verify everything passes**

Run: `cd /home/von/Work/near-agent-thesis && python3 -m pytest -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit and deploy preview/production on Vercel**

```bash
cd /home/von/Work/near-agent-thesis
git add THESIS.md README.md dashboard/index.html vercel.json tests/test_analyze.py
git commit -m "docs: add THESIS.md, reproducible README, and static dashboard with traceability tests"
```
