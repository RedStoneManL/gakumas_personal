// Composition and validation only. Effects, costs, scoring and RNG run upstream.
import {SkillCards,PItems,PDrinks,PIdols,parseEffects,transformEffects} from 'gakumas-data';
import {PHASES,S,G} from '../_vendor/gakumas_tools/packages/gakumas-engine/constants.js';
import {validateSkillCardSupport} from './training_support.mjs';

export const TYPES=['vocal','dance','visual'];
export const isCustom=e=>e?.schema_version==='arena-exam-entry/2';
export function requireValue(ok,path,message) {
  if(!ok) {const e=new Error(`${path}: ${message}`);e.path=path;e.kind='invalid_configuration';throw e;}
}
const check=requireValue;
export function keys(x,names,path) {
  check(x&&typeof x==='object'&&!Array.isArray(x),path,'expected object');
  for(const k of names)check(Object.hasOwn(x,k),`${path}.${k}`,'required');
  for(const k of Object.keys(x))check(names.includes(k),`${path}.${k}`,'unknown field');
}
function number(x,min,max,path,whole=false) {
  check(Number.isFinite(x)&&x>=min&&x<=max&&(!whole||Number.isInteger(x)),path,`expected ${whole?'integer':'number'} in [${min},${max}]`);
}
function triple(x,path,min,max,whole=false) {
  keys(x,TYPES,path);for(const k of TYPES)number(x[k],min,max,`${path}.${k}`,whole);
}
export function parseProgram(text,path) {
  check(typeof text==='string'&&text.length<=100000,path,'expected native effect DSL (max 100000 characters)');
  try {return transformEffects(parseEffects(text));}
  catch(error){check(false,path,`native DSL: ${error.message}`);}
}

