// Public decision transport. Rule execution remains in the pinned vendor files.
import { createInterface } from 'node:readline';
import { StageEngine, StageConfig, IdolConfig, IdolStageConfig, S } from 'gakumas-engine';
import { SkillCards, PItems, PDrinks, Customizations, PIdols } from 'gakumas-data';
import { G } from '../_vendor/gakumas_tools/packages/gakumas-engine/constants.js';
import { resetRand, getRandCallCount } from '../_vendor/gakumas_tools/packages/gakumas-engine/utils.js';
import {isCustom,validateCustomContext,validatePrograms,nativeSettings,installDeclarations,fullCatalog} from './training_config.mjs';
import {addWeightedBasicCardsToDeck} from './training_basic_pool.mjs';
import {installSkillCardSupport} from './training_support.mjs';
import './training_catalogue.mjs';

const copy = x => structuredClone(x);
const fail = (path, message, kind='invalid_input') => {
  const error = new Error(`${path}: ${message}`); error.kind=kind; error.path=path; throw error;
};
const check = (ok,path,message,kind) => { if(!ok) fail(path,message,kind); };
console.log = (...args) => console.error(...args);
console.warn = (...args) => fail('native',args.join(' '),'unsupported_mechanism');
const FIELDS = ['conditions','cost','actions','effects'];
const BASIC = [646,648,666,668,670];
const SUPPORT = [108,246,247,584,585];
const allowed = card => card && (
  (['produce','default'].includes(card.sourceType) && ['sense','free'].includes(card.plan)) ||
  card.pIdolId===140 || SUPPORT.includes(card.id));
const catalog = SkillCards.getAll().filter(allowed);
const ids = new Set(catalog.map(c=>c.id));
const allIds = new Set(SkillCards.getAll().map(c=>c.id));
const drinkIds = new Set(PDrinks.getAll().filter(d=>['free','sense'].includes(d.plan)).map(d=>d.id));
const strip = x => {
  if(Array.isArray(x)) return x.map(strip);
  if(x && typeof x==='object') return Object.fromEntries(Object.entries(x).filter(([k])=>!k.toLowerCase().includes('description')).map(([k,v])=>[k,strip(v)]));
  return x;
};

