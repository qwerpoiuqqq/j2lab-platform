-- QCA Accounts Migration (13 accounts)
-- Password: all "1234", encrypted with unified platform key

INSERT INTO superap_accounts (user_id_superap, password_encrypted, company_id, unit_cost_traffic, unit_cost_save, assignment_order, is_active)
VALUES
('트래픽 제이투랩',    'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 2, 21, 31, 1, true),
('월보장 제이투랩',    'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 2, 21, 31, 2, true),
('월보장 일류기획',    'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 6, 21, 31, 3, true),
('월보장 일류기획24',  'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 6, 25, 35, 4, true),
('트래픽 일류기획',    'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 6, 21, 31, 5, true),
('트래픽 제이투랩24',  'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 2, 25, 35, 6, true),
('월보장 제이투랩24',  'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 2, 25, 35, 7, true),
('트래픽 일류기획24',  'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 6, 25, 35, 8, true),
('저장 일류기획',      'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 6, 21, 31, 9, true),
('류 리워드 저장',     'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 6, 25, 35, 10, true),
('관리형 일류기획',    'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 6, 21, 31, 11, true),
('저장 일류기획24',    'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 6, 25, 35, 12, true),
('저장 제이투랩',      'gAAAAABppabwxgIuQykDm12k44sOWzxEG-NSCzlkrT_pTmAl0uAtSL8fvGBHof27zbtj2nsM3ENJtPpz1BllWHm6svXB3kI8QA==', 2, 21, 31, 13, true)
ON CONFLICT (user_id_superap) DO NOTHING;
