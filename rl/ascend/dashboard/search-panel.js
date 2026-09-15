'use strict';
window.renderSearch = function(s) {
  const d=s.search||{}, section=document.getElementById('search-section');
  section.hidden=!d.enabled;
  if(!d.enabled)return;
  const set=(id,text)=>document.getElementById(id).textContent=text;
  const n=v=>v==null?'—':Number(v).toLocaleString('zh-CN',{maximumFractionDigits:1});
  const c=d.latest?.counts||{}, inf=d.latest?.inference||{}, cfg=d.config||{};
  const pending=s.progress?.event==='search_progress'&&d.current_progress;
  const progress=pending?` · 当前搜索组已完成 ${n(pending.completed_roots)} / ${n(pending.roots)} 个点`:'';
  const work=d.current_rollout||{};
  const workload=work.kind==='exam_group'&&work.completed!=null?` · 本组考试 ${n(work.completed)}${work.total_games==null?'':` / ${n(work.total_games)}`} 局完成，${n(work.active)} 局进行中`:work.kind==='joint'&&work.completed!=null?` · 联合采样 ${n(work.completed)} 局完成，${n(work.meaningful_decisions)} / ${n(work.target_decisions)} 个有效决策`:'';
  set('search-batch',(d.batch==null?'等待第一批完整更新':`第 ${d.batch} 批 · 已提交统计`)+workload+progress);
  const replicas=d.replicas||s.practice?.config?.forks?.replicas||2;
  const upside=d.objective==='best_of_k';
  set('search-method',`构筑与打牌联合更新；构筑／考试各 4 层交互分支。同一构筑共 ${replicas} 局，${upside?'以最高分为构筑奖励；打牌按对四局最高分的贡献学习':'以均分为构筑奖励'}。约 1/${cfg.trajectory_every} 的对局启用搜索；每点 ${cfg.simulations} 次模拟、${cfg.particles} 个条件样本。${upside?'搜索采用局部 Best-of-4 估计；未到终局的叶子仍使用标量估值，不能视为精确上限。':''}`);
  const live=d.inflight_recent||{}, liveNode=document.getElementById('search-live');
  if(liveNode)liveNode.textContent=live.points?`当前采集窗口：最近 ${n(live.points)} 个搜索点（最多 ${n(live.max_points)} 个），${n(live.valid_targets)} 个可用标签、${n(live.points-live.valid_targets)} 个回退。尚未提交更新；下方仍显示完整批次统计。`:'当前没有新的未提交搜索记录。';
  const terminals=c.terminal_simulations||0, boot=c.bootstrap_simulations||0;
  const cards=[['搜索标签',`${n(c.accepted_targets)} / ${n(c.attempted_roots)}`,'通过条件采样与预算检查'],
    ['模拟到真实终局',n(terminals),`其余 ${n(boot)} 次在截断处使用模型估值`],
    ['本批学习记录',`${n(d.search_records)} / ${n(d.ppo_records)}`,'搜索监督 / PPO；二者分别计算损失'],
    ['实测推理批量',inf.inference_batches?n(inf.inference_examples/inf.inference_batches):'—','平均同时处理的搜索状态数']];
  if(upside)cards.unshift(['四局冲分验证',d.best4_validation?n(d.best4_validation.index):'待验证','每套构筑四局取最高，再按各偶像自身基线比较；与均分曲线分开']);
  const box=document.getElementById('search-metrics');box.replaceChildren();
  for(const [label,value,note] of cards){const item=document.createElement('div');item.className='metric';for(const [tag,cls,text] of [['span','label',label],['strong','value',value],['p','',note]]){const el=document.createElement(tag);el.className=cls;el.textContent=text;item.appendChild(el);}box.appendChild(item);}
  const body=document.getElementById('search-profiles');body.replaceChildren();
  for(const p of s.profiles||[]){const row=document.createElement('tr');for(const text of [p.name||p.id,n(c['profile:'+p.id]||0),n(c['accepted_profile:'+p.id]||0),n(c['fallback_profile:'+p.id]||0)]){const cell=document.createElement('td');cell.textContent=text;row.appendChild(cell);}body.appendChild(row);}
  const throughput=d.collection_seconds?n(d.batch_decisions_actual/d.collection_seconds):'—';
  set('search-cost',`采集 ${n(d.collection_seconds)} 秒 · 参数更新 ${n(d.update_seconds)} 秒 · 实际 ${throughput} 决策/秒 · 搜索墙钟 ${n(inf.search_many_seconds)} 秒 · 搜索监督损失 ${n(d.loss)}`);
  const failures=Object.entries(c).filter(([k,v])=>k.startsWith('status:')&&k!=='status:ok'&&v>0).map(([k,v])=>`${k.slice(7)} × ${v}`);
  set('search-fallbacks',failures.length?'已提交批次回退原因：'+failures.join('；'):d.batch==null?'完整批次的统计尚未提交；超时或条件采样失败的点只保留真实 PPO 样本。':'该批暂无拒绝标签；超时或条件采样失败的点只保留真实 PPO 样本。');
};