function exact(obj, keys, path) {
  check(obj && typeof obj==='object' && !Array.isArray(obj),path,'expected object');
  for(const key of Object.keys(obj)) check(keys.includes(key),`${path}.${key}`,'unsupported field','unsupported_content');
  for(const key of keys) check(Object.hasOwn(obj,key),`${path}.${key}`,'required');
}
function int(x,min,max,path) { check(Number.isInteger(x)&&x>=min&&x<=max,path,`expected integer in [${min},${max}]`); }
function validate(entry) {
  exact(entry,['schema_version','preset','source','cards','resources','p_items','memory_abilities','persistent_effects','context'],'entry');
  const custom=isCustom(entry);
  check(custom||entry.schema_version==='arena-round2-entry/1','entry.schema_version','unsupported version');
  if(custom)validateCustomContext(entry);
  else {
  check(entry.preset==='hif-round2-shro-golden/1','entry.preset','unsupported preset','unsupported_content');
  exact(entry.source,['kind','family'],'entry.source');
  check(entry.source.kind==='constrained_curriculum'&&entry.source.family==='shro-fixed-exam/1','entry.source','only the declared curriculum is admitted');
  exact(entry.context,['idol_id','params','star_quality','dearness_bonus','boundary'],'entry.context');
  check(entry.context.idol_id===140,'entry.context.idol_id','only golden idol 140 is admitted','unsupported_content');
  check(JSON.stringify(entry.context.params)==='[1871,1392,1088]'&&entry.context.star_quality===800&&entry.context.dearness_bonus===0.5,'entry.context','fixed examination calibration; arbitrary star/parameter curves are not supported','unsupported_content');
  check(entry.context.boundary==='before_opening','entry.context.boundary','do not reapply opening to a settled entry');
  }
  exact(entry.resources,['stamina','max_stamina','drinks'],'entry.resources');
  if(custom)int(entry.resources.max_stamina,1,100000,'entry.resources.max_stamina');
  else check(entry.resources.max_stamina===35,'entry.resources.max_stamina','fixed curriculum max stamina 35');
  int(entry.resources.stamina,0,entry.resources.max_stamina,'entry.resources.stamina');
  check(Array.isArray(entry.resources.drinks)&&entry.resources.drinks.length<=(custom?64:6),'entry.resources.drinks','inventory capacity exceeded');
  entry.resources.drinks.forEach((id,i)=>check(custom?PDrinks.getById(id):drinkIds.has(id),`entry.resources.drinks[${i}]`,'unknown/outside admitted drink definition','unsupported_content'));
  check(Array.isArray(entry.cards)&&entry.cards.length>=(custom?0:2)&&entry.cards.length<=(custom?512:64),'entry.cards','entry capacity exceeded; 22 is not a capacity');
  const seen=new Set(),unique=new Set();
  entry.cards.forEach((c,i)=>{
    const p=`entry.cards[${i}]`; exact(c,['instance_id','definition_id','customizations','growth','bindings'],p);
    check(typeof c.instance_id==='string'&&c.instance_id.length>0&&!c.instance_id.startsWith('generated:')&&!seen.has(c.instance_id),`${p}.instance_id`,'unique non-generated instance ID required');seen.add(c.instance_id);
    const def=SkillCards.getById(c.definition_id);
    check((custom?allIds:ids).has(c.definition_id),`${p}.definition_id`,'outside admitted content closure','unsupported_content');
    const base=def.upgraded?def.id-1:def.id;
    if(def.unique && !['L','T'].includes(def.rarity)) { check(!unique.has(base),p,'duplicate unique card');unique.add(base); }
    check(c.customizations&&typeof c.customizations==='object'&&!Array.isArray(c.customizations),`${p}.customizations`,'expected mapping');
    const options=String(def.availableCustomizations||'').split(',').map(Number);
    for(const [key,level] of Object.entries(c.customizations)) {
      const custom=Customizations.getById(Number(key));
      check(custom&&options.includes(Number(key)),`${p}.customizations.${key}`,'customization not allowed on this card','unsupported_content');
      int(level,1,Number(custom.max),`${p}.customizations.${key}`);
    }
    check(c.growth&&typeof c.growth==='object'&&!Array.isArray(c.growth),`${p}.growth`,'expected mapping');
    for(const [key,value] of Object.entries(c.growth)) {
      check(Object.hasOwn(G,key),`${p}.growth.${key}`,'unknown native growth field','unsupported_content');
      check(Number.isFinite(value)&&Math.abs(value)<=10000,`${p}.growth.${key}`,'supported numeric growth range is [-10000,10000]');
    }
    if(custom)validatePrograms(c.bindings,`${p}.bindings`,seen,c.instance_id);
    else check(Array.isArray(c.bindings)&&c.bindings.length===0,`${p}.bindings`,'bound memory/support abilities are outside this first curriculum','unsupported_content');
  });
  if(custom) {
    check(Array.isArray(entry.p_items)&&entry.p_items.length<=256&&new Set(entry.p_items).size===entry.p_items.length,'entry.p_items','expected unique native P-item IDs');
    entry.p_items.forEach((id,i)=>check(PItems.getById(id),`entry.p_items[${i}]`,'unknown native P-item'));
    for(const key of ['memory_abilities','persistent_effects'])validatePrograms(entry[key],`entry.${key}`,seen);
  } else {
  check(entry.cards.some(c=>[815,816].includes(c.definition_id)),'entry.cards','idol signature is required');
  check(Array.isArray(entry.p_items)&&entry.p_items.length===2&&entry.p_items.includes(428)&&entry.p_items.some(i=>[442,443].includes(i)),'entry.p_items','requires green HIF baton and exactly one idol item (442/443)');
  for(const key of ['memory_abilities','persistent_effects']) check(Array.isArray(entry[key])&&!entry[key].length,`entry.${key}`,'outside fresh-exam curriculum; never silently drop persistent state','unsupported_content');
  }
  return entry;
}

