// Search-only instrumentation. Original vendor and production loader stay intact.
import {readFile} from 'node:fs/promises';
import {resolve,load as baseLoad} from '../_vendor/gakumas_tools/scripts/extensionless-loader.mjs';
export {resolve};
export async function load(url,context,nextLoad) {
  if(url.endsWith('/packages/gakumas-engine/utils.js')) {
    let source=(await readFile(new URL(url),'utf8')).replace(/\r\n/g,'\n');
    const patches=[
      ['export function getRand() {','export function getRand() {\n  if(globalThis.__arenaSearch) return globalThis.__arenaSearch.random();'],
      ['export function getRandCallCount() {','export function getRandCallCount() {\n  if(globalThis.__arenaSearch) return globalThis.__arenaSearch.rng.calls;'],
      ['export function resetRand(customSeed) {','export function resetRand(customSeed) {\n  if(globalThis.__arenaSearch) globalThis.__arenaSearch.reset(customSeed ?? seed);'],
      ['  return arr;\n}', '  if(globalThis.__arenaSearch) globalThis.__arenaSearch.shuffled(arr);\n  return arr;\n}'],
    ];
    for(const [before,after] of patches) {
      if(source.split(before).length!==2)throw Error('Search RNG instrumentation source mismatch');
      source=source.replace(before,after);
    }
    return {format:'module',source,shortCircuit:true};
  }
  if(url.endsWith('/engine/training_worker.mjs')) {
    let source=(await readFile(new URL(url),'utf8')).replace(/\r\n/g,'\n');
    const anchor='const engine=new StageEngine(config);';
    if(source.split(anchor).length!==2)throw Error('Search engine instrumentation source mismatch');
    source=source.replace(anchor,anchor+'\n  globalThis.__arenaSearch.instrument(engine,entry);');
    const logAnchor='engine.logger.log=(s,type,data)=>{';
    if(source.split(logAnchor).length!==2)throw Error('Search visibility instrumentation source mismatch');
    source=source.replace(logAnchor,logAnchor+'\n    globalThis.__arenaSearch.onLog(s,type,data);');
    return {format:'module',source,shortCircuit:true};
  }
  return baseLoad(url,context,nextLoad);
}
