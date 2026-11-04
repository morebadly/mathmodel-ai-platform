/* Live writing previews. TeX is sent only to the existing isolated execution service. */
'use strict';
window.MMWritingCompiler=(()=>{
 const E=value=>window.MM.esc(value),API=()=>window.MMPlatformAPI;
 const formats={latex:'LaTeX · XeLaTeX → PDF',markdown:'Markdown · 实时排版',text:'普通文字 · 原文预览'};
 const states=new Map();let bound=null,lastAccount='',pdfLibrary=null,profileCache=null;
 const terminal=new Set(['completed','failed','cancelled','timed_out','access_revoked','uncertain','awaiting_credentials','awaiting_authorization']);
 const statusNames={queued:'等待编译',starting:'正在启动隔离编译器',running:'正在编译',cancel_requested:'正在取消',cancelled:'已取消',timed_out:'编译超时',access_revoked:'文稿或附件权限已撤销',uncertain:'远端状态待核对',failed:'编译失败',awaiting_credentials:'编译环境待配置',awaiting_authorization:'编译环境待授权'};
 const template=()=>String.raw`\section{问题与假设}
在这里填写自己的研究内容与建模假设。

\section{模型建立}
填写模型、公式与变量说明。例如：
\[
\bar{x}=\frac{1}{n}\sum_{i=1}^{n} x_i
\]

\section{结果与检验}
填写真实结果与检验方法。
`;
 function choices(){return `<fieldset class="writing-format-choices"><legend>选择写作格式</legend>${Object.entries(formats).map(([value,label])=>`<label><input type="radio" name="format" value="${value}" required ${value==='markdown'?'checked':''}><strong>${E(label)}</strong><small>${E({latex:'可直接写正文或粘贴完整 LaTeX；即时预览公式，并在隔离环境中编译 PDF。',markdown:'支持标题、表格、列表、代码块和数学公式，编辑后即时预览。',text:'直接填写正文并预览，保留换行，不解析 Markdown 或 LaTeX 命令。'}[value])}</small></label>`).join('')}</fieldset>`;}
 function tools(){return `<div class="formula-tools" aria-label="公式插入工具">${[['inline','行内公式'],['display','行间公式'],['fraction','分式'],['matrix','矩阵'],['sum','求和']].map(([kind,title])=>`<button type="button" class="btn small" data-tex-insert="${kind}">${title}</button>`).join('')}<span>选中文字后可直接包成公式；支持 $…$、\\(…\\)、\\[…\\]。</span></div>`;}
 function panel(d,resources,options={}){
  const format=d.format||'text',ids=d.compileInputIds||[],available=resources.filter(r=>r.size<=10*1048576),ordered=[...ids.map(id=>available.find(r=>r.id===id)).filter(Boolean),...available.filter(r=>!ids.includes(r.id))];
  return `<section class="panel writing-preview" data-writing-id="${E(d.id)}" data-format="${E(format)}" data-document-collection="${options.collection||'writingDrafts'}" data-compiler-field="${options.field||''}" data-input-id="${options.inputId||''}" data-document-title="${E(d.title||'论文')}"><div class="section-head"><h2>编译预览</h2><span class="badge">${E(formats[format])}</span></div><p class="field-note">${format==='latex'?'可直接写正文或粘贴完整 LaTeX。常用公式即时预览；完整排版以真正编译的 PDF 为准。停止输入约2秒后自动编译，原稿会保留。':'输入后即时更新；预览使用当前正在编辑的中文或英文稿。'}</p><div class="actions compiler-controls"><button type="button" class="btn primary small" data-compiler-action="compile">${format==='latex'?'立即编译PDF':'更新预览'}</button>${format==='latex'?'<label class="compiler-auto"><input id="writing-auto-compile" type="checkbox" checked> 自动编译</label><button type="button" class="btn small" data-compiler-action="cancel" hidden>取消编译</button>':''}<button type="button" class="btn small" data-compiler-action="source">导出当前源码</button><button type="button" class="btn small" data-compiler-action="pdf" hidden>下载 PDF</button></div><div class="compiler-status" role="status" aria-live="polite">准备预览…</div><div class="compiler-diagnostics" role="status"></div>${format==='latex'?`<details class="compiler-attachments"><summary>编译附件（最多5份，共10MB）</summary><label for="writing-compile-inputs">从已上传且有权访问的资料中选择</label><select id="writing-compile-inputs" multiple size="4">${ordered.map(r=>`<option value="${E(r.id)}" ${ids.includes(r.id)?'selected':''}>${E(r.name)}</option>`).join('')}</select><button type="button" class="btn small" data-action="${options.collection==='projects'?'clear-project-compile-inputs':'clear-writing-inputs'}">清空编译附件</button><p class="field-note compiler-input-paths"></p><p class="field-note">独立成行的分式等公式会补齐数学环境，正文会补齐中文模板，原稿保留。可在日志区导出本次可编译源码。</p></details><div class="compiler-view-tabs"><button type="button" class="btn small" data-compiler-action="live">即时正文与公式</button><button type="button" class="btn small" data-compiler-action="pdfview" disabled>完整PDF排版</button></div>`:''}<div class="compiler-output"><div class="writing-preview-html"></div><div class="compiler-pdf" hidden><div class="compiler-pagination"><button type="button" class="btn small" data-compiler-action="previous">上一页</button><span class="compiler-page-count"></span><button type="button" class="btn small" data-compiler-action="next">下一页</button></div><canvas aria-label="已编译论文 PDF 页面"></canvas></div></div><details class="compiler-log" hidden><summary>查看编译日志与源码处理</summary><div class="compiler-preparation-notes"></div><button type="button" class="btn small" data-compiler-action="prepared">导出可编译源码</button><pre></pre></details></section>`;
 }
 const account=()=>API()?.user?.id||'preview';
 function currentField(main){const fixed=main.querySelector('.writing-preview')?.dataset.compilerField;if(fixed)return fixed;for(const field of ['source','target']){const input=main.querySelector('#writing-'+field);if(input&&!input.closest('.form-field').hidden)return field;}return bound?.field||'source';}
 function current(){if(!bound||account()!==bound.owner||!bound.main.isConnected)return null;const panel=bound.main.querySelector('.writing-preview');if(!panel||panel.dataset.writingId!==bound.id)return null;return {...bound,panel,input:bound.main.querySelector(bound.inputId?'#'+bound.inputId:'#writing-'+bound.field)};}
 function selectedInputs(c){return [...(c.panel.querySelector('#writing-compile-inputs')?.selectedOptions||[])].map(o=>o.value);}
 function signature(code,ids){return JSON.stringify([code,ids]);}
 function isCurrent(state){return current()?.state===state;}
 function paths(c){const select=c.panel.querySelector('#writing-compile-inputs'),note=c.panel.querySelector('.compiler-input-paths');if(note)note.textContent=[...(select?.selectedOptions||[])].map((o,i)=>`input/${i}-${o.textContent.replace(/\\/g,'/').split('/').pop().slice(0,160)}`).join('；')||'未选择附件。';}
 function ui(state){const c=current();if(!c||c.state!==state)return;
  const changed=state.pdfSignature&&signature(c.input?.value||'',selectedInputs(c))!==state.pdfSignature;
  c.panel.querySelector('.compiler-status').textContent=(c.collection==='projects'?'项目论文':c.field==='source'?'中文原稿':'英文文稿')+' · '+(state.message||'准备预览')+(changed&&state.pdf?'；当前显示上次成功 PDF，源码已有修改。':'')+(state.previewError?'；PDF 已生成，但页面预览失败，可下载 PDF 查看：'+state.previewError:'')+(state.job?.cleanupPending?'；远端资源释放仍待确认。':'');
  c.panel.querySelector('[data-compiler-action="cancel"]')?.toggleAttribute('hidden',!state.job||terminal.has(state.job.status));
  const cancel=c.panel.querySelector('[data-compiler-action="cancel"]');if(cancel)cancel.disabled=state.job?.status==='cancel_requested';
  const compile=c.panel.querySelector('[data-compiler-action="compile"]');compile.disabled=!!state.restoring||!!state.submitting||!!state.polling||!!(state.job?.cleanupPending&&!state.pollError)||!!(state.job&&!terminal.has(state.job.status)&&!state.pollError);
  compile.textContent=state.pollError?'重新查询状态':c.format==='latex'?'立即编译PDF':'更新预览';
  c.panel.querySelector('[data-compiler-action="pdf"]').hidden=!state.pdf;
  const auto=c.panel.querySelector('#writing-auto-compile');if(auto){auto.checked=state.auto;auto.disabled=!!state.restoring;}
  const log=c.panel.querySelector('.compiler-log'),notes=state.job?.preparationNotes||[];log.hidden=!state.job?.logs&&!notes.length;if(state.job?.logs)log.querySelector('pre').textContent=state.job.logs;log.querySelector('.compiler-preparation-notes').textContent=notes.join('\n');
  const errors=c.panel.querySelector('.compiler-diagnostics');errors.replaceChildren();for(const item of state.job?.diagnostics||[]){const row=document.createElement('div');row.className='compiler-error';const text=document.createElement('p');text.textContent=(item.line?'第'+item.line+'行：':'')+item.message+' '+item.hint;row.append(text);if(item.line){const button=document.createElement('button');button.type='button';button.className='btn small';button.textContent='定位到第'+item.line+'行';button.dataset.texLine=String(item.line);row.append(button);}errors.append(row);}
  const pdfView=c.panel.querySelector('[data-compiler-action="pdfview"]');if(pdfView)pdfView.disabled=!state.pdf;
  for(const value of ['live','pdfview'])c.panel.querySelector('[data-compiler-action="'+value+'"]')?.setAttribute('aria-pressed',String((state.view==='pdf')===(value==='pdfview')));

 }
 function localPreview(){const c=current();if(!c)return;const text=c.input?.value||'',output=c.panel.querySelector('.writing-preview-html');
  if(c.format==='latex')output.innerHTML=window.MMRichText.texPreview(text);else if(c.format==='markdown')output.innerHTML=window.MMRichText.markdown(text);else{const pre=document.createElement('pre');pre.textContent=text;output.replaceChildren(pre);}
  if(c.format!=='latex')c.state.message=text?'预览已更新 · '+(c.format==='markdown'?'Markdown + 数学公式':'普通文字'):'当前稿件为空，填写内容后会在这里显示。';
  c.panel.querySelector('.compiler-pdf').hidden=c.format!=='latex'||c.state.view!=='pdf'||!c.state.pdf;output.hidden=c.format==='latex'&&c.state.view==='pdf'&&!!c.state.pdf;ui(c.state);
 }
 function stopTimers(s){clearTimeout(s.debounce);clearTimeout(s.poll);s.debounce=null;s.poll=null;}
 async function restore(state){if(state.restored||state.restoring||!API()?.user)return;state.restoring=true;ui(state);
  try{const initial=current(),rows=(await API().request('/api/execution/jobs?writingId='+encodeURIComponent(initial.id)+'&field='+initial.field+'&documentCollection='+initial.collection)).jobs;if(!isCurrent(state))return;const c=current(),matches=rows.filter(j=>j.runtime==='latex'&&j.limits?.writingId===c.id&&j.limits.field===c.field),job=matches[0];if(job){state.job=job;await poll(state);if(!state.pdf&&isCurrent(state)){const previous=matches.find(j=>j.status==='completed'&&j.id!==job.id);if(previous){const detail=(await API().request('/api/execution/jobs/'+previous.id)).job,artifact=detail.artifacts.find(a=>a.name==='main.pdf');if(artifact)await loadPdf(state,artifact,signature(detail.code,detail.inputIds||[]));}}}state.restored=true;}
  catch(error){if(isCurrent(state)){state.message='无法读取编译记录：'+error.message;state.auto=false;ui(state);}}
  finally{state.restoring=false;ui(state);if(isCurrent(state))schedule(state);}
 }
 function schedule(state){clearTimeout(state.debounce);const c=current();if(!c||c.state!==state)return;if(!state.userView&&c.format==='latex')state.view='live';localPreview();if(c.format!=='latex')return;
  ui(state);if(!state.auto||state.restoring||state.submitting||state.polling||state.job?.cleanupPending||(state.job&&!terminal.has(state.job.status)))return;
  const code=c.input?.value||'';if(!code.trim()||signature(code,selectedInputs(c))===state.lastSignature)return;
  state.debounce=setTimeout(()=>void submit(state),2000);
 }
 async function submit(state){const c=current();if(!c||c.state!==state||state.restoring||state.polling||state.submitting)return;if(c.format!=='latex'){localPreview();return;}
  if(!API()?.user){state.message='LaTeX 编译需要先登录邮箱账号。';state.auto=false;ui(state);return;}
  const code=c.input?.value||'',ids=selectedInputs(c);if(!code.trim()){state.message='请先填写完整 LaTeX 源码。';ui(state);return;}
  if(ids.length>5){state.message='编译附件最多5份，请减少选择。';state.auto=false;ui(state);return;}
  if(state.job&&!terminal.has(state.job.status))return;
  state.submitting=true;state.message='正在提交隔离编译任务…';ui(state);
  try{if(!state.pending){if(!profileCache||Date.now()-profileCache.at>90000)profileCache={at:Date.now(),value:(await API().request('/api/execution/runtimes')).runtimes.find(p=>p.id==='latex')};const profile=profileCache.value;if(!isCurrent(state))return;if(!profile||profile.status!=='ready_for_remote_test'){state.message=profile?.note||'LaTeX 编译服务尚未配置。';state.auto=false;profileCache=null;return;}state.pending={clientId:window.MM.uid(),runtime:'latex',code,inputIds:ids,seconds:Math.min(120,profile.maxSeconds),writingId:c.id,documentCollection:c.collection,field:c.field};}
   const reply=await API().request('/api/execution/jobs',{method:'POST',body:state.pending});state.lastSignature=signature(state.pending.code,state.pending.inputIds);state.pending=null;state.job=reply.job;await poll(state);}
  catch(error){if(error.status>=400&&error.status<500)state.pending=null;state.message='提交未完成：'+error.message+'。源码仍保留，可修改后重试。';state.auto=false;}
  finally{state.submitting=false;ui(state);schedule(state);}
 }
 async function poll(state){clearTimeout(state.poll);if(!state.job||!isCurrent(state)||state.polling)return;state.polling=true;
  try{state.job=(await API().request('/api/execution/jobs/'+state.job.id)).job;if(!isCurrent(state))return;
   const j=state.job;state.pollError=false;state.lastSignature=signature(j.code,j.inputIds||[]);state.message=statusNames[j.status]||j.status;
   if(j.error)state.message+='：'+j.error;
   if(j.status==='completed'){const artifact=j.artifacts.find(a=>a.name==='main.pdf');if(!artifact)throw new Error('任务未返回 PDF 文件。');if(state.loadedArtifact!==artifact.id)await loadPdf(state,artifact);state.message=j.cacheHit?'已复用相同源码的已编译PDF · 本次没有新建远程任务':'XeLaTeX 编译成功 · 真实 PDF';}
   else if(['cancelled','access_revoked','uncertain','awaiting_credentials','awaiting_authorization'].includes(j.status))state.auto=false;
   if(!terminal.has(j.status)||j.cleanupPending)state.poll=setTimeout(()=>void poll(state),900);else schedule(state);
  }catch(error){
   if(error.status===403||error.status===404){state.renderGeneration++;state.renderTask?.cancel();state.pdf?.destroy();state.pdf=null;state.bytes=null;state.loadedArtifact='';state.pdfSignature='';state.job={id:state.job.id,status:'access_revoked'};state.pollError=false;state.message='文稿或附件权限已变化，旧 PDF 已收起。请清空或重新选择有权限的附件后再编译。';const c=current();if(c?.state===state){c.panel.querySelector('.compiler-pdf').hidden=true;c.panel.querySelector('.writing-preview-html').replaceChildren();}}
   else{state.message='编译状态读取失败：'+error.message+'。可点击重新查询状态，源码仍在。';state.pollError=true;}
   state.auto=false;
  }
  finally{state.polling=false;ui(state);schedule(state);}
 }
 async function loadPdf(state,artifact,pdfSignature=state.lastSignature){const owner=account(),response=await fetch(artifact.url,{credentials:'same-origin',headers:{'X-MM-Account':owner},signal:AbortSignal.timeout(20000)});if(!response.ok)throw new Error('PDF 下载未完成，请检查登录及权限。');const data=new Uint8Array(await response.arrayBuffer());if(data.length>10*1048576||String.fromCharCode(...data.slice(0,5))!=='%PDF-')throw new Error('结果不是有效 PDF。');
  if(!isCurrent(state)||owner!==account())return;pdfLibrary??=import('./vendor/pdfjs/legacy/build/pdf.min.mjs');const pdfjs=await pdfLibrary;pdfjs.GlobalWorkerOptions.workerSrc=new URL('vendor/pdfjs/legacy/build/pdf.worker.min.mjs',document.baseURI).href;
  const pdfDoc=await pdfjs.getDocument({data:data.slice(),isEvalSupported:false,cMapUrl:new URL('vendor/pdfjs/cmaps/',document.baseURI).href,cMapPacked:true,standardFontDataUrl:new URL('vendor/pdfjs/standard_fonts/',document.baseURI).href,wasmUrl:new URL('vendor/pdfjs/wasm/',document.baseURI).href}).promise;
  if(!isCurrent(state)){pdfDoc.destroy();return;}state.renderTask?.cancel();state.pdf?.destroy();state.pdf=pdfDoc;state.bytes=data;state.pdfSignature=pdfSignature;state.loadedArtifact=artifact.id;state.page=1;if(!state.userView)state.view='pdf';await renderPage(state);
 }
 async function renderPage(state){const c=current();if(!c||c.state!==state||!state.pdf)return;state.renderTask?.cancel();const generation=++state.renderGeneration;
  try{const page=await state.pdf.getPage(state.page);if(!isCurrent(state)||generation!==state.renderGeneration)return;const canvas=c.panel.querySelector('canvas'),box=c.panel.querySelector('.compiler-pdf'),output=c.panel.querySelector('.writing-preview-html');box.hidden=state.view!=='pdf';output.hidden=state.view==='pdf';
   const base=page.getViewport({scale:1}),width=Math.max(200,Math.min(1100,c.panel.clientWidth-46)),scale=width/base.width,dpr=Math.min(devicePixelRatio||1,2),viewport=page.getViewport({scale:scale*dpr});canvas.width=viewport.width;canvas.height=viewport.height;canvas.style.width='100%';canvas.style.height='auto';
   state.renderTask=page.render({canvasContext:canvas.getContext('2d'),viewport});await state.renderTask.promise;if(generation!==state.renderGeneration)return;state.previewError='';
   c.panel.querySelector('.compiler-page-count').textContent=`第 ${state.page} / ${state.pdf.numPages} 页`;c.panel.querySelector('[data-compiler-action="previous"]').disabled=state.page===1;c.panel.querySelector('[data-compiler-action="next"]').disabled=state.page===state.pdf.numPages;
  }catch(error){if(generation===state.renderGeneration&&isCurrent(state)&&error.name!=='RenderingCancelledException'){state.previewError=error.message;ui(state);}}
 }
 function mount(main){const panel=main.querySelector('.writing-preview');if(!panel){if(bound)stopTimers(bound.state);bound=null;return;}
  const owner=account();if(owner!==lastAccount){for(const s of states.values()){stopTimers(s);s.renderTask?.cancel();s.pdf?.destroy();}states.clear();profileCache=null;lastAccount=owner;}
  const field=currentField(main),id=panel.dataset.writingId,key=owner+':'+(panel.dataset.documentCollection||'writingDrafts')+':'+id+':'+field;if(bound&&bound.state!==states.get(key))stopTimers(bound.state);
  if(!states.has(key)){states.set(key,{auto:true,view:'live',page:1,renderGeneration:0,message:'准备预览',lastSignature:'',restored:false});if(states.size>6){const oldest=states.keys().next().value,old=states.get(oldest);stopTimers(old);old.renderTask?.cancel();old.pdf?.destroy();states.delete(oldest);}}
  const state=states.get(key);bound={owner,id,field,main,state,format:panel.dataset.format,collection:panel.dataset.documentCollection||'writingDrafts',inputId:panel.dataset.inputId};paths(current());localPreview();
  if(bound.format!=='latex')localPreview();else{ui(state);if(state.pdf)void renderPage(state);if(state.job)void poll(state);else if(!state.restored)void restore(state);else schedule(state);}
 }
 document.addEventListener('input',event=>{if(event.target.matches('#writing-source,#writing-target,#stage-content')){const c=current();if(c){if(!c.inputId&&event.target.id!=='writing-'+c.field)mount(c.main);schedule(current().state);}}});
 document.addEventListener('change',event=>{const c=current();if(!c)return;if(event.target.id==='writing-auto-compile'){c.state.auto=event.target.checked;schedule(c.state);}if(event.target.id==='writing-compile-inputs'){paths(c);schedule(c.state);}});
 document.addEventListener('click',event=>{const button=event.target.closest('[data-compiler-action]'),c=current();if(!c)return;
  if(!button){
   const insert=event.target.closest('[data-tex-insert]');if(insert&&c.input&&!c.input.readOnly){const input=c.input,selected=input.value.slice(input.selectionStart,input.selectionEnd),kind=insert.dataset.texInsert;const snippets={inline:'$'+(selected||'x^2')+'$',display:'\n\\[ '+(selected||'x^2+y^2=z^2')+' \\]\n',fraction:'\n\\[ \\frac{'+(selected||'a')+'}{b} \\]\n',matrix:'\n\\[ \\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix} \\]\n',sum:'\n\\[ \\sum_{i=1}^{n} x_i \\]\n'};input.setRangeText(snippets[kind]||'',input.selectionStart,input.selectionEnd,'end');input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();}
   const line=event.target.closest('[data-tex-line]');if(line&&c.input){const lines=c.input.value.split('\n'),n=Math.min(lines.length,Math.max(1,Number(line.dataset.texLine))),offset=lines.slice(0,n-1).reduce((sum,value)=>sum+value.length+1,0);c.input.focus();c.input.setSelectionRange(offset,offset+(lines[n-1]?.length||0));}
   if(event.target.closest('.academic-filters'))mount(c.main);return;
  }

  const s=c.state,action=button.dataset.compilerAction;
  if(action==='compile'){clearTimeout(s.debounce);if(s.pollError||(s.job&&!terminal.has(s.job.status)))void poll(s);else void submit(s);}
  if(action==='cancel'&&s.job){s.auto=false;clearTimeout(s.debounce);void API().request('/api/execution/jobs/'+s.job.id,{method:'POST',body:{action:'cancel'}}).then(r=>{s.job=r.job;return poll(s);}).catch(e=>{s.message='取消未确认：'+e.message;ui(s);});}
  if(action==='live'||action==='pdfview'){s.userView=true;s.view=action==='pdfview'?'pdf':'live';localPreview();if(s.pdf)void renderPage(s);}
  if(action==='prepared'&&s.job){if(signature(c.input?.value||'',selectedInputs(c))!==s.lastSignature){s.message='请先编译当前版本，再导出可编译源码。';ui(s);}else void API().request('/api/execution/jobs/'+s.job.id+'?prepared=1').then(r=>window.MM.download(r.job.preparedCode,'可编译论文.tex','text/plain;charset=utf-8')).catch(e=>{s.message=e.message;ui(s);});}
  if(action==='previous'||action==='next'){if(s.pdf){s.page=Math.min(s.pdf.numPages,Math.max(1,s.page+(action==='next'?1:-1)));void renderPage(s);}}
  if(action==='source'){const title=c.main.querySelector('#writing-title')?.value||c.panel.dataset.documentTitle||'文稿',extension={latex:'tex',markdown:'md',text:'txt'}[c.format];window.MM.download(c.input?.value||'',title.replace(/[<>:"/\\|?*]/g,'_')+(c.field==='target'?'-英文':'')+'.'+extension,'text/plain;charset=utf-8');}
  if(action==='pdf'&&s.bytes){window.MM.download(new Blob([s.bytes],{type:'application/pdf'}),'论文编译.pdf','application/pdf');}
 });
 addEventListener('hashchange',()=>{if(bound&&!bound.main.isConnected){stopTimers(bound.state);bound=null;}});
 addEventListener('resize',()=>{if(bound?.state.pdf)void renderPage(bound.state);});
 return {choices,panel,mount,template,tools,formatLabel:format=>formats[format||'text']};
})();
