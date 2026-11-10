from __future__ import annotations
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
import requests
from src.cost_model import validate_sql_file, compute_hhi

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

FASTNEAR_RPC = "https://free.rpc.fastnear.com"
NEARBLOCKS_CHARTS = "https://api.nearblocks.io/v1/charts"
NEARBLOCKS_STATS = "https://api.nearblocks.io/v1/stats"
ONECLICK_TOKENS = "https://1click.chaindefuser.com/v0/tokens"
ONECLICK_QUOTE = "https://1click.chaindefuser.com/v0/quote"

CONSUMER_RELAYER_CONTRACTS = {
    "game.hot.tg",
    "token.sweat",
    "sweat_welcome.near",
    "claim.sweat",
    "wallet.kaiching",
    "learn.kaiching",
    "earn.kaiching",
}


def classify_block_chunks(chunks: list[dict]) -> dict:
    action_counts: Counter[str] = Counter()
    receiver_counts: Counter[str] = Counter()
    delegate_receiver_counts: Counter[str] = Counter()
    signers: set[str] = set()
    scoped_keys = 0
    full_access_keys = 0
    subaccount_txs = 0
    total_txs = 0

    for chunk in chunks:
        for tx in chunk.get("transactions", []):
            total_txs += 1
            signer_id = tx.get("signer_id", "")
            receiver_id = tx.get("receiver_id", "")
            signers.add(signer_id)
            receiver_counts[receiver_id] += 1
            is_subaccount = receiver_id.count(".") >= 2 or signer_id.count(".") >= 2

            for action in tx.get("actions", []):
                if isinstance(action, str):
                    if action == "CreateAccount":
                        action_counts["CREATE_ACCOUNT"] += 1
                    else:
                        action_counts[action.upper()] += 1
                    continue

                if "Delegate" in action:
                    action_counts["DELEGATE_ACTION"] += 1
                    del_act = action["Delegate"].get("delegate_action", {})
                    inner_receiver = del_act.get("receiver_id", receiver_id)
                    if inner_receiver.count(".") >= 2:
                        is_subaccount = True
                    delegate_receiver_counts[inner_receiver] += 1
                    receiver_counts[inner_receiver] += 1
                    for inner_act in del_act.get("actions", []):
                        if isinstance(inner_act, dict) and "AddKey" in inner_act:
                            action_counts["ADD_KEY"] += 1
                            perm = inner_act["AddKey"].get("access_key", {}).get("permission")
                            if isinstance(perm, dict) and "FunctionCall" in perm:
                                scoped_keys += 1
                            elif perm == "FullAccess" or (isinstance(perm, dict) and "FullAccess" in perm):
                                full_access_keys += 1
                elif "FunctionCall" in action:
                    action_counts["FUNCTION_CALL"] += 1
                elif "CreateAccount" in action:
                    action_counts["CREATE_ACCOUNT"] += 1
                elif "DeleteKey" in action:
                    action_counts["DELETE_KEY"] += 1
                elif "Transfer" in action:
                    action_counts["TRANSFER"] += 1
                elif "AddKey" in action:
                    action_counts["ADD_KEY"] += 1
                    perm = action["AddKey"].get("access_key", {}).get("permission")
                    if isinstance(perm, dict) and "FunctionCall" in perm:
                        scoped_keys += 1
                    elif perm == "FullAccess" or (isinstance(perm, dict) and "FullAccess" in perm):
                        full_access_keys += 1

            if is_subaccount:
                subaccount_txs += 1

    top_receivers = [
        {"receiver_id": rec, "count": cnt}
        for rec, cnt in receiver_counts.most_common(25)
    ]
    return {
        "total_transactions": total_txs,
        "unique_signers": len(signers),
        "action_counts": dict(action_counts),
        "scoped_function_call_keys": scoped_keys,
        "full_access_keys": full_access_keys,
        "subaccount_transactions": subaccount_txs,
        "top_receivers": top_receivers,
        "delegate_receivers": dict(delegate_receiver_counts.most_common(25)),
        "receiver_hhi": compute_hhi([cnt for _, cnt in receiver_counts.items()]),
    }


