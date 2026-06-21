-- Compute Metrics via Expressions
-- Order By [] Limit 1000
SELECT
  customer__country__region
  , CAST(cancellations_usd AS DOUBLE PRECISION) / CAST(NULLIF(transaction_amount_usd, 0) AS DOUBLE PRECISION) AS cancellation_rate
FROM (
  -- Join Standard Outputs
  -- Pass Only Elements:
  --   ['cancellations_usd', 'transaction_amount_usd', 'customer__country__region']
  -- Aggregate Measures
  SELECT
    subq_755.country__region AS customer__country__region
    , SUM(subq_749.transaction_amount_usd) AS transaction_amount_usd
    , SUM(subq_749.cancellations_usd) AS cancellations_usd
  FROM (
    -- Read Elements From Data Source 'transactions'
    -- Metric Time Dimension 'ds'
    -- Pass Only Elements:
    --   ['cancellations_usd', 'transaction_amount_usd', 'customer']
    SELECT
      id_customer AS customer
      , transaction_amount_usd
      , CASE WHEN transaction_type_name = 'cancellation' THEN transaction_amount_usd ELSE 0 END AS cancellations_usd
    FROM mf_test.transactions transactions_src_251
  ) subq_749
  LEFT OUTER JOIN (
    -- Join Standard Outputs
    -- Pass Only Elements:
    --   ['country__region', 'customer']
    SELECT
      customers_src_249.id_customer AS customer
      , countries_src_250.region AS country__region
    FROM mf_test.customers customers_src_249
    LEFT OUTER JOIN
      mf_test.countries countries_src_250
    ON
      customers_src_249.country = countries_src_250.country
  ) subq_755
  ON
    subq_749.customer = subq_755.customer
  GROUP BY
    subq_755.country__region
) subq_758
LIMIT 1000
-- MF_REQUEST_METADATA: {"tag_dict": {"MF_REQUEST_ID": "mf_rid__7v93wend"}}