UPDATE campaign_templates SET
  code = 'smart_traffic',
  type_name = '스마트 트래픽',
  campaign_type_selection = '플레이스 퀴즈',
  hint_text = '참여 방법에 있는 출발지에서 목적지까지 [가장 빠른] 걸음 수 맞추기',
  links = '[]'::json,
  hashtag = '#cpc_detail_place',
  modules = '["place_info", "landmark", "steps"]'::json,
  default_redirect_config = '{"channels":{"naver_app":{"weight":40,"sub":{"home":{"weight":85},"blog":{"weight":15}}},"map_app":{"weight":30,"tabs":{"map?tab=discovery":{"weight":30},"map?tab=booking":{"weight":20},"map?tab=navi":{"weight":20},"map?tab=pubtrans":{"weight":15},"map?tab=bookmark":{"weight":15}}},"browser":{"weight":30,"sub":{"home":{"weight":85},"blog":{"weight":15}}}},"place_id":"","blog_url":""}'::jsonb
WHERE id = 1;

UPDATE campaign_templates SET
  code = 'smart_save',
  type_name = '스마트 저장하기',
  campaign_type_selection = '검색 후 정답 입력',
  hint_text = '참여 방법에 있는 출발지에서 목적지까지 [가장 빠른] 걸음 수 맞추기',
  links = '[]'::json,
  hashtag = '#place_save_tab',
  modules = '["place_info", "landmark", "steps"]'::json,
  default_redirect_config = '{"channels":{"naver_app":{"weight":40,"sub":{"home":{"weight":85},"blog":{"weight":15}}},"map_app":{"weight":30,"tabs":{"map?tab=discovery":{"weight":30},"map?tab=booking":{"weight":20},"map?tab=navi":{"weight":20},"map?tab=pubtrans":{"weight":15},"map?tab=bookmark":{"weight":15}}},"browser":{"weight":30,"sub":{"home":{"weight":85},"blog":{"weight":15}}}},"place_id":"","blog_url":""}'::jsonb
WHERE id = 2;

SELECT id, code, type_name, campaign_type_selection FROM campaign_templates ORDER BY id;