export function validateCustomContext(entry) {
  check(typeof entry.preset==='string'&&entry.preset.length>0,'entry.preset','name your environment');
  const hasHif=Object.hasOwn(entry.source||{},'hif_scoring');
  keys(entry.source,['kind','family',...(hasHif?['hif_scoring']:[])],'entry.source');
  check(['custom_environment','constrained_curriculum','recorded_entry'].includes(entry.source.kind),'entry.source.kind','unknown source kind');
  check(typeof entry.source.family==='string'&&entry.source.family.length>0,'entry.source.family','source name required');
  const c=entry.context;
  const hasBasicWeights=Object.hasOwn(c,'basic_card_weights');
  const hasSupport=Object.hasOwn(c,'skill_card_support');
  keys(c,['plan','idol_id','boundary','scoring','stage','turn_types','basic_card_pool',...(hasBasicWeights?['basic_card_weights']:[]),...(hasSupport?['skill_card_support']:[])],'entry.context');
  if(hasSupport)validateSkillCardSupport(c.skill_card_support,check);
  check(['sense','logic','anomaly'].includes(c.plan),'entry.context.plan','unknown plan');
  const idol=c.idol_id===null?null:PIdols.getById(c.idol_id);
  check(c.idol_id===null||idol,'entry.context.idol_id','unknown golden idol ID');
  check(!idol||idol.plan===c.plan,'entry.context.plan','plan disagrees with selected idol');
  check(c.boundary==='before_opening','entry.context.boundary','entry must precede opening; use restore() for a running exam');
  keys(c.scoring,['mode','values','support_bonus'],'entry.context.scoring');
  check(['percent','golden_contest_params'].includes(c.scoring.mode),'entry.context.scoring.mode','use upstream percent input or upstream contest parameter formula');
  check(Array.isArray(c.scoring.values)&&c.scoring.values.length===3,'entry.context.scoring.values','three values required');
  c.scoring.values.forEach((v,i)=>number(v,0,1000000,`entry.context.scoring.values[${i}]`));
  number(c.scoring.support_bonus,0,100,'entry.context.scoring.support_bonus');
  check(c.scoring.mode!=='percent'||c.scoring.support_bonus===0,'entry.context.scoring.support_bonus','percent input is already resolved; native engine ignores support bonus in this mode');
  if(hasHif) {
    const p=entry.source.hif_scoring,path='entry.source.hif_scoring';
    check(p&&typeof p==='object'&&!Array.isArray(p),path,'expected scoring provenance');
    check(typeof p.model_version==='string'&&p.model_version.length>0,`${path}.model_version`,'model version required');
    for(const k of ['data_sha256','reference_code_sha256'])check(typeof p[k]==='string'&&/^[a-f0-9]{64}$/.test(p[k]),`${path}.${k}`,'SHA-256 required');
    check(p.arena_score_input==='display_percent',`${path}.arena_score_input`,'expected display percent');
    check(c.scoring.mode==='percent'&&Array.isArray(p.score_percents)&&p.score_percents.length===3&&p.score_percents.every((v,i)=>v===c.scoring.values[i]),path,'HIF provenance must match resolved percent inputs');
  }
  const stage=c.stage;
  keys(stage,['type','season','turnCounts','firstTurns','criteria','effects','linkTurnCounts'],'entry.context.stage');
  check(['contest','event'].includes(stage.type),'entry.context.stage.type','single-idol contest/event supported; linkContest needs multi-idol state');
  check(c.scoring.mode!=='golden_contest_params'||stage.type==='contest','entry.context.scoring.mode','native parameter formula requires contest');
  number(stage.season,1,10000,'entry.context.stage.season',true);
  triple(stage.turnCounts,'entry.context.stage.turnCounts',0,300,true);
  triple(stage.firstTurns,'entry.context.stage.firstTurns',0,1);
  triple(stage.criteria,'entry.context.stage.criteria',0,1);
  check(Math.abs(TYPES.reduce((n,k)=>n+stage.firstTurns[k],0)-1)<1e-9,'entry.context.stage.firstTurns','probabilities must sum to 1');
  check(Math.abs(TYPES.reduce((n,k)=>n+stage.criteria[k],0)-1)<1e-9,'entry.context.stage.criteria','ratios must sum to 1');
  check(Array.isArray(stage.linkTurnCounts)&&stage.linkTurnCounts.length===0,'entry.context.stage.linkTurnCounts','only single-idol stage supported');
  const n=TYPES.reduce((n,k)=>n+stage.turnCounts[k],0);
  number(n,1,300,'entry.context.stage.turnCount',true);
  if(c.turn_types!==null) {
    check(Array.isArray(c.turn_types)&&c.turn_types.length===n&&c.turn_types.every(t=>TYPES.includes(t)),'entry.context.turn_types','explicit sequence must cover all turns');
    for(const t of TYPES)check(c.turn_types.filter(k=>k===t).length===stage.turnCounts[t],'entry.context.turn_types',`sequence/count mismatch for ${t}`);
  } else {
    // Native generator reserves a final turn of each type plus a first turn.
    for(const t of TYPES)check(stage.turnCounts[t]>=1+(stage.firstTurns[t]>0?1:0),'entry.context.stage.turnCounts',`native random generation needs enough ${t} turns for first/final slots; use explicit turn_types otherwise`);
  }
  parseProgram(stage.effects,'entry.context.stage.effects');
  check(Array.isArray(c.basic_card_pool)&&c.basic_card_pool.length<=1000,'entry.context.basic_card_pool','expected pool IDs');
  c.basic_card_pool.forEach((id,i)=>check(SkillCards.getById(id)?.sourceType==='default',`entry.context.basic_card_pool[${i}]`,'must reference a native basic-card definition'));
  if(hasBasicWeights) {
    const w=c.basic_card_weights,path='entry.context.basic_card_weights';
    check(Array.isArray(w)&&w.length===c.basic_card_pool.length&&w.length>0,path,'weights must align with a nonempty pool');
    check(new Set(c.basic_card_pool).size===c.basic_card_pool.length,path,'weighted pool must contain unique IDs');
    w.forEach((v,i)=>number(v,0,1000000,`${path}[${i}]`));
    check(w.some(v=>v>0),path,'at least one positive weight required');
  }
  const batons=(entry.p_items||[]).filter(id=>[427,428,429,430,440,441].includes(id));
  check(new Set(batons).size<=1,'entry.p_items','multiple HIF baton colors are not a legal loadout');
  if(batons.length)check(c.basic_card_pool.length>0,'entry.context.basic_card_pool','baton requires a nonempty explicit pool');
  return c;
}

export function validatePrograms(programs,path,instanceIds,bind=null) {
  check(Array.isArray(programs)&&programs.length<=256,path,'expected at most 256 effect declarations');
  const seen=new Set();
  programs.forEach((p,i)=>{
    const at=`${path}[${i}]`;
    keys(p,['id','effects','counters'],at);
    check(typeof p.id==='string'&&p.id&&!seen.has(p.id),`${at}.id`,'unique ability ID required');seen.add(p.id);
    check(p.counters&&typeof p.counters==='object'&&!Array.isArray(p.counters),`${at}.counters`,'expected native effect counter map');
    for(const [k,v] of Object.entries(p.counters))number(v,0,1000000,`${at}.counters.${k}`,true);
    const effects=parseProgram(p.effects,`${at}.effects`);
    for(const e of effects)check(e.phase,`${at}.effects`,'declare a native phase for each top-level effect');
    if(bind!==null)check(instanceIds.has(bind),`${at}.bind_to`,'unknown card instance');
  });
}

