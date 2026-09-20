'use strict';
window.renderSearch = function(s) {
  const d=s.search||{}, section=document.getElementById('search-section');
  section.hidden=!d.enabled;
  if(!d.enabled)return;
  const set=(id,text)=>document.getElementById(id).textContent=text;
  const n=v=>v==null?'—':Number(v).toLocaleString('zh-CN',{maximumFractionDigits:1});
  const loss=v=>v==null?'—':Number(v).toLocaleString('zh-CN',{maximumSignificantDigits:5});
  const c=d.latest?.counts||{}, inf=d.latest?.inference||{}, cfg=d.config||{};
  const supervision=d.supervision||{}, auxiliary=(supervision.execution_mode||cfg.execution_mode)==='auxiliary';
  const pending=s.status==='running'&&s.progress?.event==='search_progress'&&d.current_progress;
  const progress=pending?` · 当前主 rank：${n(pending.roots)} 个搜索在途/待回收；累计判定 ${n(pending.attempted)} 个，预算准入 ${n(pending.accepted)} 个（不含其他 rank）`:'';
  const scope=c.ranks_reporting>1?`全局 ${n(c.ranks_reporting)} 个 rank 汇总`:'主采样器局部';
  const work=d.current_rollout||{};
  const workload=work.kind==='exam_group'&&work.completed!=null?` · 本组考试 ${n(work.completed)}${work.total_games==null?'':` / ${n(work.total_games)}`} 局完成，${n(work.active)} 局进行中`:work.kind==='joint'&&work.completed!=null?` · 联合采样 ${n(work.completed)} 局完成，${n(work.meaningful_decisions)} / ${n(work.target_decisions)} 个有效决策`:'';
  set('search-batch',(d.batch==null?'等待第一批完整更新':`第 ${d.batch} 批 · 已提交统计`)+workload+progress);
  const replicas=d.replicas||s.practice?.config?.forks?.replicas||2;
  const upside=d.objective==='best_of_k';
  const method=auxiliary?'实局由策略采样，搜索只提供额外 CE 监督；目标比较各动作超越另外三局真实最高分的平均贡献。只接受真实终局且通过粒子证据门槛的标签；有限自适应搜索并非独立验证。':`搜索可以接管被选中的实局动作，搜索监督与 PPO 按动作来源区分。${upside?'旧搜索目标使用局部 Best-of-4 估计；有限搜索不能视为精确上限。':''}`;
  const resources=d.resource_settings||{};
  const applied=resources.parallel_roots!=null?` 当前生效：全局并行搜索 ${n(resources.parallel_roots)}，推理合批 ${n(resources.inference_batch)}，每卡微批 ${n(resources.microbatch)}。`:'';
  set('search-method',`构筑与打牌联合更新。同一构筑共 ${replicas} 局，${upside?'以最高分为构筑奖励；打牌按对四局最高分的贡献学习':'以均分为构筑奖励'}。约 1/${cfg.trajectory_every} 的对局启用搜索；每点最多 ${n(cfg.simulations)} 次模拟、${n(cfg.particles)} 个条件样本，时限 ${n(cfg.seconds)} 秒。${method}${applied}`);
  const live=d.inflight_recent||{}, liveNode=document.getElementById('search-live');
  const liveAdmitted=live.budget_admitted_roots??live.valid_targets;
  if(liveNode)liveNode.textContent=live.points?`当前采集窗口：最近 ${n(live.points)} 个搜索点（最多 ${n(live.max_points)} 个），${n(liveAdmitted)} 个通过预算准入、${n(live.points-liveAdmitted)} 个未准入。${auxiliary?'最终 CE 标签还需结合真实四局结果及证据门槛判定。':''}尚未提交更新；下方仍显示完整批次统计。`:'当前没有新的未提交搜索记录。';
  const terminals=c.terminal_simulations||0, boot=c.bootstrap_simulations||0;
  const cards=[['搜索预算准入',`${n(c.accepted_targets)} / ${n(c.attempted_roots)}`,`${scope}已提交计数；分母是已判定 roots，不包括在途搜索，也不等于最终 CE 标签数`],
    ['模拟到真实终局',n(terminals),auxiliary?`${n(boot)} 次遇到截断估值；此类结果不作为辅助 CE 证据`:`${n(boot)} 次在截断处使用模型估值`],
    ['真实动作记录',`${n(supervision.actor_search_records??d.search_records)} / ${n(supervision.real_ppo_records??d.ppo_records)}`,'全局：搜索接管动作 / 策略 PPO 动作；辅助标签不改变动作来源'],
    ['实测推理批量',inf.inference_batches?n(inf.inference_examples/inf.inference_batches):'—','主采样器：平均每次推理的搜索状态数，不是设备利用率']];
  if(auxiliary)cards.splice(3,0,
    ['辅助搜索证据',n(supervision.auxiliary_raw_roots),'全局：附在真实 PPO 记录上的原始搜索 root'],
    ['辅助 CE 标签',n(supervision.auxiliary_labels),'全局：通过质量门的标签；作为 PPO 记录的额外监督，不重复计作实局动作'],
    ['正权重标签',`${n(supervision.auxiliary_weighted_labels)} / ${n(supervision.auxiliary_labels)}`,supervision.auxiliary_labels>0&&supervision.auxiliary_weighted_labels!=null?`占质量门标签 ${n(100*supervision.auxiliary_weighted_labels/supervision.auxiliary_labels)}%；零权重标签不提供该项学习信号`:'等待完整批次的质量门统计']);
  if(upside)cards.unshift(['四局冲分验证',d.best4_validation?n(d.best4_validation.index):'待验证','每套构筑四局取最高，再按各偶像自身基线比较；与均分曲线分开']);
  const box=document.getElementById('search-metrics');box.replaceChildren();
  for(const [label,value,note] of cards){const item=document.createElement('div');item.className='metric';for(const [tag,cls,text] of [['span','label',label],['strong','value',value],['p','',note]]){const el=document.createElement(tag);el.className=cls;el.textContent=text;item.appendChild(el);}box.appendChild(item);}
  const body=document.getElementById('search-profiles');body.replaceChildren();body.title=`按偶像列出的成功数是${scope}预算准入，不是最终辅助 CE 标签数`;
  for(const p of s.profiles||[]){const row=document.createElement('tr');for(const text of [p.name||p.id,n(c['profile:'+p.id]||0),n(c['accepted_profile:'+p.id]||0),n(c['fallback_profile:'+p.id]||0)]){const cell=document.createElement('td');cell.textContent=text;row.appendChild(cell);}body.appendChild(row);}
  const throughput=d.collection_seconds?n(d.batch_decisions_actual/d.collection_seconds):'—';
  const total=d.collection_seconds!=null&&d.update_seconds!=null?d.collection_seconds+d.update_seconds:null;
  const rate=total>0&&d.batch_decisions_actual!=null?n(d.batch_decisions_actual/total):'—';
  set('search-cost',`整批采样／搜索／fork／bank ${n(d.collection_seconds)} 秒 · PPO 更新 ${n(d.update_seconds)} 秒 · 采样阶段 ${throughput} 决策/秒 · 采样＋更新 ${rate} 决策/秒（不含评估） · 主采样器搜索 ${n(inf.search_many_seconds)} 秒，已包含在采样阶段内 · 搜索监督损失 ${loss(d.loss)}`);
  const stages=document.getElementById('search-stage-history');
  if(stages){
    stages.replaceChildren();
    const history=s.performance?.batches||[];
    const shown=history.length>7?[history[0],...history.slice(-6)]:history;
    for(const r of shown){const row=document.createElement('tr');for(const value of [n(r.batch)+(r.from_current_revision?'':' · 接续前'),n(r.decisions),n(r.ppo_records),n(r.collection_seconds==null?null:r.collection_seconds/60),n(r.update_seconds==null?null:r.update_seconds/60),n(r.decisions_per_second)]){const cell=document.createElement('td');cell.textContent=value;row.appendChild(cell);}stages.appendChild(row);}
    if(!shown.length){const row=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=6;cell.textContent='等待第一批完整提交。';row.appendChild(cell);stages.appendChild(row);}
  }
  const failures=Object.entries(c).filter(([k,v])=>k.startsWith('status:')&&!['status:ok','status:ok_truncated'].includes(k)&&v>0).map(([k,v])=>`${k.slice(7)} × ${v}`);
  const rejected=Object.entries(supervision.auxiliary_rejected_reasons||{}).filter(([,v])=>v>0).map(([k,v])=>`${k} × ${v}`);
  const reasons=failures.length?`${scope}未准入原因：`+failures.join('；'):d.batch==null?'完整批次的统计尚未提交。':`${scope}该批暂无未准入记录。`;
  set('search-fallbacks',reasons+(auxiliary?` 全局辅助质量门拒绝 ${n(supervision.auxiliary_rejected_roots)} 个 root${rejected.length?'：'+rejected.join('；'):''}；真实 PPO 样本保留。`:''));
};
