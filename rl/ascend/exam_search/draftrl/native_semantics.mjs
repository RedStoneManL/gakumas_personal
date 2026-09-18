// Read-only semantic compilation. Never creates/starts an exam or resets RNG.
import {readFileSync} from 'node:fs';
import {SkillCards, Customizations, parseEffects, transformEffects} from 'gakumas-data';
import CardManager from '../runtime/arena/gakumas_arena/_vendor/gakumas_tools/packages/gakumas-engine/engine/CardManager/index.js';
import {S, G} from '../runtime/arena/gakumas_arena/_vendor/gakumas_tools/packages/gakumas-engine/constants.js';
import {getBaseId, getRandCallCount} from '../runtime/arena/gakumas_arena/_vendor/gakumas_tools/packages/gakumas-engine/utils.js';
import '../runtime/arena/gakumas_arena/engine/training_catalogue.mjs';

const SCHEMA = 'arena-native-semantics/1';
const fields = ['conditions', 'cost', 'actions', 'effects'];
const manager = new CardManager({logger: null});
const fail = message => { throw new Error(message); };
// getLines warns when a selected customization cannot find its anchor. Do not
// cache a silently incomplete semantic program in that case.
console.warn = (...args) => fail(args.join(' '));

function compileCard(request) {
  const definition = SkillCards.getById(request.definition_id);
  if (!definition) fail(`Unknown card definition: ${request.definition_id}`);
  const customizations = request.customizations || {};
  const growth = request.growth || {};
  const allowed = new Set(String(definition.availableCustomizations || '').split(',').filter(Boolean).map(Number));
  const selected = [];
  for (const [id, level] of Object.entries(customizations)) {
    const customization = Customizations.getById(Number(id));
    if (!allowed.has(Number(id)) || !customization || !Number.isInteger(level) || level < 1 || level > Number(customization.max))
      fail(`Invalid customization ${id}:${level} for card ${definition.id}`);
    selected.push(customization);
  }
  for (const [name, value] of Object.entries(growth)) {
    if (!Object.hasOwn(G, name) || !Number.isFinite(value) || Math.abs(value) > 10000)
      fail(`Invalid growth field ${name}`);
  }
  const state = [];
  state[S.cardMap] = [{id: definition.id, baseId: getBaseId(definition), c11n: customizations,
    growth: Object.fromEntries(Object.entries(growth).map(([name, value]) => [G[name], value]))}];
  const effective = Object.fromEntries(fields.map(field => [field, manager.getLines(state, 0, field)]));
  // Native CardManager.useCard checks these metadata flags outside getLines.
  // This is the default disposition only: holdThis/thisCardHeld overrides it.
  const removesLimit = selected.some(customization => customization.limit === 0);
  const removed = Boolean(definition.limit) && !removesLimit;
  return {
    definition_id: definition.id, base_id: getBaseId(definition), customizations, growth,
    effective,
    effective_traits: {
      base_limit: definition.limit ?? null,
      effective_limit: removesLimit ? 0 : (definition.limit ?? null),
      limit_removed_by_customization: removesLimit,
      force_initial_hand: Boolean(manager.isForceInitialHand(state, 0)),
      normal_post_use_zone: removed ? 'removed' : 'discarded',
      removed_after_use: removed, discard_after_use: !removed,
      disposition_scope: 'normal_after_use_unless_held',
      source_type: definition.sourceType ?? null, owner_id: definition.pIdolId ?? null,
      card_type: definition.type ?? null, rarity: definition.rarity ?? null,
      upgraded: Boolean(definition.upgraded), unique: Boolean(definition.unique),
    },
  };
}

try {
  const request = JSON.parse(readFileSync(0, 'utf8'));
  if (request.schema_version !== SCHEMA || !Array.isArray(request.cards) || !Array.isArray(request.programs))
    fail('Invalid semantic batch schema');
  const before = getRandCallCount();
  const cards = request.cards.map(compileCard);
  const programs = request.programs.map(text => {
    if (typeof text !== 'string' || text.length > 100000) fail('Expected native DSL of at most 100000 characters');
    return transformEffects(parseEffects(text));
  });
  const delta = getRandCallCount() - before;
  if (delta !== 0) fail('Semantic compilation consumed native RNG');
  process.stdout.write(JSON.stringify({schema_version: SCHEMA, ok: true, cards, programs, rng_calls_delta: delta}));
} catch (error) {
  process.stdout.write(JSON.stringify({schema_version: SCHEMA, ok: false, error: String(error.message || error)}));
  process.exitCode = 1;
}
