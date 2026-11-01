/* Presentation-only integration. Never changes business records, identities or form values. */
'use strict';
(() => {
 const key='mathmodel-ui-preferences-v1',languages=['zh','en','ru'],names={zh:'中文',en:'English',ru:'Русский'};
 const root=document.documentElement,original=new WeakMap(),attributes=new WeakMap();
 let observer;
 let view={recordId:'not-ready'};
 let preferences={language:'zh',theme:'system'};
 try{const saved=JSON.parse(localStorage.getItem(key)||'{}');if(languages.includes(saved.language))preferences.language=saved.language;if(['light','dark','system'].includes(saved.theme))preferences.theme=saved.theme;}catch{}
 const media=matchMedia('(prefers-color-scheme: dark)');
 const icons={light:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',dark:'<path d="M20 14A8 8 0 0 1 10 4a8 8 0 1 0 10 10Z"/>',system:'<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/>'};
 const svg=path=>`<svg viewBox="0 0 24 24" aria-hidden="true">${path}</svg>`;
 const escape=text=>String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const tr=text=>preferences.language==='zh'?String(text):(window.MMAcademicMessages?.[String(text)]?.[preferences.language==='ru'?1:0]||String(text));
 function theme(){root.dataset.mmUi='academic';root.dataset.mmTheme=preferences.theme==='system'?(media.matches?'dark':'light'):preferences.theme;root.lang={zh:'zh-CN',en:'en',ru:'ru'}[preferences.language];}
 function save(){try{localStorage.setItem(key,JSON.stringify(preferences));}catch{}theme();translate();sync();}
 function translate(){
  observer?.disconnect();
  try {
  // Only marked system captions are translated. User text, filenames, option values and errors are untouched.
  document.querySelectorAll('[data-ui-label]').forEach(el=>{if(!original.has(el))original.set(el,el.textContent);const next=tr(original.get(el));if(el.textContent!==next)el.textContent=next;});
  document.querySelectorAll('[data-ui-attributes]').forEach(el=>{
   let map=attributes.get(el);if(!map){map={};attributes.set(el,map);}
   for(const attr of ['aria-label','title','placeholder']){if(!el.hasAttribute(attr))continue;map[attr]??=el.getAttribute(attr);const next=tr(map[attr]);if(el.getAttribute(attr)!==next)el.setAttribute(attr,next);}
  });
  } finally {if(document.body)observer?.observe(document.body,{childList:true,subtree:true});}
 }
 function mark(selector){document.querySelectorAll(selector).forEach(el=>{if(!el.children.length)el.setAttribute('data-ui-label','');});}
 function sync(){
  document.querySelectorAll('.academic-controls').forEach(box=>{
   const label=box.querySelector('.academic-language-name');if(label.textContent!==names[preferences.language])label.textContent=names[preferences.language];label.lang=preferences.language;
   box.querySelector('.academic-language-face').setAttribute('aria-label',tr('界面语言')+': '+names[preferences.language]);
   box.querySelector('[data-ui-language="-1"]').setAttribute('aria-label',tr('上一种语言'));
   box.querySelector('[data-ui-language="1"]').setAttribute('aria-label',tr('下一种语言'));
   box.querySelector('.academic-theme').setAttribute('aria-label',tr('外观'));
   box.querySelectorAll('[data-ui-theme]').forEach(button=>{const caption=tr({light:'亮色',dark:'暗色',system:'跟随系统'}[button.dataset.uiTheme]);button.setAttribute('aria-label',caption);button.title=caption;button.setAttribute('aria-pressed',String(preferences.theme===button.dataset.uiTheme));});
  });
 }
 function cycle(direction){preferences.language=languages[(languages.indexOf(preferences.language)+direction+languages.length)%languages.length];save();}
 function controls(){
  const box=document.createElement('div');box.className='academic-controls';
  box.innerHTML=`<div class="academic-language"><button type="button" data-ui-language="-1">${svg('<path d="m14 6-6 6 6 6"/>')}</button><div class="academic-language-face" tabindex="0" role="group"><span class="academic-language-name"></span></div><button type="button" data-ui-language="1">${svg('<path d="m10 6 6 6-6 6"/>')}</button></div><div class="academic-theme" role="group">${Object.entries(icons).map(([name,path])=>`<button type="button" data-ui-theme="${name}" aria-pressed="false">${svg(path)}</button>`).join('')}</div>`;
  box.addEventListener('click',e=>{const lang=e.target.closest('[data-ui-language]'),selected=e.target.closest('[data-ui-theme]');if(lang)cycle(Number(lang.dataset.uiLanguage));if(selected){preferences.theme=selected.dataset.uiTheme;save();}});
  const face=box.querySelector('.academic-language-face');let start=null;
  face.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();cycle(e.key==='ArrowRight'?1:-1);}});
  face.addEventListener('pointerdown',e=>{if(e.button!==0)return;start={id:e.pointerId,x:e.clientX,y:e.clientY};face.setPointerCapture(e.pointerId);});
  face.addEventListener('pointerup',e=>{if(!start||start.id!==e.pointerId)return;const dx=e.clientX-start.x,dy=e.clientY-start.y;start=null;if(face.hasPointerCapture(e.pointerId))face.releasePointerCapture(e.pointerId);if(Math.abs(dx)>=28&&Math.abs(dx)>Math.abs(dy))cycle(dx<0?1:-1);});
  face.addEventListener('pointercancel',()=>{start=null;});return box;
 }
 function mount(metadata){
  if(metadata)view=metadata;
  const host=document.querySelector('.top-actions')||document.querySelector('.portal-page');
  if(host&&!host.querySelector('.academic-controls')){const box=controls();if(host.matches('.portal-page'))host.querySelector('.portal-brand').after(box);else host.prepend(box);}
  document.querySelectorAll('.brand-symbol').forEach(el=>{if(!el.querySelector('img'))el.innerHTML='<img class="academic-logo" src="design/uiux-b-prototype/assets/association-logo.png" alt="数学建模协会会标">';});
  // A shared action helper also renders filenames. Only these fixed action captions are system text.
  const fixedActions=new Set(['new-project','save-stage','new-task','new-team','new-plan','new-writing','open-training','open-tutor','server-sync','server-export-draft','server-logout','email-auth-mode','email-resend-code','menu','guide']);
  document.querySelectorAll('button[data-action]').forEach(button=>{if(!fixedActions.has(button.dataset.action))return;for(const node of [...button.childNodes]){if(node.nodeType===Node.TEXT_NODE&&node.textContent.trim()){const span=document.createElement('span');span.setAttribute('data-ui-label','');span.textContent=node.textContent;node.replaceWith(span);}}});
  mark('.nav-item>span:not(.count),.nav-label,.space-identity strong,.breadcrumb span,.breadcrumb strong,.portal-login>.eyebrow,.portal-login>h2,.portal-login>p,.portal-role-cards strong,.portal-role-cards small,.portal-admin-link,.form-field>label,.form-field>small,.email-auth-fields>button,.email-tabs button,.email-inline button');
  if(view.recordId==='')mark('.page-head h1,.page-head .subhead');
  translate();sync();
 }
 window.MMAcademicUI={mount,text:tr,system:text=>`<span data-ui-label>${escape(text)}</span>`,getPreferences:()=>({...preferences})};
 media.addEventListener('change',()=>{if(preferences.theme==='system')theme();});
 addEventListener('storage',e=>{if(e.key!==key)return;try{const next=JSON.parse(e.newValue||'{}');if(languages.includes(next.language)&&['light','dark','system'].includes(next.theme)){preferences=next;theme();translate();sync();}}catch{}});
 theme();
 observer=new MutationObserver(()=>{translate();});
 addEventListener('DOMContentLoaded',()=>{
  mount();observer.observe(document.body,{childList:true,subtree:true});
  document.querySelector('.skip-link')?.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();const main=document.getElementById('main');if(main){main.focus();main.scrollIntoView();}});
 });
})();
