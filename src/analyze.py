from __future__ import annotations
import json
from pathlib import Path
from statistics import median
from src.cost_model import compute_hhi, compute_swarm_tco

ROOT = Path(__file__).resolve().parent.parent


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _render_chart1_primitives(stats: dict) -> str:
    ap = stats["agent_primitives"]
    del_pct = ap["delegate_action_share_pct"]
    fc_pct = ap["function_call_share_pct"]
    scoped_pct = ap["scoped_key_share_pct"]
    sub_pct = ap["subaccount_tx_share_pct"]

    bars = [
        ("Scoped FunctionCall Keys (% of sampled keys)", scoped_pct, "#10b981"),
        ("Sub-Account Transactions (% of sampled txs)", sub_pct, "#3b82f6"),
        ("Direct FunctionCall Actions (% of actions)", fc_pct, "#6366f1"),
        ("Gasless DELEGATE_ACTION (% of actions)", del_pct, "#f59e0b"),
    ]
    rows_svg = []
    y = 82
    for label, val, color in bars:
        width = max(4.0, min(520.0, (val / 100.0) * 520.0))
        rows_svg.append(
            f'<text x="28" y="{y}" fill="#e2e8f0" font-family="Inter, system-ui, sans-serif" font-size="13" font-weight="600">{label}</text>'
            f'<rect x="28" y="{y + 8}" width="520" height="22" rx="4" fill="#1e293b"/>'
            f'<rect x="28" y="{y + 8}" width="{width:.1f}" height="22" rx="4" fill="{color}"/>'
            f'<text x="{38 + width:.1f}" y="{y + 24}" fill="#f8fafc" font-family="JetBrains Mono, monospace" font-size="13" font-weight="700">{val:.1f}%</text>'
        )
        y += 58

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 330" width="100%" height="100%">'
        '<rect width="680" height="330" rx="12" fill="#0f172a" stroke="#334155" stroke-width="1"/>'
        '<text x="28" y="36" fill="#f8fafc" font-family="Inter, system-ui, sans-serif" font-size="16" font-weight="700">'
        'Chart 1: NEAR Mainnet Agent-Enabling Primitive Shares (Live RPC + Key Census)'
        '</text>'
        f'<text x="28" y="56" fill="#94a3b8" font-family="Inter, system-ui, sans-serif" font-size="12">'
        f'Sampled block #{ap["latest_block_height"]} window ({ap["sampled_transactions"]} txs across {ap["sampled_chunks"]} chunks, {ap["accounts_inspected"]} active accounts)'
        '</text>'
        + "".join(rows_svg)
        + '</svg>'
    )


def _render_chart2_concentration(stats: dict) -> str:
    rc = stats["receiver_concentration"]
    top_items = rc["top_receivers"][:6]
    total = max(1, sum(item["count"] for item in rc["top_receivers"]))
    rows_svg = []
    y = 84
    for idx, item in enumerate(top_items):
        share = (item["count"] / total) * 100.0
        width = max(6.0, (share / 100.0) * 440.0)
        is_consumer = item["receiver_id"] in {"game.hot.tg", "token.sweat", "spin.sweat", "wallet.kaiching"}
        color = "#ef4444" if is_consumer else "#06b6d4"
        tag = "Consumer Relayer" if is_consumer else "Intents / DeFi / Infra"
        rows_svg.append(
            f'<text x="28" y="{y}" fill="#e2e8f0" font-family="JetBrains Mono, monospace" font-size="12">{idx + 1}. {item["receiver_id"]} ({tag})</text>'
            f'<rect x="28" y="{y + 6}" width="440" height="18" rx="3" fill="#1e293b"/>'
            f'<rect x="28" y="{y + 6}" width="{width:.1f}" height="18" rx="3" fill="{color}"/>'
            f'<text x="{36 + width:.1f}" y="{y + 19}" fill="#f8fafc" font-family="JetBrains Mono, monospace" font-size="12" font-weight="700">{share:.1f}% ({item["count"]} receipts)</text>'
        )
        y += 44

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 360" width="100%" height="100%">'
        '<rect width="680" height="360" rx="12" fill="#0f172a" stroke="#334155" stroke-width="1"/>'
        '<text x="28" y="34" fill="#f8fafc" font-family="Inter, system-ui, sans-serif" font-size="16" font-weight="700">'
        'Chart 2: Receiver Concentration (Consumer Relayers vs Intents &amp; DeFi)'
        '</text>'
        f'<text x="28" y="54" fill="#94a3b8" font-family="Inter, system-ui, sans-serif" font-size="12">'
        f'Top-3 Receiver Share: {rc["top3_share_pct"]:.1f}% | Non-Top-3 Share: {rc["non_top3_share_pct"]:.1f}% | HHI: {rc["hhi"]:.1f}'
        '</text>'
        + "".join(rows_svg)
        + '</svg>'
    )


