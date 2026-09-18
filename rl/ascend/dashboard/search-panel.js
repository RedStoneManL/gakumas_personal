'use strict';
window.renderSearch = function(s) {
  const d=s.search||{}, section=document.getElementById('search-section');
  section.hidden=!d.enabled;
  if(!d.enabled)return;
  const set=(id,text)=>document.getElementById(id).textContent=text;
  const n=v=>v==null?'—':Number(v).toLocaleString('zh-CN',{maximumFractionDigits:1});
  const c=d.latest?.counts||{}, inf=d.latest?.inference||{}, cfg=d.config||{};
  const supervision=d.supervision||{}, auxiliary=(supervision.execution_mode||cfg.execution_mode)==='auxiliary';
  const pending=s.progress?.event==='search_progress'&&d.current_progress;
  const progress=pending?` · 当前搜索组已完成 ${n(pending.completed_roots)} / ${n(pending.roots)} 个点`:'';
  const work=d.current_rollout||{};
  const workload=work.kind==='exam_group'&&work.completed!=null?` · 本组考试 ${n(work.completed)}${work.total_games==null?'':` / ${n(work.total_games)}`} 局完成，${n(work.active)} 局进行中`:work.kind==='joint'&&work.completed!=null?` · 联合采样 ${n(work.completed)} 局完成，${n(work.meaningful_decisions)} / ${n(work.target_decisions)} 个有效决策`:'';
  set('search-batch',(d.batch==null?'等待第一批完整更新':`第 ${d.batch} 批 · 已提交统计`)+workload+progress);
  const replicas=d.replicas||s.practice?.config?.forks?.replicas||2;
  const upside=d.objective==='best_of_k';
  const method=auxiliary?'实局由策略采样，搜索只提供额外 CE 监督；目标比较各动作超越另外三局真实最高分的平均贡献。只接受真实终局且通过粒子证据门槛的标签；有限自适应搜索并非独立验证。':`搜索可以接管被选中的实局动作，搜索监督与 PPO 按动作来源区分。${upside?'旧搜索目标使用局部 Best-of-4 估计；有限搜索不能视为精确上限。':''}`;
  set('search-method',`构筑与打牌联合更新。同一构筑共 ${replicas} 局，${upside?'以最高分为构筑奖励；打牌按对四局最高分的贡献学习':'以均分为构筑奖励'}。约 1/${cfg.trajectory_every} 的对局启用搜索；每点 ${cfg.simulations} 次模拟、${cfg.particles} 个条件样本。${method}`);
  const live=d.inflight_recent||{}, liveNode=document.getElementById('search-live');
  const liveAdmitted=live.budget_admitted_roots??live.valid_targets;
  if(liveNode)liveNode.textContent=live.points?`当前采集窗口：最近 ${n(live.points)} 个搜索点（最多 ${n(live.max_points)} 个），${n(liveAdmitted)} 个通过预算准入、${n(live.points-liveAdmitted)} 个未准入。${auxiliary?'最终 CE 标签还需结合真实四局结果及证据门槛判定。':''}尚未提交更新；下方仍显示完整批次统计。`:'当前没有新的未提交搜索记录。';
  const terminals=c.terminal_simulations||0, boot=c.bootstrap_simulations||0;
  const cards=[['搜索预算准入',`${n(c.accepted_targets)} / ${n(c.attempted_roots)}`,'主采样器局部计数；不等于全局 CE 标签数，不按设备数外推'],
    ['模拟到真实终局',n(terminals),auxiliary?`${n(boot)} 次遇到截断估值；此类结果不作为辅助 CE 证据`:`${n(boot)} 次在截断处使用模型估值`],
    ['真实动作记录',`${n(supervision.actor_search_records??d.search_records)} / ${n(supervision.real_ppo_records??d.ppo_records)}`,'全局：搜索接管动作 / 策略 PPO 动作；辅助标签不改变动作来源'],
    ['实测推理批量',inf.inference_batches?n(inf.inference_examples/inf.inference_batches):'—','平均同时处理的搜索状态数']];
  if(auxiliary)cards.splice(3,0,
    ['辅助搜索证据',n(supervision.auxiliary_raw_roots),'全局：附在真实 PPO 记录上的原始搜索 root'],
    ['辅助 CE 标签',`${n(supervision.auxiliary_labels)} / ${n(supervision.auxiliary_weighted_labels)}`,'通过质量门标签 / 其中正权重标签；是 PPO 记录的额外监督，不能重复计作实局动作']);
  if(upside)cards.unshift(['四局冲分验证',d.best4_validation?n(d.best4_validation.index):'待验证','每套构筑四局取最高，再按各偶像自身基线比较；与均分曲线分开']);
  const box=document.getElementById('search-metrics');box.replaceChildren();
  for(const [label,value,note] of cards){const item=document.createElement('div');item.className='metric';for(const [tag,cls,text] of [['span','label',label],['strong','value',value],['p','',note]]){const el=document.createElement(tag);el.className=cls;el.textContent=text;item.appendChild(el);}box.appendChild(item);}
  const body=document.getElementById('search-profiles');body.replaceChildren();body.title='按偶像列出的成功数是主采样器预算准入，不是最终辅助 CE 标签数';
  for(const p of s.profiles||[]){const row=document.createElement('tr');for(const text of [p.name||p.id,n(c['profile:'+p.id]||0),n(c['accepted_profile:'+p.id]||0),n(c['fallback_profile:'+p.id]||0)]){const cell=document.createElement('td');cell.textContent=text;row.appendChild(cell);}body.appendChild(row);}
  const throughput=d.collection_seconds?n(d.batch_decisions_actual/d.collection_seconds):'—';
  set('search-cost',`采集 ${n(d.collection_seconds)} 秒 · 参数更新 ${n(d.update_seconds)} 秒 · 实际 ${throughput} 决策/秒 · 搜索墙钟 ${n(inf.search_many_seconds)} 秒 · 搜索监督损失 ${n(d.loss)}`);
  const failures=Object.entries(c).filter(([k,v])=>k.startsWith('status:')&&!['status:ok','status:ok_truncated'].includes(k)&&v>0).map(([k,v])=>`${k.slice(7)} × ${v}`);
  const rejected=Object.entries(supervision.auxiliary_rejected_reasons||{}).filter(([,v])=>v>0).map(([k,v])=>`${k} × ${v}`);
  const reasons=failures.length?'主采样器未准入原因：'+failures.join('；'):d.batch==null?'完整批次的统计尚未提交。':'主采样器该批暂无未准入记录。';
  set('search-fallbacks',reasons+(auxiliary?` 全局辅助质量门拒绝 ${n(supervision.auxiliary_rejected_roots)} 个 root${rejected.length?'：'+rejected.join('；'):''}；真实 PPO 样本保留。`:''));
};
