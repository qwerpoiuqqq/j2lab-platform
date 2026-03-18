UPDATE campaign_templates SET
  default_redirect_config = '{"channels":{"naver_app":{"weight":25,"sub":{"home":{"weight":97},"blog":{"weight":3}}},"map_app":{"weight":50,"tabs":{"map?tab=discovery":{"weight":25},"map?tab=booking":{"weight":20},"map?tab=navi":{"weight":20},"map?tab=pubtrans":{"weight":15},"map?tab=bookmark":{"weight":20}}},"browser":{"weight":25,"sub":{"home":{"weight":97},"blog":{"weight":3}}}},"place_id":"","blog_url":""}'::jsonb
WHERE id IN (1, 2);

SELECT id, code, default_redirect_config->'channels'->'map_app'->'weight' as map_weight,
       default_redirect_config->'channels'->'naver_app'->'weight' as naver_weight,
       default_redirect_config->'channels'->'browser'->'weight' as browser_weight
FROM campaign_templates;