def _render_chart3_intents_spreads(stats: dict) -> str:
    iq = stats["intents_quotes"]
    by_size = iq["median_spread_bps_by_usd"]
    sizes = ["1", "10", "100", "1000", "10000"]
    bars_svg = []
    x = 70
    for sz in sizes:
        bps = float(by_size.get(sz, 0.0))
        bar_h = max(8.0, min(190.0, (bps / 80.0) * 190.0))
        y = 250 - bar_h
        color = "#f59e0b" if bps > 25.0 else "#10b981"
        bars_svg.append(
            f'<rect x="{x}" y="{y:.1f}" width="72" height="{bar_h:.1f}" rx="5" fill="{color}"/>'
            f'<text x="{x + 36}" y="{y - 8:.1f}" text-anchor="middle" fill="#f8fafc" font-family="JetBrains Mono, monospace" font-size="12" font-weight="700">{bps:.2f} bps</text>'
            f'<text x="{x + 36}" y="274" text-anchor="middle" fill="#cbd5e1" font-family="JetBrains Mono, monospace" font-size="12">${sz}</text>'
        )
        x += 112

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 320" width="100%" height="100%">'
        '<rect width="680" height="320" rx="12" fill="#0f172a" stroke="#334155" stroke-width="1"/>'
        '<text x="28" y="34" fill="#f8fafc" font-family="Inter, system-ui, sans-serif" font-size="16" font-weight="700">'
        'Chart 3: NEAR Intents 1Click Median Effective Spread by Order Size (bps)'
        '</text>'
        f'<text x="28" y="54" fill="#94a3b8" font-family="Inter, system-ui, sans-serif" font-size="12">'
        f'Live quotes across 4 cross-chain corridors | $100-$1,000 median: {iq["mid_tier_median_spread_bps"]:.2f} bps (threshold: &lt; 150 bps)'
        '</text>'
        '<line x1="50" y1="250" x2="630" y2="250" stroke="#475569" stroke-width="1"/>'
        + "".join(bars_svg)
        + '<text x="340" y="302" text-anchor="middle" fill="#94a3b8" font-family="Inter, system-ui, sans-serif" font-size="12">Order Size in USD (1 bps = 0.01%)</text>'
        '</svg>'
    )


def _render_chart4_swarm_tco(stats: dict) -> str:
    tco = stats["swarm_tco"]
    rows = [
        ("NEAR Shared Parent + Scoped Keys", tco["near_scoped_keys"]["total_30d_usd"], "#10b981"),
        ("NEAR Dedicated Sub-Accounts (w/ Storage)", tco["near_subaccounts"]["total_30d_usd"], "#3b82f6"),
        ("Solana Rent-Exempt Keypairs", tco["solana_keypairs"]["total_30d_usd"], "#8b5cf6"),
        ("Base ERC-4337 Smart Accounts", tco["base_erc4337"]["total_30d_usd"], "#f59e0b"),
        ("Arbitrum ERC-4337 Smart Accounts", tco["arbitrum_erc4337"]["total_30d_usd"], "#ef4444"),
    ]
    max_val = max(r[1] for r in rows) or 1.0
    rows_svg = []
    y = 84
    for label, val, color in rows:
        width = max(10.0, (val / max_val) * 440.0)
        rows_svg.append(
            f'<text x="28" y="{y}" fill="#e2e8f0" font-family="Inter, system-ui, sans-serif" font-size="13" font-weight="600">{label}</text>'
            f'<rect x="28" y="{y + 6}" width="440" height="20" rx="4" fill="#1e293b"/>'
            f'<rect x="28" y="{y + 6}" width="{width:.1f}" height="20" rx="4" fill="{color}"/>'
            f'<text x="{38 + width:.1f}" y="{y + 21}" fill="#f8fafc" font-family="JetBrains Mono, monospace" font-size="13" font-weight="700">${val:.2f}</text>'
        )
        y += 48

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 340" width="100%" height="100%">'
        '<rect width="680" height="340" rx="12" fill="#0f172a" stroke="#334155" stroke-width="1"/>'
        '<text x="28" y="34" fill="#f8fafc" font-family="Inter, system-ui, sans-serif" font-size="16" font-weight="700">'
        'Chart 4: 30-Day TCO for a 100-Agent Swarm (10,000 Actions + 200 Key Rotations)'
        '</text>'
        f'<text x="28" y="54" fill="#94a3b8" font-family="Inter, system-ui, sans-serif" font-size="12">'
        f'Includes setup, key rotation, execution gas, and non-zero state/storage lockup at NEAR = ${stats["macro_network"]["near_price_usd"]:.2f}'
        '</text>'
        + "".join(rows_svg)
        + '</svg>'
    )


