'use strict';
M3.capture=()=>{const s=document.getElementById('stage-editor');if(s&&!s.disabled){const key='stage:'+s.dataset.project+':'+s.dataset.stage,p=M3.project(s.dataset.project);if(p&&s.value!==p.stages[Number(s.dataset.stage)].content)M3.ui.buffers[key]=s.value;else delete M3.ui.buffers[key]}const d=document.getElementById('draft-editor');if(d){const key='draft:'+d.dataset.draft,record=M3.data.drafts.find(x=>x.id===d.dataset.draft);if(record&&d.value!==record.text)M3.ui.buffers[key]=d.value;else delete M3.ui.buffers[key]}document.querySelectorAll('[data-note]').forEach(n=>{const key='check:'+n.dataset.note,c=M3.data.checklists.find(x=>x.id===n.dataset.note);if(c&&n.value!==c.note)M3.ui.buffers[key]=n.value;else delete M3.ui.buffers[key]});const q=document.querySelector('form[data-form=ai] textarea[name=question]');if(q)M3.ui.buffers.ai=q.value};
M3.applyTheme=()=>{const pref=M3.data.preferences.theme;document.documentElement.dataset.theme=pref==='system'?(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'):pref};
M3.render=()=>{
 M3.settle();M3.applyTheme();const u=M3.ui,d=M3.data;
 document.getElementById('theme').value=d.preferences.theme;document.getElementById('language').value=d.preferences.language;
 document.getElementById('scenario').value=u.scenario;
 document.getElementById('identity').innerHTML=`<span class="identity-dot"></span>${d.session.logged?'学生端 · 演示账号':'访客 · 尚未登录'}`;
 let previous='';document.getElementById('nav').innerHTML=M3.routes.map(([route,label,group])=>{const head=group!==previous?`<div class="nav-group">${e(group)}</div>`:'';previous=group;return head+`<a class="nav-item ${u.route===route?'active':''}" href="#${route}" ${u.route===route?'aria-current="page"':''}>${M3.icon(route)}<span class="nav-label">${e(label)}</span></a>`}).join('');
 const name=M3.routes.find(x=>x[0]===u.route)?.[1]||({auth:'学生账号',trash:'回收站'})[u.route]||'页面不存在';
 document.getElementById('breadcrumb').innerHTML=`学生端 <span class="dot-sep">/</span><b>${e(name)}</b>`;
 let body='';
 if(!d.session.logged&&u.route!=='auth')body=M3.hero('登录后继续','当前只演示账号流程，不创建真实账号。')+M3.empty('需要先登录演示账号','登录后保留原来的页面目标。',l('进入演示登录','auth/login','primary'));
 else if(u.route==='auth')body=S3.auth();
 else if(u.scenario==='denied')body=M3.hero(name,'访问权限状态')+M3.empty('暂无访问权限','可能尚未加入团队，或资料访问权已撤销。不会展示受限正文。',b('返回正常演示','retry',{},'primary'));
 else if(u.scenario==='error')body=M3.hero(name,'加载失败状态')+M3.empty('暂时无法加载','已有记录未删除。请重试，或返回上一个可用页面。',b('重试加载','retry',{},'primary')+l('返回首页','home'));
 else if(u.scenario==='loading')body=M3.hero(name,'正在加载')+panel('<span class="busy-dot"></span>正在加载演示内容…<div class="skeleton"></div><div class="skeleton short"></div><div class="skeleton"></div>'+b('完成本次加载演示','retry',{},'small'));
 else if(u.scenario==='empty'&&u.id)body=M3.hero(name,'空内容状态')+M3.empty('这里暂时没有内容','这是评审用空状态，不会清除实际演示记录。',b('返回正常内容','retry',{},'primary'));
 else {
  const collections={workspace:'projects',training:'tasks',submissions:'submissions',knowledge:'resources',papers:'papers',writing:'drafts',competition:'competitions',notifications:'notifications',execution:'runs',documents:'documents',tutor:'chats',chat:'teams'};
  const collection=collections[u.route],record=u.id&&collection?d[collection].find(x=>x.id===u.id):null;
  const comp=record&&u.route==='workspace'?d.competitions.find(c=>c.projectId===record.id):null;
  if(u.id&&collection&&!record)body=M3.hero(name,'记录访问状态')+M3.empty('记录不存在或已不可访问','请返回列表重新选择，原型不会静默跳转首页。',l('返回列表',u.route,'primary'));
  else if(comp&&u.actor!=='captain'&&!comp.members.some(m=>m.id===u.actor&&m.status==='joined'))body=M3.hero(name,'竞赛成员权限')+M3.empty('先加入该竞赛才能查看','未接受邀请的成员不能访问本轮成果。',l('查看竞赛邀请','competition/'+comp.id,'primary'));
  else body=(S3[u.route]||(()=>M3.hero('页面不存在','不会静默跳回首页。')+M3.empty('找不到这个入口','请从左侧导航重新进入。',l('返回首页','home','primary'))))();
 }
 const warning='';
 document.getElementById('main').innerHTML=warning+(u.scenario==='save-error'?note('当前为保存失败评审状态；操作不写入演示存储，输入留在页面。','error')+'<div class="mb"></div>':'')+body;
};
M3.route=()=>{M3.capture();let [route='home',id='']=decodeURIComponent(location.hash.slice(1)).split('/');if(!route)route='home';if(route!==M3.ui.route){M3.ui.tab='all';M3.ui.search='';M3.ui.scope='all'}M3.ui.route=route;M3.ui.id=id;M3.render();scrollTo(0,0)};
M3.modalForm=(name,id,body,submit='保存',context='',wide=false)=>M3.modal(name,M3.form(id,body,submit,context),wide);
M3.act=(act,a={})=>{
 M3.capture();const d=M3.data,u=M3.ui,p=a.id?M3.project(a.id):null;
 if(act==='close'){if(document.getElementById('modal').open)M3.close();else M3.toast('已取消本次发送，输入仍保留在当前页面。');return}if(act==='go')return M3.go(a.route);if(act==='retry'){u.scenario='normal';M3.render();return}
 if(act==='stop-ai'){u.generation=null;M3.close();M3.render();M3.toast('已停止演示生成，已保存的问题仍保留。');return}
 if(act==='tab'){u.tab=a.value;M3.render();return}if(act==='clear-search'){u.search='';u.scope='all';M3.render();return}
 if(act==='stage'){u.stage=Number(a.index);M3.render();return}
 if(act==='new-project'||act==='edit-project')return M3.modalForm(act==='new-project'?'创建建模项目':'编辑项目','project',M3.field('项目名称','title',p?.title||'')+M3.area('问题描述（可后补）','description',p?.description||'')+privateNote(),'保存项目',p?.id||'');
 if(act==='new-practice')return M3.modalForm('创建个人练习','practice',M3.field('练习名称','title')+M3.area('练习目标与交付要求','requirements','',true)+M3.area('自我检查依据','rubric')+note('这是个人练习，不会以教师任务身份发布，也不会自动共享。'),'创建个人练习');
 if(act==='start-task'){
  const t=M3.task(a.id);if(!t)return M3.toast('任务不存在');const current=d.projects.filter(p=>p.taskId===t.id&&!M3.locked(p));const available=d.projects.filter(p=>!p.taskId&&!M3.locked(p));
  return M3.modal('开始训练',`<p class="modal-sub">${e(t.title)} · 提交时才生成教师可见快照。</p>${current.length?`<h3>继续已关联项目</h3><div class="actions">${current.map(p=>l(p.title,'workspace/'+p.id,'small')).join('')}</div><div class="divider"></div>`:''}`+M3.form('start-task',M3.select('新建或关联','projectId',[['new','新建项目'],...available.map(p=>[p.id,p.title])])+M3.field('新建时使用的项目名称','title',t.title+' · 我的项目','text',false),'进入项目',t.id));
 }
 if(act==='save-stage'||act==='toggle-stage'){
  if(!p||M3.locked(p))return M3.toast('成果已锁定或项目不可用');const i=Number(a.index),key='stage:'+p.id+':'+i;const content=u.buffers[key]??p.stages[i].content;
  if(M3.commit(()=>{p.stages[i].content=content;if(act==='toggle-stage')p.stages[i].done=!p.stages[i].done;p.updatedAt=M3.now()},act==='save-stage'?'阶段笔记已保存':'阶段完成标记已更新')){delete u.buffers[key];M3.render()}return;
 }
 if(act==='export-project'){if(p)M3.exportText(p.title+'.txt',p.stages.map(s=>s.title+'\n'+s.content+'\n完成标记：'+s.done).join('\n\n'));return}
 if(act==='attach-project')return M3.modalForm('关联已有资料','attach-project',M3.select('选择有权资料','resourceId',M3.studentResources().map(r=>[r.id,r.name]))+note('关联到个人工作区不等于向教师共享；提交时才保存附件快照。'),'关联资料',a.id);
 if(act==='submit-project'){
  if(!p||M3.locked(p))return M3.toast('项目不存在或已锁定');const t=M3.task(p.taskId);if(!t)return M3.toast('该项目尚未关联训练任务');if(!M3.canSubmit(t))return M3.modal('当前不可提交',note('本轮已过截止且不允许提交。旧成果与反馈仍保留；如需重交，请联系教师重新开放。','warning')+b('返回任务','go',{route:'training/'+t.id},'primary'));
  const previous=M3.latest(t.id),next=(previous?.version||0)+1;const unfinished=previous?d.checklists.filter(x=>x.submissionId===previous.id&&!x.done):[];
  return M3.modal('确认提交版本 V'+next,`<p class="modal-sub">${e(t.title)} · ${e(p.title)}</p><div class="step-strip"><span>确认要求</span><span>检查快照</span><span>生成版本回执</span></div><p class="help">将保存当前已保存的八阶段内容与附件；未点“保存”的编辑不包含在快照中。教师不会因此看到整个私人工作区。</p><div class="shared-section">${p.stages.filter(s=>s.done).length}/8 阶段完成标记 · 附件 ${p.resources.length} 份 · 截止 ${M3.date(M3.taskDeadline(t))}</div>`+M3.form('submit-project',M3.area(previous?'本次修改说明':'提交说明','notes','',true)+(unfinished.length?`<h3>选择带入的未完成清单项</h3><p class="help">原清单及评语保留。个人备注不会随重交共享。</p>${unfinished.map(x=>`<label class="checkbox-row"><input type="checkbox" name="carry" value="${x.id}"><span>${e(x.text)}</span></label>`).join('')}`:'')+`<label class="checkbox-row"><input type="checkbox" name="confirmed" required><span>我已检查当前保存内容、附件和提交要求，确认生成不可覆盖的本次快照。</span></label>`,'确认提交 V'+next,p.id),true);
 }
 if(act==='add-check'){
  const s=M3.submission(a.sid),f=s?.feedbackItems.find(x=>x.id===a.fid);if(!f)return;if(d.checklists.some(x=>x.submissionId===s.id&&x.feedbackId===f.id))return M3.toast('该反馈已加入清单，不会重复添加');
  if(M3.commit(()=>d.checklists.push({id:M3.id('check'),submissionId:s.id,feedbackId:f.id,text:f.text,done:false,note:'',sourceVersion:s.version,carriedFrom:null}),'已加入个人修改清单'))M3.render();return;
 }
 if(act==='save-check-note'){
  const c=d.checklists.find(c=>c.id===a.id);if(c&&M3.commit(()=>c.note=u.buffers['check:'+c.id]??c.note,'个人备注已保存，不向教师展示')){delete u.buffers['check:'+c.id];M3.render()}return;
 }
 if(act==='feedback-anchor'){u.stage=Number(a.index);return M3.go('workspace/'+a.pid)}
 if(act==='new-resource')return M3.modalForm('添加个人演示资料','resource',M3.field('名称','name')+M3.select('类别','category',[['建模方法','建模方法'],['数据资料','数据资料'],['论文写作','论文写作']])+M3.field('来源说明','source')+M3.area('演示正文','text','',true)+note('只输入演示资料，不读取本机文件。公共资料由管理员维护。'),'添加资料');
 if(act==='favorite'){const r=M3.resource(a.id);if(r&&M3.commit(()=>r.favorite=!r.favorite,r.favorite?'已取消收藏':'已收藏'))M3.render();return}
 if(act==='share-resource'||act==='comp-share'){
  const rs=d.resources.filter(r=>r.scope==='personal');if(!rs.length)return M3.toast('没有个人资料可共享');return M3.modalForm('确认共享范围',act==='comp-share'?'competition-share':'share-resource',(act==='share-resource'?M3.select('共享到团队','teamId',d.teams.filter(t=>t.joined).map(t=>[t.id,t.name])):'')+M3.select('选择个人资料','resourceId',rs.map(r=>[r.id,r.name]),a.id)+note('只有明确选中的资料副本向该团队共享，其他个人内容仍为私有。'),'明确共享',a.id);
 }
 if(act==='copy-citation'){const r=M3.resource(a.id);return M3.modal('来源引用',`<p class="reading">${e(r.name)} — ${e(r.source)}（演示资料）</p>${b('复制演示引用','copy-text',{id:r.id},'primary')}`)}
 if(act==='copy-text'){const r=M3.resource(a.id);navigator.clipboard?.writeText(r.name+' — '+r.source+'（演示）').then(()=>M3.toast('引用已复制')).catch(()=>M3.toast('浏览器未允许复制，请手动选中引用。'));return}
 if(act==='cite-ai'){const r=M3.resource(a.id);u.citation={id:r.id,name:r.name,text:r.text};u.buffers.ai='请基于所引资料，解释我还需要检查哪些建模条件。';M3.go('tutor');return}
 if(act==='remove-citation'){delete u.citation;M3.render();return}
 if(act==='new-ai'){const id=M3.id('ai');if(M3.commit(()=>d.chats.unshift({id,title:'新问题 · 演示',mode:'基础解释',messages:[]}),'已创建私人演示对话'))M3.go('tutor/'+id);return}
 if(act==='save-ai'){
  const f=document.querySelector('[data-form=ai]');if(!f)return;const question=f.elements.question.value.trim();if(!question)return M3.toast('请先填写问题');let c=d.chats.find(x=>x.id===a.id),id=c?.id||M3.id('ai');if(M3.commit(()=>{if(!c){c={id,title:question.slice(0,24),mode:f.elements.mode.value,messages:[]};d.chats.unshift(c)}c.messages.push({role:'user',text:question,at:M3.now()})},'问题已保存，未调用模型')){u.buffers.ai='';M3.go('tutor/'+id);M3.render()}return;
 }
 if(act==='ai-error'){u.buffers.ai=document.querySelector('[data-form=ai] textarea')?.value||u.buffers.ai||'';return M3.modal('演示生成失败',note('模型服务暂不可用。问题和引用仍保留，可重试或先保存问题。','error')+b('返回继续编辑','close',{},'primary'))}
 if(['paper-ai','draft-ai'].includes(act)&&M3.aiRestriction('方法探索'))return M3.toast(M3.aiRestriction('方法探索'));
 if(act==='retry-paper'){const paper=d.papers.find(x=>x.id===a.id);if(paper&&M3.commit(()=>paper.parseStatus='ready','演示解析已重试，原件名称未改变'))M3.render();return}
 if(act==='attach-draft'||act==='attach-paper'){const item=act==='attach-draft'?d.drafts.find(x=>x.id===a.id):d.papers.find(x=>x.id===a.id);const ps=d.projects.filter(p=>!M3.locked(p));if(!item||!ps.length)return M3.toast('没有可关联的项目，请先创建项目');return M3.modalForm('确认关联成果快照','attach-output',M3.select('目标项目','projectId',ps.map(p=>[p.id,p.title]))+note('只关联当前已保存内容的副本，不改原件，也不直接向教师提交。需要共享给教师时，请在项目中确认提交。'),'关联到项目',JSON.stringify({kind:act==='attach-draft'?'draft':'paper',id:a.id}))}
 if(act==='new-paper')return M3.modalForm('添加演示论文','paper',M3.field('论文名称','title')+M3.field('原件名称','originalName','示例论文.pdf')+M3.select('演示解析状态','parseStatus',[['ready','解析成功（示例正文）'],['failed','解析失败']])+note('只创建演示原件记录，不读取真实文件。'),'添加论文');
 if(act==='paper-to-draft'){
  const paper=d.papers.find(p=>p.id===a.id),existing=d.drafts.find(x=>x.paperId===a.id);if(existing)return M3.go('writing/'+existing.id);
  if(!paper)return;const id=M3.id('draft');if(M3.commit(()=>d.drafts.unshift({id,title:paper.title+' · 修改稿',paperId:paper.id,text:paper.originalText,textLanguage:'中文',versions:[],updatedAt:M3.now()}),'已创建关联文稿；原论文未覆盖'))M3.go('writing/'+id);return;
 }
 if(act==='export-paper'){const paper=d.papers.find(p=>p.id===a.id);if(paper)M3.exportText(paper.title+'-演示原文.txt',paper.originalText);return}
 if(act==='paper-annotate')return M3.modalForm('添加个人批注','annotate',M3.area('批注','text','',true),'保存批注',a.id);
 if(act==='paper-score'){const p=d.papers.find(p=>p.id===a.id);return M3.modalForm('个人七维评价记录','paper-score',note('个人自评，不是教师成绩。各项留空时不生成完整评价。')+['问题理解','模型假设','模型构建','算法实现','结果验证','论文写作','创新性'].map((k,i)=>M3.field(k+'（0—100，可空）','score'+i,p.scores[i]??'','number',false)).join(''),'保存个人记录',a.id)}
 if(act==='paper-ai')return M3.modal('AI建议演示',note('以下为固定演示内容，不是对论文的真实模型分析。')+'<p class="reading">可检查变量单位、库存约束和参数来源。请由作者判断并核验。</p>'+b('关闭','close',{},'primary'));
 if(act==='new-draft')return M3.modalForm('新建写作文稿','draft',M3.field('文稿标题','title')+M3.select('正文语言','textLanguage',[['中文','中文'],['English','English'],['Русский','Русский']])+M3.area('初始正文（可空）','text'),'创建文稿');
 if(act==='save-draft'){const x=d.drafts.find(x=>x.id===a.id);if(x&&M3.commit(()=>{x.text=u.buffers['draft:'+x.id]??x.text;x.updatedAt=M3.now()},'文稿草稿已保存')){delete u.buffers['draft:'+x.id];M3.render()}return}
 if(act==='version-draft')return M3.modalForm('保存命名版本','draft-version',M3.field('版本名称','name','','text',true,'例如：补充模型约束后。将包含当前编辑区文字。'),'保存版本',a.id);
 if(act==='view-version'){const x=d.drafts.find(x=>x.id===a.did),v=x?.versions.find(v=>v.id===a.vid);if(!v)return;return M3.modal(v.name,`<p class="modal-sub">${M3.date(v.at)} · 原论文不会被覆盖</p><pre class="original-pre">${e(v.text)}</pre><div class="actions">${b('恢复到编辑区','restore-version',{did:x.id,vid:v.id},'primary')}${b('关闭','close')}</div>`,true)}
 if(act==='restore-version'){const x=d.drafts.find(x=>x.id===a.did),v=x?.versions.find(v=>v.id===a.vid);if(!v)return;u.buffers['draft:'+x.id]=v.text;M3.close();M3.render();M3.toast('已恢复到编辑区，尚未覆盖保存的草稿。');return}
 if(act==='export-draft'){const x=d.drafts.find(x=>x.id===a.id);if(!x)return;return M3.modal('确认导出文稿',`<p>将导出当前已保存文稿的纯文本，不覆盖论文原件。未保存编辑请先保存。</p>${b('确认导出演示文本','confirm-export-draft',{id:x.id},'primary')}`)}
 if(act==='confirm-export-draft'){const x=d.drafts.find(x=>x.id===a.id);M3.exportText(x.title+'.txt',x.text);M3.close();return}
 if(act==='draft-ai'){u.suggestionDraft=a.id;return M3.modal('写作建议演示',note('固定演示建议，不是真实翻译或模型回复。')+'<p>建议补充一句：“结果仅适用于当前数据范围，后续需以独立样本验证。”</p>'+b('主动采纳到编辑区','accept-draft-ai',{id:a.id},'primary')+b('暂不采纳','close'))}
 if(act==='accept-draft-ai'){const x=d.drafts.find(x=>x.id===a.id),key='draft:'+x.id;u.undoDraft={id:x.id,text:u.buffers[key]??x.text};u.buffers[key]=(u.buffers[key]??x.text)+'\n\n结果仅适用于当前数据范围，后续需以独立样本验证。';M3.close();M3.render();M3.modal('已采纳到编辑区',note('建议尚未保存，可以撤销。')+b('撤销本次采纳','undo-draft-ai',{},'primary')+b('保留并继续','close'));return}
 if(act==='undo-draft-ai'){if(u.undoDraft){u.buffers['draft:'+u.undoDraft.id]=u.undoDraft.text;delete u.undoDraft}M3.close();M3.render();return}
 if(act==='read-notification'){const n=M3.visibleNotifications().find(n=>n.id===a.id);if(n&&M3.commit(()=>n.read=true,'通知已读状态已保存'))M3.render();return}
 if(act==='read-all'){if(M3.commit(()=>M3.visibleNotifications().forEach(n=>n.read=true),'已标为全部已读'))M3.render();return}
 if(act==='chat-members'){const t=d.teams.find(t=>t.id===a.id);return M3.modal('团队成员',`<p>${e(t.name)}</p>${t.members.map(n=>`<div class="member-list">${e(n)} · 演示成员</div>`).join('')}`)}
 if(act==='new-document')return M3.modalForm('添加演示解析任务','document',M3.field('文件名称','name','示例材料.pdf')+M3.select('类型','kind',[['文档','文档'],['图片OCR','图片OCR'],['音频转写','音频转写']])+M3.select('演示结果','result',[['ready','完成'],['failed','失败']])+note('只使用固定演示内容，不读取任何真实原件或音频。'),'开始演示解析');
 if(act==='retry-document'){const x=d.documents.find(x=>x.id===a.id);if(x&&M3.commit(()=>{x.status='ready';x.text='【重试后的演示结果】资料包含模型变量、数据来源与约束条件。此内容不是实际文件解析。'},'演示解析重试完成'))M3.render();return}
 if(act==='new-run'||act==='retry-run'){const r=d.runs.find(x=>x.id===a.id);return M3.modalForm('配置演示运行','run',M3.field('运行名称','title',r?.title||'建模代码验证 · 演示')+M3.select('演示环境','runtime',[['python','Python · 演示环境']])+M3.area('代码（不会执行）','code',r?.code||'print("model demo")',true)+M3.select('演示结果','result',[['success','成功结果'],['failed','运行错误']])+note('不执行输入代码，不发送远程请求。结果与日志用于交互演示。'),'开始演示任务')}
 if(act==='cancel-run'){const r=d.runs.find(x=>x.id===a.id);if(r&&['queued','running'].includes(r.status)&&M3.commit(()=>{r.status='cancelled';r.log+='\n演示运行已取消。'},'演示运行已取消'))M3.render();return}
 if(act==='export-run'){const r=d.runs.find(x=>x.id===a.id);if(r)M3.exportText('演示运行结果.txt','固定演示结果，未实际执行输入代码。\n'+r.log);return}
 if(act==='export-progress'){const text=d.projects.map(p=>p.title+'：'+p.stages.filter(s=>s.done).length+'/8手动完成').join('\n');M3.exportText('演示成长记录.txt',text+'\n不代表能力评价。不含学习时长。');return}
 if(act==='logout'){if(M3.commit(()=>d.session.logged=false,'已退出演示账号'))M3.go('auth/login');return}
 if(act==='verify-email')return M3.go('auth/verify');
 if(act==='resend-code')return M3.toast('演示验证码：123456。没有发送真实邮件。');
 if(act==='teacher-auth'){T.role='mentor';M3.go('mentor/auth/login');return}
 if(act==='admin-entry')return M3.modal('管理员入口',note('保留管理员入口，账号由平台单独开通。本轮不重做管理后台，本原型不登录真实管理员。')+b('关闭','close',{},'primary'));
 if(act==='export-demo'){M3.exportText('MathModel-学生端演示数据.json',JSON.stringify(d,null,2));return}
 if(act==='reset')return M3.modal('重置演示数据',note('只重置此独立原型的演示记录，不影响正式项目、线上账号或阶段2文件。','warning')+b('确认重置本原型','confirm-reset',{},'danger')+b('取消','close'));
 if(act==='confirm-reset'){M3.data=M3.seed();M3.ui.buffers={};M3.ui.generation=null;M3.ui.scenario='normal';M3.save();M3.close();M3.go('home');M3.render();return}
 if(M3.competitionAction?.(act,a))return;
 M3.toast('该操作的业务边界已在界面中说明。');
};
M3.competitionAction=(act,a)=>{
 const acts=['new-competition','start-competition','confirm-start','finish-competition','confirm-finish','invite-member','accept-invite','new-assignment','edit-assignment','comp-share','copy-competition'];
 if(!acts.includes(act))return false;
 const d=M3.data,u=M3.ui,c=d.competitions.find(c=>c.id===(a.cid||a.id));
 if(act==='new-competition'){M3.modalForm('配置模拟竞赛','competition',M3.field('竞赛名称','title')+M3.select('参与方式','mode',[['personal','个人'],['team','团队']])+M3.field('时长（分钟）','minutes','60','number')+M3.select('AI规则','aiPolicy',[['关闭AI','关闭AI'],['仅基础知识查询','仅基础知识查询'],['开放辅助','开放辅助']])+M3.area('题目、要求与规则','rules','',true)+note('关闭页面不暂停；到时锁定已保存成果。团队协作仅使用演示成员。'),'创建竞赛');return true}
 if(!c){M3.toast('竞赛记录不存在');return true}
 M3.settle();const captain=u.actor==='captain',member=c.members.find(m=>m.id===u.actor),joined=captain||member?.status==='joined';
 if(act==='accept-invite'){if(member?.status!=='invited'){M3.toast('此邀请不可用');return true}if(M3.commit(()=>member.status='joined','演示成员已加入'))M3.render();return true}
 if(!joined){M3.toast('尚未加入，不能访问团队成果');return true}
 if(['start-competition','confirm-start','finish-competition','confirm-finish','invite-member','new-assignment','edit-assignment'].includes(act)&&!captain){M3.toast('只有队长可以执行此操作');return true}
 if(act==='start-competition'){if(c.status!=='ready'){M3.toast('当前不可开始');return true}M3.modal('确认开始计时',note('规则：'+c.rules)+`<p>${c.minutes}分钟 · ${e(c.aiPolicy)}。开始后关闭页面或离线不暂停，到时锁定已保存成果。</p>`+b('确认并开始','confirm-start',{id:c.id},'primary')+b('取消','close'));return true}
 if(act==='confirm-start'){if(c.status!=='ready')return true;const id=M3.id('comp-project');if(M3.commit(()=>{const p={id,title:c.title+' · 本轮成果',description:c.rules,taskId:null,competitionId:c.id,stages:M3.defaultStages(),resources:[],createdAt:M3.now(),updatedAt:M3.now()};d.projects.push(p);c.projectId=id;c.status='active';c.startedAt=M3.now()},'模拟竞赛已开始计时')){M3.close();M3.render()}return true}
 if(act==='finish-competition'){M3.modal('确认提前结束',note('将锁定本轮已保存项目与协作记录。之后只能复制为个人练习继续。','warning')+b('确认结束并锁定','confirm-finish',{id:c.id},'danger')+b('取消','close'));return true}
 if(act==='confirm-finish'){if(c.status==='active'&&M3.commit(()=>M3.finishCompetition(c),'本轮竞赛已结束并锁定')){M3.close();M3.render()}return true}
 if(act==='copy-competition'){if(c.status!=='completed'){M3.toast('结束后才能复制本轮成果');return true}const p=M3.clone(c.snapshot),id=M3.id('practice-project');p.id=id;p.title+=' · 赛后个人练习';p.taskId=null;delete p.competitionId;p.createdAt=M3.now();p.updatedAt=M3.now();if(M3.commit(()=>d.projects.push(p),'已复制为个人练习，竞赛原记录未改变'))M3.go('workspace/'+id);return true}
 if(c.status==='completed'){M3.toast('本轮已锁定，不能改写');return true}
 if(act==='invite-member'){M3.modalForm('邀请演示成员','competition-invite',M3.field('演示成员名称','name','示例成员')+note('只创建待加入的演示成员，不发送真实邀请。'),'创建演示邀请',c.id);return true}
 if(act==='new-assignment'||act==='edit-assignment'){const x=c.assignments.find(x=>x.id===a.id);M3.modalForm('成员分工','assignment',M3.field('工作事项','title',x?.title||'')+M3.select('负责人','owner',c.members.filter(m=>m.status==='joined').map(m=>[m.id,m.name]),x?.owner||'captain')+M3.select('状态','status',[['todo','待开始'],['doing','进行中'],['done','已完成']],x?.status||'todo'),'保存分工',JSON.stringify({cid:c.id,id:x?.id||''}));return true}
 return true;
};
M3.formError=(form,msg)=>{const el=form.querySelector('.form-error');if(el){el.hidden=false;el.textContent=msg;el.scrollIntoView({block:'nearest'})}else M3.toast(msg)};
M3.onForm=async form=>{
 const id=form.dataset.form,context=form.dataset.context,fd=new FormData(form),get=k=>String(fd.get(k)||'').trim(),d=M3.data,u=M3.ui;
 const done=(fn,msg,route)=>{if(M3.commit(fn,msg)){if(document.getElementById('modal').open)M3.close();if(route)M3.go(route);M3.render();return true}M3.formError(form,'保存失败，当前输入仍保留。');return false};
 try{
 if(id==='project'){const old=M3.project(context);if(old&&M3.locked(old))throw new Error('竞赛成果已锁定');const pid=old?.id||M3.id('project');done(()=>{if(old){old.title=get('title');old.description=get('description');old.updatedAt=M3.now()}else d.projects.unshift({id:pid,title:get('title'),description:get('description'),taskId:null,stages:M3.defaultStages(),resources:[],createdAt:M3.now(),updatedAt:M3.now()})},'项目已保存','workspace/'+pid);return}
 if(id==='practice'){const tid=M3.id('practice');done(()=>d.tasks.unshift({id:tid,title:get('title'),kind:'practice',teamId:null,requirements:get('requirements'),rubric:get('rubric')||'按自己的目标检查成果。',dueAt:null,allowLate:true,createdAt:M3.now()}),'个人练习已创建','training/'+tid);return}
 if(id==='start-task'){const t=M3.task(context);if(!t)throw new Error('任务不存在');const selected=get('projectId'),pid=selected==='new'?M3.id('project'):selected;const p=M3.project(pid);if(selected!=='new'&&(!p||p.taskId||M3.locked(p)))throw new Error('项目已关联其他任务或不可用，请重新选择');done(()=>{if(selected==='new')d.projects.unshift({id:pid,title:get('title')||t.title,description:t.requirements,taskId:t.id,stages:M3.defaultStages(),resources:[],createdAt:M3.now(),updatedAt:M3.now()});else p.taskId=t.id},'任务已关联私人项目','workspace/'+pid);return}
 if(id==='attach-project'){const p=M3.project(context);if(!p||M3.locked(p))throw new Error('项目不可编辑');const rid=get('resourceId');if(!M3.resource(rid))throw new Error('资料不存在');if(p.resources.includes(rid))throw new Error('资料已关联，不重复添加');done(()=>p.resources.push(rid),'资料已关联');return}
 if(id==='submit-project'){
  const p=M3.project(context),t=M3.task(p?.taskId);if(!p||!t||M3.locked(p))throw new Error('项目不可提交');if(!M3.canSubmit(t))throw new Error('截止时间或提交权限已变化，请返回任务核对。');if(!fd.has('confirmed'))throw new Error('请先确认提交要求');const previous=M3.latest(t.id),version=(previous?.version||0)+1,sid=M3.id('submission');const carry=fd.getAll('carry').map(String),selected=d.checklists.filter(x=>carry.includes(x.id)&&x.submissionId===previous?.id&&!x.done);const time=M3.now();
  done(()=>{d.submissions.push({id:sid,taskId:t.id,projectId:p.id,personId:'student1',taskSnapshot:M3.clone(t),version,submittedAt:time,status:'submitted',notes:get('notes'),snapshot:M3.clone(p),attachments:M3.shareResources(p),feedback:'',feedbackItems:[],teacher:t.teacher||'',revisionDueAt:null,late:M3.taskDeadline(t)&&new Date(time)>new Date(M3.taskDeadline(t))});for(const old of selected)d.checklists.push({id:M3.id('check'),submissionId:sid,feedbackId:old.feedbackId,text:old.text,done:false,note:'',sourceVersion:old.sourceVersion,carriedFrom:old.id});d.notifications.unshift({id:M3.id('note'),title:'提交版本 V'+version+' 已保存',body:'成果快照已生成，等待教师评阅。',route:'submissions/'+sid,read:false,at:time})},'版本 V'+version+' 已提交，旧版本未覆盖','submissions/'+sid);return;
 }
 if(id==='attach-output'){const v=JSON.parse(context),p=M3.project(get('projectId'));if(!p||M3.locked(p))throw new Error('目标项目不可编辑');const item=v.kind==='draft'?d.drafts.find(x=>x.id===v.id):d.papers.find(x=>x.id===v.id);if(!item)throw new Error('成果不存在');const rid=M3.id('output');done(()=>{d.resources.push({id:rid,name:item.title+' · 成果快照',scope:'personal',type:v.kind==='draft'?'文稿快照':'论文快照',category:'论文写作',source:'学生主动关联的演示成果',text:v.kind==='draft'?item.text:item.originalText,favorite:false});p.resources.push(rid)},'成果快照已关联；原件未改变，尚未向教师提交');return}
 if(id==='resource'){const rid=M3.id('resource');done(()=>d.resources.unshift({id:rid,name:get('name'),category:get('category'),scope:'personal',type:'知识条目',source:get('source'),text:get('text'),favorite:false}),'个人资料已添加','knowledge/'+rid);return}
 if(id==='share-resource'){const r=M3.resource(get('resourceId')),team=d.teams.find(t=>t.id===get('teamId')&&t.joined);if(!r||r.scope!=='personal'||!team)throw new Error('资料或共享范围不可用');done(()=>d.resources.push({...M3.clone(r),id:M3.id('shared'),scope:'team',teamId:team.id,source:r.source+' · 学生明确共享副本',favorite:false}),'已向团队共享选定资料副本');return}
 if(id==='ai'){
  const restriction=M3.aiRestriction(get('mode'));if(restriction)throw new Error(restriction);
  const q=get('question');if(!q)throw new Error('先描述已知条件与问题');let c=d.chats.find(c=>c.id===context),cid=c?.id||M3.id('ai');if(!done(()=>{if(!c){c={id:cid,title:q.slice(0,24),mode:get('mode'),messages:[]};d.chats.unshift(c)}c.mode=get('mode');c.messages.push({role:'user',text:q+(u.citation?'\n引用：'+u.citation.name:''),at:M3.now()})},'问题已保存，准备演示回复','tutor/'+cid))return;u.buffers.ai='';M3.render();
  const token=M3.id('generation');u.generation=token;M3.modal('正在生成演示回复',note('模拟等待，不调用真实模型。')+b('停止本次演示','stop-ai',{},'danger'));
  setTimeout(()=>{if(u.generation!==token)return;u.generation=null;const current=d.chats.find(c=>c.id===cid);if(current&&M3.commit(()=>current.messages.push({role:'assistant',text:'【固定演示回复】先列出问题目标、已知数据和约束，再检查变量单位与边界。此内容不是真实模型分析，请人工核验。',at:M3.now()}),'演示回复已保存')){M3.close();M3.render()}},1500);return;
 }
 if(id==='paper'){const pid=M3.id('paper');done(()=>d.papers.unshift({id:pid,title:get('title'),originalName:get('originalName'),originalText:'【演示原件正文】\n研究目标、数据与模型约束。此文本不是实际文件解析结果。',parseStatus:get('parseStatus'),scores:Array(7).fill(null),annotations:[],shared:false,createdAt:M3.now()}),'演示原件记录已添加','papers/'+pid);return}
 if(id==='annotate'){const p=d.papers.find(x=>x.id===context);if(!p)throw new Error('论文不存在');done(()=>p.annotations.push({id:M3.id('annotation'),text:get('text'),at:M3.now()}),'个人批注已保存');return}
 if(id==='paper-score'){const p=d.papers.find(x=>x.id===context),scores=Array.from({length:7},(_,i)=>get('score'+i)===''?null:Number(get('score'+i)));if(scores.some(n=>n!==null&&(!Number.isFinite(n)||n<0||n>100)))throw new Error('各项需为0—100，或留空');done(()=>p.scores=scores,'个人评价记录已保存，不作为教师成绩');return}
 if(id==='draft'){const did=M3.id('draft');done(()=>d.drafts.unshift({id:did,title:get('title'),paperId:null,text:get('text'),textLanguage:get('textLanguage'),versions:[],updatedAt:M3.now()}),'新文稿已创建','writing/'+did);return}
 if(id==='draft-version'){const x=d.drafts.find(x=>x.id===context);if(!x)throw new Error('文稿不存在');const text=u.buffers['draft:'+x.id]??x.text;done(()=>{x.versions.unshift({id:M3.id('version'),name:get('name'),text,at:M3.now()});x.text=text;x.updatedAt=M3.now()},'命名版本已保存，原件未改变');return}
 if(id==='competition'){const minutes=Number(get('minutes'));if(!Number.isFinite(minutes)||minutes<1||minutes>43200)throw new Error('演示时长设为1—43200分钟');const cid=M3.id('competition');done(()=>d.competitions.push({id:cid,title:get('title'),mode:get('mode'),minutes,aiPolicy:get('aiPolicy'),rules:get('rules'),status:'ready',startedAt:null,finishedAt:null,projectId:null,members:[{id:'captain',name:'林同学 · 示例队长',status:'joined'}],assignments:[],messages:[],shared:[]}), '模拟竞赛已配置','competition/'+cid);u.actor='captain';return}
 if(id==='competition-invite'){const c=d.competitions.find(x=>x.id===context);if(!c||u.actor!=='captain'||c.status==='completed')throw new Error('无权邀请或竞赛已锁定');done(()=>c.members.push({id:M3.id('member'),name:get('name'),status:'invited'}),'已创建演示邀请；切换成员身份可接受');return}
 if(id==='assignment'){const v=JSON.parse(context),c=d.competitions.find(x=>x.id===v.cid);if(!c||u.actor!=='captain'||c.status==='completed')throw new Error('无权调整或竞赛已锁定');const member=c.members.find(m=>m.id===get('owner')&&m.status==='joined');if(!member)throw new Error('成员未加入');done(()=>{let x=c.assignments.find(x=>x.id===v.id);if(x)Object.assign(x,{title:get('title'),owner:member.id,status:get('status')});else c.assignments.push({id:M3.id('assignment'),title:get('title'),owner:member.id,status:get('status')})},'分工已保存');return}
 if(id==='competition-message'||id==='competition-share'){
  const c=d.competitions.find(x=>x.id===context),member=c?.members.find(m=>m.id===u.actor);M3.settle();if(!c||c.status!=='active'||member?.status!=='joined')throw new Error('未加入、尚未开始或竞赛已锁定');
  if(id==='competition-message')done(()=>c.messages.push({id:M3.id('msg'),author:member.name,text:get('text'),at:M3.now()}),'演示讨论已保存');else{const r=M3.resource(get('resourceId'));if(!r||r.scope!=='personal')throw new Error('共享资料不可用');done(()=>c.shared.push({id:M3.id('shared'),name:r.name,text:r.text,author:member.name,at:M3.now()}),'选定成果已明确共享到竞赛')}return;
 }
 if(id==='chat'){const team=d.teams.find(t=>t.id===context&&t.joined);if(!team)throw new Error('没有团队访问权');done(()=>d.messages.push({id:M3.id('message'),teamId:team.id,author:d.session.name,text:get('text'),attachment:get('attachment'),at:M3.now()}),'演示团队消息已保存');return}
 if(id==='document'){const did=M3.id('document');if(!done(()=>d.documents.push({id:did,name:get('name'),kind:get('kind'),status:'processing',text:''}),'演示解析任务已创建','documents/'+did))return;const result=get('result');setTimeout(()=>{const doc=M3.data.documents.find(x=>x.id===did);if(!doc)return;doc.status=result;doc.text=result==='ready'?'【固定演示解析】模型变量、数据来源、约束与验证。不是实际文件解析、OCR或音频转写结果。':'';M3.save();M3.render()},1200);return}
 if(id==='run'){const rid=M3.id('run'),result=get('result');if(!done(()=>d.runs.unshift({id:rid,title:get('title'),code:get('code'),runtime:get('runtime'),status:'queued',log:'演示任务已排队，代码未实际执行。',createdAt:M3.now()}),'演示运行已排队','execution/'+rid))return;setTimeout(()=>{const r=M3.data.runs.find(r=>r.id===rid);if(r?.status!=='queued')return;r.status='running';r.log+='\n演示工作进程已开始。';M3.save();M3.render()},600);setTimeout(()=>{const r=M3.data.runs.find(r=>r.id===rid);if(r?.status!=='running')return;r.status=result;r.log+=result==='success'?'\n固定演示结果：运行结束，示例产物可下载。不是该代码的执行输出。':'\n演示错误：运行未完成。输入代码仍保留，可复制重试。';M3.save();M3.render()},2500);return}
 if(id==='profile'){if(!get('email').endsWith('@example.invalid'))throw new Error('请使用@example.invalid演示邮箱，勿输入真实账号');done(()=>{d.session.name=get('name');d.session.email=get('email')},'演示个人资料已保存');return}
 if(['login','register','recover'].includes(id)){if(!get('email').endsWith('@example.invalid'))throw new Error('请使用@example.invalid演示邮箱');if(['login','register'].includes(id)&&get('password').length<6)throw new Error('演示密码至少6位，不会存储');if(id==='login'){done(()=>{d.session.logged=true;d.session.email=get('email')},'演示登录成功','home')}else if(id==='register'){u.authPending={name:get('name'),email:get('email')};M3.go('auth/verify')}else{u.authEmail=get('email');M3.go('auth/reset-password')}return}
 if(id==='verify'){if(get('code')!=='123456')throw new Error('演示验证码无效，请输入123456');done(()=>{d.session.logged=true;d.session.verified=true;if(u.authPending)Object.assign(d.session,u.authPending)},'演示邮箱已验证','home');return}
 if(id==='reset-password'){if(get('code')!=='123456')throw new Error('演示验证码无效');if(get('password').length<6||get('password')!==get('confirm'))throw new Error('密码至少6位，且两次输入一致');M3.toast('演示重设完成；没有保存或修改真实密码。');M3.go('auth/login');return}
 }catch(error){M3.formError(form,error.message)}
};
document.addEventListener('click',event=>{const button=event.target.closest('[data-act]');if(button){event.preventDefault();M3.act(button.dataset.act,button.dataset)}else if(event.target.closest('a[href^="#"]')){M3.capture();if(document.getElementById('modal').open)M3.close()}});
document.addEventListener('input',event=>{const el=event.target;if(el.id==='stage-editor'||el.id==='draft-editor'){M3.capture();const status=document.getElementById('save-state');if(status)status.textContent='有未保存修改，切换页面不会丢失当前会话输入。'}if(el.matches('[data-note]'))M3.ui.buffers['check:'+el.dataset.note]=el.value});
document.addEventListener('submit',event=>{const form=event.target;if(form.matches('[data-search]')){event.preventDefault();M3.capture();const fd=new FormData(form);M3.ui.search=String(fd.get('q')||'').trim();M3.ui.scope=String(fd.get('scope')||'all');M3.render()}else if(form.dataset.form){event.preventDefault();M3.onForm(form)}});
document.addEventListener('change',event=>{
 const el=event.target;M3.capture();
 if(el.id==='scenario'){M3.ui.scenario=el.value;M3.render();return}
 if(el.id==='theme'){M3.data.preferences.theme=el.value;M3.save();M3.applyTheme();return}
 if(el.id==='language'){M3.data.preferences.language=el.value;M3.save();M3.render();return}
 if(el.id==='competition-actor'){M3.ui.actor=el.value;M3.render();return}
 if(el.dataset.check){const c=M3.data.checklists.find(c=>c.id===el.dataset.check);if(c&&M3.commit(()=>c.done=el.checked,'个人完成标记已保存，不代表教师认可'))M3.render();else M3.render();return}
 if(el.id==='reminder-consent'){if(!M3.commit(()=>M3.data.preferences.reminders=el.checked,'演示提醒意愿已保存，未发信'))M3.render();return}
 if(el.dataset.assignment){const c=M3.data.competitions.find(c=>c.id===el.dataset.comp),a=c?.assignments.find(x=>x.id===el.dataset.assignment);M3.settle();if(!c||!a||c.status!=='active'||(M3.ui.actor!=='captain'&&a.owner!==M3.ui.actor)){M3.toast('当前没有修改此分工的权限');M3.render();return}if(M3.commit(()=>a.status=el.value,'分工进度已更新'))M3.render();return}
});
document.getElementById('reset-demo').addEventListener('click',()=>M3.act('reset'));
const systemTheme=matchMedia('(prefers-color-scheme:dark)');systemTheme.addEventListener('change',()=>{if(M3.data.preferences.theme==='system')M3.applyTheme()});
window.addEventListener('hashchange',M3.route);
document.getElementById('modal').addEventListener('cancel',()=>{if(M3.ui.generation){M3.ui.generation=null;M3.toast('已停止演示生成，问题仍保留。')}});
window.addEventListener('beforeunload',event=>{if(Object.keys(M3.ui.buffers).some(k=>k.startsWith('stage:')||k.startsWith('draft:'))){event.preventDefault();event.returnValue=''}});
setInterval(()=>{if(M3.settle()){M3.render();M3.toast('模拟计时已到，本轮已保存成果锁定。')}else document.querySelectorAll('[data-timer]').forEach(el=>{const c=M3.data.competitions.find(c=>c.id===el.dataset.timer);if(c)el.textContent=M3.remaining(c)})},1000);
M3.route();

// The skip link focuses the existing content, without entering a business route.
document.querySelector('a.skip')?.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();const main=document.getElementById('main');main.setAttribute('tabindex','-1');main.focus();main.scrollIntoView();});