class Selection extends Error {
  constructor(state,choice) { super('selection'); this.state=state; this.choice=choice; }
}
class Strategy {
  constructor(ctx) { this.ctx=ctx;this.answers=[];this.index=0; }
  pick(s,raw,num,optional,type) {
    // UI candidate enumeration must not expose the internal mountain order.
    const cards=[...raw].sort((a,b)=>a-b);
    const choice={type,min:optional?0:Math.min(num,cards.length),max:Math.min(num,cards.length),
      ordered:true,allow_duplicates:false,can_skip:optional,context:copy(this.ctx.selectionContext||{}),
      candidates:cards.map((card,index)=>({index,instance_id:uid(this.ctx,card),definition_id:s[S.cardMap][card].id}))};
    if(this.index===this.answers.length) throw new Selection(s,choice);
    const answer=this.answers[this.index++];
    check(Array.isArray(answer)&&answer.length>=choice.min&&answer.length<=choice.max,'choice.indices','invalid selection size');
    check(new Set(answer).size===answer.length&&answer.every(i=>Number.isInteger(i)&&i>=0&&i<cards.length),'choice.indices','invalid or duplicate index');
    return answer.map(index=>raw.indexOf(cards[index]));
  }
  pickCardsToHold(s,c,n=1,o=false) { return this.pick(s,c,n,o,'hold'); }
  pickCardsToMoveToHand(s,c,n=1) { return this.pick(s,c,n,false,'move_to_hand'); }
  pickCardsToUseFree(s,c,n=1) { return this.pick(s,c,n,false,'use_selected'); }
}
function uid(ctx,i) { return ctx.entry.cards[i]?.instance_id ?? `generated:${i-ctx.entry.cards.length}`; }
function indexOf(ctx,s,id) { return s[S.cardMap].findIndex((_,i)=>uid(ctx,i)===id); }

