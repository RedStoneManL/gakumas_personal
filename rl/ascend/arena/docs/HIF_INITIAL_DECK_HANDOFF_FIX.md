# HIF produce initial cards and memory reservation — 2026-09-10

The S4+ conditional runner exposed two independent construction bugs. Both are fixed in the recommended HIF profile.

- Whole-produce reset used the standalone exam practice-deck builder, which randomly filled to 15 cards. It now follows `ProduceInitialDeck` by scenario and exam effect, reads every `ExamInitialDeck` card and upgrade count, then adds the current idol's unique card and ProduceStart memories. Repeated basics remain separate copies. For the guide's Sense 広, this is seven HIF basics + the current idol card + Chant memory = nine initial cards. No random cards, other idols' cards, or random upgraded variants are supplied.
- Final-stage construction normalized an already restored selection deck twice. With the Footlight switch off, this rewrote an owned customized Footlight into Call & Response and could create a duplicate unique card. The final handoff now preserves the owned card IDs, customizations, and memory provenance. Account switch settings still govern subsequent offers.

The guide explicitly enables `produce_card_conversion_after_ids=['p_card-01-act-3_185']` in its loadout. Equivalent research setting: `card_switches={'p_card-01-act-3_030': True}`. This is a configuration choice, not a free card grant.

The official [memory produce help](https://stat.game-gakuen-idolmaster.jp/html/help/f55ad8e5c496ac39b7d4fa3ac94ba36c2326b9cfefd425b894e070e60ecc8536/index.html) states that an equipped unique memory card does not appear among produce acquisitions, and multiple equipped memories of the same unique card grant only one copy. The fetched HTML is archived in `research/official-memory-memory-produce-20260910.html`.

Accordingly, unique memory IDs are reserved in the general acquisition pool and source-specific sampler throughout produce, including before the deferred grant and after deletion. Converted source IDs are checked again after mapping. Nonunique memories such as Mental Focus are not reserved. Identical duplicate unique memories grant once; if differing versions of the same unique card are configured at the same grant phase, the current implementation retains configured order rather than claiming an unverified server variant-selection rule. No already owned card is silently deleted or replaced.

Validation: 29 tests passed across `test_hif_initial_deck_handoff.py`, `test_hif_loadout_handoff.py`, and `test_hif_reward_controls.py`. The new cases cover three initial seeds, deep-copy isolation, card-switch basics, two handoff switch settings, source reservation before/after grant, and one-time unique-memory grants. Prior S4+ demonstration attempts made before these fixes are superseded and must not be reported as valid results.

The S4+ demonstration still explicitly assumes five exam scores. Its first-legal-action native exam resource trace does not prove those target scores achievable. Account level, support levels, growth panels, and four configured guide memories are declared inputs; final parameters and star quality must come from the resulting produce actions and accepted score rewards.