export function nativeSettings(entry) {
  if(!isCustom(entry))return {plan:'sense',idol_id:140,values:[2030,1472,1098],max_stamina:35,percent:true,support_bonus:0,
    stage:{type:'contest',plan:'sense',season:51,turnCounts:{vocal:5,dance:4,visual:3},firstTurns:{vocal:1,dance:0,visual:0},criteria:{vocal:.45,dance:.30,visual:.25},effects:[],linkTurnCounts:[]},turn_types:null,basic_card_pool:[646,648,666,668,670],basic_card_weights:null};
  const c=entry.context;
  return {plan:c.plan,idol_id:c.idol_id,values:c.scoring.values,max_stamina:entry.resources.max_stamina,
    percent:c.scoring.mode==='percent',support_bonus:c.scoring.support_bonus,
    stage:{...c.stage,plan:c.plan,effects:parseProgram(c.stage.effects,'entry.context.stage.effects')},
    turn_types:c.turn_types,basic_card_pool:c.basic_card_pool,basic_card_weights:c.basic_card_weights??null};
}

// Reject unknown action/phase names before starting. Execution stays upstream.
export function checkNativeProgram(effects,engine,path) {
  const visit=(list,path)=>list.forEach((effect,i)=>{
    const p=`${path}[${i}]`;
    if(effect.phase)check(PHASES.includes(effect.phase),`${p}.phase`,`unknown native phase ${effect.phase}`);
    for(const [j,a] of (effect.actions||[]).entries()) {
      const at=`${p}.actions[${j}]`;
      if(a.type==='assignment')check(Object.hasOwn(S,a.lhs)||Object.hasOwn(G,a.lhs)||Object.hasOwn(engine.executor.intermediateResolvers,a.lhs)||a.lhs==='effectCounter',at,`unknown native field ${a.lhs}`);
      else if(['call','identifier'].includes(a.type))check(Object.hasOwn(engine.executor.specialActions,a.name),at,`unknown native operation ${a.name}`);
      else check(false,at,`unknown action type ${a.type}`);
    }
    if(effect.effects)visit(effect.effects,`${p}.effects`);
  });
  visit(effects,path);
}

export function installDeclarations(ctx) {
  const {entry,engine,state:s}=ctx;
  if(!isCustom(entry))return;
  checkNativeProgram(engine.config.stage.effects,engine,'entry.context.stage.effects');
  for(const e of engine.config.stage.effects)check(e.phase,'entry.context.stage.effects','declare a native phase for top-level stage effects');
  const add=(p,index,kind,path)=>{
    const effects=parseProgram(p.effects,path);
    checkNativeProgram(effects,engine,path);
    const source=index===null?{type:'stage',ability_id:p.id,ability_kind:kind}:
      {type:'skillCard',id:s[S.cardMap][index].id,idx:index,ability_id:p.id,ability_kind:kind};
    const usePhases=['beforeCardUsed','cardUsed','activeCardUsed','mentalCardUsed','afterCardUsed','afterActiveCardUsed','afterMentalCardUsed'];
    if(index!==null)for(const effect of effects)if(usePhases.includes(effect.phase))effect.conditions=[
      ...(effect.conditions||[]),{type:'comparison',op:'==',left:{type:'identifier',name:'usedCard'},right:{type:'number',value:index}}];
    const id=s[S.effectInstanceId];
    engine.effectManager.setEffects(s,effects,source);
    s[S.effectCounters][id]={...p.counters};s[S.effectInstanceId]=id+1;
  };
  entry.cards.forEach((c,i)=>c.bindings.forEach((p,j)=>add(p,i,'binding',`entry.cards[${i}].bindings[${j}].effects`)));
  for(const kind of ['memory_abilities','persistent_effects'])entry[kind].forEach((p,j)=>add(p,null,kind,`entry.${kind}[${j}].effects`));
}

export function fullCatalog() {
  return {cards:SkillCards.getAll(),p_items:PItems.getAll(),drinks:PDrinks.getAll(),idols:PIdols.getAll()};
}
