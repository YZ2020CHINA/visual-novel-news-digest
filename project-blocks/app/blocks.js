/* Project Blocks adapter for the GalFlow 1.12 canvas. No external dependencies. */
(() => {
  'use strict';
  const TYPES = {
    prologue: ['需求', '#9b8aff', '明确要做什么'], route: ['模块', '#72a8f8', '划分功能边界'],
    common: ['任务', '#73d2b3', '可执行的工序'], character: ['资源', '#e6b66d', '素材与参考文件'],
    branch: ['决策', '#f295ac', '记录方案与取舍'], ending: ['验收', '#b0cb70', '验证交付结果']
  };
  const STATUS = {todo:['待开始','#9baac4'], doing:['进行中','#8ba9ff'], blocked:['受阻','#edaa6b'], review:['待验收','#c5a2fa'], done:['已完成','#73d2b3']};
  const RELATIONS = ['前置依赖','组成模块','提供资源','验证结果','参考关联'];
  let revision = null, baseline = '', remote = null, loading = true, saving = false, panel = null;
  let statusFilter = 'all';
  let dataFile = 'project-blocks/data/project.json';
  const $ = id => document.getElementById(id);
  const esc = escapeHtml;
  const uid = prefix => prefix + '_' + crypto.randomUUID();
  const wf = n => n.workflow || {status:'todo', acceptance:[], files:[], priority:'P1'};
  function snapshot(){ project.title = projectTitleInput.value || '未命名项目'; return JSON.stringify(project); }
  function dirty(){ return snapshot() !== baseline; }
  function links(){return project.nodes.flatMap(n => n.choices?.length ? n.choices.filter(c=>c.target).map(c=>({from:n.id,to:c.target,type:c.tag || '前置依赖'})) : n.defaultNext ? [{from:n.id,to:n.defaultNext,type:'前置依赖'}] : []);}
  function prerequisites(n){return links().filter(e=>e.to===n.id && e.type==='前置依赖').map(e=>project.nodes.find(x=>x.id===e.from)).filter(Boolean);}
  function blockers(n){return prerequisites(n).filter(x=>wf(x).status!=='done');}
  function stats(){
    if (!$('pb-count')) return;
    const done = project.nodes.filter(n=>wf(n).status==='done').length;
    $('pb-count').textContent = project.nodes.length;
    $('pb-done').textContent = done;
    $('pb-links').textContent = links().length;
    $('pb-blocked').textContent = project.nodes.filter(n=>wf(n).status==='blocked').length;
    $('pb-progress').style.width = (project.nodes.length ? done/project.nodes.length*100 : 0)+'%';
    const indicator = $('pb-sync');
    indicator.dataset.dirty = String(dirty());
    indicator.textContent = loading ? '正在读取工程…' : remote ? '磁盘有新版本 · 点击处理冲突' : revision ? (dirty() ? '有未保存修改 · Ctrl+S 写入工程' : '已与本地工程同步') : '离线模式 · 保存为 JSON';
    $('pb-save').disabled = loading || saving;
    document.querySelectorAll('.story-node').forEach(el=>{
      const n = project.nodes.find(n=>n.id===el.dataset.id);
      el.classList.toggle('pb-hidden-card', !!n && statusFilter!=='all' && wf(n).status!==statusFilter);
    });
    let empty = $('pb-empty');
    if (!project.nodes.length && !empty){empty=document.createElement('div');empty.id='pb-empty';empty.className='pb-empty';empty.textContent='从左侧拖入第一块积木\n或使用「从大纲生成」创建工序';empty.style.whiteSpace='pre-line';canvasViewport.append(empty);}
    if(project.nodes.length && empty)empty.remove();
  }
  const originalRender = renderAll;
  renderAll = function(){originalRender();stats();};
  const originalCard = createNodeElement;
  createNodeElement = function(n){
    const card=originalCard(n), w=wf(n), s=STATUS[w.status] || STATUS.todo;
    card.style.setProperty('--pb-color', n.color || TYPES[n.routeType]?.[1] || '#8b9dff');
    const info=document.createElement('div');info.className='pb-card-info';
    info.innerHTML=`<span class="pb-pill" data-status="${esc(w.status || 'todo')}" style="--status-color:${s[1]}">${s[0]}</span><span>${esc(w.priority || 'P1')} · ${esc(n.characters || '未分配')}</span>`;
    card.querySelector('.node-header').after(info);
    const detail=document.createElement('div');detail.className='pb-card-check';
    const count=(w.acceptance || []).length;
    detail.innerHTML=`${count ? '☑ '+count+' 条验收标准' : '○ 待补充验收标准'}${blockers(n).length ? ' <span class="pb-warn">· '+blockers(n).length+' 项前置未完成</span>' : ''}<div class="pb-card-files">${esc((w.files || []).join(' · ') || n.location || '尚未关联文件')}</div>`;
    card.querySelector('.node-body').after(detail);
    if(n.choices?.length){const port=document.createElement('div');port.className='port port-out-default';port.dataset.portType='default-out';port.dataset.nodeId=n.id;port.title='拖动以增加一条前置依赖';card.append(port);}
    return card;
  };
  completeConnection=function(sourceId,choiceId,targetId){
    const source=project.nodes.find(n=>n.id===sourceId),target=project.nodes.find(n=>n.id===targetId);
    if(!source || !target || source===target)return;
    if(!choiceId && links().some(e=>e.from===sourceId && e.to===targetId && e.type==='前置依赖'))return showToast('这条前置依赖已存在','info');
    pushHistory();
    if(choiceId){const rel=source.choices.find(c=>c.id===choiceId);if(rel)rel.target=targetId;}
    else{source.choices ||= [];if(source.defaultNext){source.choices.push({id:uid('rel'),text:'前置依赖',tag:'前置依赖',target:source.defaultNext});delete source.defaultNext;}source.choices.push({id:uid('rel'),text:'前置依赖',tag:'前置依赖',target:targetId});}
    renderAll();triggerAutoSave();showToast('已连接：'+source.title+' → '+target.title,'success');
  };

  function closePanel(){if(panel){panel.remove();panel=null;}}
  function dialog(title,subtitle,body,actions){
    closePanel();panel=document.createElement('div');panel.className='pb-overlay';
    panel.innerHTML=`<section class="pb-dialog" role="dialog" aria-modal="true" aria-label="${esc(title)}"><h2>${esc(title)}</h2><p>${esc(subtitle)}</p>${body}<p id="pb-error" class="pb-error" role="alert"></p><div class="pb-actions">${actions}<button class="pb-btn" id="pb-close">关闭</button></div></section>`;
    document.body.append(panel);$('pb-close').onclick=closePanel;
    panel.addEventListener('pointerdown',e=>{if(e.target===panel)closePanel();});
    const first=panel.querySelector('input,textarea,button');first?.focus();
    return panel;
  }
  function err(message){if($('pb-error'))$('pb-error').textContent=message;else showToast(message,'info');}
  function lines(text){return text.split('\n').map(x=>x.trim()).filter(Boolean);}
  function options(dict,value){return Object.entries(dict).map(([key,item])=>`<option value="${key}" ${key===value?'selected':''}>${esc(item[0])}</option>`).join('');}
  function editNode(id){
    const n=project.nodes.find(n=>n.id===id);if(!n)return;
    const w=wf(n);
    const field=(label,id,value,wide=false,textarea=false)=>`<label class="pb-field ${wide?'wide':''}">${label}${textarea?`<textarea id="${id}">${esc(value)}</textarea>`:`<input id="${id}" value="${esc(value)}">`}</label>`;
    dialog('编辑工序积木','把目标、文件和验收标准放在同一张卡片上。关系的箭头从前置工序指向后续工序。',`<div class="pb-grid">
      ${field('卡片名称','pb-title',n.title)}<label class="pb-field">积木类型<select id="pb-type">${options(TYPES,n.routeType)}</select></label>
      <label class="pb-field">工序状态<select id="pb-status">${options(STATUS,w.status)}</select></label><label class="pb-field">优先级<select id="pb-priority">${['P0','P1','P2','P3'].map(v=>`<option ${w.priority===v?'selected':''}>${v}</option>`).join('')}</select></label>
      ${field('负责人','pb-owner',n.characters || '')}${field('交付物','pb-deliverable',n.bgm || '')}
      ${field('任务目标','pb-goal',n.summary || '',true,true)}${field('关联文件 / 路径（每行一个）','pb-files',(w.files || (n.location?[n.location]:[])).join('\n'),true,true)}
      ${field('验收标准（每行一条）','pb-acceptance',(w.acceptance || []).join('\n'),true,true)}${field('给 Codex 的执行说明','pb-instructions',n.script || '',true,true)}
      ${field('阻塞原因 / 待确认事项','pb-block-reason',w.blockReason || '',true)}
      </div><div class="pb-eyebrow">输出关系</div><div id="pb-relations"></div><button class="pb-btn" id="pb-add-rel">＋ 增加关系</button>`, '<button class="pb-btn pb-primary" id="pb-apply">保存卡片</button>');
    function row(type='前置依赖',target=''){
      const r=document.createElement('div');r.className='pb-rel-row';
      r.innerHTML=`<select class="rel-type">${RELATIONS.map(x=>`<option ${x===type?'selected':''}>${x}</option>`).join('')}</select><select class="rel-target"><option value="">选择目标工序…</option>${project.nodes.filter(x=>x.id!==id).map(x=>`<option value="${esc(x.id)}" ${x.id===target?'selected':''}>${esc(x.title)}</option>`).join('')}</select><button title="删除关系">×</button>`;
      r.querySelector('button').onclick=()=>r.remove();$('pb-relations').append(r);
    }
    (n.choices?.length?n.choices.filter(c=>c.target).map(c=>[c.tag || '前置依赖',c.target]):n.defaultNext?[['前置依赖',n.defaultNext]]:[]).forEach(args=>row(...args));
    $('pb-add-rel').onclick=()=>row();
    $('pb-apply').onclick=()=>{
      if(!$('pb-title').value.trim())return err('请填写卡片名称');
      const relations=[...$('pb-relations').children].map(r=>({tag:r.querySelector('.rel-type').value,target:r.querySelector('.rel-target').value}));
      if(relations.some(r=>!r.target))return err('请选择关系目标，或删除空关系');
      if(new Set(relations.map(r=>r.tag+'|'+r.target)).size!==relations.length)return err('存在重复关系');
      const status=$('pb-status').value;
      if(status==='done' && blockers(n).length)return err('仍有前置工序未完成，请先完成前置工序或调整依赖关系');
      pushHistory();n.title=$('pb-title').value.trim();n.routeType=$('pb-type').value;n.color=TYPES[n.routeType][1];n.characters=$('pb-owner').value.trim();n.bgm=$('pb-deliverable').value.trim();n.summary=$('pb-goal').value;n.script=$('pb-instructions').value;
      n.workflow={...w,status,priority:$('pb-priority').value,files:lines($('pb-files').value),acceptance:lines($('pb-acceptance').value),blockReason:$('pb-block-reason').value};n.location=n.workflow.files.join(', ');
      n.choices=relations.map(r=>({id:uid('rel'),text:r.tag,tag:r.tag,target:r.target}));delete n.defaultNext;
      closePanel();renderAll();triggerAutoSave();
    };
  }
  openNodeModal=editNode;
  const originalAdd=addNewNode;
  addNewNode=function(props={}){
    const type=props.routeType || 'common';
    return originalAdd({title:'新的'+(TYPES[type]?.[0] || '任务'),routeType:type,color:TYPES[type]?.[1] || '#73d2b3',characters:'',location:'',bgm:'',summary:'描述这一工序的目标与边界',script:'',image:'',choices:[],workflow:{status:'todo',priority:'P1',files:[],acceptance:[]},...props});
  };

  function taskText(nodes){
    return `# ${project.title} — Codex 任务\n\n工程文件：${dataFile}\n\n请先检查相关文件，再按依赖顺序实施；不要仅根据计划标记已完成。完成后更新工程 JSON 中对应 ID 的状态、文件路径和验收证据，保留其他卡片、坐标与关系。\n\n`+nodes.map(n=>{
      const w=wf(n), prereq=prerequisites(n);
      return `## ${n.title}\n\n- 卡片 ID：${n.id}\n- 类型：${TYPES[n.routeType]?.[0] || '任务'}\n- 状态：${STATUS[w.status]?.[0] || '待开始'}\n- 优先级：${w.priority || 'P1'}\n- 负责人：${n.characters || '待分配'}\n- 前置工序：${prereq.map(x=>x.title+' ['+x.id+']').join('、') || '无'}\n- 文件：${(w.files || []).join('、') || n.location || '待确定'}\n- 交付物：${n.bgm || '待确定'}\n\n目标：${n.summary || '待补充'}\n\n执行说明：\n${n.script || '请根据现有代码和任务目标实施。'}\n\n验收标准：\n${(w.acceptance || []).map(x=>'- [ ] '+x).join('\n') || '- [ ] 请先补充可验证的标准'}\n${w.blockReason?'\n阻塞原因：'+w.blockReason+'\n':''}`;
    }).join('\n---\n\n');
  }
  function download(name,text,type='text/plain'){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function showTask(nodes){
    const text=taskText(nodes);
    dialog('交给 Codex 的任务',`已整理 ${nodes.length} 张卡片。复制后粘贴到对应项目的 Codex 聊天，或下载任务文件。`,`<pre class="pb-code">${esc(text)}</pre>`,'<button class="pb-btn" id="pb-task-download">下载 Markdown</button><button class="pb-btn pb-primary" id="pb-task-copy">复制任务</button>');
    $('pb-task-download').onclick=()=>download('CODEX_TASK.md',text,'text/markdown');
    $('pb-task-copy').onclick=async()=>{try{await navigator.clipboard.writeText(text);showToast('已复制任务说明','success');}catch{err('剪贴板不可用，请下载 Markdown 或手动选择文本');}};
  }
  function outline(){
    dialog('从大纲生成积木','每个非空行生成一张卡片。支持「需求：标题」「模块：标题」「任务：标题」「资源：标题」「决策：标题」「验收：标题」；缩进表示层级。',`<div class="pb-grid"><label class="pb-field wide">项目大纲<textarea id="pb-outline" style="min-height:220px" placeholder="需求：项目目标\n  模块：页面与交互\n    任务：实现卡片编辑\n    验收：保存并重新打开工程"></textarea></label><label class="pb-field">生成方式<select id="pb-outline-mode"><option value="hierarchy">按缩进建立组成关系</option><option value="sequence">按行序建立前置依赖</option><option value="loose">仅生成卡片</option></select></label></div>`,'<button class="pb-btn pb-primary" id="pb-generate">追加到当前工程</button>');
    $('pb-generate').onclick=()=>{
      const text=$('pb-outline').value, mode=$('pb-outline-mode').value;
      const input=text.split('\n').filter(x=>x.trim());if(!input.length)return err('请先填写大纲');if(input.length>200)return err('每次最多生成 200 张卡片');
      const base=screenToWorld(canvasViewport.getBoundingClientRect().left+70,canvasViewport.getBoundingClientRect().top+70),stack=[],created=[];
      pushHistory();
      input.forEach((line,i)=>{
        const indent=(line.match(/^\s*/)[0].replace(/\t/g,'  ').length);
        const cleaned=line.trim().replace(/^[-*#]+\s*/,''), match=cleaned.match(/^(需求|模块|任务|资源|决策|验收)[:：]\s*(.+)$/);
        const type=match?Object.keys(TYPES).find(k=>TYPES[k][0]===match[1]):'common';
        const n={id:uid('block'),title:match?match[2]:cleaned,routeType:type,color:TYPES[type][1],x:base.x+(mode==='sequence'?i:Math.min(4,Math.floor(indent/2)))*450,y:base.y+(mode==='sequence'?0:i*310),summary:'',script:'',characters:'',location:'',bgm:'',choices:[],workflow:{status:'todo',priority:'P1',acceptance:[],files:[]}};
        while(stack.length && stack.at(-1).indent>=indent)stack.pop();
        const from=mode==='hierarchy'?stack.at(-1)?.node:mode==='sequence'?created.at(-1):null;
        if(from)from.choices.push({id:uid('rel'),text:mode==='sequence'?'前置依赖':'组成模块',tag:mode==='sequence'?'前置依赖':'组成模块',target:n.id});
        stack.push({indent,node:n});created.push(n);
      });
      project.nodes.push(...created);closePanel();renderAll();fitCanvasView();triggerAutoSave();showToast('已生成 '+created.length+' 张积木卡片','success');
    };
  }
  function checkProject(p){
    if(!p || !Array.isArray(p.nodes))throw Error('缺少 nodes 数组');
    const ids=new Set();for(const n of p.nodes){if(!n || typeof n.id!=='string' || !/^[a-zA-Z0-9_-]+$/.test(n.id) || ids.has(n.id))throw Error('卡片 ID 无效或重复');ids.add(n.id);if(!Number.isFinite(n.x)||!Number.isFinite(n.y))throw Error('卡片坐标无效');if(n.choices && !Array.isArray(n.choices))throw Error('关系格式无效');}
    for(const n of p.nodes){for(const c of n.choices || [])if(!c || typeof c.id!=='string' || (c.target && !ids.has(c.target)))throw Error('关系目标或 ID 无效');if(n.defaultNext && !ids.has(n.defaultNext))throw Error('默认关系目标不存在');}
    p.groups ||= [];p.stickyNotes ||= [];p.customRoutes ||= [];p.viewport ||= {x:60,y:50,scale:.8};
    if(!Number.isFinite(p.viewport.x)||!Number.isFinite(p.viewport.y)||!Number.isFinite(p.viewport.scale)||p.viewport.scale<=0)throw Error('视口参数无效');
    return p;
  }
  function applyProject(p,rev,history=false){
    checkProject(p);if(history)pushHistory();project=p;revision=rev;projectTitleInput.value=p.title || '未命名项目';selectedNodeIds.clear();selectedStickyIds.clear();syncCustomRoutesFromNodes();updateCanvasTransform();renderAll();baseline=snapshot();remote=null;triggerAutoSave();stats();
  }
  async function poll(){
    if(saving)return;
    try{const res=await fetch('/api/project',{cache:'no-store'});const data=await res.json();if(!res.ok)throw Error(data.error);checkProject(data.project);if(data.dataFile)dataFile=data.dataFile;
      if(revision!==data.revision){if(!loading && dirty()){remote=data;stats();}else if(!panel && !document.querySelector('.story-node.dragging') && !document.activeElement.matches('input,textarea'))applyProject(data.project,data.revision);}
      if(loading){loading=false;stats();}
    }catch(e){if(loading){loading=false;baseline=snapshot();showToast('本地服务未连接，当前可离线编辑并导出 JSON','info');}else if(revision){$('pb-sync').textContent='同步暂不可用：'+e.message;}}
  }
  function conflict(){
    if(!remote)return;
    dialog('处理工程版本冲突','你在画布上有修改，磁盘文件也被更新了。先下载当前画布备份，再选择需要保留的版本。','<div class="pb-help"><div>读取磁盘版本：采用 Codex 或其他编辑器写入的新工程。<br>保留当前画布：用画布内容覆盖已读取的磁盘版本，保存前会再次检查版本。</div></div>','<button class="pb-btn" id="pb-conf-backup">下载当前备份</button><button class="pb-btn" id="pb-conf-disk">读取磁盘版本</button><button class="pb-btn pb-primary" id="pb-conf-local">保留当前画布</button>');
    $('pb-conf-backup').onclick=()=>download('project-local-backup.json',snapshot(),'application/json');
    $('pb-conf-disk').onclick=()=>{const r=remote;closePanel();applyProject(r.project,r.revision,true);};
    $('pb-conf-local').onclick=()=>{revision=remote.revision;remote=null;closePanel();save();};
  }
  async function save(){
    if(saving || loading)return;if(remote)return conflict();
    if(!revision){saveProjectJson();return;}
    saving=true;stats();
    try{checkProject(project);const sent=snapshot();const res=await fetch('/api/project',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:JSON.parse(sent),revision})});const data=await res.json();
      if(res.status===409){saving=false;await poll();conflict();return;}if(!res.ok)throw Error(data.error || '保存失败');revision=data.revision;baseline=sent;showToast('工程已写入 '+dataFile,'success');
    }catch(e){err('保存失败：'+e.message);}finally{saving=false;stats();}
  }
  function inspectGraph(){
    const edges=links().filter(e=>e.type==='前置依赖'), states=new Map(),cycles=[];
    function visit(id,path){if(states.get(id)===1){cycles.push([...path,id]);return;}if(states.get(id)===2)return;states.set(id,1);edges.filter(e=>e.from===id).forEach(e=>visit(e.to,[...path,id]));states.set(id,2);}
    project.nodes.forEach(n=>visit(n.id,[]));
    const missing=project.nodes.filter(n=>!wf(n).acceptance?.length);
    dialog('检查工序关系','检查前置依赖中的循环，以及缺少验收标准的卡片。',`<div class="pb-help"><div>${cycles.length?'⚠ 发现 '+cycles.length+' 处循环依赖':'✓ 前置依赖没有循环'}${cycles.map(c=>'<p>'+c.map(id=>esc(project.nodes.find(n=>n.id===id)?.title || id)).join(' → ')+'</p>').join('')}</div><div>${missing.length?'○ '+missing.length+' 张卡片缺少验收标准':'✓ 所有卡片都有验收标准'}<p>${missing.map(n=>esc(n.title)).join('、')}</p></div></div>`,'');
  }
  function help(){dialog('项目积木工坊 · 使用方法','基于你的 GalFlow 1.12 无限画布改造，面向项目结构、工序与 Codex 协作。',`<div class="pb-help"><div>① 搭结构<br><small>点击或拖拽左侧积木；也可粘贴大纲批量生成。拖动卡片标题移动；空白处拖动平移；滚轮缩放；Shift 拖拽框选分组。</small></div><div>② 接关系<br><small>从右侧端口拖至另一张卡片；双击卡片可编辑多条具名关系。前置依赖箭头从「先做」指向「后做」；组成、资源和参考关系不会阻塞工序。</small></div><div>③ 给任务<br><small>选中卡片后点击「Codex 任务」；未选中时导出全工程。可填写文件、交付物、验收标准与执行说明。</small></div><div>④ 与 Codex 协作<br><small>使用启动脚本打开后，Ctrl+S 将画布写入 data/project.json。让 Codex 读取和更新这个文件；页面每 3 秒检查磁盘更新。有本地修改时会提示冲突。磁盘保存保留上一份 backup；刷新前先保存，JSON 下载可额外备份。</small></div><div>快捷键<br><small>Ctrl+S 保存 · Ctrl+Z 撤销 · Ctrl+Y 重做 · N 新建任务 · Delete 删除选中 · F 专注 · Esc 关闭窗口。此版本通过本地文件协作，卡片状态由你或 Codex 更新。</small></div></div>`,'');}

  function setupSidebarResize(){
    const sidebar=$('sidebar'),main=sidebar.parentElement,library=sidebar.querySelector('.pb-library');
    const directory=document.createElement('section');directory.className='pb-directory';directory.setAttribute('aria-label','工程目录');
    ['.sidebar-header','.chapter-list','.sidebar-footer'].forEach(selector=>directory.append(sidebar.querySelector(selector)));
    const heightHandle=document.createElement('div'),widthHandle=document.createElement('div');
    heightHandle.className='pb-resizer pb-pane-resizer';widthHandle.className='pb-resizer pb-width-resizer';
    sidebar.append(heightHandle,directory);sidebar.after(widthHandle);
    const readSize=key=>{const value=Number(safeGetStorage(key));return Number.isFinite(value)&&value>0?value:null;};
    let preferredWidth=readSize('projectblocks_sidebar_width') || parseFloat(getComputedStyle(main).getPropertyValue('--pb-sidebar-width')) || 320;
    let preferredHeight=readSize('projectblocks_library_height') || Math.min(library.scrollHeight,sidebar.clientHeight*.43);
    const clamp=(n,min,max)=>Math.min(max,Math.max(min,n));
    function bounds(axis){return axis==='width'?{min:200,max:Math.max(200,Math.min(640,main.clientWidth-260))}:{min:60,max:Math.max(60,sidebar.clientHeight-210)};}
    function update(){
      const width=bounds('width'),height=bounds('height');
      main.style.setProperty('--pb-sidebar-width',clamp(preferredWidth,width.min,width.max)+'px');
      sidebar.style.setProperty('--pb-library-height',clamp(preferredHeight,height.min,height.max)+'px');
      widthHandle.setAttribute('aria-valuenow',Math.round(clamp(preferredWidth,width.min,width.max)));
      heightHandle.setAttribute('aria-valuenow',Math.round(clamp(preferredHeight,height.min,height.max)));
      for(const [handle,b] of [[widthHandle,width],[heightHandle,height]]){handle.setAttribute('aria-valuemin',b.min);handle.setAttribute('aria-valuemax',b.max);}
    }
    function remember(){safeSetStorage('projectblocks_sidebar_width',String(preferredWidth));safeSetStorage('projectblocks_library_height',String(preferredHeight));}
    for(const [handle,axis,label] of [[heightHandle,'height','调整积木区与工程目录高度'],[widthHandle,'width','调整左侧栏宽度']]){
      handle.tabIndex=0;handle.setAttribute('role','separator');handle.setAttribute('aria-label',label);handle.setAttribute('aria-orientation',axis==='width'?'vertical':'horizontal');handle.title=label+' · 拖动或使用方向键 · 双击恢复';
      handle.addEventListener('pointerdown',e=>{
        if(e.button!==0)return;e.preventDefault();handle.setPointerCapture(e.pointerId);
        const start=axis==='width'?e.clientX:e.clientY,initial=axis==='width'?sidebar.getBoundingClientRect().width:library.getBoundingClientRect().height;
        handle.dataset.dragging='true';document.body.classList.add('pb-resizing');document.body.style.setProperty('--pb-resize-cursor',axis==='width'?'col-resize':'row-resize');
        const move=event=>{const b=bounds(axis),value=clamp(initial+(axis==='width'?event.clientX:event.clientY)-start,b.min,b.max);if(axis==='width')preferredWidth=value;else preferredHeight=value;update();};
        const finish=()=>{handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',finish);handle.removeEventListener('pointercancel',finish);handle.removeEventListener('lostpointercapture',finish);handle.dataset.dragging='false';document.body.classList.remove('pb-resizing');remember();updateMinimap();};
        handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',finish);handle.addEventListener('pointercancel',finish);handle.addEventListener('lostpointercapture',finish);
      });
      handle.addEventListener('keydown',e=>{
        const delta=axis==='width'?{ArrowLeft:-16,ArrowRight:16}:{ArrowUp:-16,ArrowDown:16};
        if(!(e.key in delta))return;e.preventDefault();const b=bounds(axis),current=Number(handle.getAttribute('aria-valuenow')),value=clamp(current+delta[e.key],b.min,b.max);if(axis==='width')preferredWidth=value;else preferredHeight=value;update();remember();
      });
      handle.addEventListener('dblclick',()=>{if(axis==='width')preferredWidth=320;else preferredHeight=Math.min(library.scrollHeight,sidebar.clientHeight*.43);update();remember();});
    }
    update();new ResizeObserver(update).observe(main);
  }

  function boot(){
    closeNodeModal();document.title='项目积木工坊 · Project Blocks';
    // Remove original demo before the local service responds.
    project={title:'项目积木工坊',version:'1.0',viewport:{x:50,y:60,scale:.8},nodes:[],groups:[],stickyNotes:[],customRoutes:[]};
    try{const cached=safeGetStorage('projectblocks_project_data_v2');if(cached)project=checkProject(JSON.parse(cached));}catch{}
    projectTitleInput.value=project.title;
    applyTheme(currentTheme,currentUiStyle);
    Object.assign(I18N_DICT['zh-CN'],{brandName:'项目积木工坊',tagOutline:'目标',tagCharacter:'资源',tagPrologue:'需求',tagCommon:'任务',tagBranch:'决策',tagRoute:'模块',tabEnding:'验收',sidebarTitle:'工程目录',searchPlaceholder:'搜索工序、负责人、文件…',nodeCharactersTip:'负责人',nodeLocationTip:'文件路径',nodeBgmTip:'交付物',choicesHeaderLeft:'输出关系',choicesHeaderRight:'连接',portInTip:'关系入口',portOutTip:'拖至后续工序',connDefaultTag:'前置依赖',toastReady:'项目积木工坊已就绪'});
    applyLanguage('zh-CN');
    const logo=document.querySelector('.brand-logo');if(logo)logo.textContent='▦';
    // Dedicated project controls replace story-specific documents and packaging.
    ['btn-export-script','btn-package-zip','btn-csp-doc-view','wrap-csp-lang','btn-csp-help'].forEach(id=>{const el=$(id);if(el)el.style.display='none';});
    const top=document.createElement('div');top.className='pb-top';top.innerHTML='<button id="pb-outline-btn">从大纲生成</button><button id="pb-check">检查关系</button><button id="pb-task">Codex 任务 ↗</button><button id="pb-export">导出 JSON</button><button id="pb-help">使用说明</button><button id="pb-save" class="pb-primary">保存工程</button>';document.querySelector('header').append(top);
    const strip=document.createElement('div');strip.className='pb-strip';strip.innerHTML='<span>PROJECT / 工序画布</span><span><strong id="pb-count">0</strong> 个积木</span><span><strong id="pb-links">0</strong> 条关系</span><span><strong id="pb-done">0</strong> 已完成</span><span><strong id="pb-blocked">0</strong> 受阻</span><div class="pb-progress"><i id="pb-progress"></i></div><span class="pb-sync" id="pb-sync" style="cursor:pointer"></span>';document.querySelector('header').after(strip);
    const lib=document.createElement('div');lib.className='pb-library';lib.innerHTML='<div class="pb-eyebrow">BUILDING BLOCKS</div><div class="pb-library-title">从一块积木开始</div><div class="pb-bricks">'+Object.entries(TYPES).map(([type,v])=>`<button class="pb-brick" draggable="true" data-type="${type}" style="--brick:${v[1]}">${v[0]}<span>${v[2]}</span></button>`).join('')+'</div><p>点击添加，或拖入画布<br>双击卡片编辑 · 拖动端口连接</p>';document.querySelector('.sidebar').prepend(lib);
    lib.querySelectorAll('button').forEach(btn=>{btn.onclick=()=>addNewNode({routeType:btn.dataset.type});btn.ondragstart=e=>e.dataTransfer.setData('application/project-block',btn.dataset.type);});
    canvasViewport.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('application/project-block'))e.preventDefault();});
    canvasViewport.addEventListener('drop',e=>{const type=e.dataTransfer.getData('application/project-block');if(!TYPES[type])return;e.preventDefault();const p=screenToWorld(e.clientX,e.clientY);addNewNode({routeType:type,x:Math.round(p.x-160),y:Math.round(p.y-40)});});
    const sf=document.createElement('select');sf.id='pb-status-filter';sf.className='pb-status-filter';sf.innerHTML='<option value="all">全部工序状态</option>'+options(STATUS,'');document.querySelector('.sidebar-header').append(sf);sf.onchange=()=>{statusFilter=sf.value;stats();};
    setupSidebarResize();
    $('pb-outline-btn').onclick=outline;$('pb-check').onclick=inspectGraph;$('pb-help').onclick=help;$('pb-save').onclick=save;$('pb-sync').onclick=conflict;
    $('pb-export').onclick=()=>download('project.blocks.json',snapshot(),'application/json');
    $('pb-task').onclick=()=>{const selected=project.nodes.filter(n=>selectedNodeIds.has(n.id));showTask(selected.length?selected:project.nodes);};
    // Replace original download-save with service save; file-menu JSON export remains available via conflict backup and task workflow.
    $('btn-save-json').addEventListener('click',e=>{e.stopImmediatePropagation();save();},true);
    jsonFileInput.addEventListener('change',e=>{e.stopImmediatePropagation();const file=e.target.files[0];if(!file)return;const reader=new FileReader();reader.onload=()=>{try{const p=checkProject(JSON.parse(reader.result));pushHistory();const oldRevision=revision;applyProject(p,oldRevision);baseline='';stats();showToast('已导入，保存工程后写入磁盘','success');}catch(error){showToast('导入失败：'+error.message,'info');}};reader.readAsText(file);e.target.value='';},true);
    document.addEventListener('keydown',e=>{
      if(e.key==='Escape' && panel){closePanel();e.stopImmediatePropagation();return;}
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();e.stopImmediatePropagation();save();return;}
      if(panel){if(!['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))e.stopImmediatePropagation();return;}
      if(!['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)&&e.key.toLowerCase()==='n'&&!e.ctrlKey&&!e.metaKey){e.preventDefault();addNewNode();}
    },true);
    window.addEventListener('beforeunload',e=>{if(!loading && dirty()){e.preventDefault();e.returnValue='';}});
    baseline=snapshot();renderAll();poll();setInterval(poll,3000);setInterval(stats,800);
  }
  window.addEventListener('DOMContentLoaded',boot);
})();