def parse_quote_spread_bps(
    corridor: str,
    amount_usd: float,
    response_status: int,
    payload: dict,
    latency_ms: float,
) -> dict:
    if response_status in (200, 201) and isinstance(payload, dict) and "quote" in payload:
        q = payload["quote"]
        in_usd = float(q.get("amountInUsd") or amount_usd)
        out_usd = float(q.get("amountOutUsd") or 0.0)
        if in_usd > 0 and out_usd > 0:
            spread_bps = round(max(0.0, ((in_usd - out_usd) / in_usd) * 10000.0), 2)
            return {
                "corridor": corridor,
                "amount_usd": amount_usd,
                "status": "quoted",
                "amount_in_usd": round(in_usd, 4),
                "amount_out_usd": round(out_usd, 4),
                "spread_bps": spread_bps,
                "time_estimate_sec": int(q.get("timeEstimate", 0)),
                "latency_ms": round(latency_ms, 1),
            }
    return {
        "corridor": corridor,
        "amount_usd": amount_usd,
        "status": "unquoted",
        "amount_in_usd": amount_usd,
        "amount_out_usd": None,
        "spread_bps": None,
        "time_estimate_sec": None,
        "latency_ms": round(latency_ms, 1),
        "error": payload.get("message", f"HTTP {response_status}") if isinstance(payload, dict) else str(payload),
    }


