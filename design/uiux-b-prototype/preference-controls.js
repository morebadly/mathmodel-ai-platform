'use strict';
// Presentation controls reuse the existing preference handlers and persistence.
(()=>{
 const langSelect=document.getElementById('language'),themeSelect=document.getElementById('theme');
 if(!langSelect||!themeSelect)return;
 const languages=['zh','en','ru'],names={zh:'中文',en:'English',ru:'Русский'};
 const words={zh:{language:'界面语言，左右滑动或按方向键切换',prev:'上一种语言',next:'下一种语言',theme:'外观',light:'亮色',dark:'暗色',system:'跟随系统'},en:{language:'Interface language. Swipe or use arrow keys',prev:'Previous language',next:'Next language',theme:'Appearance',light:'Light',dark:'Dark',system:'System'},ru:{language:'Язык интерфейса. Смахните или используйте стрелки',prev:'Предыдущий язык',next:'Следующий язык',theme:'Оформление',light:'Светлое',dark:'Тёмное',system:'Системное'}};
 const svg=path=>`<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${path}</svg>`;
 const icons={light:svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5"/>'),dark:svg('<path d="M20.7 13A9 9 0 0 1 11 3.3 9 9 0 1 0 20.7 13Z"/>'),system:svg('<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/>')};
 const carousel=document.createElement('div');carousel.className='language-carousel';carousel.setAttribute('role','group');
 carousel.innerHTML=`<button type="button" class="language-step" data-direction="-1">${svg('<path d="m14 7-5 5 5 5"/>')}</button><div class="language-window" tabindex="0"><span class="language-name" data-user-content></span></div><button type="button" class="language-step" data-direction="1">${svg('<path d="m10 7 5 5-5 5"/>')}</button>`;
 const themes=document.createElement('div');themes.className='theme-icons';themes.setAttribute('role','group');
 themes.innerHTML=['light','dark','system'].map(theme=>`<button type="button" class="theme-icon" data-theme-choice="${theme}" aria-pressed="false">${icons[theme]}</button>`).join('');
 langSelect.hidden=true;themeSelect.hidden=true;langSelect.tabIndex=-1;themeSelect.tabIndex=-1;
 langSelect.insertAdjacentElement('afterend',carousel);themeSelect.insertAdjacentElement('afterend',themes);
 const face=carousel.querySelector('.language-window'),label=carousel.querySelector('.language-name');
 const setAttr=(el,key,value)=>{if(el.getAttribute(key)!==value)el.setAttribute(key,value);const saved=L10N.attrs.get(el);if(saved&&key in saved)saved[key]=value};
 function sync(){const pref=M3.data.preferences,lang=pref.language||'zh',w=words[lang]||words.zh;
  if(label.textContent!==names[lang])label.textContent=names[lang]||names.zh;
  label.lang=lang;setAttr(carousel,'aria-label',w.language);setAttr(face,'aria-label',names[lang]+'. '+w.language);setAttr(face,'title',w.language);
  for(const b of carousel.querySelectorAll('button'))setAttr(b,'aria-label',Number(b.dataset.direction)<0?w.prev:w.next);
  setAttr(themes,'aria-label',w.theme);
  for(const b of themes.querySelectorAll('button')){const t=b.dataset.themeChoice;setAttr(b,'aria-pressed',String(pref.theme===t));setAttr(b,'aria-label',w[t]);setAttr(b,'title',w[t])}
 }
 function chooseLanguage(direction){const index=languages.indexOf(M3.data.preferences.language),next=languages[(Math.max(0,index)+direction+languages.length)%languages.length];
  M3.capture();langSelect.value=next;langSelect.dispatchEvent(new Event('change',{bubbles:true}));sync();
  if(!matchMedia('(prefers-reduced-motion: reduce)').matches&&label.animate)label.animate([{opacity:.25,transform:`translateX(${direction>0?12:-12}px)`},{opacity:1,transform:'translateX(0)'}],{duration:180,easing:'ease-out'});
 }
 carousel.addEventListener('click',e=>{const b=e.target.closest('[data-direction]');if(b)chooseLanguage(Number(b.dataset.direction))});
 carousel.addEventListener('keydown',e=>{if(e.target!==face)return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();chooseLanguage(e.key==='ArrowRight'?1:-1)}});
 let start=null;
 face.addEventListener('pointerdown',e=>{if(e.button!==0)return;start={id:e.pointerId,x:e.clientX,y:e.clientY};face.setPointerCapture(e.pointerId)});
 face.addEventListener('pointerup',e=>{if(!start||e.pointerId!==start.id)return;const dx=e.clientX-start.x,dy=e.clientY-start.y;start=null;if(face.hasPointerCapture(e.pointerId))face.releasePointerCapture(e.pointerId);if(Math.abs(dx)>=28&&Math.abs(dx)>Math.abs(dy))chooseLanguage(dx<0?1:-1)});
 face.addEventListener('pointercancel',()=>{start=null});
 themes.addEventListener('click',e=>{const b=e.target.closest('[data-theme-choice]');if(!b)return;themeSelect.value=b.dataset.themeChoice;themeSelect.dispatchEvent(new Event('change',{bubbles:true}));sync()});
 const render=M3.render;M3.render=function(...args){const result=render.apply(this,args);sync();return result};
 const applyTheme=M3.applyTheme;M3.applyTheme=function(...args){const result=applyTheme.apply(this,args);sync();return result};
 sync();
})();
