// Arena transport around the unmodified gakumas-tools golden. One process per
// request isolates its module-global RNG. Only JSON is written to stdout.
import { readFileSync } from 'node:fs';
import { StageEngine, StageConfig, IdolConfig, IdolStageConfig, StagePlayer,
  STRATEGIES, S, resetRand } from 'gakumas-engine';
import { SkillCards, PItems, PDrinks, Customizations, Stages, parseEffects, transformEffects } from 'gakumas-data';

const RULES = 'arena-gakumas-tools/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/1';
console.log = (...args) => console.error(...args);
const clone = value => structuredClone(value);
function requireThat(ok, message) { if (!ok) throw new Error(message); }

class Selection extends Error {
  constructor(state, choice) { super('selection'); this.state = state; this.choice = choice; }
}
class TapeStrategy {
  constructor() { this.answers=[]; this.index=0; }
  pick(state, cards, num, optional, type) {
    const choice={type, candidates:cards.map((card, index)=>({index,card,
      id:state[S.cardMap][card].id, name:SkillCards.getById(state[S.cardMap][card].id).name})),
      min:optional?0:Math.min(num,cards.length), max:Math.min(num,cards.length)};
    if(this.index===this.answers.length) throw new Selection(state,choice);
    const selected=this.answers[this.index++];
    requireThat(Array.isArray(selected) && selected.length>=choice.min && selected.length<=choice.max,
      'Invalid selection size');
    requireThat(new Set(selected).size===selected.length && selected.every(i=>Number.isInteger(i)&&i>=0&&i<cards.length),
      'Invalid or duplicate selection index');
    return selected;
  }
  pickCardsToHold(s,c,n=1,optional=false) { return this.pick(s,c,n,optional,'hold'); }
  pickCardsToMoveToHand(s,c,n=1) { return this.pick(s,c,n,false,'move_to_hand'); }
  pickCardsToUseFree(s,c,n=1) { return this.pick(s,c,n,false,'use_selected'); }
}

function create(config, seed) {
  requireThat(config && config.loadout, 'config.loadout is required');
  const loadout=clone(config.loadout);
  requireThat(Array.isArray(loadout.params)&&loadout.params.length===4&&loadout.params.every(Number.isFinite),
    'loadout.params must contain vocal, dance, visual, max stamina');
  requireThat(loadout.params.every(n=>n>=0)&&loadout.params[3]>0,'Invalid params');
  requireThat(Array.isArray(loadout.skillCardIdGroups)&&loadout.skillCardIdGroups.flat().every(id=>id===0||SkillCards.getById(id)),
    'Unknown golden skill-card ID');
  requireThat(Array.isArray(loadout.pItemIds)&&loadout.pItemIds.every(id=>id===0||PItems.getById(id)),
    'Unknown golden P-item ID');
  const allDrinks=clone(config.drinks||[]);
  requireThat(allDrinks.every(id=>PDrinks.getById(id)),'Unknown golden drink ID');
  resetRand(seed);
  const sourceStage=config.stage ? clone(config.stage) : clone(Stages.getById(config.stage_id));
  requireThat(sourceStage,'Provide stage_id or a complete stage configuration');
  requireThat(sourceStage.type!=='linkContest','Link contest needs multiple idol configs; not exposed by this adapter');
  if(typeof sourceStage.effects==='string') sourceStage.effects=transformEffects(parseEffects(sourceStage.effects));
  sourceStage.effects ||= [];
  sourceStage.linkTurnCounts ||= [];
  requireThat(['vocal','dance','visual'].every(k=>Number.isInteger(sourceStage.turnCounts?.[k])&&sourceStage.turnCounts[k]>=0),
    'Invalid turn counts');
  const idol=new IdolConfig(loadout);
  const stage=new StageConfig(sourceStage);
  const engine=new StageEngine(new IdolStageConfig(idol,stage,!!config.enter_percents));
  const strategy=new TapeStrategy(); engine.strategy=strategy;
  let state=engine.getInitialState();
  if(config.turn_types) {
    requireThat(config.turn_types.length===stage.turnCount&&config.turn_types.every(k=>['vocal','dance','visual'].includes(k)),
      'turn_types must specify every turn');
    state[S.turnTypes]=clone(config.turn_types);
  }
  if(config.starting_stamina!=null) {
    requireThat(Number.isFinite(config.starting_stamina)&&config.starting_stamina>=0&&config.starting_stamina<=idol.params.stamina,
      'starting_stamina outside max stamina');
    state[S.stamina]=config.starting_stamina;
  }
  return {engine,strategy,state,drinks:allDrinks};
}

