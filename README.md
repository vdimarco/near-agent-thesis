# NEAR Agent Economy Thesis: Onchain Primitives, Solver Spreads, and Swarm Unit Economics

**NEAR Hackathon: Build Beyond Boundaries (November 2026)**
- **Tracks:** `thesis` (02. Investment Thesis), `agents` (07. Agent Economy)
- **Full Written Thesis:** [`THESIS.md`](THESIS.md)
- **Static Dashboard:** [`dashboard/index.html`](dashboard/index.html)

---

## What Problem This Solves

Investors and builders evaluating NEAR for the AI agent economy often rely on headline transaction counts without testing whether those transactions reflect real agent primitives or subsidized consumer apps, and without measuring the actual 30-day cost of running an agent swarm on NEAR versus Base, Arbitrum, and Solana.

This repository tests the hypothesis that NEAR's native account primitives (`FunctionCall` access keys, sub-accounts, `DELEGATE_ACTION` meta-transactions, and `intents.near` cross-chain settlement) create a structural cost and execution advantage for autonomous agents, and reports every result that cuts against our hypothesis.

---

## Key Findings (Traceable to `data/audit_stats.json`)

1. **100-Agent Swarm 30-Day TCO (PASSED Check 2):** Running 100 agents executing 10,000 actions with 200 key rotations costs **$11.21** on NEAR using a shared parent account with scoped `FunctionCall` keys, or **$17.84** using dedicated sub-accounts (which locks **$6.48** in refundable storage at `0.001 NEAR` per 100 bytes). The identical workload costs **$30.70** on Base (ERC-4337), **$38.60** on Arbitrum (ERC-4337), and **$21.23** on Solana.
2. **NEAR Intents Cross-Chain Execution Spreads (PASSED Check 3):** Live `dry: true` quotes from `https://1click.chaindefuser.com/v0/quote` across 4 corridors (`USDC_NEAR_to_ARB`, `USDC_NEAR_to_BASE`, `USDC_NEAR_to_SOL`, `wNEAR_to_ARB_USDC`) show a median effective spread of **1.67 bps** on $100 to $1,000 transfers (well below our 150 bps falsification ceiling) with a **579.2 ms** median quote latency. On $1 micro-transfers, fixed withdrawal fees raise the median spread to **67.96 bps**, showing that sub-dollar agent payments should settle internally on `intents.near` before batching external withdrawals above $10 (**8.78 bps** median).
3. **Consumer Relayer Concentration & Key Mix (FAILED Check 1 - Reported Counter-Evidence):** While `DELEGATE_ACTION` accounts for **65.0%** of sampled mainnet actions and sub-accounts appear in **35.4%** of transactions, **66.4%** of top-receiver receipts go to three consumer apps (`token.sweat`, `spin.sweat`, `game.hot.tg`), with **33.6%** going to non-top-3 contracts (`intents.near` is #4 at **9.8%**, HHI **1683.69**). Across inspected active accounts, scoped `FunctionCall` keys represent **18.9%** of keys (below our 25.0% target) because consumer relayers use `FullAccess` key pools, whereas `intents.near` uses 100% scoped `FunctionCall` keys (9 of 9).

---

## Do X, See Y (Reproducibility Steps for Judges and Screening Agents)

Every chart and number in `THESIS.md` and `dashboard/index.html` reproduces offline from `data/raw/` in one command with zero cloud credentials required:

### Step 1: Install dependencies
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
- **Expected result:** `pytest`, `requests`, and `google-cloud-bigquery` install cleanly.

### Step 2: Rebuild all statistics and SVG charts from raw data (offline)
```bash
.venv/bin/python -m src.analyze
```
- **Expected result:** Prints the JSON falsification scorecard (`check1_scoped_keys_ge_25pct`, `check2_near_scoped_tco_lt_evm`, `check3_intents_mid_tier_spread_lt_150bps`) and regenerates `data/audit_stats.json` plus all four SVG charts in `dashboard/assets/chart1_primitives.svg` through `chart4_swarm_tco.svg`.

### Step 3: Run the automated verification and traceability test suite
```bash
.venv/bin/python -m pytest -v
```
- **Expected result:** `8 passed`. Verifies that every BigQuery SQL file in `sql/` filters on `block_date`, tests the HHI and 100-agent swarm cost model, tests the RPC and 1Click quote parsers, and asserts that every headline number in `THESIS.md` and `dashboard/index.html` matches `data/audit_stats.json`.

### Step 4: Refresh live mainnet data (optional, requires internet)
```bash
.venv/bin/python -m src.fetch
```
- **Expected result:** Pulls fresh daily series from NearBlocks (`/v1/charts`, `/v1/stats`), samples live blocks and access keys from FastNEAR RPC (`https://free.rpc.fastnear.com`), fetches 20 live cross-chain solver quotes from NEAR Intents 1Click API (`https://1click.chaindefuser.com/v0/quote`), validates the BigQuery SQL queries in `sql/` with a 50 GB scan guard (`maximum_bytes_billed=50_000_000_000`), and updates `data/raw/*.json`.

### Step 5: Open the static dashboard
```bash
python3 -m http.server 8080 --directory dashboard
```
- **Expected result:** Open `http://localhost:8080` to view all four charts, the expandable SQL and API queries behind each chart, the one-sentence chart takeaways, and the interactive 100-agent swarm cost calculator.

---

## NEAR Technologies Analyzed and Integrated

- **NEAR Intents (`intents.near` & 1Click API `https://1click.chaindefuser.com/v0`):** Live cross-chain solver quote benchmarking and contract storage/key inspection.
- **NEP-366 Meta-Transactions (`DELEGATE_ACTION`):** Empirical share and relayer concentration analysis across mainnet blocks and BigQuery `receipt_actions`.
- **Scoped Access Keys (`FunctionCall` vs. `FullAccess`) & Sub-Accounts:** Onchain key permission audit via FastNEAR `view_access_key_list` and 30-day swarm storage-staking cost model.
- **NEAR Public Lakehouse (`bigquery-public-data.crypto_near_mainnet_us`):** Partitioned SQL queries in `sql/` covering `receipt_actions`, `transactions`, and `execution_outcomes`.

---

## Disclosure (Hackathon Rule Q-015)

One person may submit up to 2 independent projects if disclosed in each README. If a second independent project is submitted by Vaughn DiMarco (such as an onchain commit-reveal swarm coordinator extending `swarm-alignment-2026`), it is a separate codebase solving multi-agent deliberation collapse rather than the onchain investment thesis and unit-economics model in this repository.
