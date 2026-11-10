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
