(() => {
  const status = document.querySelector('#resource-status');
  const form = document.querySelector('#resource-form');
  const labels = {workers: '采样进程', parallel_roots: '并行搜索', inference_batch: '推理合批', microbatch: '每卡微批', torch_threads: '每卡 CPU 线程'};
  let state, dirty = false, busy = false;
  Object.entries(labels).forEach(([key, title]) => {
    const label = document.createElement('label'); label.textContent = title + ' ';
    const input = document.createElement('input');
    Object.assign(input, {name: key, type: 'number', min: '1', step: '1', required: true});
    input.style.width = '7em'; input.addEventListener('input', () => { dirty = true; });
    label.append(input); form.append(label);
  });
  const submit = document.createElement('button');
  submit.type = 'submit'; submit.textContent = '下一批应用'; form.append(submit);
  function render(value) {
    state = value; const actual = value.actual || {};
    if (!dirty) Object.keys(labels).forEach(key => { form.elements[key].value = actual[key] ?? value.configured[key] ?? ''; });
    submit.disabled = busy || !value.enabled;
    status.textContent = actual.mode
      ? `当前：${actual.workers} 个采样进程 · ${actual.parallel_roots} 个并行搜索 · 推理合批 ${actual.inference_batch} · 每卡微批 ${actual.microbatch} · 全局批量 ${value.effective_minibatch}`
      : '等待训练写入资源状态';
    if (value.requested?.request_id && value.requested.request_id !== actual.request_id) status.textContent += ' · 有待应用请求';
    if (value.error) status.textContent += ' · ' + value.error;
  }
  async function refresh() {
    try { const response = await fetch('/api/generalist/resources'); if (!response.ok) throw new Error('资源状态读取失败'); render(await response.json()); }
    catch (error) { status.textContent = error.message; }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (!state?.enabled || busy) return;
    const parallelism = Object.fromEntries(Object.keys(labels).map(key => [key, Number(form.elements[key].value)]));
    if (Object.values(parallelism).some(value => !Number.isSafeInteger(value) || value < 1)) { status.textContent = '请输入可精确表示的正整数。'; return; }
    busy = true; submit.disabled = true;
    try {
      const response = await fetch('/api/generalist/resources', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({run_id: state.run_id, parallelism})});
      const value = await response.json(); if (!response.ok) throw new Error(value.error || '资源请求失败');
      dirty = false; render(value);
    } catch (error) { status.textContent = error.message; }
    finally { busy = false; submit.disabled = !state.enabled; }
  });
  refresh(); setInterval(refresh, 5000);
})();
