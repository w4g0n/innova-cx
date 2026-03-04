-- =============================================================================
-- zzz_seed_analytics.sql — ML pipeline seed data
-- =============================================================================
-- Runs AFTER zzz_analytics_mvs.sh (alphabetically: zzz_s > zzz_a), which means
-- all required tables already exist.
-- Uses ticket_code subselects instead of hardcoded UUIDs.
-- Idempotent: all statements use WHERE NOT EXISTS.
--
-- TYPE RULE (CRITICAL — do not regress):
--   model_execution_log.agent_name  → agent_name_type ENUM → cast with ::agent_name_type ✓
--   agent_output_log.agent_name     → VARCHAR(80)           → plain text, NO cast          ✓
-- =============================================================================

\echo '--- zzz_seed_analytics: Section 28: MODEL EXECUTION LOG ---'
BEGIN;

INSERT INTO model_execution_log (
  id, execution_id, ticket_id, agent_name, model_version,
  triggered_by, started_at, completed_at, status,
  input_token_count, output_token_count, inference_time_ms, confidence_score, error_flag
)
SELECT
  v.mel_id::uuid,
  v.exec_id::uuid,
  t.id,
  v.agent_name::agent_name_type,  -- model_execution_log.agent_name IS agent_name_type ENUM
  v.model_version,
  v.triggered_by::trigger_source,
  v.started_at::timestamptz,
  v.completed_at::timestamptz,
  v.status::execution_status,
  v.in_tok, v.out_tok, v.inf_ms,
  v.conf, v.err_flag
