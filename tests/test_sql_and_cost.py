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
