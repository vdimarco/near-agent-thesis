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
