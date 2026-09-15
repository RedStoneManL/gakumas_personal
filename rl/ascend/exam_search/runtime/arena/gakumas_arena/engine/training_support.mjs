// Adapter-owned temporary support levels. No vendor files or global RNG are replaced.
import {SkillCards,parseEffects,transformEffects} from 'gakumas-data';
import {S} from '../_vendor/gakumas_tools/packages/gakumas-engine/constants.js';
import {getRand} from '../_vendor/gakumas_tools/packages/gakumas-engine/utils.js';

const copy=x=>structuredClone(x);
const parse=text=>transformEffects(parseEffects(text));
const stable=x=>JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v);
function lists(effects,result=[]) {
  for(const effect of effects||[]) {
    if(effect.actions)result.push(effect.actions);
    if(effect.effects)lists(effect.effects,result);
  }
  return result;
}
const atoms=text=>lists(parse(text)).flat();
function matches(effects,needle) {
  const found=[];
  for(const list of lists(effects))for(let i=0;i<=list.length-needle.length;i++)
    if(needle.every((a,j)=>stable(a)===stable(list[i+j])))found.push({list,index:i});
  return found;
}
export function patchSupportLines(original,patches) {
  const result=copy(original||[]);
  for(const patch of [...patches].reverse()) {
    if(patch.op==='condition') {
      let changed=0;
      const visit=x=>{
        if(!x||typeof x!=='object')return;
        if(x.type==='comparison'&&x.left?.name===patch.field&&x.right?.value===patch.old) {x.right={...x.right,value:patch.new};changed++;}
        for(const v of Object.values(x))if(typeof v==='object')visit(v);
      };visit(result);
      if(!changed)throw Error(`condition ${patch.field}: ${patch.old}`);
      continue;
    }
    const old=atoms(patch.old),replacement=atoms(patch.new);
    if(old.length) {
      const match=matches(result,old)[patch.occurrence||0];
      if(!match)throw Error(`missing ${patch.old} (occurrence ${patch.occurrence||0})`);
      match.list.splice(match.index,old.length,...replacement);
    } else if(replacement.length) {
      // Structural inserts in this master snapshot are unconditional. Keep
      // them outside any condition attached to the next original effect.
      const anchor=patch.before?atoms(patch.before):null;
      let top=result.length;
      if(anchor) {
        let remaining=patch.occurrence||0,found=false;
        for(let i=0;i<result.length;i++) {
          const n=matches([result[i]],anchor).length;
          if(remaining<n){top=i;found=true;break;}remaining-=n;
        }
        if(!found)throw Error(`missing insertion anchor ${patch.before}`);
      }
      result.splice(top,0,{actions:replacement});
    }
  }
  return result;
}

export function compileSupportCatalog(variants) {
  const byId=new Map(),audit=[];
  for(const row of variants) {
    const original=SkillCards.getById(row.upgraded_definition_id);
    const levels={1:original};
    for(const level of [2,3]) {
      const definition={...original},failures=[];
      for(const field of ['actions','effects','cost']) {
        try {definition[field]=patchSupportLines(original[field],row.levels[level].patches[field]);}
        catch(error) {failures.push(`${field}: ${error.message}`);}
      }
      levels[level]=definition;
      audit.push({master_card_id:row.master_card_id,level,failures});
    }
    const compiled={...row,levels};
    byId.set(row.base_definition_id,compiled);byId.set(row.upgraded_definition_id,compiled);
  }
  return {byId,audit};
}

export function validateSkillCardSupport(config,check) {
  const path='entry.context.skill_card_support';
  check(config&&config.schema_version==='arena-skill-card-support/1',path,'unknown support schema');
  check(Array.isArray(config.sources)&&config.sources.length<=6,`${path}.sources`,'at most six support sources');
  check(new Set(config.sources.map(s=>s.support_card_id)).size===config.sources.length,`${path}.sources`,'duplicate support source');
  check(config.target_policy==='uniform'&&config.order_policy==='loadout_order',path,'unknown support selection/order policy');
  for(const [i,s] of config.sources.entries()) {
    check(typeof s.support_card_id==='string'&&s.support_card_id,`${path}.sources[${i}]`,'source ID required');
    check(Number.isFinite(s.probability)&&s.probability>=0&&s.probability<=1,`${path}.sources[${i}].probability`,'expected 0..1');
    check(s.turn_type===null||['vocal','dance','visual'].includes(s.turn_type),`${path}.sources[${i}].turn_type`,'unknown lesson color');
  }
  check(Array.isArray(config.variants)&&config.variants.length<=1000,`${path}.variants`,'expected master support variants');
  const ids=new Set();
  for(const row of config.variants) {
    const base=SkillCards.getById(row.base_definition_id),up=SkillCards.getById(row.upgraded_definition_id);
    check(base&&!base.upgraded&&up?.upgraded&&up.id===base.id+1,path,'support identity must match a native base/+1 pair');
    check(!ids.has(base.id),path,'duplicate support family');ids.add(base.id);
    for(const level of [2,3])for(const field of ['actions','effects','cost'])
      check(Array.isArray(row.levels?.[level]?.patches?.[field]),path,`missing level ${level} ${field} patches`);
  }
}