function create(entry,seed,options={}) {
  validate(entry); resetRand(seed);
  if(options.logs!==undefined) check(typeof options.logs==='boolean','options.logs','expected boolean');
  if(options.max_native_actions!==undefined) int(options.max_native_actions,0,10000000,'options.max_native_actions');
  const cfg=nativeSettings(entry);
  const idol=new IdolConfig({params:[...cfg.values,cfg.max_stamina],supportBonus:cfg.support_bonus,pItemIds:entry.p_items,skillCardIdGroups:[entry.cards.map(c=>c.definition_id)]});
  // Full-entry mode preserves every validated instance, order and customization.
  idol.cards=entry.cards.map(c=>({id:c.definition_id,customizations:copy(c.customizations)}));
  Object.assign(idol,{plan:cfg.plan,pIdolId:cfg.idol_id,idolId:PIdols.getById(cfg.idol_id)?.idolId??null,recommendedEffect:PIdols.getById(cfg.idol_id)?.recommendedEffect??null});
  const stage=new StageConfig(cfg.stage);
  const config=new IdolStageConfig(idol,stage,cfg.percent);
  config.defaultCardIds=[]; // Entry is complete: do not add a contest starter deck.
  const engine=new StageEngine(config);
  if(cfg.turn_types)engine.turnManager.generateTurnTypes=()=>copy(cfg.turn_types);
  const ctx={entry,engine,state:null,drinks:copy(entry.resources.drinks),knownTop:[],knownOrders:[],openingAudit:[],selectionContext:null,cost:{native_actions:0,rule_operations:0,replay_entries:0},options};
  engine.strategy=new Strategy(ctx);
  const cm=engine.cardManager;
  const addBasics=cm.addRandomBasicCardToDeckAtRandom.bind(cm);
  cm.addRandomBasicCardToDeckAtRandom=(s,num)=>{
    const before=s[S.cardMap].length;
    const audit={source:copy(s[S.triggeredEffect]?.source??null),phase:s[S.phase],deck_count_before:s[S.deckCards].length,requested:num,pool:[...cfg.basic_card_pool],sampling:cfg.basic_card_weights===null?'golden_uniform_unique_ids':'configured_weighted_basic_pool',...(cfg.basic_card_weights===null?{}:{weights:[...cfg.basic_card_weights]})};
    const result=cfg.basic_card_weights===null?addBasics(s,num):addWeightedBasicCardsToDeck(cm,s,num,cfg.basic_card_pool,cfg.basic_card_weights);
    audit.deck_count_after=s[S.deckCards].length;
    audit.generated=s[S.cardMap].slice(before).map((c,j)=>({definition_id:c.id,instance_id:uid(ctx,before+j),private_deck_index:s[S.deckCards].indexOf(before+j)}));
    ctx.openingAudit.push(audit);return result;
  };
  for(const name of ['moveSelectedToHandByTarget','holdSelectedByTarget','useSelectedCard','useSelectedCardFree']) {
    if(typeof cm[name]!=='function') continue;
    const original=cm[name].bind(cm);
    cm[name]=(s,target,...args)=>{
      const prior=ctx.selectionContext;
      ctx.selectionContext={operation:name,target:copy(target),source_instance:s[S.usedCard]==null?null:uid(ctx,s[S.usedCard]),phase:s[S.phase]??null,payment:name==='useSelectedCard'?'native_card_cost':'effect_defined'};
      try { return original(s,target,...args); } finally {ctx.selectionContext=prior;}
    };
  }
  // Visibility ledger follows publicly revealed movements, independently of logs.
  const log=engine.logger.log.bind(engine.logger);
  engine.logger.log=(s,type,data)=>{
    ctx.knownTop=ctx.knownTop.filter(i=>s[S.deckCards]?.includes(i));
    ctx.knownOrders=ctx.knownOrders.map(order=>order.filter(i=>s[S.deckCards]?.includes(i))).filter(order=>order.length>1);
    if(type==='moveCardToTopOfDeck') { const i=s[S.movedCard];ctx.knownOrders=ctx.knownOrders.map(order=>order.filter(j=>j!==i)).filter(order=>order.length>1);ctx.knownTop=[i,...ctx.knownTop.filter(j=>j!==i)]; }
    if(type==='addCardToTopOfDeck') { const i=s[S.cardMap].length-1;ctx.knownTop=[i,...ctx.knownTop]; }
    if(type==='addCardToDeckAtRandom'||type==='moveCardToDeckAtRandom') {if(ctx.knownTop.length>1) ctx.knownOrders.push([...ctx.knownTop]);ctx.knownTop=[];}
    if(options.logs) return log(s,type,data);
  };
  const pushGraph=engine.logger.pushGraphData.bind(engine.logger);
  engine.logger.pushGraphData=s=>{
    const ledger=s[S.graphData]?.arenaScoreByColor;
    if(options.logs)pushGraph(s);
    if(ledger)s[S.graphData]={...s[S.graphData],arenaScoreByColor:ledger};
  };
  const recycle=cm.recycleDiscards.bind(cm);
  cm.recycleDiscards=s=>{ctx.knownTop=[];ctx.knownOrders=[];return recycle(s);};
  const executeAction=engine.executor.executeAction.bind(engine.executor);
  engine.executor.executeAction=(...args)=>{
    ctx.cost.native_actions++;
    check(ctx.cost.native_actions<=(options.max_native_actions??200000),'budget.native_actions','native work budget exhausted','budget_exhausted');
    const [s,action]=args;
    const isScore=action.type==='assignment'&&action.lhs==='score';
    const before=isScore?s[S.score]:0;
    const result=executeAction(...args);
    if(isScore) {
      const color=engine.turnManager.getTurnType(s);
      const ledger={vocal:0,dance:0,visual:0,...s[S.graphData]?.arenaScoreByColor};
      ledger[color]+=(s[S.score]-before);
      // Copy-on-write follows native graphData cloning, including choice replay
      // and speculative card previews. Diagnostic collection never changes score.
      s[S.graphData]={...s[S.graphData],arenaScoreByColor:ledger};
    }
    return result;
  };
  const trigger=engine.effectManager.triggerEffectsForPhase.bind(engine.effectManager);
  engine.effectManager.triggerEffectsForPhase=(...args)=>{ctx.cost.rule_operations++;return trigger(...args);};
  installSkillCardSupport(ctx);
  ctx.state=engine.getInitialState();
  config.defaultCardIds=cfg.basic_card_pool; // Full entry; only the native refill handler uses this pool.
  entry.cards.forEach((c,i)=>{
    if(Object.keys(c.growth).length) ctx.state[S.cardMap][i].growth=Object.fromEntries(Object.entries(c.growth).map(([k,v])=>[G[k],v]));
  });
  ctx.state[S.stamina]=entry.resources.stamina;
  installDeclarations(ctx);
  return ctx;
}

