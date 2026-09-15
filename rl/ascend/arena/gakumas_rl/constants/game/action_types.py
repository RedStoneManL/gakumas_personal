"""培育与考试动作类型常量。"""

ACTION_REFRESH = 'refresh'
ACTION_ACTIVITY = 'activity'
ACTION_BUSINESS = 'business'
ACTION_ACTIVITY_SUPPLY = 'activity_supply'
ACTION_OUTING = 'outing'
ACTION_SCHOOL_CLASS = 'school_class'
ACTION_PRESENT = 'present'
ACTION_PRE_AUDITION_CONTINUE = 'pre_audition_continue'
# 相談（商店）作为每周动作：进入 / 结束 / 刷新商品
ACTION_CONSULT = 'consult'
ACTION_CONSULT_FINISH = 'consult_finish'
ACTION_SHOP_REROLL = 'shop_reroll'
# 课程结束的技能卡奖励（3 选 1）：选择第 n 张 / 放弃 / 再抽选
CARD_REWARD_PICK_ACTION_TYPES = tuple(f'card_reward_pick_{index}' for index in range(1, 4))
ACTION_CARD_REWARD_SKIP = 'card_reward_skip'
ACTION_CARD_REWARD_REROLL = 'card_reward_reroll'

EXAM_ACTION_CARD = 'card'
EXAM_ACTION_DRINK = 'drink'
EXAM_ACTION_END_TURN = 'end_turn'
