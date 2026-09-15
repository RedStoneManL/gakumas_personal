"""训练与模拟共享的偶像配装数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_DEARNESS_LEVEL = 20
"""训练与无状态接口在未显式指定时使用的亲爱度等级。"""


@dataclass(frozen=True)
class IdolStatProfile:
    """偶像卡在培育与考试中的基础属性快照。"""

    idol_card_id: str
    character_id: str
    plan_type: str
    exam_effect_type: str
    initial_exam_deck_id: str
    audition_difficulty_id: str
    unique_produce_card_id: str
    vocal: float
    dance: float
    visual: float
    vocal_growth_rate: float
    dance_growth_rate: float
    visual_growth_rate: float
    stamina: float


@dataclass(frozen=True)
class ProduceSkillEffect:
    """一条已解析的培育技能（ProduceSkill 行 → ProduceEffect id），来源可以是偶像卡/支援卡/メモリー。"""

    skill_id: str
    level: int
    trigger_id: str
    effect_ids: tuple[str, ...] = ()
    #: 来源标签（``level_limit`` 才能開花 / ``potential`` ポテンシャル / ``prima_stella`` プリマステラ /
    #: ``memory`` メモリーアビリティ / ``support_card`` 支援卡）；仅用于追溯与统计，运行时不区分。
    source: str = ''
    #: Same skill on two equipped supports contributes twice; only its historical
    #: levels on one support are replacements. Preserve the owning card's identity.
    support_card_id: str = ''


@dataclass(frozen=True)
class ProduceMemoryCardSpec:
    """メモリー携带的技能卡（主数据 ``MemoryGift.produceCard`` 结构）。"""

    card_id: str
    upgrade_count: int = 0
    #: ``ProduceCardCustomize`` id 按获得顺序排列；同一自定义多级时重复 id。
    customize_ids: tuple[str, ...] = ()
    #: ``ProduceMemoryProduceCardPhaseType_ProduceStart``（培育开始入组）或 ``_EndAuditionMid``（中期试验后入组）。
    phase_type: str = 'ProduceMemoryProduceCardPhaseType_ProduceStart'


@dataclass(frozen=True)
class ProduceMemorySpec:
    """培育メモリー（编成时带入培育的メモリー），字段与主数据 ``MemoryGift`` 行一一对应。

    培育内生效的部分：``produce_card``（按 ``phase_type`` 入组）与 ``ability_ids``
    （``MemoryAbility`` → ``ProduceSkill p_memory_skill-*`` → ``ProduceEffect``，作为培育技能注册）。
    三维 / 体力 / ``exam_battle_*`` 是コンテスト（メモリー对战）用数值，培育里不使用，只作记录。
    """

    memory_id: str = ''
    idol_card_id: str = ''
    grade: str = ''
    produce_card: ProduceMemoryCardSpec | None = None
    ability_ids: tuple[str, ...] = ()
    ability_levels: tuple[int, ...] = ()
    vocal: int = 0
    dance: int = 0
    visual: int = 0
    stamina: int = 0
    exam_battle_produce_card_ids: tuple[str, ...] = ()
    exam_battle_produce_item_ids: tuple[str, ...] = ()
    #: 生成角色在 idol_card_id 中保留；已知的使用限制另列，空元组表示未声明额外角色限制。
    allowed_character_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProduceCardConversionSpec:
    """技能卡切换的单条生效配置。"""

    before_card_id: str
    after_card_id: str
    condition_set_id: str = ''
    is_not_reward: bool = False


@dataclass(frozen=True)
class ExamStatusEnchantSpec:
    """考试开场挂载的附魔规格，保留持续回合与触发次数。"""

    enchant_id: str
    effect_turn: int | None = None
    effect_count: int | None = None
    source_identity: str = ''


@dataclass(frozen=True)
class DeckArchetype:
    """主数据里为偶像卡推荐的卡组流派信息。"""

    group_id: str
    sample_group_id: str
    description: str
    recommended_card_ids: tuple[str, ...] = ()
    sample_card_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExamEpisodeRandomizationConfig:
    """考试环境的 episode 级上下文随机化配置。"""

    enabled: bool = False
    stat_jitter_ratio: float = 0.10
    score_bonus_jitter_ratio: float = 0.05
    randomize_use_after_item: bool = False
    randomize_stage_type: bool = False


@dataclass(frozen=True)
class SupportCardSelection:
    """自动编成器输出的一张支援卡及其评分说明。"""

    support_card_id: str
    support_card_level: int
    support_card_type: str
    score: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class IdolLoadout:
    """训练、模拟与 API 共享的统一偶像配装对象。"""

    idol_card_id: str
    producer_level: int
    idol_rank: int
    dearness_level: int
    use_after_item: bool
    stat_profile: IdolStatProfile
    deck_archetype: DeckArchetype | None = None
    produce_skills: tuple[ProduceSkillEffect, ...] = ()
    produce_card_conversions: tuple[ProduceCardConversionSpec, ...] = ()
    produce_item_id: str = ''
    extra_produce_item_ids: tuple[str, ...] = ()
    support_cards: tuple[SupportCardSelection, ...] = ()
    exam_status_enchant_ids: tuple[str, ...] = ()
    exam_status_enchant_specs: tuple[ExamStatusEnchantSpec, ...] = ()
    exam_score_bonus_multiplier: float = 1.0
    assist_mode: bool = False
    #: ポテンシャル 段数（0~4，``IdolCardPotential``）；``produce_skills`` / 成长率 / 体力已按此解析。
    potential_level: int = 0
    #: プリマステラ 解放（0/1，``IdolCardPrimaStellaProduceSkill``）；技能只在 H.I.F 本戦 剧本里进入 ``produce_skills``。
    prima_stella_level: int = 0
    #: 带入培育的メモリー（已解析的结构化配置，卡与アビリティ已分别并入初始卡组与 ``produce_skills``）。
    memories: tuple[ProduceMemorySpec, ...] = ()
    metadata: dict[str, str | int | float] = field(default_factory=dict)