def rpc_call(method: str, params: dict) -> dict:
    resp = requests.post(
        FASTNEAR_RPC,
        json={"jsonrpc": "2.0", "id": "1", "method": method, "params": params},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["result"]


def audit_account_access_keys(account_ids: list[str]) -> dict:
    total_fc = 0
    total_fa = 0
    per_account: list[dict] = []
    for acct in sorted(set(account_ids)):
        if not acct:
            continue
        try:
            res = rpc_call(
                "query",
                {"request_type": "view_access_key_list", "finality": "final", "account_id": acct},
            )
            keys = res.get("keys", [])
            fc = sum(
                1
                for k in keys
                if isinstance(k.get("access_key", {}).get("permission"), dict)
                and "FunctionCall" in k["access_key"]["permission"]
            )
            fa = sum(
                1
                for k in keys
                if k.get("access_key", {}).get("permission") == "FullAccess"
            )
            total_fc += fc
            total_fa += fa
            per_account.append(
                {
                    "account_id": acct,
                    "function_call_keys": fc,
                    "full_access_keys": fa,
                    "total_keys": fc + fa,
                }
            )
        except Exception:
            continue
    return {
        "accounts_inspected": len(per_account),
        "total_function_call_keys": total_fc,
        "total_full_access_keys": total_fa,
        "per_account": per_account,
    }


def fetch_fastnear_sample(num_blocks: int = 24, step_blocks: int = 1) -> dict:
    latest = rpc_call("block", {"finality": "final"})
    latest_height = int(latest["header"]["height"])
    intents_acct = rpc_call(
        "query",
        {"request_type": "view_account", "finality": "final", "account_id": "intents.near"},
    )

    all_chunks: list[dict] = []
    sampled_heights: list[int] = []
    discovered_accounts: set[str] = {
        "intents.near",
        "v2.ref-finance.near",
        "omni.bridge.near",
        "v1.signer",
        "social.near",
    }
    try:
        nb_txns = requests.get("https://api.nearblocks.io/v1/txns?page=1&per_page=25", timeout=15).json()
        for tx in nb_txns.get("txns", []):
            for field in ("signer_account_id", "receiver_account_id", "predecessor_account_id"):
                val = tx.get(field)
                if val and (val.endswith(".near") or val.endswith(".tg") or val.endswith(".sweat")):
                    discovered_accounts.add(val)
    except Exception:
        pass

    for idx in range(num_blocks):
        target_height = latest_height - (idx * step_blocks)
        try:
            blk = rpc_call("block", {"block_id": target_height})
        except Exception:
            blk = latest if idx == 0 else None
        if not blk:
            continue
        sampled_heights.append(int(blk["header"]["height"]))
        for ch_hdr in blk.get("chunks", []):
            if int(ch_hdr.get("gas_used", 0)) == 0:
                continue
            try:
                ch = rpc_call("chunk", {"chunk_id": ch_hdr["chunk_hash"]})
                all_chunks.append(ch)
                for tx in ch.get("transactions", []):
                    for field in ("signer_id", "receiver_id"):
                        val = tx.get(field, "")
                        if val.endswith(".near") or val.endswith(".tg") or val.endswith(".sweat"):
                            discovered_accounts.add(val)
            except Exception:
                continue

    classified = classify_block_chunks(all_chunks)
    key_audit = audit_account_access_keys(list(discovered_accounts)[:35])
    classified["scoped_function_call_keys"] += key_audit["total_function_call_keys"]
    classified["full_access_keys"] += key_audit["total_full_access_keys"]
    classified["access_key_audit"] = key_audit
    classified["latest_block_height"] = latest_height
    classified["sampled_block_heights"] = sampled_heights
    classified["sampled_chunks_count"] = len(all_chunks)
    classified["intents_contract_storage_bytes"] = int(intents_acct.get("storage_usage", 0))
    classified["intents_contract_balance_near"] = round(int(intents_acct.get("amount", "0")) / 1e24, 2)
    return classified


def fetch_nearblocks() -> tuple[dict, dict]:
    charts = requests.get(NEARBLOCKS_CHARTS, timeout=25).json()
    stats = requests.get(NEARBLOCKS_STATS, timeout=25).json()
    return charts, stats


def fetch_intents_quotes() -> dict:
    tokens = requests.get(ONECLICK_TOKENS, timeout=20).json()
    token_map = {(t.get("symbol"), t.get("blockchain")): t for t in tokens}
    usdc_near = token_map[("USDC", "near")]
    wnear = token_map[("wNEAR", "near")]
    near_price = float(wnear.get("price") or 3.56)

    corridors = [
        {
            "name": "USDC_NEAR_to_ARB",
            "label": "USDC (NEAR -> Arbitrum)",
            "origin": usdc_near["assetId"],
            "origin_decimals": 6,
            "origin_price": 1.0,
            "dest": token_map[("USDC", "arb")]["assetId"],
            "recipient": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        },
        {
            "name": "USDC_NEAR_to_BASE",
            "label": "USDC (NEAR -> Base)",
            "origin": usdc_near["assetId"],
            "origin_decimals": 6,
            "origin_price": 1.0,
            "dest": token_map[("USDC", "base")]["assetId"],
            "recipient": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        },
        {
            "name": "USDC_NEAR_to_SOL",
            "label": "USDC (NEAR -> Solana)",
            "origin": usdc_near["assetId"],
            "origin_decimals": 6,
            "origin_price": 1.0,
            "dest": token_map[("USDC", "sol")]["assetId"],
            "recipient": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        },
        {
            "name": "wNEAR_to_ARB_USDC",
            "label": "wNEAR -> Arbitrum USDC",
            "origin": wnear["assetId"],
            "origin_decimals": 24,
            "origin_price": near_price,
            "dest": token_map[("USDC", "arb")]["assetId"],
            "recipient": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        },
    ]

    sizes_usd = [1.0, 10.0, 100.0, 1000.0, 10000.0]
    deadline = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    quotes: list[dict] = []

    for corr in corridors:
        for amt_usd in sizes_usd:
            token_units = amt_usd / corr["origin_price"]
            raw_amount = str(max(1, int(round(token_units * (10 ** corr["origin_decimals"])))))
            req_body = {
                "dry": True,
                "swapType": "EXACT_INPUT",
                "slippageTolerance": 100,
                "originAsset": corr["origin"],
                "depositType": "ORIGIN_CHAIN",
                "destinationAsset": corr["dest"],
                "amount": raw_amount,
                "refundTo": "intents.near",
                "refundType": "ORIGIN_CHAIN",
                "recipient": corr["recipient"],
                "recipientType": "DESTINATION_CHAIN",
                "deadline": deadline,
            }
            t0 = time.perf_counter()
            resp = requests.post(ONECLICK_QUOTE, json=req_body, timeout=20)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            try:
                payload = resp.json()
            except Exception:
                payload = {"message": resp.text[:200]}
            parsed = parse_quote_spread_bps(
                corridor=corr["name"],
                amount_usd=amt_usd,
                response_status=resp.status_code,
                payload=payload,
                latency_ms=latency_ms,
            )
            parsed["corridor_label"] = corr["label"]
            quotes.append(parsed)
            time.sleep(0.15)

    return {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "supported_tokens_count": len(tokens),
        "near_price_usd": near_price,
        "quotes": quotes,
    }


def try_fetch_bigquery(sql_dir: Path) -> dict:
    sql_files = sorted(sql_dir.glob("*.sql"))
    for path in sql_files:
        validate_sql_file(path)

    status: dict = {
        "dataset": "bigquery-public-data.crypto_near_mainnet_us",
        "maximum_bytes_billed": 50_000_000_000,
        "lake_deprecation_date": "2026-03-24",
        "validated_sql_files": [p.name for p in sql_files],
        "executed_live_bq": False,
        "rows_by_query": {},
    }
    try:
        from google.cloud import bigquery  # type: ignore

        client = bigquery.Client()
        for path in sql_files:
            job_config = bigquery.QueryJobConfig(maximum_bytes_billed=50_000_000_000)
            query_job = client.query(path.read_text(encoding="utf-8"), job_config=job_config)
            rows = [dict(r) for r in query_job.result()]
            status["rows_by_query"][path.name] = rows
        status["executed_live_bq"] = True
    except Exception as exc:
        status["note"] = (
            "SQL queries validated for block_date partition filters. "
            f"BigQuery ADC not active in current shell ({exc.__class__.__name__}); "
            "live 2026 mainnet metrics pulled via FastNEAR RPC, NearBlocks API, and 1Click API."
        )
    return status


def run_fetch(output_dir: Path = RAW_DIR) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    charts, stats = fetch_nearblocks()
    # Keep the last 365 days of daily charts so the repo stays lightweight and fast
    daily_rows = charts.get("charts", [])[-365:]
    (output_dir / "nearblocks_charts.json").write_text(
        json.dumps({"charts": daily_rows}, indent=2), encoding="utf-8"
    )
    (output_dir / "nearblocks_stats.json").write_text(
        json.dumps(stats, indent=2), encoding="utf-8"
    )

    fastnear = fetch_fastnear_sample(num_blocks=24, step_blocks=1)
    (output_dir / "fastnear_block_sample.json").write_text(
        json.dumps(fastnear, indent=2), encoding="utf-8"
    )

    intents = fetch_intents_quotes()
    (output_dir / "intents_quotes.json").write_text(
        json.dumps(intents, indent=2), encoding="utf-8"
    )

    bq_status = try_fetch_bigquery(ROOT / "sql")
    (output_dir / "bq_status.json").write_text(
        json.dumps(bq_status, indent=2, default=str), encoding="utf-8"
    )

    provenance = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": [
            NEARBLOCKS_CHARTS,
            NEARBLOCKS_STATS,
            FASTNEAR_RPC,
            ONECLICK_TOKENS,
            ONECLICK_QUOTE,
            "bigquery-public-data.crypto_near_mainnet_us",
        ],
        "nearblocks_days_saved": len(daily_rows),
        "fastnear_latest_block": fastnear["latest_block_height"],
        "fastnear_sampled_transactions": fastnear["total_transactions"],
        "intents_quotes_count": len(intents["quotes"]),
    }
    (output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    return provenance


if __name__ == "__main__":
    prov = run_fetch()
    print(json.dumps(prov, indent=2))
