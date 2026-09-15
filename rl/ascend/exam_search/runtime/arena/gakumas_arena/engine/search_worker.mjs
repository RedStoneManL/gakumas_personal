/** Resident hypothetical worlds; native JS still executes every game rule.
 * Conditional proposal: reveal entries of exchangeable shuffle blocks lazily.
 * Order-sensitive operations freeze the remaining permutation and use rejection.
 * All recorded observations AND public draw traces are checked, from opening.
 */
import {createInterface} from 'node:readline';
import {createHash} from 'node:crypto';
import {create,execute,project} from './training_worker.mjs';
import {S} from '../_vendor/gakumas_tools/packages/gakumas-engine/constants.js';

const copy=structuredClone;
const stable=x=>x===undefined?'null':x===null||typeof x!=='object'?JSON.stringify(x):Array.isArray(x)?'['+x.map(stable).join(',')+']':'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+stable(x[k])).join(',')+'}';
const hash=x=>createHash('sha256').update(stable(x)).digest('hex');
function fail(kind,message){const e=Error(message);e.kind=kind;throw e;}
function assert(ok,message,kind='invalid_input'){if(!ok)fail(kind,message);}
const blankCost=()=>({candidates:0,accepted:0,branches:0,native_actions:0,rule_operations:0,replay_entries:0,rng_calls:0,conditional_draws:0,frozen_order_operations:0,world_initializations:0,projections:0});
let work,limits,deadline,freezeReasons={};
function tick(key,n=1){if(key)work[key]=(work[key]??0)+n;if(key==='rule_operations'&&work[key]%512===0)process.stdout.write(JSON.stringify({progress:{...work,cost_complete:false}})+'\n');if(performance.now()>=deadline)fail('deadline','search deadline exceeded');if(key&&limits[key]!==undefined&&work[key]>limits[key])fail('budget_exhausted',key+' exhausted');}
const cost=()=>({...work,milliseconds:performance.now()-limits.started,cost_complete:true});
const rng={value:0,calls:0};
let blocks={},blockSerial=0,guide=null,guidePrefix=false,draws=[],drawIndex=0,logWeight=0,entryNow;
function uid(i){return entryNow.cards[i]?.instance_id??`generated:${i-entryNow.cards.length}`;}
function nativeRandom(){tick('rng_calls');rng.calls++;let t=(rng.value=(rng.value+0x6d2b79f5)>>>0);t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;}
function shuffleBlock(arr){if(!arr.length||!arr.every(Number.isInteger))return;const id=++blockSerial;for(const i of arr)blocks[i]=id;}
// Every non-listed method that can inspect/mutate pile order materializes all
// remaining latent assignments. This is conservative (slower), never a reset
// of the posterior to a fresh unconstrained deck.
const symmetricMethods=new Set(['constructor','initializeState','changeIdol','getLines','getCardEffects','getCardCosts','getCardSourceType','getCardRarity','getTargetRuleCards','findCardPile','isCardUsable','isForceInitialHand','useCard','grow','drawCard','recycleDiscards','peekDeck','isUpgradable','upgrade','discardHand','upgradeHand','exchangeHand','upgradeRandomCardInHand','addRandomUpgradedCardToHand','addRandomBasicCardToDeckAtRandom','addCardToTopOfDeck','addCardToDeck','addCardToHand','hold','enforceHoldLimit','holdThisCard','moveHeldCardsToHand']);
// The adapter enumerates these candidates by stable instance index, and maps
// ordered public answers back to native positions. Unselected slots remain
// exchangeable; lower-level random/order-dependent operations still freeze.
for(const name of ['moveSelectedToHandByTarget','holdSelectedByTarget','useSelectedCard','useSelectedCardFree'])symmetricMethods.add(name);
// Uniformly picking an identity (without replacement) does not reveal the
// relative order of the remaining shuffle slots. Moving it to top DOES fix it.
for(const name of ['moveCardToHand','moveCardToHandFromDeckOrDiscards','moveCardToHandFromRemoved','moveToHandByTarget','removeCardByTarget','holdRandomByTarget','useRandomCardFree','moveCardToTopOfDeck','moveToTopOfDeckByTarget','findCardsMatchingTargetInPiles','moveCardBetweenPiles','moveToDeckByTarget','holdCard'])symmetricMethods.add(name);
function instrument(engine,entry){
  entryNow=entry;
  for(const [owner,name,key] of [[engine.executor,'executeAction','native_actions'],[engine.effectManager,'triggerEffectsForPhase','rule_operations']]){
    const original=owner[name].bind(owner);owner[name]=(...args)=>{tick(key);return original(...args);};
  }
  const cm=engine.cardManager;
  for(const name of Object.getOwnPropertyNames(Object.getPrototypeOf(cm))){
    if(symmetricMethods.has(name)||typeof cm[name]!=='function')continue;
    const original=cm[name].bind(cm);cm[name]=(...args)=>{tick('frozen_order_operations');freezeReasons[name]=(freezeReasons[name]??0)+1;blocks={};return original(...args);};
  }
  const move=cm.moveCardBetweenPiles.bind(cm);
  cm.moveCardBetweenPiles=(s,pick,...args)=>{delete blocks[pick.cardIdx];return move(s,pick,...args);};
  const insert=cm.addCardToDeck.bind(cm);
  cm.addCardToDeck=(s,...args)=>{
    const old=[...s[S.deckCards]],block=blocks[old[0]],whole=old.length===0||(block!==undefined&&old.every(i=>blocks[i]===block));
    const result=insert(s,...args);
    // Uniform insertion into a uniform permutation is another uniform
    // permutation. A deck with fixed/relative-order constraints is left frozen
    // at its sampled insertion position and conditioned by rejection instead.
    if(whole)shuffleBlock(s[S.deckCards]);
    return result;
  };
  const change=cm.changeIdol.bind(cm);
  cm.changeIdol=s=>{const result=change(s);const forced=++blockSerial,normal=++blockSerial;for(const i of s[S.deckCards])blocks[i]=cm.isForceInitialHand(s,i)?forced:normal;return result;};
  const peek=cm.peekDeck.bind(cm);
  cm.peekDeck=s=>{
    const i=peek(s),block=blocks[i];
    // In the pinned native code peekDeck is used only by the forced-opening
    // boolean check. Same-class exchangeable members reveal no extra identity.
    if(i!==undefined&&(block===undefined||s[S.deckCards].filter(k=>blocks[k]===block).some(k=>cm.isForceInitialHand(s,k)!==cm.isForceInitialHand(s,i))))delete blocks[i];
    return i;
  };
  const draw=cm.drawCard.bind(cm);
  cm.drawCard=s=>{
    tick(null);
    if(s[S.handCards].length>=5)return draw(s);
    if(!s[S.deckCards].length&&s[S.discardedCards].length)cm.recycleDiscards(s);
    const deck=s[S.deckCards];if(!deck.length)return draw(s);
    let i=deck.at(-1);
    if(guide!==null&&(!guidePrefix||drawIndex<guide.length)){
      const wanted=guide[drawIndex];if(wanted===undefined)fail('incompatible','extra draw absent from public trace');
      const position=deck.findIndex(k=>uid(k)===wanted);
      if(position<0)fail('incompatible','recorded draw is absent from this deck');
      const block=blocks[i];
      if(block!==undefined){
        const choices=deck.filter(k=>blocks[k]===block);
        if(blocks[deck[position]]!==block)fail('incompatible','draw conflicts with a fixed order constraint');
        logWeight-=Math.log(choices.length);tick('conditional_draws');
        [deck[position],deck[deck.length-1]]=[deck.at(-1),deck[position]];
        i=deck.at(-1);
      }else if(position!==deck.length-1)fail('incompatible','fixed top differs from public draw');
    }
    // Record before movement triggers: nested draws may otherwise reorder logs.
    draws.push(uid(i));drawIndex++;delete blocks[i];
    return draw(s);
  };
}
globalThis.__arenaSearch={rng,random:nativeRandom,reset(seed){rng.value=seed>>>0;rng.calls=0;},shuffled:shuffleBlock,instrument,
  onLog(s,type){if(type==='moveCardToTopOfDeck')delete blocks[s[S.movedCard]];for(const i of Object.keys(blocks))if(!s[S.deckCards]?.includes(Number(i)))delete blocks[i];}};

