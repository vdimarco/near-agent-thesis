# Protocol Primitives for the Agent Economy: An Evidence-First Investment Thesis for NEAR

- **Track:** `thesis` (02. Investment Thesis) and `agents` (07. Agent Economy)
- **Author:** Vaughn DiMarco
- **Snapshot Date:** 2026-11-10 (Mainnet Block `#223968544`, NEAR Price `$3.56`)
- **Reproducibility:** Run `python -m src.analyze` to rebuild `data/audit_stats.json` and all four charts in `dashboard/assets/` offline in under 1 second.

---

## 1. Core Claim

NEAR Protocol's native account and execution primitives (`FunctionCall` scoped access keys, hierarchical sub-accounts, `DELEGATE_ACTION` gasless meta-transactions, and `intents.near` cross-chain settlement) give autonomous AI agents a measurable cost and security advantage over EVM ERC-4337 smart accounts (Base and Arbitrum) and Solana.

Specifically, operating a 100-agent swarm that executes 10,000 actions and rotates keys twice per month costs **$11.21** over 30 days on NEAR using a shared parent account with scoped `FunctionCall` keys, or **$17.84** using dedicated sub-accounts (including **$6.48** in refundable state storage). The equivalent workload costs **$30.70** on Base (ERC-4337), **$38.60** on Arbitrum One (ERC-4337), and **$21.23** on Solana. For cross-chain settlement, live NEAR Intents 1Click solver quotes across USDC and wNEAR corridors achieve a median effective spread of **1.67 bps** (0.0167%) on $100 to $1,000 transfers with a median quote latency of **579.2 ms**.

However, our pre-registered falsification suite also exposes two major counter-facts that cut against an uncritical agent-economy narrative:
1. **Consumer Relayer Concentration:** While `DELEGATE_ACTION` already represents **65.0%** of sampled mainnet actions, **66.4%** of top-receiver receipts flow to just three consumer applications (`token.sweat`, `spin.sweat`, and `game.hot.tg`), leaving **33.6%** for non-top-3 contracts (`intents.near` accounts for **9.8%** of top-receiver volume, with an overall receiver HHI of **1683.69**).
2. **FullAccess Key Over-Use in Consumer Relayers (Failed Falsification Check 1):** Across the active accounts inspected in our mainnet block window, scoped `FunctionCall` keys represent **18.9%** of active keys (10 `FunctionCall` keys vs. 43 `FullAccess` keys), falling below our pre-registered **25.0%** threshold. While core infrastructure like `intents.near` uses 100% scoped `FunctionCall` keys (9 of 9 keys), high-throughput consumer relayers still rely heavily on `FullAccess` key pools.

---

## 2. Pre-Registered Falsification Scorecard

Before running the analyzer, we locked three falsification checks in `docs/superpowers/specs/2026-11-10-near-agent-thesis-design.md`:

| Check ID | Hypothesis / Threshold | Observed Value | Verdict |
| --- | --- | --- | --- |
| **Check 1** | Scoped `FunctionCall` keys represent `>= 25.0%` of keys on active sampled accounts | **18.9%** (10 `FunctionCall` / 53 total keys) | **FAILED** (Consumer relayers skew toward `FullAccess` key pools; `intents.near` is 9/9 `FunctionCall`) |
| **Check 2** | 30-day TCO of a 100-agent swarm (10,000 actions, 200 rotations) on NEAR is lower than Base and Arbitrum ERC-4337 | **$11.21** (NEAR scoped keys) and **$17.84** (NEAR sub-accounts) vs. **$30.70** (Base) and **$38.60** (Arbitrum) | **PASSED** (63.5% cheaper than Base with scoped keys; 41.9% cheaper with dedicated sub-accounts) |
| **Check 3** | Live NEAR Intents 1Click median spread on $100 to $1,000 cross-chain transfers is `< 150.0 bps` | **1.67 bps** median across 4 corridors (20/20 live quotes succeeded across 229 supported tokens) | **PASSED** (nearly 90x tighter than the 150 bps ceiling on $100 to $1,000 sizes) |

---

## 3. Evidence For the Thesis

### 3.1 Protocol-Level Account Abstraction Without ERC-4337 Bundler Overhead

On EVM L2s (Base and Arbitrum), giving an AI agent a scoped spending or method-restricted key requires deploying an ERC-4337 smart contract wallet (plus a session-key validator module) and paying bundler `UserOperation` overhead on every call. On NEAR, every account natively supports multiple `FunctionCall` access keys restricted to a target contract (`receiver_id`), a method allowlist (`method_names`), and a gas allowance (`allowance`).

| Architecture | 30-Day Setup (100 Agents) | 200 Key Rotations | 10,000 Agent Actions | Storage / Rent Lockup | Total 30-Day TCO |
| --- | --- | --- | --- | --- | --- |
| **NEAR Shared Parent + Scoped Keys** | $0.04 | $0.14 | $11.04 | $0.00 ($0.40 refundable key bond) | **$11.21** |
| **NEAR Dedicated Sub-Accounts** | $0.19 | $0.14 | $11.04 | $6.48 (refundable at `0.001 NEAR`/100B) | **$17.84** |
| **Solana Rent-Exempt Keypairs** | $0.05 | $0.20 | $4.50 | $16.48 (rent-exempt deposit) | **$21.23** |
| **Base ERC-4337 Smart Accounts** | $1.80 | $0.90 | $28.00 | $0.00 | **$30.70** |
| **Arbitrum ERC-4337 Smart Accounts** | $2.40 | $1.20 | $35.00 | $0.00 | **$38.60** |

### 3.2 Gasless Execution and Sub-Account Usage on Mainnet

