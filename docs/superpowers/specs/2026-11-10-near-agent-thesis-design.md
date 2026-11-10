# NEAR Investment Thesis Design Spec: Protocol Primitives for the Agent Economy

- **Date:** 2026-11-10
- **Event:** NEAR Hackathon: Build Beyond Boundaries (2026-11-01 to 2026-11-14)
- **Primary Track:** `thesis` (02. Investment Thesis)
- **Secondary Track Fit:** `agents` (07. Agent Economy)
- **Repository Root:** `/home/von/Work/near-agent-thesis`

## 1. Purpose and Core Hypothesis

This project tests a specific long-term investment thesis for NEAR Protocol using reproducible onchain queries, live API benchmarks, and an explicit unit-economics model:

- **Primary Claim:** NEAR Protocol's native account and execution primitives (`FunctionCall` scoped access keys, hierarchical sub-accounts, `DELEGATE_ACTION` gasless meta-transactions, and `intents.near` cross-chain intent settlement) provide a structural cost and security advantage for autonomous AI agents compared with EVM ERC-4337 smart accounts (Base and Arbitrum) and Solana. Furthermore, machine-pattern and delegated actions already represent the majority of NEAR mainnet execution volume.
- **Counter-Hypotheses Tested (Evidence Against):**
  1. **Relayer and Receiver Concentration:** A large fraction of NEAR's `DELEGATE_ACTION` and automated `FUNCTION_CALL` volume is concentrated in a small number of consumer applications (such as Sweat, HOT, and Kai-Ching) rather than a diverse base of autonomous agent contracts.
  2. **Sub-Account Storage Lockup Overhead:** NEAR requires `0.001 NEAR` per 100 bytes of account state (`~0.0182 NEAR` minimum for a basic named sub-account). For large swarms of low-frequency or short-lived agents, this refundable storage deposit exceeds the one-time deployment cost of stateless keys on competing chains unless agents share parent accounts through scoped `FunctionCall` keys.
  3. **Micro-Payment Spread Floor on NEAR Intents:** Cross-chain settlement through NEAR Intents 1Click swaps faces minimum solver spreads and destination chain gas floors that make sub-dollar cross-chain agent payments uneconomical compared with same-chain NEP-141/NEP-245 transfers inside `intents.near`.
- **Falsification Criteria (What Would Change Our Mind):**
  1. If scoped `FunctionCall` key additions (`ADD_KEY` with `FUNCTION_CALL` permission) represent less than 25% of all new keys added on NEAR, or if non-top-3 receiver share of delegated/automated calls fails to grow over the measured timeline.
  2. If the 30-day total cost of operating a 100-agent swarm executing 10,000 actions with key rotation on NEAR exceeds the cost of an equivalent ERC-4337 smart-account swarm on Base or Arbitrum.
  3. If live NEAR Intents 1Click solver quotes fail to return valid quotes or exceed 150 basis points (1.5%) in round-trip spread on standard $100 to $1,000 agent settlement corridors across USDC, wNEAR, ETH, and SOL.

## 2. Architecture and Components

The system consists of five isolated, testable components:

1. **BigQuery SQL Suite (`sql/`):**
   - `sql/01_agent_primitives_daily.sql`: Queries `bigquery-public-data.crypto_near_mainnet_us.receipt_actions` partitioned by `block_date` to compute daily counts and unique accounts for `FUNCTION_CALL`, `DELEGATE_ACTION`, `CREATE_ACCOUNT`, and `ADD_KEY` (split by `FUNCTION_CALL` vs. `FULL_ACCESS` permission).
   - `sql/02_receiver_concentration.sql`: Queries `bigquery-public-data.crypto_near_mainnet_us.receipt_actions` partitioned by `block_date` to calculate top receiver contract shares and the daily Herfindahl-Hirschman Index (HHI) across `DELEGATE_ACTION` and `FUNCTION_CALL` receipts.
   - `sql/03_gas_and_storage_costs.sql`: Joins `receipt_actions` and `execution_outcomes` on matching `block_date` partitions to compute empirical p50 and p95 `gas_burnt` and `tokens_burnt` per action kind (`ADD_KEY`, `DELETE_KEY`, `CREATE_ACCOUNT`, `DELEGATE_ACTION`, `FUNCTION_CALL`).
