// Evidence-backed catalogue corrections for TrainingExam only. Rule DSL and
// vendored files stay unchanged; baseline run_exam does not import this module.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {SkillCards} from 'gakumas-data';

const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
const canonical = value => Array.isArray(value) ? value.map(canonical) :
  value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;
const digest = value => createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
const data = read('../content/native_catalogue_overrides.json');
const rawCards = new Map(read('../_vendor/gakumas_tools/packages/gakumas-data/json/skill_cards.json').map(row => [row.id, row]));
const rawCustomizations = new Map(read('../_vendor/gakumas_tools/packages/gakumas-data/json/customizations.json').map(row => [row.id, row]));
const fail = message => { throw new Error(`effective catalogue: ${message}`); };
if(data.schema_version !== 'arena-native-catalogue-overrides/1') fail('unsupported schema');
if(new Set(data.cards.map(row => row.native_card_id)).size !== data.cards.length) fail('duplicate card');

for(const patch of data.cards) {
  const raw = rawCards.get(patch.native_card_id), parsed = SkillCards.getById(patch.native_card_id);
  if(patch.field !== 'availableCustomizations' || !raw || !parsed || digest(raw) !== patch.raw_card_sha256 || raw.availableCustomizations !== patch.before)
    fail(`raw source mismatch: card ${patch.native_card_id}`);
  const custom = rawCustomizations.get(patch.effective_customization_id);
  if(!custom || digest(custom) !== patch.effective_customization_sha256)
    fail(`customization source mismatch: ${patch.effective_customization_id}`);
  const effective = {...raw, availableCustomizations: patch.after};
  if(digest(effective) !== patch.effective_card_sha256) fail(`output mismatch: card ${patch.native_card_id}`);
  if(String(parsed.availableCustomizations) !== patch.before) fail(`parsed catalogue already changed: card ${patch.native_card_id}`);
  // getAll/getById/getFiltered share this one parsed object. The native engine's
  // availability validation and the public catalogue therefore see one truth.
  parsed.availableCustomizations = patch.after.split(',').filter(Boolean);
}

export const catalogueOverridesVersion = data.rules_version;