function execute(ctx,action,answers) {
  ctx.cost.replay_entries++;
  const {engine}=ctx;const strategy=engine.strategy;
  strategy.answers=answers;strategy.index=0;
  if(action.type==='start') ctx.state=engine.startStage(ctx.state);
  else {
    const s=ctx.state;check(s[S.turnsRemaining]>0,'action','exam has ended');
    if(action.type==='play') {
      const i=indexOf(ctx,s,action.instance_id);
      check(i>=0&&s[S.cardUsesRemaining]>0&&s[S.handCards].includes(i)&&engine.isCardUsable(s,i),'action.instance_id','card is not legal');
      ctx.state=engine.useCard(s,i);
    } else if(action.type==='drink') {
      int(action.slot,0,ctx.drinks.length-1,'action.slot');
      engine.effectManager.triggerEffects(s,PDrinks.getById(ctx.drinks[action.slot]).actions);
      ctx.drinks.splice(action.slot,1);
    } else if(action.type==='end_turn') ctx.state=engine.endTurn(s);
    else fail('action.type','unknown action');
  }
  check(strategy.index===answers.length,'history.choices','unused answers');
}

function project(ctx,choice,revision,status='running') {
  const s=ctx.state, {engine}=ctx;
  check(Number.isFinite(s[S.score]),'state.score','non-finite score','native_exception');
  ctx.knownTop=ctx.knownTop.filter(i=>s[S.deckCards].includes(i));
  check(s[S.cardMap].length<=4096,'state.cardMap','instance capacity exceeded','capacity_exceeded');
  for(const c of s[S.cardMap]) check((isCustom(ctx.entry)?allIds:ids).has(c.id),'state.cardMap.definition_id',`generated card ${c.id} outside closure`,'unsupported_content');
  const excluded=new Set(['logs','graphData','deckCards','handCards','discardedCards','removedCards','heldCards','cardMap','turnTypes']);
  const state={},absent=[];
  for(const [name,i] of Object.entries(S)) if(!excluded.has(name)) {
    if(s[i]===undefined) absent.push(name); else state[name]=copy(s[i]);
  }
  const byUid=i=>uid(ctx,i), sorted=arr=>[...arr].sort((a,b)=>a-b).map(byUid);
  const cards=s[S.cardMap].map((card,i)=>({instance_id:byUid(i),definition_id:card.id,base_id:card.baseId,...(card.arenaSupport?{temporary_support:copy(card.arenaSupport)}:{}),customizations:copy(card.c11n||{}),growth:Object.fromEntries(Object.entries(G).filter(([,n])=>Object.hasOwn(card.growth||{},n)).map(([name,n])=>[name,card.growth[n]])),effective:Object.fromEntries(FIELDS.map(key=>[key,strip(engine.cardManager.getLines(s,i,key))]))}));
  const ended=s[S.turnsRemaining]<=0;
  const actions=[];
  if(!choice&&!ended&&status==='running') {
    for(const card of [...s[S.handCards]].sort((a,b)=>a-b)) if(s[S.cardUsesRemaining]>0&&engine.isCardUsable(s,card)) actions.push({type:'play',instance_id:byUid(card)});
    ctx.drinks.forEach((_,slot)=>actions.push({type:'drink',slot}));
    actions.push({type:'end_turn'});
  }
  const definitions={cards:[...new Set(cards.map(c=>c.definition_id))].sort((a,b)=>a-b).map(id=>strip(SkillCards.getById(id))),p_items:ctx.entry.p_items.map(id=>strip(PItems.getById(id))),drinks:[...new Set(ctx.drinks)].sort((a,b)=>a-b).map(id=>strip(PDrinks.getById(id)))};
  if(isCustom(ctx.entry))definitions.configured_abilities={bindings:ctx.entry.cards.map(c=>({instance_id:c.instance_id,bindings:copy(c.bindings)})),memory_abilities:copy(ctx.entry.memory_abilities),persistent_effects:copy(ctx.entry.persistent_effects)};
  return {schema_version:'arena-public-exam/1',observation_scope:'public',preset:ctx.entry.preset,decision_version:revision,
    context:{...copy(ctx.entry.context),boundary:choice?'selection':ended?'terminal':'decision',max_stamina:ctx.entry.resources.max_stamina,multipliers:copy(engine.config.typeMultipliers),turn_types:copy(s[S.turnTypes])},
    knowledge:{state_complete_for_admitted_closure:true,absent_fields:absent,deck_membership:'complete',deck_order:'unknown_except_known_top',known_top_next_draw_first:true},
    state,cards,definitions,zones:{hand:s[S.handCards].map(byUid),deck:{members:sorted(s[S.deckCards]),known_top:ctx.knownTop.map(byUid),known_relative_orders:ctx.knownOrders.map(order=>order.filter(i=>s[S.deckCards].includes(i))).filter(order=>order.length>1).map(order=>order.map(byUid)),size:s[S.deckCards].length},discarded:sorted(s[S.discardedCards]),removed:sorted(s[S.removedCards]),held:s[S.heldCards].map(byUid)},
    drinks:copy(ctx.drinks),choice:choice?{...choice,decision_version:revision}:null,
    actions:actions.map(a=>({...a,decision_version:revision})),
    result:{terminated:ended,truncated:status==='truncated',reason:ended?'normal':status==='truncated'?'external_truncation':null,score:s[S.score],score_by_color:copy(s[S.graphData]?.arenaScoreByColor??{vocal:0,dance:0,visual:0}),final_score:ended?s[S.score]:null,round2_score:ended?s[S.score]:null,combined_score:null,rank:null}};
}