function execute(ctx, action, choices) {
  const {engine,strategy}=ctx;
  strategy.answers=choices; strategy.index=0;
  const s=ctx.state;
  if(action.type==='start') ctx.state=engine.startStage(s);
  else {
    requireThat(s[S.turnsRemaining]>0,'Exam has ended');
    if(action.type==='play') {
      requireThat(s[S.cardUsesRemaining]>0&&s[S.handCards].includes(action.card)&&engine.isCardUsable(s,action.card),
        'Card is not legal in the current hand');
      ctx.state=engine.useCard(s,action.card);
    } else if(action.type==='end_turn') ctx.state=engine.endTurn(s);
    else if(action.type==='drink') {
      requireThat(Number.isInteger(action.slot)&&action.slot>=0&&action.slot<ctx.drinks.length,'Invalid drink slot');
      // Inventory/action dispatch is an Arena extension; effect semantics are the
      // exact upstream PDrinks AST. It does not consume a card action or emit cardUsed.
      engine.effectManager.triggerEffects(s,PDrinks.getById(ctx.drinks[action.slot]).actions);
      ctx.drinks.splice(action.slot,1);
    } else throw new Error('Unknown action type');
  }
  requireThat(strategy.index===choices.length,'Unused choice answers');
}

function observe(ctx, choice=null) {
  const {state:s,engine}=ctx;
  const named={};
  for(const [name,index] of Object.entries(S)) if(s[index]!==undefined) named[name]=s[index];
  const terminated=s[S.turnsRemaining]<=0;
  const actions=[];
  if(!choice&&!terminated) {
    for(const card of s[S.handCards]) if(s[S.cardUsesRemaining]>0&&engine.isCardUsable(s,card))
      actions.push({type:'play',card,id:s[S.cardMap][card].id,name:SkillCards.getById(s[S.cardMap][card].id).name});
    ctx.drinks.forEach((id,slot)=>actions.push({type:'drink',slot,id,name:PDrinks.getById(id).name}));
    actions.push({type:'end_turn'});
  }
  return {rules_version:RULES,score:s[S.score],terminated,choice,actions,state:named,
    drinks:ctx.drinks,logs:s[S.logs].map(i=>engine.logger.logs[i]),
    extensions:['inventory_drink_dispatch','optional_explicit_turns_and_starting_stamina'],
    observation_scope:'offline_full_state'};
}

function replay(snapshot) {
  requireThat(snapshot.schema_version==='arena-golden-snapshot/1'&&snapshot.rules_version===RULES,'Snapshot version mismatch');
  const next=clone(snapshot);
  const ctx=create(next.config,next.seed);
  requireThat(Array.isArray(next.history),'Invalid history');
  for(let i=0;i<next.history.length;i++) {
    const entry=next.history[i];
    requireThat((i===0)===(entry.action.type==='start'),'Invalid start action in history');
    execute(ctx,entry.action,entry.choices);
  }
  let choice=null;
  if(next.pending) {
    requireThat((next.history.length===0)===(next.pending.action.type==='start'),'Invalid pending start');
    try {
      execute(ctx,next.pending.action,next.pending.choices);
      next.history.push(next.pending); next.pending=null;
    } catch(error) {
      if(!(error instanceof Selection)) throw error;
      ctx.state=error.state; choice=error.choice;
    }
  }
  return {snapshot:next,observation:observe(ctx,choice)};
}

async function main(request) {
  if(request.op==='lookup') {
    requireThat(typeof request.query==='string'&&request.query.length>0,'Nonempty query required');
    const matches=[];
    for(const [kind,table] of Object.entries({skill_cards:SkillCards,p_items:PItems,p_drinks:PDrinks,customizations:Customizations}))
      for(const row of table.getAll()) if(row.name.includes(request.query))
        matches.push({kind,id:row.id,name:row.name,definition:row});
    return {rules_version:RULES,matches};
  }
  if(request.op==='replay') return replay(request.snapshot);
  if(request.op==='rollout') {
    const ctx=create(request.config,request.seed);
    requireThat(!request.config.drinks?.length&&!request.config.turn_types&&request.config.starting_stamina==null,
      'Golden heuristic rollout uses upstream StagePlayer initialization; use step mode for drinks/explicit initial state');
    const strategy=new STRATEGIES.HeuristicStrategy(ctx.engine); ctx.engine.strategy=strategy;
    // create() initializes once; StagePlayer initializes again. Rewind so this
    // matches upstream tests/lib.mjs exactly, including the RNG draw sequence.
    resetRand(request.seed);
    const result=await new StagePlayer(ctx.engine,strategy).play();
    return {rules_version:RULES,...result};
  }
  throw new Error('Unknown operation');
}
try {
  const result=await main(JSON.parse(readFileSync(0,'utf8')));
  process.stdout.write(JSON.stringify({ok:true,result})+'\n');
} catch(error) {
  process.stdout.write(JSON.stringify({ok:false,error:error.message})+'\n');
  process.exitCode=1;
}