In our live FastNEAR mainnet sample around block `#223968544` (110 non-empty chunks, 79 transactions):
- **65.0%** of all actions are `DELEGATE_ACTION` (NEP-366 meta-transactions where a relayer pays gas on behalf of the signing key).
- **33.8%** of actions are direct `FUNCTION_CALL` invocations.
- **35.4%** of transactions involve hierarchical sub-accounts (`count(".") >= 2`, such as `v2.ref-finance.near`, `omni.bridge.near`, or `game.hot.tg`).
- Across the trailing 30 days on NearBlocks, NEAR processed a mean of **662,520** daily transactions with an average block time of **0.561 seconds** across **371** online validator nodes.

### 3.3 Cross-Chain Settlement Efficiency via NEAR Intents (`intents.near`)

Autonomous agents often need to pay for APIs or settle invoices on external chains (Arbitrum, Base, Solana) without holding native gas on every destination network. Our live probe of `https://1click.chaindefuser.com/v0/quote` (`dry: true`) across 4 corridors (`USDC_NEAR_to_ARB`, `USDC_NEAR_to_BASE`, `USDC_NEAR_to_SOL`, and `wNEAR_to_ARB_USDC`) and 5 order sizes ($1, $10, $100, $1,000, $10,000) shows:
- **$100 swaps:** Median effective spread of **1.75 bps** (`USDC_NEAR_to_ARB` at **1.34 bps**, `USDC_NEAR_to_BASE` at **1.63 bps**, `USDC_NEAR_to_SOL` at **1.87 bps**).
- **$1,000 swaps:** Median effective spread of **1.46 bps** (`USDC_NEAR_to_ARB` at **1.07 bps**, `USDC_NEAR_to_SOL` at **1.22 bps**, `USDC_NEAR_to_BASE` at **1.70 bps**).
- **Onchain footprint:** `intents.near` already holds **13.56 GB** (`13,555,359,691` bytes) of state storage and **136,265.98 NEAR** in balance, accounting for **9.8%** of top-receiver receipts in our live mainnet block sample.

---

## 4. Evidence Against the Thesis (What Cuts Against Our Claim)

1. **Consumer Relayer Dominance (66.4% Top-3 Concentration):** Most `DELEGATE_ACTION` volume today is not autonomous AI agent commerce. In our live block sample, **66.4%** of top-receiver receipts went to `token.sweat` (32), `spin.sweat` (31), and `game.hot.tg` (18). If NEAR fails to convert its meta-transaction infrastructure from subsidized consumer clickers to revenue-generating agent contracts like `intents.near` (**9.8%** share), transaction counts will remain a noisy proxy for economic value.
2. **Low Scoped-Key Adoption Among High-Volume Accounts (18.9% vs. 25.0% Target):** Although NEAR offers native `FunctionCall` keys, **81.1%** of keys on the active accounts in our sample were `FullAccess` keys (driven by consumer relayers rotating full-access key pools for throughput). In contrast, `intents.near` uses **9 `FunctionCall` keys and 0 `FullAccess` keys**, demonstrating that security-critical intent infrastructure relies on scoped keys even when consumer apps do not.
3. **Sub-Dollar Cross-Chain Spread Floor (67.96 bps at $1):** While $100 to $1,000 cross-chain swaps clear at a median of **1.67 bps**, fixed destination withdrawal fees push the median spread on **$1.00** cross-chain swaps to **67.96 bps** (**55.02 bps** to Arbitrum, **26.02 bps** to Base, **102.06 bps** to Solana). Sub-dollar agent micro-payments should therefore settle inside the `intents.near` multi-token ledger (NEP-245) and batch withdrawals to external chains only when balances exceed $10 (where median spread drops to **8.78 bps**).
4. **Sub-Account Storage Lockup ($6.48 per 100 Agents):** Creating a dedicated named sub-account per agent locks `~0.0182 NEAR` (`$0.0648` at `$3.56`/NEAR) for 1,820 bytes of state. For a 10,000-agent fleet, that equals **$647.92** in locked working capital. Builders should prefer a shared parent account issuing scoped `FunctionCall` keys (112 bytes per key, or **$0.40** refundable bond per 100 agents) unless per-agent contract isolation is required.
5. **Data Infrastructure Gap (NEAR Lake S3 Deprecation):** The AWS S3 NEAR Lake feed that populated `bigquery-public-data.crypto_near_mainnet_us` was deprecated on **2026-03-24**. While our repository includes validated, `block_date`-partitioned BigQuery SQL queries (`sql/01_agent_primitives_daily.sql`, `sql/02_receiver_concentration.sql`, `sql/03_gas_and_storage_costs.sql`) with a 50 GB scan guard for historical analysis, institutional analysts evaluating NEAR in late 2026 must combine BigQuery historical partitions with live RPC and indexer endpoints.

---

## 5. What Would Change Our Mind

We would downgrade this thesis from constructive to neutral/negative if any of the following occur over the next two quarters:
1. **`intents.near` Share Reversal:** If `intents.near` and non-consumer DeFi/agent contracts fall below **5.0%** of mainnet function-call and delegated receipts while top-3 consumer relayer concentration rises above **80.0%**.
2. **Solver Spread Expansion:** If median 1Click solver spreads on $100 to $1,000 USDC corridors widen above **25.0 bps** (from **1.67 bps** today) or quote failure rates exceed **5.0%**.
3. **EVM Native Account Abstraction Parity:** If EIP-7702 / RIP-7560 reduces Base and Arbitrum session-key rotation and `UserOperation` gas overhead by more than **70%**, erasing NEAR's **$11.21 vs. $30.70** 30-day swarm TCO advantage.
