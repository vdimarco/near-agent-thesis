from __future__ import annotations
from pathlib import Path


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