FROM (VALUES
  ('81000000-0000-0000-0000-000000000001','82000000-0000-0000-0000-000000000001','CX-A001','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'5 days'::interval, now()-'5 days'::interval+interval'1.2s', 'success',312,48,1200,0.9120,FALSE),
  ('81000000-0000-0000-0000-000000000002','82000000-0000-0000-0000-000000000001','CX-A001','priority',   'priority-v1.8.0',   'ingest',   now()-'5 days'::interval, now()-'5 days'::interval+interval'0.9s', 'success',280,36, 900,0.8250,FALSE),
  ('81000000-0000-0000-0000-000000000003','82000000-0000-0000-0000-000000000002','CX-A002','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'4 days'::interval, now()-'4 days'::interval+interval'1.1s', 'success',295,45,1100,0.8750,FALSE),
  ('81000000-0000-0000-0000-000000000004','82000000-0000-0000-0000-000000000002','CX-A002','routing',    'routing-v1.5.2',    'ingest',   now()-'4 days'::interval, now()-'4 days'::interval+interval'0.8s', 'success',260,40, 800,0.7700,FALSE),
  ('81000000-0000-0000-0000-000000000005','82000000-0000-0000-0000-000000000003','CX-A003','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'1 day'::interval,  now()-'1 day'::interval+interval'1.3s',  'success',330,52,1300,0.9400,FALSE),
  ('81000000-0000-0000-0000-000000000006','82000000-0000-0000-0000-000000000003','CX-A003','priority',   'priority-v1.8.0',   'ingest',   now()-'1 day'::interval,  now()-'1 day'::interval+interval'1.0s',  'success',290,42,1000,0.9100,FALSE),
  ('81000000-0000-0000-0000-000000000007','82000000-0000-0000-0000-000000000004','CX-A004','feature',    'feature-v1.2.0',    'ingest',   now()-'2 days'::interval, now()-'2 days'::interval+interval'2.1s', 'success',410,80,2100,0.8300,FALSE),
  ('81000000-0000-0000-0000-000000000008','82000000-0000-0000-0000-000000000005','CX-H001','sla',        'sla-v1.3.1',        'ingest',   now()-'6 days'::interval, now()-'6 days'::interval+interval'0.6s', 'success',200,30, 600,0.8800,FALSE),
  ('81000000-0000-0000-0000-000000000009','82000000-0000-0000-0000-000000000006','CX-H002','resolution', 'resolution-v1.6.0', 'ingest',   now()-'13 days'::interval,now()-'13 days'::interval+interval'1.8s','success',380,70,1800,0.8500,FALSE),
  ('81000000-0000-0000-0000-000000000010','82000000-0000-0000-0000-000000000007','CX-A005','sentiment',  'sentiment-v2.0.5',  'reprocess',now()-'7 days'::interval, now()-'7 days'::interval+interval'1.0s', 'success',270,40,1000,0.6500,FALSE),
  -- Additional executions spread across last 30 days for richer MV data
  ('81000000-0000-0000-0000-000000000011','82000000-0000-0000-0000-000000000011','CX-A006','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'8 days'::interval, now()-'8 days'::interval+interval'1.1s', 'success',305,47,1100,0.8600,FALSE),
  ('81000000-0000-0000-0000-000000000012','82000000-0000-0000-0000-000000000012','CX-A007','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'9 days'::interval, now()-'9 days'::interval+interval'0.9s', 'success',290,44,900, 0.5200,FALSE),
  ('81000000-0000-0000-0000-000000000013','82000000-0000-0000-0000-000000000013','CX-A008','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'10 days'::interval,now()-'10 days'::interval+interval'1.2s','success',318,50,1200,0.7900,FALSE),
  ('81000000-0000-0000-0000-000000000014','82000000-0000-0000-0000-000000000014','CX-A009','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'11 days'::interval,now()-'11 days'::interval+interval'1.0s','success',302,46,1000,0.9100,FALSE),
  ('81000000-0000-0000-0000-000000000015','82000000-0000-0000-0000-000000000015','CX-A010','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'12 days'::interval,now()-'12 days'::interval+interval'1.3s','success',325,51,1300,0.5500,FALSE),
  ('81000000-0000-0000-0000-000000000016','82000000-0000-0000-0000-000000000016','CX-H003','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'3 days'::interval, now()-'3 days'::interval+interval'1.4s', 'success',340,55,1400,0.8800,FALSE),
  ('81000000-0000-0000-0000-000000000017','82000000-0000-0000-0000-000000000017','CX-H004','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'6 days'::interval, now()-'6 days'::interval+interval'1.1s', 'success',308,48,1100,0.9200,FALSE),
  ('81000000-0000-0000-0000-000000000018','82000000-0000-0000-0000-000000000018','CX-H005','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'14 days'::interval,now()-'14 days'::interval+interval'0.8s','success',285,43,800, 0.4800,FALSE),
  ('81000000-0000-0000-0000-000000000019','82000000-0000-0000-0000-000000000019','CX-H006','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'15 days'::interval,now()-'15 days'::interval+interval'1.5s','success',352,57,1500,0.8300,FALSE),
  ('81000000-0000-0000-0000-000000000020','82000000-0000-0000-0000-000000000020','CX-H007','sentiment',  'sentiment-v2.1.0',  'ingest',   now()-'16 days'::interval,now()-'16 days'::interval+interval'1.2s','success',316,49,1200,0.7600,FALSE),
  -- Feature agent executions
  ('81000000-0000-0000-0000-000000000021','82000000-0000-0000-0000-000000000021','CX-A006','feature',    'feature-v1.2.0',    'ingest',   now()-'8 days'::interval, now()-'8 days'::interval+interval'2.0s', 'success',400,78,2000,0.8100,FALSE),
  ('81000000-0000-0000-0000-000000000022','82000000-0000-0000-0000-000000000022','CX-A007','feature',    'feature-v1.2.0',    'ingest',   now()-'9 days'::interval, now()-'9 days'::interval+interval'2.2s', 'success',415,82,2200,0.5800,FALSE),
  ('81000000-0000-0000-0000-000000000023','82000000-0000-0000-0000-000000000023','CX-H003','feature',    'feature-v1.2.0',    'ingest',   now()-'3 days'::interval, now()-'3 days'::interval+interval'1.9s', 'success',395,76,1900,0.9100,FALSE),
  ('81000000-0000-0000-0000-000000000024','82000000-0000-0000-0000-000000000024','CX-H004','feature',    'feature-v1.2.0',    'ingest',   now()-'6 days'::interval, now()-'6 days'::interval+interval'2.3s', 'success',420,84,2300,0.8600,FALSE),
  ('81000000-0000-0000-0000-000000000025','82000000-0000-0000-0000-000000000025','CX-H005','feature',    'feature-v1.2.0',    'ingest',   now()-'14 days'::interval,now()-'14 days'::interval+interval'2.1s','success',408,80,2100,0.4500,FALSE)
) AS v(mel_id, exec_id, tc, agent_name, model_version, triggered_by, started_at, completed_at, status, in_tok, out_tok, inf_ms, conf, err_flag)
JOIN tickets t ON t.ticket_code = v.tc
WHERE NOT EXISTS (
  SELECT 1 FROM model_execution_log m WHERE m.id = v.mel_id::uuid
);

COMMIT;

\echo '--- zzz_seed_analytics: Section 29: SENTIMENT OUTPUTS ---'
BEGIN;

-- NOTE: execution_id in sentiment_outputs references model_execution_log.id (= mel_id).
-- created_at defaults to now() at insert time → always within "last 30 days".
-- Low-confidence rows (confidence_score < 0.60) are intentionally included so the
-- UI shows a non-zero "Low Confidence Rate".
INSERT INTO sentiment_outputs (execution_id, ticket_id, model_version, sentiment_label, sentiment_score, confidence_score, emotion_tags, raw_scores, is_current)
SELECT
  v.mel_id::uuid,
  t.id,
  v.model_version,
  v.sentiment_label,
  v.sentiment_score,
  v.confidence_score,
  v.emotion_tags,
  v.raw_scores::jsonb,
  TRUE
FROM (VALUES
  -- Original 5 rows
  ('81000000-0000-0000-0000-000000000001','CX-A001','sentiment-v2.1.0','Negative',    -0.7200,0.9120,ARRAY['frustration','urgency'],   '{"negative":0.912,"neutral":0.071,"positive":0.017}'),
  ('81000000-0000-0000-0000-000000000003','CX-A002','sentiment-v2.1.0','Negative',    -0.5500,0.8750,ARRAY['frustration'],             '{"negative":0.875,"neutral":0.100,"positive":0.025}'),
  ('81000000-0000-0000-0000-000000000005','CX-A003','sentiment-v2.1.0','Negative',    -0.8800,0.9400,ARRAY['anger','urgency'],         '{"negative":0.940,"neutral":0.042,"positive":0.018}'),
  ('81000000-0000-0000-0000-000000000010','CX-A005','sentiment-v2.0.5','Neutral',      0.1000,0.6500,ARRAY['neutral'],                 '{"negative":0.200,"neutral":0.650,"positive":0.150}'),
  ('81000000-0000-0000-0000-000000000009','CX-H002','sentiment-v2.1.0','Negative',    -0.4000,0.8500,ARRAY['frustration'],             '{"negative":0.850,"neutral":0.110,"positive":0.040}'),
  -- Additional rows for richer UI (mixed labels; 3 rows with confidence < 0.60 for non-zero low_conf_rate)
  ('81000000-0000-0000-0000-000000000011','CX-A006','sentiment-v2.1.0','Neutral',      0.0500,0.8600,ARRAY['neutral'],                 '{"negative":0.100,"neutral":0.860,"positive":0.040}'),
  ('81000000-0000-0000-0000-000000000012','CX-A007','sentiment-v2.1.0','Positive',     0.6200,0.5200,ARRAY['satisfaction'],            '{"negative":0.050,"neutral":0.430,"positive":0.520}'),
  ('81000000-0000-0000-0000-000000000013','CX-A008','sentiment-v2.1.0','Negative',    -0.3300,0.7900,ARRAY['frustration'],             '{"negative":0.790,"neutral":0.160,"positive":0.050}'),
  ('81000000-0000-0000-0000-000000000014','CX-A009','sentiment-v2.1.0','Very Negative',-0.9100,0.9100,ARRAY['anger','urgency','fear'], '{"negative":0.910,"neutral":0.060,"positive":0.030}'),
  ('81000000-0000-0000-0000-000000000015','CX-A010','sentiment-v2.1.0','Neutral',      0.0200,0.5500,ARRAY['neutral'],                 '{"negative":0.200,"neutral":0.550,"positive":0.250}'),
  ('81000000-0000-0000-0000-000000000016','CX-H003','sentiment-v2.1.0','Very Negative',-0.8500,0.8800,ARRAY['anger','frustration'],    '{"negative":0.880,"neutral":0.080,"positive":0.040}'),
  ('81000000-0000-0000-0000-000000000017','CX-H004','sentiment-v2.1.0','Negative',    -0.6700,0.9200,ARRAY['urgency','frustration'],   '{"negative":0.920,"neutral":0.058,"positive":0.022}'),
  ('81000000-0000-0000-0000-000000000018','CX-H005','sentiment-v2.1.0','Negative',    -0.4500,0.4800,ARRAY['frustration'],             '{"negative":0.480,"neutral":0.380,"positive":0.140}'),
  ('81000000-0000-0000-0000-000000000019','CX-H006','sentiment-v2.1.0','Positive',     0.7500,0.8300,ARRAY['relief','satisfaction'],   '{"negative":0.050,"neutral":0.120,"positive":0.830}'),
  ('81000000-0000-0000-0000-000000000020','CX-H007','sentiment-v2.1.0','Negative',    -0.5900,0.7600,ARRAY['frustration','urgency'],   '{"negative":0.760,"neutral":0.170,"positive":0.070}')
) AS v(mel_id, tc, model_version, sentiment_label, sentiment_score, confidence_score, emotion_tags, raw_scores)
JOIN tickets t ON t.ticket_code = v.tc
WHERE NOT EXISTS (
  SELECT 1 FROM sentiment_outputs s WHERE s.execution_id = v.mel_id::uuid
);

COMMIT;

\echo '--- zzz_seed_analytics: Section 30: PRIORITY OUTPUTS ---'
BEGIN;

INSERT INTO priority_outputs (execution_id, ticket_id, model_version, suggested_priority, confidence_score, reasoning, is_current)
SELECT
  v.exec_id::uuid,
  t.id,
  v.model_version,
  v.suggested_priority::ticket_priority,
  v.confidence_score::numeric,
  v.reasoning,
  TRUE
FROM (VALUES
  ('81000000-0000-0000-0000-000000000002','CX-A001','priority-v1.8.0','High',    0.8250,'Prolonged HVAC outage with high negative sentiment.'),
  ('81000000-0000-0000-0000-000000000006','CX-A003','priority-v1.8.0','Critical',0.9100,'Elevator stuck between floors — life safety risk.'),
  ('81000000-0000-0000-0000-000000000010','CX-A005','priority-v1.8.0','Low',     0.6500,'Water leak contained; no immediate risk to operations.')
) AS v(exec_id, tc, model_version, suggested_priority, confidence_score, reasoning)
JOIN tickets t ON t.ticket_code = v.tc
WHERE NOT EXISTS (
  SELECT 1 FROM priority_outputs p WHERE p.execution_id = v.exec_id::uuid
);

COMMIT;

\echo '--- zzz_seed_analytics: Section 31: ROUTING OUTPUTS ---'
BEGIN;

INSERT INTO routing_outputs (execution_id, ticket_id, model_version, suggested_department_id, confidence_score, reasoning, is_current)
SELECT
  v.exec_id::uuid,
  t.id,
  v.model_version,
  d.id,
  v.confidence_score,
  v.reasoning,
  TRUE
FROM (VALUES
  ('81000000-0000-0000-0000-000000000004','CX-A002','routing-v1.5.2','Maintenance',0.7700,'Badge reader failure requires Maintenance team.')
) AS v(exec_id, tc, model_version, dept_name, confidence_score, reasoning)
JOIN tickets t ON t.ticket_code = v.tc
JOIN departments d ON d.name = v.dept_name
WHERE NOT EXISTS (
  SELECT 1 FROM routing_outputs r WHERE r.execution_id = v.exec_id::uuid
);

COMMIT;

\echo '--- zzz_seed_analytics: Section 32: SLA OUTPUTS ---'
BEGIN;

INSERT INTO sla_outputs (execution_id, ticket_id, model_version, predicted_respond_mins, predicted_resolve_mins, breach_risk, confidence_score, is_current)
SELECT
  v.exec_id::uuid,
  t.id,
  v.model_version,
  v.respond_mins::integer,
  v.resolve_mins::integer,
  v.breach_risk::numeric,
  v.confidence_score::numeric,
  TRUE
FROM (VALUES
  ('81000000-0000-0000-0000-000000000008','CX-H001','sla-v1.3.1',240,1080,0.6200,0.8800),
  ('81000000-0000-0000-0000-000000000006','CX-A003','sla-v1.3.1', 30, 480,0.9500,0.9100)
) AS v(exec_id, tc, model_version, respond_mins, resolve_mins, breach_risk, confidence_score)
JOIN tickets t ON t.ticket_code = v.tc
WHERE NOT EXISTS (
  SELECT 1 FROM sla_outputs s WHERE s.execution_id = v.exec_id::uuid
);

COMMIT;

\echo '--- zzz_seed_analytics: Section 33: RESOLUTION OUTPUTS ---'
BEGIN;

INSERT INTO resolution_outputs (execution_id, ticket_id, model_version, suggested_text, kb_references, confidence_score, is_current)
SELECT
  v.exec_id::uuid,
  t.id,
  v.model_version,
  v.suggested_text,
  v.kb_references,
  v.confidence_score,
  TRUE
FROM (VALUES
  ('81000000-0000-0000-0000-000000000009','CX-H002','resolution-v1.6.0','Restore power from secondary distribution board and test all circuits.',ARRAY['KB-0041','KB-0088'],0.8500),
  ('81000000-0000-0000-0000-000000000002','CX-A001','resolution-v1.6.0','Replace HVAC compressor unit and re-commission the cooling system.',    ARRAY['KB-0012','KB-0034'],0.8200)
) AS v(exec_id, tc, model_version, suggested_text, kb_references, confidence_score)
JOIN tickets t ON t.ticket_code = v.tc
WHERE NOT EXISTS (
  SELECT 1 FROM resolution_outputs r WHERE r.execution_id = v.exec_id::uuid
);

COMMIT;

\echo '--- zzz_seed_analytics: Section 34: FEATURE OUTPUTS ---'
BEGIN;

-- raw_features JSONB contains business_impact, safety_concern, issue_severity, issue_urgency.
-- These keys are extracted by mv_feature_daily to produce non-zero UI counts.
-- Some rows intentionally have confidence_score < 0.60 to show non-zero Low Confidence Rate.
INSERT INTO feature_outputs (execution_id, ticket_id, model_version, asset_category, topic_labels, confidence_score, raw_features, is_current)
SELECT
  v.mel_id::uuid,
  t.id,
  v.model_version,
  v.asset_category,
  v.topic_labels,
  v.confidence_score,
  v.raw_features::jsonb,
  TRUE
FROM (VALUES
  ('81000000-0000-0000-0000-000000000007','CX-A004','feature-v1.2.0','Network', ARRAY['network','floor','workstations','offline'],0.8300,
   '{"is_recurring":false,"language":"en","word_count":12,"business_impact":"High","safety_concern":false,"issue_severity":"High","issue_urgency":"High"}'),
  ('81000000-0000-0000-0000-000000000005','CX-A003','feature-v1.2.0','Elevator',ARRAY['elevator','stuck','floors','safety'],     0.9200,
   '{"is_recurring":false,"language":"en","word_count":9,"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"High"}'),
  ('81000000-0000-0000-0000-000000000021','CX-A006','feature-v1.2.0','Cleaning',ARRAY['cleaning','schedule','block'],            0.8100,
   '{"is_recurring":true,"language":"en","word_count":8,"business_impact":"Low","safety_concern":false,"issue_severity":"Low","issue_urgency":"Low"}'),
  ('81000000-0000-0000-0000-000000000022','CX-A007','feature-v1.2.0','Security',ARRAY['perimeter','fence','security'],           0.5800,
   '{"is_recurring":false,"language":"en","word_count":7,"business_impact":"Medium","safety_concern":true,"issue_severity":"Medium","issue_urgency":"Low"}'),
  ('81000000-0000-0000-0000-000000000023','CX-H003','feature-v1.2.0','CCTV',    ARRAY['cctv','offline','security','monitoring'], 0.9100,
   '{"is_recurring":false,"language":"en","word_count":10,"business_impact":"High","safety_concern":true,"issue_severity":"High","issue_urgency":"Critical"}'),
  ('81000000-0000-0000-0000-000000000024','CX-H004','feature-v1.2.0','Cooling', ARRAY['server','room','overheating','hvac'],     0.8600,
   '{"is_recurring":true,"language":"en","word_count":11,"business_impact":"High","safety_concern":false,"issue_severity":"High","issue_urgency":"High"}'),
  ('81000000-0000-0000-0000-000000000025','CX-H005','feature-v1.2.0','Civil',   ARRAY['water','flooding','basement','carpark'],  0.4500,
   '{"is_recurring":false,"language":"en","word_count":8,"business_impact":"Medium","safety_concern":true,"issue_severity":"High","issue_urgency":"Medium"}')
) AS v(mel_id, tc, model_version, asset_category, topic_labels, confidence_score, raw_features)
JOIN tickets t ON t.ticket_code = v.tc
WHERE NOT EXISTS (
  SELECT 1 FROM feature_outputs f WHERE f.execution_id = v.mel_id::uuid
);

COMMIT;

\echo '--- zzz_seed_analytics: Section 35: AGENT OUTPUT LOG ---'
BEGIN;

-- CRITICAL FIX: agent_output_log.agent_name is VARCHAR(80), NOT agent_name_type ENUM.
-- Using ::agent_name_type cast here causes:
--   ERROR: column "agent_name" is of type character varying but expression is of type agent_name_type
-- Solution: insert plain text (no cast). VARCHAR accepts text literals directly.
-- The WHERE NOT EXISTS also compares VARCHAR = text — no cast needed.
INSERT INTO agent_output_log (execution_id, ticket_id, agent_name, step_order, input_state, output_state, state_diff, inference_time_ms, error_flag)
SELECT
  v.exec_id::uuid,
  t.id,
  v.agent_name,              -- VARCHAR(80): plain text, no ::agent_name_type cast
  v.step_order,
  v.input_state::jsonb,
  v.output_state::jsonb,
  v.state_diff::jsonb,
  v.inf_ms,
  FALSE
FROM (VALUES
  ('82000000-0000-0000-0000-000000000001','CX-A001','sentiment',1,'{"text":"HVAC completely offline - Server Room B"}',       '{"label":"Negative","score":-0.72}',        '{"sentiment_label":"Negative"}',1200),
  ('82000000-0000-0000-0000-000000000001','CX-A001','priority', 2,'{"sentiment":"Negative","category":"hvac"}',              '{"priority":"High","confidence":0.825}',     '{"priority":"High"}',             900),
  ('82000000-0000-0000-0000-000000000002','CX-A002','sentiment',1,'{"text":"Access badge readers down - Gate 2"}',            '{"label":"Negative","score":-0.55}',        '{"sentiment_label":"Negative"}',1100),
  ('82000000-0000-0000-0000-000000000002','CX-A002','routing',  3,'{"category":"access","department":"maintenance"}',        '{"department":"Maintenance","confidence":0.77}','{"department":"Maintenance"}', 800),
  ('82000000-0000-0000-0000-000000000003','CX-A003','sentiment',1,'{"text":"Elevator B stuck between floors"}',               '{"label":"Negative","score":-0.88}',        '{"sentiment_label":"Negative"}',1300),
  ('82000000-0000-0000-0000-000000000003','CX-A003','priority', 2,'{"sentiment":"Negative","category":"elevator"}',          '{"priority":"Critical","confidence":0.91}',  '{"priority":"Critical"}',        1000)
) AS v(exec_id, tc, agent_name, step_order, input_state, output_state, state_diff, inf_ms)
JOIN tickets t ON t.ticket_code = v.tc
WHERE NOT EXISTS (
  SELECT 1 FROM agent_output_log a
  WHERE a.execution_id = v.exec_id::uuid
    AND a.agent_name   = v.agent_name   -- VARCHAR = text: fully compatible, no cast
    AND a.step_order   = v.step_order
);

COMMIT;

-- =============================================================================
-- Final step: refresh all analytics MVs to include the just-inserted seed data.
-- This is the critical step that makes the UI show non-zero values.
-- Safe to call multiple times (idempotent REFRESH MATERIALIZED VIEW).
-- =============================================================================
\echo '--- zzz_seed_analytics: Final MV refresh ---'
SELECT refresh_analytics_mvs();