function replay(snapshot,options={}) {
  const started=performance.now();const next=copy(snapshot);
  check(next.schema_version==='arena-training-snapshot/1','snapshot.schema_version','version mismatch');
  int(next.seed,0,4294967295,'snapshot.seed');int(next.revision,0,1000000,'snapshot.revision');
  check(['running','truncated'].includes(next.status),'snapshot.status','invalid status');
  const ctx=create(next.entry,next.seed,options);
  check(Array.isArray(next.history),'snapshot.history','expected action journal');
  next.history.forEach((e,i)=>{check((i===0)===(e.action.type==='start'),`snapshot.history[${i}]`,'invalid start');execute(ctx,e.action,e.choices);});
  let choice=null;
  if(next.pending) {
    check((next.history.length===0)===(next.pending.action.type==='start'),'snapshot.pending','invalid start');
    try {execute(ctx,next.pending.action,next.pending.choices);next.history.push(next.pending);next.pending=null;}
    catch(error) {if(!(error instanceof Selection)) throw error;ctx.state=error.state;choice=error.choice;}
  }
  const observation=project(ctx,choice,next.revision,next.status);
  return {snapshot:next,observation,cost:{...ctx.cost,rng_calls:getRandCallCount(),milliseconds:performance.now()-started},
    ...(options.debug?{private_debug:{scope:'PRIVATE_DEBUG',state:Object.fromEntries(Object.entries(S).filter(([,i])=>ctx.state[i]!==undefined).map(([k,i])=>[k,ctx.state[i]])),known_top:ctx.knownTop,opening_audit:ctx.openingAudit,logs:ctx.engine.logger.logs}}:{})};
}

export {validate,create,execute,project,replay,ids,BASIC};
if(process.argv.includes('--server')) {
  const lines=createInterface({input:process.stdin,crlfDelay:Infinity});
  for await(const line of lines) {
    try {const req=JSON.parse(line);const result=req.op==='catalog'?(req.scope==='all'?strip({...fullCatalog(),customizations:Customizations.getAll()}):{cards:catalog.map(strip),p_items:[428,442,443].map(id=>strip(PItems.getById(id))),drinks:PDrinks.getAll().filter(d=>drinkIds.has(d.id)).map(strip),basic_pool:BASIC}):replay(req.snapshot,req.options);process.stdout.write(JSON.stringify({ok:true,result})+'\n');}
    catch(error) {process.stdout.write(JSON.stringify({ok:false,error:{kind:error.kind||'native_exception',path:error.path||'native',message:error.message}})+'\n');}
  }
}
