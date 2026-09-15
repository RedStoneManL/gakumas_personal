// Scenario sampling policy: keep vendor files immutable and use the golden RNG
// stream plus native addCardToDeck for all instance creation/pile operations.
import {getRand} from '../_vendor/gakumas_tools/packages/gakumas-engine/utils.js';

export function addWeightedBasicCardsToDeck(cardManager,state,num,cardIds,weights) {
  if(!Array.isArray(weights)||weights.length!==cardIds.length||
     new Set(cardIds).size!==cardIds.length||weights.some(w=>!Number.isFinite(w)||w<0)) {
    throw new Error('Invalid weighted basic-card pool');
  }
  const total=weights.reduce((sum,weight)=>sum+weight,0);
  if(!Number.isFinite(total)||total<=0)throw new Error('Weighted basic-card pool needs a positive total weight');
  for(let i=0;i<num;i++) {
    const target=getRand()*total;
    let index=0,cumulative=0;
    for(let j=0;j<weights.length;j++) {
      cumulative+=weights[j];
      if(weights[j]>0)index=j; // Last positive is a rounding-safe fallback.
      if(target<cumulative)break;
    }
    cardManager.addCardToDeck(state,cardIds[index]);
  }
}
