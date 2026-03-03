-- =============================================================================
-- zzz_seed_analytics.sql — ML pipeline seed data
-- =============================================================================
-- Runs AFTER zzz_analytics_mvs.sh (alphabetically: zzz_s > zzz_a), which means
-- all required tables already exist:
--   model_execution_log, agent_output_log  → from 001_agent_execution_logs.sql
--   sentiment_outputs, priority_outputs,   → from 000_analytics_prerequisites.sql
--   routing_outputs, sla_outputs,
--   resolution_outputs, feature_outputs
--
-- Idempotent: all statements use ON CONFLICT DO NOTHING.
-- Ends with SELECT refresh_analytics_mvs() so the analytics materialized views
-- include this demo data on a fresh volume.
-- =============================================================================

\echo "--- zzz_seed_analytics: Section 28: MODEL EXECUTION LOG ---"
-- =============================================================================
-- 28. MODEL EXECUTION LOG
-- =============================================================================
BEGIN;

INSERT INTO model_execution_log (
  id, execution_id, ticket_id, agent_name, model_version,
  triggered_by, started_at, completed_at, status,
  input_token_count, output_token_count, inference_time_ms, confidence_score, error_flag
) VALUES
  ('81000000-0000-0000-0000-000000000001', '82000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'sentiment',   'sentiment-v2.1.0',   'ingest',    now()-'5 days'::interval,  now()-'5 days'::interval+interval'1.2s',  'success', 312, 48,  1200, 0.9120, FALSE),
  ('81000000-0000-0000-0000-000000000002', '82000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'priority',    'priority-v1.8.0',    'ingest',    now()-'5 days'::interval,  now()-'5 days'::interval+interval'0.9s',  'success', 280, 36,   900, 0.8250, FALSE),
  ('81000000-0000-0000-0000-000000000003', '82000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 'sentiment',   'sentiment-v2.1.0',   'ingest',    now()-'4 days'::interval,  now()-'4 days'::interval+interval'1.1s',  'success', 295, 45,  1100, 0.8750, FALSE),
  ('81000000-0000-0000-0000-000000000004', '82000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 'routing',     'routing-v1.5.2',     'ingest',    now()-'4 days'::interval,  now()-'4 days'::interval+interval'0.8s',  'success', 260, 40,   800, 0.7700, FALSE),
  ('81000000-0000-0000-0000-000000000005', '82000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000003', 'sentiment',   'sentiment-v2.1.0',   'ingest',    now()-'1 day'::interval,   now()-'1 day'::interval+interval'1.3s',   'success', 330, 52,  1300, 0.9400, FALSE),
  ('81000000-0000-0000-0000-000000000006', '82000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000003', 'priority',    'priority-v1.8.0',    'ingest',    now()-'1 day'::interval,   now()-'1 day'::interval+interval'1.0s',   'success', 290, 42,  1000, 0.9100, FALSE),
  ('81000000-0000-0000-0000-000000000007', '82000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000006', 'feature',     'feature-v1.2.0',     'ingest',    now()-'2 days'::interval,  now()-'2 days'::interval+interval'2.1s',  'success', 410, 80,  2100, 0.8300, FALSE),
  ('81000000-0000-0000-0000-000000000008', '82000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000008', 'sla',         'sla-v1.3.1',         'ingest',    now()-'6 days'::interval,  now()-'6 days'::interval+interval'0.6s',  'success', 200, 30,   600, 0.8800, FALSE),
  ('81000000-0000-0000-0000-000000000009', '82000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000009', 'resolution',  'resolution-v1.6.0',  'ingest',    now()-'13 days'::interval, now()-'13 days'::interval+interval'1.8s', 'success', 380, 70,  1800, 0.8500, FALSE),
  ('81000000-0000-0000-0000-000000000010', '82000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000004', 'sentiment',   'sentiment-v2.0.5',   'reprocess', now()-'7 days'::interval,  now()-'7 days'::interval+interval'1.0s',  'success', 270, 40,  1000, 0.6500, FALSE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- zzz_seed_analytics: Section 29: SENTIMENT OUTPUTS ---"
-- =============================================================================
-- 29. SENTIMENT OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO sentiment_outputs (execution_id, ticket_id, model_version, sentiment_label, sentiment_score, confidence_score, emotion_tags, raw_scores, is_current) VALUES
  ('81000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'sentiment-v2.1.0', 'Negative',  -0.7200, 0.9120, ARRAY['frustration','urgency'],   '{"negative":0.912,"neutral":0.071,"positive":0.017}'::jsonb, TRUE),
  ('81000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000002', 'sentiment-v2.1.0', 'Negative',  -0.5500, 0.8750, ARRAY['frustration'],              '{"negative":0.875,"neutral":0.100,"positive":0.025}'::jsonb, TRUE),
  ('81000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000003', 'sentiment-v2.1.0', 'Negative',  -0.8800, 0.9400, ARRAY['anger','urgency'],          '{"negative":0.940,"neutral":0.042,"positive":0.018}'::jsonb, TRUE),
  ('81000000-0000-0000-0000-000000000010', 'c1000000-0000-0000-0000-000000000004', 'sentiment-v2.0.5', 'Neutral',    0.1000, 0.6500, ARRAY['neutral'],                  '{"negative":0.200,"neutral":0.650,"positive":0.150}'::jsonb, TRUE),
  ('81000000-0000-0000-0000-000000000009', 'c1000000-0000-0000-0000-000000000009', 'sentiment-v2.1.0', 'Negative',  -0.4000, 0.8500, ARRAY['frustration'],              '{"negative":0.850,"neutral":0.110,"positive":0.040}'::jsonb, TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- zzz_seed_analytics: Section 30: PRIORITY OUTPUTS ---"
-- =============================================================================
-- 30. PRIORITY OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO priority_outputs (execution_id, ticket_id, model_version, suggested_priority, confidence_score, reasoning, is_current) VALUES
  ('81000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000001', 'priority-v1.8.0', 'High',     0.8250, 'Prolonged broadband outage with high negative sentiment.', TRUE),
  ('81000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000003', 'priority-v1.8.0', 'Critical', 0.9100, 'Complete mobile outage affecting entire area.',            TRUE),
  ('81000000-0000-0000-0000-000000000010', 'c1000000-0000-0000-0000-000000000004', 'priority-v1.8.0', 'Low',      0.6500, 'Hardware inquiry, no immediate service impact.',           TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- zzz_seed_analytics: Section 31: ROUTING OUTPUTS ---"
-- =============================================================================
-- 31. ROUTING OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO routing_outputs (execution_id, ticket_id, model_version, suggested_department_id, confidence_score, reasoning, is_current) VALUES
  ('81000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000002', 'routing-v1.5.2', 'a1000000-0000-0000-0000-000000000003', 0.7700, 'Billing overcharge requires Billing & Finance team.',  TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- zzz_seed_analytics: Section 32: SLA OUTPUTS ---"
-- =============================================================================
-- 32. SLA OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO sla_outputs (execution_id, ticket_id, model_version, predicted_respond_mins, predicted_resolve_mins, breach_risk, confidence_score, is_current) VALUES
  ('81000000-0000-0000-0000-000000000008', 'c1000000-0000-0000-0000-000000000008', 'sla-v1.3.1', 240,  1080, 0.6200, 0.8800, TRUE),
  ('81000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000003', 'sla-v1.3.1',  30,   480, 0.9500, 0.9100, TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- zzz_seed_analytics: Section 33: RESOLUTION OUTPUTS ---"
-- =============================================================================
-- 33. RESOLUTION OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO resolution_outputs (execution_id, ticket_id, model_version, suggested_text, kb_references, confidence_score, is_current) VALUES
  ('81000000-0000-0000-0000-000000000009', 'c1000000-0000-0000-0000-000000000009', 'resolution-v1.6.0', 'Optimise IPTV multicast routing configuration at exchange level.', ARRAY['KB-0041','KB-0088'], 0.8500, TRUE),
  ('81000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000001', 'resolution-v1.6.0', 'Replace CPE modem and re-provision the DSL line.',                 ARRAY['KB-0012','KB-0034'], 0.8200, TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- zzz_seed_analytics: Section 34: FEATURE OUTPUTS ---"
-- =============================================================================
-- 34. FEATURE OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO feature_outputs (execution_id, ticket_id, model_version, asset_category, topic_labels, confidence_score, raw_features, is_current) VALUES
  ('81000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000006', 'feature-v1.2.0', 'Email',   ARRAY['email','corporate','outage'],  0.8300, '{"is_recurring":false,"language":"en","word_count":12}'::jsonb, TRUE),
  ('81000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000003', 'feature-v1.2.0', 'Mobile',  ARRAY['mobile','outage','area-wide'],  0.9200, '{"is_recurring":false,"language":"en","word_count":9}'::jsonb,  TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- zzz_seed_analytics: Section 35: AGENT OUTPUT LOG ---"
-- =============================================================================
-- 35. AGENT OUTPUT LOG
-- =============================================================================
BEGIN;

INSERT INTO agent_output_log (execution_id, ticket_id, agent_name, step_order, input_state, output_state, state_diff, inference_time_ms, error_flag) VALUES
  ('82000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'sentiment',  1, '{"text":"My internet is slow for 3 days!"}'::jsonb,        '{"label":"Negative","score":-0.72}'::jsonb,           '{"sentiment_label":"Negative"}'::jsonb,           1200, FALSE),
  ('82000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'priority',   2, '{"sentiment":"Negative","category":"network"}'::jsonb,     '{"priority":"High","confidence":0.825}'::jsonb,       '{"priority":"High"}'::jsonb,                       900, FALSE),
  ('82000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 'sentiment',  1, '{"text":"I was charged double this month!"}'::jsonb,        '{"label":"Negative","score":-0.55}'::jsonb,           '{"sentiment_label":"Negative"}'::jsonb,           1100, FALSE),
  ('82000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 'routing',    3, '{"category":"billing","department":"customer_exp"}'::jsonb, '{"department_id":"billing_dept","confidence":0.77}'::jsonb,'{"department":"Billing & Finance"}'::jsonb,     800, FALSE),
  ('82000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000003', 'sentiment',  1, '{"text":"No signal at all in Fujairah!"}'::jsonb,           '{"label":"Negative","score":-0.88}'::jsonb,           '{"sentiment_label":"Negative"}'::jsonb,           1300, FALSE),
  ('82000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000003', 'priority',   2, '{"sentiment":"Negative","category":"mobile"}'::jsonb,      '{"priority":"Critical","confidence":0.91}'::jsonb,    '{"priority":"Critical"}'::jsonb,                  1000, FALSE)
ON CONFLICT DO NOTHING;
COMMIT;

-- =============================================================================
-- Refresh analytics materialized views to include the ML pipeline demo data
-- =============================================================================
SELECT refresh_analytics_mvs();