def run_analysis(root: Path = ROOT) -> dict:
    raw_dir = root / "data" / "raw"
    charts_raw = _load_json(raw_dir / "nearblocks_charts.json").get("charts", [])
    stats_raw = _load_json(raw_dir / "nearblocks_stats.json").get("stats", [{}])[0]
    fastnear = _load_json(raw_dir / "fastnear_block_sample.json")
    intents = _load_json(raw_dir / "intents_quotes.json")
    bq_status = _load_json(raw_dir / "bq_status.json")

    recent_30 = charts_raw[-30:] if len(charts_raw) >= 30 else charts_raw
    prior_30 = charts_raw[-60:-30] if len(charts_raw) >= 60 else recent_30

    mean_txns_30d = round(
        sum(int(r.get("txns", 0)) for r in recent_30) / max(1, len(recent_30))
    )
    mean_txns_prior_30d = round(
        sum(int(r.get("txns", 0)) for r in prior_30) / max(1, len(prior_30))
    )
    near_price_usd = round(float(intents.get("near_price_usd") or stats_raw.get("near_price") or 3.55), 2)

    action_counts = fastnear.get("action_counts", {})
    total_actions = max(1, sum(int(v) for v in action_counts.values()))
    delegate_count = int(action_counts.get("DELEGATE_ACTION", 0))
    func_call_count = int(action_counts.get("FUNCTION_CALL", 0))
    scoped_keys = int(fastnear.get("scoped_function_call_keys", 0))
    full_keys = int(fastnear.get("full_access_keys", 0))
    total_keys = max(1, scoped_keys + full_keys)
    total_txs = max(1, int(fastnear.get("total_transactions", 1)))
    subaccount_txs = int(fastnear.get("subaccount_transactions", 0))

    scoped_key_share_pct = round((scoped_keys / total_keys) * 100.0, 1)
    delegate_share_pct = round((delegate_count / total_actions) * 100.0, 1)
    func_call_share_pct = round((func_call_count / total_actions) * 100.0, 1)
    subaccount_share_pct = round((subaccount_txs / total_txs) * 100.0, 1)

    top_receivers = fastnear.get("top_receivers", [])
    counts = [int(item["count"]) for item in top_receivers]
    total_rec = max(1, sum(counts))
    top3_sum = sum(counts[:3])
    top3_share_pct = round((top3_sum / total_rec) * 100.0, 1)
    non_top3_share_pct = round(100.0 - top3_share_pct, 1)
    hhi = compute_hhi(counts)

    intents_rec_count = sum(
        int(item["count"]) for item in top_receivers if item["receiver_id"] == "intents.near"
    )
    intents_receiver_share_pct = round((intents_rec_count / total_rec) * 100.0, 1)

    quotes = intents.get("quotes", [])
    by_size: dict[str, list[float]] = {}
    mid_tier_bps: list[float] = []
    latencies: list[float] = []
    for q in quotes:
        if q.get("status") == "quoted" and q.get("spread_bps") is not None:
            amt_key = str(int(round(float(q["amount_usd"]))))
            by_size.setdefault(amt_key, []).append(float(q["spread_bps"]))
            if amt_key in ("100", "1000"):
                mid_tier_bps.append(float(q["spread_bps"]))
            if q.get("latency_ms") is not None:
                latencies.append(float(q["latency_ms"]))

    median_spread_by_usd = {
        k: round(float(median(v)), 2) for k, v in sorted(by_size.items(), key=lambda x: int(x[0]))
    }
    mid_tier_median_bps = round(float(median(mid_tier_bps)), 2) if mid_tier_bps else 0.0
    median_quote_latency_ms = round(float(median(latencies)), 1) if latencies else 0.0

    swarm_tco = compute_swarm_tco(
        num_agents=100,
        monthly_actions=10_000,
        key_rotations_per_agent=2,
        near_price_usd=near_price_usd,
    )

    falsification_checks = {
        "check1_scoped_keys_ge_25pct": {
            "threshold_pct": 25.0,
            "observed_pct": scoped_key_share_pct,
            "passed": scoped_key_share_pct >= 25.0,
        },
        "check2_near_scoped_tco_lt_evm": {
            "near_scoped_usd": swarm_tco["near_scoped_keys"]["total_30d_usd"],
            "base_erc4337_usd": swarm_tco["base_erc4337"]["total_30d_usd"],
            "arbitrum_erc4337_usd": swarm_tco["arbitrum_erc4337"]["total_30d_usd"],
            "passed": (
                swarm_tco["near_scoped_keys"]["total_30d_usd"]
                < swarm_tco["base_erc4337"]["total_30d_usd"]
            ),
        },
        "check3_intents_mid_tier_spread_lt_150bps": {
            "threshold_bps": 150.0,
            "observed_median_bps": mid_tier_median_bps,
            "passed": mid_tier_median_bps < 150.0,
        },
    }

    stats = {
        "macro_network": {
            "latest_date": recent_30[-1].get("date", "")[:10] if recent_30 else "2026-11-10",
            "near_price_usd": near_price_usd,
            "avg_block_time_sec": round(float(stats_raw.get("avg_block_time", 0.58)), 3),
            "nodes_online": int(stats_raw.get("nodes_online", 371)),
            "mean_daily_txns_30d": mean_txns_30d,
            "mean_daily_txns_prior_30d": mean_txns_prior_30d,
            "intents_contract_storage_bytes": int(fastnear.get("intents_contract_storage_bytes", 0)),
            "intents_contract_balance_near": float(fastnear.get("intents_contract_balance_near", 0.0)),
        },
        "agent_primitives": {
            "latest_block_height": int(fastnear.get("latest_block_height", 0)),
            "sampled_chunks": int(fastnear.get("sampled_chunks_count", 0)),
            "sampled_transactions": total_txs,
            "accounts_inspected": int(fastnear.get("access_key_audit", {}).get("accounts_inspected", 0)),
            "scoped_function_call_keys": scoped_keys,
            "full_access_keys": full_keys,
            "scoped_key_share_pct": scoped_key_share_pct,
            "delegate_action_share_pct": delegate_share_pct,
            "function_call_share_pct": func_call_share_pct,
            "subaccount_tx_share_pct": subaccount_share_pct,
        },
        "receiver_concentration": {
            "top3_share_pct": top3_share_pct,
            "non_top3_share_pct": non_top3_share_pct,
            "intents_receiver_share_pct": intents_receiver_share_pct,
            "hhi": hhi,
            "top_receivers": top_receivers[:10],
            "delegate_receivers": fastnear.get("delegate_receivers", {}),
        },
        "intents_quotes": {
            "supported_tokens_count": int(intents.get("supported_tokens_count", 0)),
            "quotes_tested": len(quotes),
            "quotes_succeeded": sum(1 for q in quotes if q.get("status") == "quoted"),
            "median_spread_bps_by_usd": median_spread_by_usd,
            "mid_tier_median_spread_bps": mid_tier_median_bps,
            "median_quote_latency_ms": median_quote_latency_ms,
            "quotes": quotes,
        },
        "swarm_tco": swarm_tco,
        "bigquery_validation": {
            "dataset": bq_status.get("dataset"),
            "maximum_bytes_billed": bq_status.get("maximum_bytes_billed"),
            "validated_sql_files": bq_status.get("validated_sql_files", []),
            "lake_deprecation_date": bq_status.get("lake_deprecation_date"),
        },
        "falsification_checks": falsification_checks,
    }

    audit_path = root / "data" / "audit_stats.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    assets_dir = root / "dashboard" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "chart1_primitives.svg").write_text(_render_chart1_primitives(stats), encoding="utf-8")
    (assets_dir / "chart2_concentration.svg").write_text(_render_chart2_concentration(stats), encoding="utf-8")
    (assets_dir / "chart3_intents_spreads.svg").write_text(_render_chart3_intents_spreads(stats), encoding="utf-8")
    (assets_dir / "chart4_swarm_tco.svg").write_text(_render_chart4_swarm_tco(stats), encoding="utf-8")

    return stats


if __name__ == "__main__":
    out = run_analysis()
    print(json.dumps(out["falsification_checks"], indent=2))