export function installSkillCardSupport(ctx) {
  const config=ctx.entry.context.skill_card_support;
  if(!config?.sources.length)return;
  const {byId,audit}=compileSupportCatalog(config.variants);
  const errors=audit.filter(r=>r.failures.length);
  if(errors.length) {
    const error=Error(`support master/golden mismatch: ${JSON.stringify(errors)}`);
    error.path='entry.context.skill_card_support.variants';error.kind='invalid_configuration';throw error;
  }
  ctx.skillCardSupportAudit={schema_version:config.schema_version,compiled_variants:audit.length,failed_variants:0,
    sampling_approximation:config.sampling_approximation};
  const {engine}=ctx,cm=engine.cardManager,tm=engine.turnManager;
  const getLines=cm.getLines.bind(cm);
  cm.getLines=(s,index,attribute)=>{
    const card=s[S.cardMap][index],support=card.arenaSupport;
    if(!support||support.level<=1)return getLines(s,index,attribute);
    const def=byId.get(card.id).levels[support.level];
    // Native customization anchors are applied to the upgraded program itself.
    // The override is synchronous and restored before yielding or running effects.
    const original=SkillCards.getById;
    SkillCards.getById=id=>id===card.id?def:original.call(SkillCards,id);
    try{return getLines(s,index,attribute);}finally{SkillCards.getById=original;}
  };
  function refreshPrimary(s,index,before) {
    const after=cm.getLines(s,index,'effects');
    if(before.length!==after.length)throw Error('support primary-effect topology changed');
    let slot=0;
    s[S.effects]=s[S.effects].map(effect=>{
      if(effect.source?.type!=='skillCard'||!effect.source?.primary||effect.source.idx!==index)return effect;
      // Expired native effects can become {} in place. Remember the template
      // slot across upgrades so a later sibling never inherits the wrong AST.
      const effectSlot=effect.arenaSupportSlot??before.findIndex((rule,i)=>i>=slot&&rule.phase===effect.phase);
      const prior=before[effectSlot],next=after[effectSlot];slot=effectSlot+1;
      if(!prior||!next)return effect;
      const changed={...effect,arenaSupportSlot:effectSlot};
      for(const key of ['actions','effects','conditions']) {
        if(next[key]===undefined)delete changed[key];else changed[key]=copy(next[key]);
      }
      if(Number.isFinite(prior.limit)&&Number.isFinite(next.limit)&&Number.isFinite(effect.limit))
        changed.limit=Math.max(0,effect.limit+next.limit-prior.limit);
      return changed;
    });
  }
  function clear(s) {
    for(let index=0;index<s[S.cardMap].length;index++) {
      const card=s[S.cardMap][index];
      if(!card.arenaSupport)continue;
      const before=cm.getLines(s,index,'effects');
      const restored={...card,id:card.arenaSupport.permanent_id};delete restored.arenaSupport;
      s[S.cardMap][index]=restored;refreshPrimary(s,index,before);
    }
  }
  const isUpgradable=cm.isUpgradable.bind(cm),upgrade=cm.upgrade.bind(cm);
  cm.isUpgradable=(s,index)=>{
    const card=s[S.cardMap][index];
    if(!card.arenaSupport)return isUpgradable(s,index);
    const permanent=SkillCards.getById(card.arenaSupport.permanent_id);
    return !permanent.upgraded&&permanent.type!=='trouble'&&permanent.rarity!=='L';
  };
  cm.upgrade=(s,index)=>{
    const card=s[S.cardMap][index];
    if(!card.arenaSupport)return upgrade(s,index);
    if(!cm.isUpgradable(s,index))return;
    const before=cm.getLines(s,index,'effects');
    s[S.cardMap][index]={...card,arenaSupport:{...card.arenaSupport,
      permanent_id:card.arenaSupport.permanent_id+1,level:Math.min(3,card.arenaSupport.level+1)}};
    s[S.turnCardsUpgraded]++;refreshPrimary(s,index,before);
  };
  function apply(s) {
    const color=tm.getTurnType(s),events=[];
    for(const source of config.sources) {
      if(source.turn_type!==null&&source.turn_type!==color)continue;
      const candidates=s[S.handCards].filter(index=>{
        const card=s[S.cardMap][index],def=SkillCards.getById(card.id);
        return byId.has(card.id)&&def.type!=='trouble'&&def.rarity!=='L'&&(card.arenaSupport?.level??Number(!!def.upgraded))<3;
      });
      if(!candidates.length||source.probability===0)continue;
      if(getRand()>=source.probability)continue;
      const index=candidates[Math.floor(getRand()*candidates.length)],card=s[S.cardMap][index];
      const family=byId.get(card.id),prior=card.arenaSupport;
      const before=cm.getLines(s,index,'effects');
      const support={permanent_id:prior?.permanent_id??card.id,
        level:(prior?.level??Number(!!SkillCards.getById(card.id).upgraded))+1,
        sources:[...(prior?.sources||[]),source.support_card_id]};
      s[S.cardMap][index]={...card,id:family.upgraded_definition_id,arenaSupport:support};
      refreshPrimary(s,index,before);
      events.push({source:source.support_card_id,card_index:index,upgrade_level:support.level});
      engine.logger.log(s,'skillCardSupport',{source:source.support_card_id,card:index,upgradeLevel:support.level});
    }
    s[S.graphData]={...s[S.graphData],arenaSkillCardSupport:{turn:s[S.turnsElapsed]+1,events}};
  }
  const start=tm.startTurn.bind(tm),end=tm.endTurn.bind(tm);
  tm.startTurn=(s,...args)=>{clear(s);const result=start(s,...args);apply(s);return result;};
  tm.endTurn=s=>{const result=end(s);if(s[S.turnsRemaining]<=0)clear(s);return result;};
}
