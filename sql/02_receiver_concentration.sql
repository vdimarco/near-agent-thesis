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