const contexts=new Map(),worlds=new Map();let serial=0;
function save(ctx){const data={};for(const [k,v] of Object.entries(ctx))if(!['engine','entry','options'].includes(k))data[k]=v;return copy({data,rng,blocks,blockSerial,loggerDisabled:ctx.engine.logger.disabled});}
function load(ctx,frame){const f=copy(frame);for(const k of Object.keys(ctx))if(!['engine','entry','options'].includes(k))delete ctx[k];Object.assign(ctx,f.data);Object.assign(rng,f.rng);blocks=f.blocks;blockSerial=f.blockSerial;entryNow=ctx.entry;ctx.engine.logger.disabled=f.loggerDisabled;ctx.engine.logger.logs=[];}
function cleanObservation(observation){const o=copy(observation);delete o.version;return o;}
function begin(entry,seed,role='hypothetical'){
  tick('world_initializations');blocks={};blockSerial=0;guide=null;draws=[];entryNow=entry;
  const ctx=create(copy(entry),seed,{logs:false,max_native_actions:10000000});
  const key=hash(entry);contexts.set(key,ctx);
  return {context:key,frame:save(ctx),anchor:null,pending:null,choice:null,revision:0,partial:[],selectionVersion:0,role,weight:0,drawTrace:[],historyKey:hash({entry})};
}
function ctxFor(world){const ctx=contexts.get(world.context);assert(ctx,'expired world context','expired_handle');load(ctx,world.frame);return ctx;}
function view(world){tick('projections');const ctx=ctxFor(world);return project(ctx,copy(world.choice),world.revision);}
function runCall(world,action,answers,expectedDraws,anchor=null){
  const ctx=contexts.get(world.context);
  if(anchor)load(ctx,anchor);else load(ctx,world.frame);
  const before=save(ctx);
  guidePrefix=expectedDraws==null&&anchor!==null;
  guide=expectedDraws??(guidePrefix?copy(world.drawTrace):null);draws=[];drawIndex=0;logWeight=0;
  tick('replay_entries');
  let choice=null;
  try{execute(ctx,action,answers);}catch(e){if(e.constructor.name!=='Selection')throw e;ctx.state=e.state;choice=e.choice;}
  if(guide!==null&&(guidePrefix?drawIndex<guide.length:drawIndex!==guide.length))fail('incompatible','unconsumed public draw trace');
  world.frame=save(ctx);world.drawTrace=copy(draws);world.choice=choice;
  world.pending=choice?{action:copy(action),answers:copy(answers)}:null;
  world.anchor=choice?before:null;
  world.weight=logWeight;guide=null;
}
function opening(world,expectedDraws){runCall(world,{type:'start'},[],expectedDraws);const o=view(world);world.historyKey=hash({prior:world.historyKey,observation:o,draws:world.drawTrace});return o;}
function currentVersion(world,command){assert(command.decision_version===world.revision,'expired decision version','stale_decision');}
function advance(world,command,expectedDraws=null){
  currentVersion(world,command);
  const before=view(world);assert(!before.result.terminated&&!before.result.truncated,'closed world','episode_closed');
  const c=copy(command);const type=c.type;
  if(type==='choice_append'||type==='choice_finish'){
    assert(world.choice,'no pending choice','no_choice');assert(c.selection_version===world.selectionVersion,'expired selection version','stale_selection');
    if(type==='choice_append'){
      assert(Number.isInteger(c.index)&&c.index>=0&&c.index<world.choice.candidates.length&&!world.partial.includes(c.index)&&world.partial.length<world.choice.max,'illegal partial selection','illegal_choice');
      assert(c.instance_id===undefined||c.instance_id===world.choice.candidates[c.index].instance_id,'candidate identity mismatch','illegal_choice');
      world.partial.push(c.index);world.selectionVersion++;return before;
    }
    assert(world.partial.length>=world.choice.min&&world.partial.length<=world.choice.max,'selection not complete','illegal_choice');
    c.type='choose';c.indices=copy(world.partial);
  }
  if(c.type==='choose'){
    assert(world.choice&&world.pending,'no pending choice','no_choice');
    assert(type==='choice_finish'||!world.partial.length,'finish partial selection instead of replacing it','illegal_choice');
    const indices=c.indices;
    assert(Array.isArray(indices)&&indices.length>=world.choice.min&&indices.length<=world.choice.max&&new Set(indices).size===indices.length&&indices.every(i=>Number.isInteger(i)&&i>=0&&i<world.choice.candidates.length),'illegal ordered selection','illegal_choice');
    runCall(world,world.pending.action,[...world.pending.answers,indices],expectedDraws,world.anchor);
  }else{
    assert(!world.choice,'resolve pending choice first','pending_choice');
    assert(before.actions.some(a=>stable(a)===stable(c)),'not a current legal action','illegal_action');
    delete c.decision_version;runCall(world,c,[],expectedDraws);
  }
  world.revision++;world.partial=[];world.selectionVersion=0;
  const committed=c.type==='choose'?{type:'choose',indices:c.indices,decision_version:command.decision_version}:command;
  const o=view(world);world.historyKey=hash({prior:world.historyKey,command:committed,observation:o,draws:world.drawTrace});return o;
}
function publicView(world,observation=null){
  const o=observation??view(world),partial=copy(world.partial);
  let actions=o.actions;
  if(world.choice){actions=[];if(partial.length<world.choice.max)for(const candidate of world.choice.candidates)if(!partial.includes(candidate.index))actions.push({type:'choice_append',index:candidate.index,instance_id:candidate.instance_id,decision_version:world.revision,selection_version:world.selectionVersion});if(partial.length>=world.choice.min)actions.push({type:'choice_finish',decision_version:world.revision,selection_version:world.selectionVersion});}
  return {observation:o,partial_selection:partial,selection_version:world.selectionVersion,actions,public_history_key:hash({history:world.historyKey,partial})};
}
function register(world){assert(worlds.size<(limits.max_worlds??256),'worker world capacity reached','capacity_exceeded');const handle='world:'+(++serial);worlds.set(handle,world);return handle;}
function get(handle,role=null){assert(typeof handle==='string'&&worlds.has(handle),'unknown/released handle','expired_handle');const w=worlds.get(handle);if(role)assert(w.role===role,'only independently sampled hypothetical worlds may branch','wrong_world_role');return w;}
function validateHistory(history){
  assert(history?.schema_version==='arena-public-history/1','full public history schema required');
  assert(history.initial?.observation&&Array.isArray(history.steps),'initial observation and every submitted command required');
  assert(history.steps.length<=4096,'history capacity');
  const records=[history.initial,...history.steps];
  const noPrivate=x=>{if(!x||typeof x!=='object')return;for(const [k,v] of Object.entries(x)){assert(!['seed','rng','rng_state','snapshot','private_debug','deckCards'].includes(k),'private fields are not sampler input');noPrivate(v);}};
  noPrivate(history);
  for(let i=0;i<records.length;i++){
    const r=records[i];assert(Object.keys(r).every(k=>(i===0?['observation','draws']:['observation','draws','command']).includes(k)),'unknown public history field');
    assert(r.observation.observation_scope==='public'&&r.observation.schema_version==='arena-public-exam/1','public observations required');
    assert(!r.observation.zones?.deck?.known_bottom&&!r.observation.peek,'external peek/bottom evidence needs a native public visibility adapter','unsupported_knowledge');
    assert(r.observation.decision_version===i,'missing/reordered decision in public history');
    if(r.draws!==undefined)assert(Array.isArray(r.draws)&&r.draws.every(id=>typeof id==='string'),'draws must contain only publicly drawn instance IDs');
    if(i)assert(r.command&&!['choice_append','choice_finish'].includes(r.command.type),'history records committed native commands only');
  }
}
function sample(req){
  validateHistory(req.history);assert(!req.history.steps.at(-1)?.observation.result.truncated,'truncated history cannot produce search labels');
  const target=req.particles;assert(Number.isInteger(target)&&target>=1&&target<=128,'particles 1..128 required');
  assert(worlds.size+target<=(limits.max_worlds??256),'release worlds before sampling another root','capacity_exceeded');
  const accepted=[];let attempts=0,reason=null;const rejected={};
  const reject=why=>{rejected[why]=(rejected[why]??0)+1;};
  const mismatch=(a,b,path='')=>{if(stable(a)===stable(b))return null;if(a&&b&&typeof a==='object'&&typeof b==='object'){for(const k of new Set([...Object.keys(a),...Object.keys(b)])){const p=mismatch(a[k],b[k],path+'.'+k);if(p)return p;}}return path;};
  // Independent proposals. Draw constraints are importance proposals, not
  // overwrites of the latest hand. Every full historical projection is checked.
  const seedStream={value:req.search_seed>>>0};
  const nextSeed=()=>{seedStream.value=(Math.imul(seedStream.value,1664525)+1013904223)>>>0;return seedStream.value;};
  while(accepted.length<target&&attempts<(req.max_candidates??target*32)){
    tick('candidates');attempts++;
    try{
      const w=begin(req.entry,nextSeed());let total=0;
      const o=opening(w,req.history.initial.draws);total+=w.weight;
      if(stable(o)!==stable(cleanObservation(req.history.initial.observation))){reject('initial'+mismatch(o,cleanObservation(req.history.initial.observation)));continue;}
      let compatible=true;
      for(const record of req.history.steps){
        // Pending selections replay only their in-flight native command. The
        // already-conditioned prefix likelihood must not be counted twice.
        const prevPending=w.pending? w.weight:0;
        const after=advance(w,record.command,record.draws);
        total+=w.weight-prevPending;
        if(stable(after)!==stable(cleanObservation(record.observation))){reject('decision'+w.revision+mismatch(after,cleanObservation(record.observation)));compatible=false;break;}
      }
      if(!compatible)continue;
      w.totalLogWeight=total;
      for(const index of req.partial_selection??[]){advance(w,{type:'choice_append',index,decision_version:w.revision,selection_version:w.selectionVersion});}
      accepted.push(w);tick('accepted');
    }catch(e){if(e.kind==='incompatible'){reject(e.message);continue;}if(['deadline','budget_exhausted'].includes(e.kind)){reason=e.kind;break;}throw e;}
  }
  const diagnostics={rejected,freeze_reasons:freezeReasons};
  if(accepted.length<target||reason)return {status:reason??'insufficient_particles',valid_for_search:false,handles:[],weights:[],accepted:accepted.length,attempts,final_score:null,diagnostics};
  const max=Math.max(...accepted.map(w=>w.totalLogWeight));const raw=accepted.map(w=>Math.exp(w.totalLogWeight-max)),sum=raw.reduce((a,b)=>a+b,0),weights=raw.map(v=>v/sum),ess=1/weights.reduce((a,w)=>a+w*w,0);
  const distinct=new Set(accepted.map(w=>hash(w.frame.data.state))).size;
  if(ess<Math.max(1,(req.min_ess_fraction??0.5)*target))return {status:'degenerate',valid_for_search:false,handles:[],weights,accepted:target,attempts,effective_sample_size:ess,distinct_particles:distinct,final_score:null};
  const rootView=publicView(accepted[0]);const handles=accepted.map(register);
  return {status:'ok',valid_for_search:true,handles,weights,accepted:target,attempts,effective_sample_size:ess,distinct_particles:distinct,duplicate_particles:target-distinct,resampled:false,independent_equal_weight_posterior_samples:false,method:'draw-conditioned-sequential-importance/1',assumptions:['Native stochastic mechanisms; ideal independent uniform RNG calls, not inference over the actual 32-bit simulator seed.','Exchangeable shuffle slots conditioned on public draw traces; order-sensitive operations freeze assignments and use rejection.','Finite weighted particle posterior; non-draw random outcomes use full-history rejection.'],view:rootView,diagnostics};
}
function dispatch(req){
  if(req.op==='sample')return sample(req);
  if(req.op==='record_create'){
    const w=begin(req.entry,req.seed,'recorded');opening(w,null);return {status:'ok',handle:register(w),view:publicView(w),draws:w.drawTrace};
  }
  if(req.op==='release'){worlds.delete(req.handle);const used=new Set([...worlds.values()].map(w=>w.context));for(const k of contexts.keys())if(!used.has(k))contexts.delete(k);return {status:'ok',resident_worlds:worlds.size};}
  if(req.op==='stats')return {status:'ok',resident_worlds:worlds.size,contexts:contexts.size};
  if(req.op==='batch'){
    const results=[];for(const item of req.commands){try{tick(null);results.push(dispatch({op:'step',...item}));}catch(e){return {status:e.kind??'native_exception',message:e.message,results,completed:results.length,valid_for_search:false,final_score:null};}}return {status:'ok',results,completed:results.length};
  }
  const world=get(req.handle);
  if(req.op==='clone'){get(req.handle,'hypothetical');tick('branches');const w=copy(world);return {status:'ok',handle:register(w)};}
  if(req.op==='observe')return {status:'ok',view:publicView(world)};
  if(req.op==='step'){
    // Only publish the copy after success. Invalid input, timeout and native
    // exceptions leave the handle, RNG, partial choice and source world intact.
    const w=copy(world);const o=advance(w,req.command);
    const result={status:o.result.terminated?'terminal':'ok',view:publicView(w,o),draws:w.drawTrace,final_score:o.result.final_score};
    tick(null);worlds.set(req.handle,w);return result;
  }
  fail('invalid_input','unknown operation');
}
const lines=createInterface({input:process.stdin,crlfDelay:Infinity});
for await(const line of lines){
  let result;
  try{
    const req=JSON.parse(line);work=blankCost();freezeReasons={};limits={...(req.budget??{}),started:performance.now()};deadline=limits.started+(limits.milliseconds??5000);
    result=dispatch(req);result.cost=cost();
  }catch(e){result={status:e.kind??'native_exception',message:e.message,valid_for_search:false,final_score:null,cost:work?cost():null};}
  guide=null;const used=new Set([...worlds.values()].map(w=>w.context));for(const k of contexts.keys())if(!used.has(k))contexts.delete(k);
  process.stdout.write(JSON.stringify(result)+'\n');
}