2. **Data Fetcher (`src/fetch.py`):**
   - Executes the three SQL queries via `google-cloud-bigquery` with a strict `QueryJobConfig(maximum_bytes_billed=50_000_000_000)` guard so queries stay within the free BigQuery tier and fail fast if a partition filter is missing.
   - Bridges the post-March-2026 NEAR Lake indexing gap by pulling live 2026 mainnet data from three public endpoints:
     - `https://api.nearblocks.io/v1/charts` and `/v1/stats` for daily mainnet transactions, gas fees, active accounts, and NEAR price through November 2026.
     - `https://free.rpc.fastnear.com` for a stratified sample of live 2026 mainnet blocks/chunks and `intents.near` contract state (`storage_usage`, active receipt mix, scoped key ratios).
     - `https://1click.chaindefuser.com/v0/tokens` and `POST https://1click.chaindefuser.com/v0/quote` (`dry: true`) for live cross-chain solver quotes across token corridors (USDC, wNEAR, ETH, SOL, BTC) and payment sizes ($1, $10, $100, $1,000, $10,000). If `NEAR_INTENTS_JWT` is set in `.env`, it also queries `https://explorer.near-intents.org/api/v0/transactions`.
   - Saves raw, deterministic CSV and JSON artifacts into `data/raw/`.
3. **Analyzer and Cost Model (`src/analyze.py` and `src/cost_model.py`):**
   - Reads only from `data/raw/` so any judge or automated screening agent (Claude Code or Codex) can reproduce every chart and statistic offline with `python -m src.analyze`.
   - Computes the 30-day swarm TCO model across NEAR (sub-account model vs. shared-account scoped `FunctionCall` key model), Base (ERC-4337), Arbitrum (ERC-4337), and Solana.
   - Outputs `data/audit_stats.json` (single source of truth for every number in `THESIS.md` and the dashboard) and generates four publication-grade SVG charts in `dashboard/assets/`.
4. **Static Dashboard (`dashboard/index.html`):**
   - Self-contained static HTML/CSS/JS page deployable to Vercel.
   - Displays the thesis summary, falsification scorecard, interactive 100-agent swarm cost calculator, and the four charts.
   - Alongside each chart, renders the exact SQL or API query that produced it and one plain sentence stating what the chart shows.
5. **Written Thesis (`THESIS.md`) and Verification Suite (`tests/test_analyze.py`):**
   - `THESIS.md`: Written report containing the claim, the evidence for it, the evidence against it, and the falsification criteria.
   - `tests/test_analyze.py`: Automated tests verifying that (a) every `.sql` file filters on `block_date`, (b) `python -m src.analyze` produces a complete `data/audit_stats.json` and all four SVG charts without network calls, and (c) key numerical claims in `THESIS.md` and `dashboard/index.html` match `data/audit_stats.json`.

## 3. Data Flow

```text
[BigQuery: crypto_near_mainnet_us]  [NearBlocks API]  [FastNEAR RPC]  [1Click Intents API]
                 \                         |                 |                /
                  +------------------------+-----------------+---------------+
                                                   |
                                       python -m src.fetch
                                                   |
                                                   v
                                        data/raw/*.json, *.csv
                                                   |
                                      python -m src.analyze
                                                   |
                        +--------------------------+--------------------------+
                        |                                                     |
                        v                                                     v
              data/audit_stats.json                                dashboard/assets/*.svg
                        |                                                     |
                        +--------------------------+--------------------------+
                                                   |
                                      python -m pytest tests/
                                                   |
                                                   v
                                 THESIS.md + dashboard/index.html (Vercel)
```

## 4. Error Handling and Cost Controls

- **BigQuery Scan Cap:** Every BigQuery execution sets `maximum_bytes_billed` in `QueryJobConfig` and supports a `--dry-run` flag that prints estimated megabytes scanned before executing.
- **Credential Fallback:** If GCP credentials are not yet active when `src/fetch.py` runs, `--source api` pulls the live RPC, NearBlocks, and 1Click datasets independently, and `--source bq` runs the BigQuery queries as soon as `gcloud` or application-default credentials are authenticated.
- **Rate Limits and Retries:** HTTP requests to `1click.chaindefuser.com`, `api.nearblocks.io`, and `free.rpc.fastnear.com` use bounded exponential backoff on HTTP 429/502/503/504 and record exact timestamps in `data/raw/provenance.json`.

## 5. Verification Criteria ("Do X, See Y" for Judges)

1. Run `python -m pytest -q` -> all tests pass, confirming SQL `block_date` partition guards, cost-model invariants, and number traceability between `data/audit_stats.json`, `THESIS.md`, and `dashboard/index.html`.
2. Run `python -m src.analyze` -> regenerates `data/audit_stats.json` and `dashboard/assets/*.svg` from `data/raw/` in under 5 seconds with zero network calls required.
3. Open `dashboard/index.html` locally or at the deployed Vercel URL -> view all four charts, expand the exact SQL/API query behind each chart, and adjust the interactive swarm-cost parameters.
