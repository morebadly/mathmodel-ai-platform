/* PR B layout for live records. Moves existing DOM nodes; never copies form values,
   changes action identifiers, writes records, or calls a business API. */
'use strict';
(() => {
 const ui=new Map();
 const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const key=(route,suffix='')=>`${window.MMPlatformAPI?.user?.id||'preview'}:${route}:${suffix}`;
 const direct=(parent,selector)=>[...parent.children].filter(n=>n.matches(selector));
 function disclosure(node,title,route,id){
  if(!node)return null;
  const box=el('details','academic-disclosure'),summary=el('summary','',title);
  box.dataset.layoutDisclosure=id;box.open=ui.get(key(route,id))===true;
  box.append(summary);node.before(box);box.append(node);
  box.addEventListener('toggle',()=>ui.set(key(route,id),box.open));return box;
 }
 function header(main){
  const h=main.querySelector(':scope>.page-head');if(!h)return;
  h.classList.add('academic-page-banner');
  const copy=h.firstElementChild,actions=h.querySelector(':scope>.actions');
  if(copy){copy.classList.add('academic-page-intro');if(actions)copy.append(actions);}
  const eyebrow=h.querySelector('.eyebrow');if(eyebrow)eyebrow.textContent='SMBU · MATHEMATICAL MODELING';
 }
 function filtering(main,route,items,labels){
  let bar=main.querySelector(`[data-page-filter="${route}"]`);
  if(!bar&&!items.length)return;
  if(bar&&!items.length){bar.hidden=true;return;}
  if(!bar){bar=el('div','academic-filters');bar.dataset.pageFilter=route;items[0].closest('.panel,.card-grid')?.before(bar);}
  if(!bar.children.length)for(const [value,label] of labels){const b=el('button','',label);b.type='button';b.dataset.filterValue=value;bar.append(b);}
  const name=key(route,'filter');let selected=ui.get(name)||'all';
  if(!labels.some(([value])=>value===selected))selected='all';
  const empty=el('p','academic-filter-empty','当前筛选下没有记录。');bar.after(empty);
  function apply(value){ui.set(name,value);for(const item of items)item.hidden=value!=='all'&&item.dataset.filterKind!==value;for(const b of bar.querySelectorAll('button')){const active=b.dataset.filterValue===value;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));}empty.hidden=items.some(item=>!item.hidden);}
  bar.addEventListener('click',e=>{const b=e.target.closest('[data-filter-value]');if(b)apply(b.dataset.filterValue);});apply(selected);
 }
 function cards(table,kind){
  if(!table)return;
  const grid=el('div','academic-resource-grid');
  for(const row of table.tBodies[0]?.rows||[]){
   const cells=[...row.cells];if(cells.length<2)continue;
   const card=el('article','academic-resource-card');card.dataset.layoutCard=kind;
   if(kind==='knowledge'){
    const scope=cells[1]?.querySelector('.badge');if(scope)card.append(scope);
    const view=cells.at(-1)?.querySelector('[data-action="view-resource"]');
    if(view){view.classList.remove('icon-btn');view.classList.add('btn','primary','small');view.append(el('span','','阅读与引用'));}
   }
   for(let i=0;i<cells.length;i++){
    const slot=el('div',i===0?'academic-resource-name':i===cells.length-1?'academic-resource-actions':'academic-resource-meta');
    slot.append(...cells[i].childNodes);card.append(slot);
   }grid.append(card);
  }
  if(!grid.children.length){grid.append(el('div','academic-page-empty','暂无记录，上传或创建后会显示在这里。'));}
  const wrap=table.parentElement.matches('.table-wrap')?table.parentElement:table;wrap.replaceWith(grid);
 }
 function knowledge(main){
  const layout=main.querySelector('.resource-layout');if(!layout)return;
  const categories=layout.querySelector('.category-list'),content=layout.querySelector(':scope>section');
  if(categories){const selector=el('details','academic-categories');selector.append(el('summary','','资料分类'));categories.before(selector);selector.append(categories);}
  if(content){const search=content.querySelector('#library-search');if(search)layout.before(search);}
  cards(main.querySelector('.resource-table'),'knowledge');
  const note=main.querySelector(':scope>.notice'),footer=main.querySelector(':scope>.page-footer');if(note&&footer)footer.before(note);
 }
 function submissions(main){
  const rows=[...main.querySelectorAll('.resource-table tbody tr')];
  for(const row of rows){const text=row.cells[2]?.textContent||'';row.dataset.filterKind=text.includes('退回')?'returned':text.includes('已评阅')?'reviewed':'submitted';}
  filtering(main,'submissions',rows,[['all','全部'],['submitted','待评阅'],['returned','退回修改'],['reviewed','已评阅']]);
 }
 function writing(main){
  const form=main.querySelector('#writing-form');if(!form)return;
  const grid=form.querySelector('.bilingual-grid');if(!grid)return;
  const source=form.querySelector('#writing-source')?.closest('.form-field'),target=form.querySelector('#writing-target')?.closest('.form-field'),notes=form.querySelector('#writing-notes')?.closest('.form-field');
  const panels=[source,target,notes].filter(Boolean),bar=el('div','academic-filters');bar.setAttribute('aria-label','文稿编辑区');
  const store=key('writing','editor-tab:'+(main.querySelector('.writing-preview')?.dataset.writingId||'')),saved=ui.get(store)||0;
  function choose(index){ui.set(store,index);panels.forEach((p,i)=>p.hidden=i!==index);[...bar.children].forEach((b,i)=>{b.classList.toggle('active',i===index);b.setAttribute('aria-pressed',String(i===index));});}
  ['中文原稿','英文文稿','术语与修改记录'].slice(0,panels.length).forEach((name,index)=>{const button=el('button','',name);button.type='button';button.addEventListener('click',()=>choose(index));bar.append(button);});
  grid.before(bar);for(const panel of panels)grid.append(panel);choose(saved);
 }
 function account(main){
  const panels=direct(main,'.panel,details.panel');if(panels.length<2)return;
  const split=el('div','academic-account-grid'),aside=el('div','academic-account-aside');panels[0].before(split);split.append(panels[0],aside);
  panels.slice(1).forEach(panel=>{if(panel.querySelector('[data-action="server-export"]'))split.after(panel);else aside.append(panel);});
 }
 function execution(main){
  const env=main.querySelector(':scope>.email-service-grid');disclosure(env,'运行环境与授权状态','execution','environments');
  const split=main.querySelector(':scope>.two-col');if(!split)return;
  const formPanel=split.querySelector('#workflow-run-form')?.closest('section.panel'),result=split.querySelector(':scope>section.panel:last-child');
  if(!formPanel||formPanel===result)return;
  split.before(result,formPanel);split.remove();const config=disclosure(formPanel,'配置运行','execution','run-config');
  const button=el('button','btn primary','配置运行');button.type='button';button.addEventListener('click',()=>{config.open=true;ui.set(key('execution','run-config'),true);config.scrollIntoView({block:'start'});config.querySelector('select,input,textarea')?.focus({preventScroll:true});});
  main.querySelector('.academic-page-intro>.actions')?.prepend(button);
 }
 function documents(main){cards(main.querySelector('.resource-table'),'document');}
 function retrieval(main){
  const form=main.querySelector('#workflow-retrieval-form');if(form){const panel=form.closest('.panel');panel.before(form);panel.classList.add('academic-search-results');}
  const index=main.querySelector('#workflow-index-form')?.closest('.panel');disclosure(index,'索引任务与处理状态','retrieval','index');
 }
 function analytics(main){
  const evidence=main.querySelector('.academic-grade-evidence');
  const extra=direct(main,'.stats,.two-col,.panel').filter(n=>n!==evidence);if(!extra.length)return;
  const group=el('div','academic-statistics-extra');extra[0].before(group);for(const node of extra)group.append(node);
  disclosure(group,'更多使用与成绩统计','analytics','usage');
 }
 function login(main){
  const portal=main.querySelector('.portal-page');if(!portal)return;
  portal.classList.add('academic-auth-page');
 }
 function dialog(modal){
  if(!modal)return;
  modal.classList.add('academic-dialog');
  const body=modal.querySelector('.modal-body');if(!body)return;
  if(modal.querySelector('#import-form,#task-form,#competition-form'))body.classList.add('academic-upload-form');
  if(!modal.querySelector('form'))body.classList.add('academic-reading-dialog');
 }
 // Fullscreen is presentation-only: keep the original forms and reading nodes in place.
 // The document element survives app renders, so native fullscreen does not interrupt saves.
 let expanded=null,nativeOwned=false,nativeBusy=false,inertNodes=[];
 const expandRoot=document.documentElement;
 function restoreInert(){for(const [node,value] of inertNodes)node.inert=value;inertNodes=[];}
 function isolate(main){
  restoreInert();
  for(let node=main;node&&node!==document.body;node=node.parentElement){
   for(const sibling of node.parentElement?.children||[]){
    if(sibling===node||sibling.matches('dialog,script,style,link,.toast,[role="alert"]'))continue;
    inertNodes.push([sibling,sibling.inert]);sibling.inert=true;
   }
  }
 }
 function expandCaption(bar,on){
  const button=bar.querySelector('button'),caption=el('span','',on?'退出全屏':'全屏');caption.setAttribute('data-ui-label','');
  button.querySelector('span').replaceWith(caption);button.setAttribute('aria-pressed',String(on));
  bar.classList.toggle('is-expanded',on);
 }
 function closeNative(){
  if(nativeBusy)return;
  if(nativeOwned&&document.fullscreenElement===expandRoot){
   nativeOwned=false;nativeBusy=true;
   document.exitFullscreen().catch(()=>{}).finally(()=>{nativeBusy=false;});
  }else nativeOwned=false;
 }
 function leaveExpanded(focus=true){
  const previous=expanded;expanded=null;restoreInert();expandRoot.classList.remove('mm-expanded-view');
  if(previous){
   previous.main.classList.remove('academic-expanded-main');expandCaption(previous.bar,false);
   if(previous.home.isConnected)previous.home.append(previous.bar);
   if(focus&&previous.main.isConnected){window.scrollTo(previous.x,previous.y);previous.bar.querySelector('button').focus({preventScroll:true});}
  }
  closeNative();
 }
 function applyExpanded(main,bar){
  main.prepend(bar);main.classList.add('academic-expanded-main');expandRoot.classList.add('mm-expanded-view');isolate(main);expandCaption(bar,true);
 }
 function fullscreen(main,view){
  const route=view.route;
  const allowed=route==='tutor'||route==='chat'||(route==='papers'&&!!main.querySelector('.lab-layout'))||(route==='writing'&&!!main.querySelector('#writing-form'))||(route==='workspace'&&!!main.querySelector('.writing-preview'));
  const identity=key(route,`${view.space||''}:${view.recordId||''}`);
  if(expanded&&(!allowed||expanded.identity!==identity))leaveExpanded(false);
  if(!allowed)return;
  const intro=main.querySelector('.academic-page-intro');if(!intro)return;
  let home=intro.querySelector(':scope>.actions');if(!home){home=el('div','actions');intro.append(home);}
  const bar=el('div','academic-expand-bar'),label=el('strong','academic-expand-title',main.querySelector('h1')?.textContent||'');
  label.setAttribute('data-ui-label','');
  const hint=el('small','academic-expand-hint','Esc 退出全屏');hint.setAttribute('data-ui-label','');
  const button=el('button','btn small');button.type='button';button.setAttribute('aria-controls',main.id);button.setAttribute('aria-pressed','false');
  button.innerHTML='<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/></svg><span data-ui-label>全屏</span>';
  bar.append(label,hint,button);home.append(bar);
  button.addEventListener('click',()=>{
   if(expanded){leaveExpanded();return;}
   expanded={identity,main,bar,home,x:window.scrollX,y:window.scrollY};
   applyExpanded(main,bar);button.focus({preventScroll:true});
   // Unsupported/denied native fullscreen still provides the full webpage workspace.
   if(!document.fullscreenElement&&!nativeBusy&&expandRoot.requestFullscreen){
    nativeOwned=true;nativeBusy=true;
    expandRoot.requestFullscreen().then(()=>{
     nativeBusy=false;if(!expanded)closeNative();else nativeOwned=document.fullscreenElement===expandRoot;
    }).catch(()=>{nativeBusy=false;nativeOwned=false;});
   }
  });
  if(expanded){const top=expanded.main.scrollTop;expanded={...expanded,main,bar,home};applyExpanded(main,bar);main.scrollTop=top;}
 }
 document.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&!event.isComposing&&expanded&&!document.querySelector('dialog[open]')){event.preventDefault();leaveExpanded();}
 });
 document.addEventListener('fullscreenchange',()=>{if(nativeOwned&&document.fullscreenElement!==expandRoot)leaveExpanded();});
 function mount(view={}){
  const main=document.querySelector('main.main')||document.querySelector('#main');if(!main||main.dataset.academicPage)return;
  const route=view.route||'login';main.dataset.academicPage=route;main.dataset.academicDetail=String(!!view.recordId);
  if(route==='login'){if(expanded)leaveExpanded(false);login(main);return;}
  header(main);
  if(route==='training')filtering(main,'training',[...main.querySelectorAll('[data-filter-kind]')],[['all','全部'],['teaching','教师任务'],['personal','个人练习']]);
  if(route==='knowledge')knowledge(main);
  if(route==='submissions')submissions(main);
  if(route==='writing')writing(main);window.MMWritingCompiler?.mount(main);
  if(route==='account'||route==='student-profile')account(main);
  if(route==='execution')execution(main);
  if(route==='documents')documents(main);
  if(route==='retrieval')retrieval(main);
  if(route==='analytics')analytics(main);
  if(route==='monitor'){
   const legacy=direct(main,'.table-wrap')[0];disclosure(legacy,'更多学习会话统计','monitor','usage');
  }
  fullscreen(main,view);
 }
 window.MMAcademicPages={mount,dialog};
})();
