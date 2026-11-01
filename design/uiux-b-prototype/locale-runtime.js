'use strict';
L10N.language=()=>M3.data.preferences.language||'zh';
L10N.dataText=()=>{const values=new Set();const keys=new Set(['title','name','text','content','notes','feedback','requirements','rubric','rules','description','originalText','originalName','source','body','author','teacher','reason','assessment']);const walk=x=>{if(!x||typeof x!=='object')return;for(const [k,v]of Object.entries(x)){if(keys.has(k)&&typeof v==='string'&&v&&!(k==='title'&&typeof x.done==='boolean'))values.add(v.trim());else if(typeof v==='object')walk(v)}};walk(M3.data);return values};
L10N.translate=(s,depth=0)=>{
 const lang=L10N.language();if(lang==='zh'||!/[\u3400-\u9fff]/.test(s))return s;const i=lang==='ru'?1:0,raw=s.trim(),pair=L10N.dict[raw];
 if(L10N.currentData?.has(raw)||L10N.dataParts?.has(raw)||L10N.currentData?.has(raw.replace(/^●\s*/,'')))return s;
 if(pair)return s.replace(raw,pair[i]);
 if(depth>3)return s;
 if(raw.endsWith(' *'))return L10N.translate(raw.slice(0,-2),depth+1)+' *';
 const num=raw.match(/^(\d+\.\s*)(.+)$/);if(num&&L10N.dict[num[2]])return num[1]+L10N.translate(num[2]);
 const patterns=[
 [/^第(\d+)行列数不正确$/,m=>(i?'Неверное число столбцов в строке ':'Incorrect column count in row ')+m[1]],
 [/^第(\d+)行邮箱不在授权学生范围$/,m=>(i?'Строка ':'Row ')+m[1]+(i?': почта вне доступной группы':': email outside authorized students')],
 [/^负责：(.+)$/,m=>(i?'Ответственный: ':'Assigned to: ')+m[1]],
 [/^(.+)状态$/,m=>m[1]+(i?' — состояние':' state')],
 [/^(\d+)\s*分钟$/,m=>m[1]+(i?' мин':' min')],
 [/^(.+)模拟 · (\d+) 分钟 · AI规则：(.+)$/,m=>L10N.translate(m[1],depth+1)+(i?' · Тренировка · ':' simulation · ')+m[2]+(i?' мин · ИИ: ':' min · AI policy: ')+L10N.translate(m[3],depth+1)],
 [/^(.+)。开始后关闭页面或离线不暂停，到时锁定已保存成果。$/,m=>L10N.translate(m[1],depth+1)+(i?'. Закрытие страницы или отключение сети не останавливает отсчёт. По истечении времени сохранённые результаты блокируются.':'. Closing the page or going offline does not pause timing. Saved results lock at expiry.')],
 [/^有效记录 (\d+)；重复跳过 (\d+)；待新增 (\d+)。确认时会重新校验权限和冲突。$/,m=>(i?'Записей: ':'Valid rows: ')+m[1]+(i?'; дубликатов пропущено: ':'; duplicates skipped: ')+m[2]+(i?'; новых: ':'; to add: ')+m[3]+(i?'. При подтверждении права и конфликты проверяются снова.':'. Permissions and conflicts are rechecked on confirmation.')],
 [/^计划 (.+)$/,m=>(i?'Запланировано: ':'Scheduled: ')+L10N.translate(m[1],depth+1)],
 [/^规则：(.+)$/,m=>(i?'Правила: ':'Rules: ')+m[1]],
 [/^版本 V(\d+)$/,m=>(i?'Версия V':'Version V')+m[1]],
 [/^(.+)（0—100，可空）$/,m=>L10N.translate(m[1],depth+1)+(i?' (0–100, необязательно)':' (0–100, optional)')],
 [/^确认提交(版本)? V(\d+)$/,m=>(i?'Подтвердить сдачу V':'Confirm submission V')+m[2]],
 [/^关联教学任务：(.+)$/,m=>(i?'Учебное задание: ':'Teaching task: ')+m[1]],
 [/^(\d+)\/8 阶段完成标记 · 附件 (\d+) 份 · 截止 (.+)$/,m=>m[1]+(i?'/8 этапов отмечено · Вложений: ':'/8 stages marked · Attachments: ')+m[2]+(i?' · Срок: ':' · Due: ')+m[3]],
 [/^截止 (.+)$/,m=>(i?'Срок: ':'Due: ')+m[1]],
 [/^重交截止：(.+)（北京时间）$/,m=>(i?'Повторная сдача: ':'Revision due: ')+m[1]+(i?' (Пекин)':' (Beijing)')],
 [/^修订 (\d+)$/,m=>(i?'Редакция ':'Revision ')+m[1]],
 [/^(\d+) 位授权学生$/,m=>m[1]+(i?' студентов с доступом':' authorized students')],
 [/^手动记录 (\d+) \/ 8 阶段$/,m=>(i?'Отмечено этапов: ':'Stages recorded: ')+m[1]+' / 8'],
 [/^(\d+)\/8 手动标记$/,m=>m[1]+'/8'+(i?' отмечено вручную':' manually marked')],
 [/^(\d+)\/8 手动完成$/,m=>m[1]+'/8'+(i?' отмечено выполненным':' marked complete')],
 [/^(\d+)\/8 阶段已标记；提交时的阶段记录如下。$/,m=>m[1]+(i?'/8 этапов отмечено; ниже записи на момент сдачи.':'/8 stages marked; submitted stage records appear below.')],
 [/^阶段 (\d+) \/ 8 · 标记完成不代表能力或数学正确性评价。$/,m=>(i?'Этап ':'Stage ')+m[1]+(i?' / 8 · Отметка не оценивает способности или математическую корректность.':' / 8 · Completion is not an assessment of ability or mathematical correctness.')],
 [/^提交版本 V(\d+) · (.+)$/,m=>(i?'Сданная версия V':'Submission V')+m[1]+' · '+m[2]],
 [/^最新提交 V(\d+)$/,m=>(i?'Последняя работа V':'Latest submission V')+m[1]],
 [/^(演示已保存|最后保存) (.+)$/,m=>(i?'Сохранено: ':'Saved: ')+m[2]],
 [/^我的问题 · (.+)$/,m=>(i?'Мой вопрос · ':'My question · ')+m[1]],
 [/^AI演示回复 · (.+)$/,m=>(i?'Демоответ ИИ · ':'AI demo response · ')+m[1]],
 [/^从提交 V(\d+) 带入未完成项$/,m=>(i?'Перенести незавершённые пункты из V':'Carry unfinished items from V')+m[1]],
 [/^继承自提交 V(\d+) 的未完成项，非本版本的新评语。$/,m=>(i?'Незавершённый пункт из V':'Unfinished item carried from V')+m[1]+(i?', не новый отзыв к этой версии.':', not new feedback for this version.')],
 [/^范围：(.+)$/,m=>(i?'Доступ: ':'Scope: ')+L10N.translate(m[1],depth+1)],
 [/^来源：(.+)。此条目和原文均为演示资料，不代表真实论文检索结果。$/,m=>(i?'Источник: ':'Source: ')+m[1]+(i?'. Запись и оригинал — демоматериалы, а не результаты реального поиска.':'. This entry and original are demo data, not a real paper search result.')]
 ];for(const [pattern,fn]of patterns){const m=raw.match(pattern);if(m)return fn(m)}
 if(/[·：]/.test(raw)){const parts=raw.split(/(\s*·\s*|：)/);const out=parts.map(x=>/[\u3400-\u9fff]/.test(x)?L10N.translate(x,depth+1):x).join('');if(out!==raw)return out;if(parts.some(x=>L10N.currentData?.has(x.trim())||L10N.dataParts?.has(x.trim())))return s}
 L10N.missing.add(raw);return s;
};
L10N.apply=()=>{
 L10N.observer?.disconnect();const lang=L10N.language();document.documentElement.lang={zh:'zh-CN',en:'en',ru:'ru'}[lang];document.title='MathModel AI · '+({zh:'双端交互原型',en:'Student & Teacher Prototype',ru:'Прототип для студентов и преподавателей'})[lang];
 const data=L10N.dataText();L10N.currentData=data;L10N.dataUnion??=new Set();data.forEach(s=>L10N.dataUnion.add(s));L10N.dataParts=new Set([...data].flatMap(s=>s.split(/\s*·\s*|：/)).filter(Boolean));const walk=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;
 while(n=walk.nextNode()){
  if(n.parentElement.closest('script,style,textarea,pre.code,.original-pre,[data-user-content]'))continue;
  if(!L10N.original.has(n))L10N.original.set(n,n.textContent);const raw=L10N.original.get(n);
  if(data.has(raw.trim())&&!n.parentElement.closest('option,button,.nav-item,.nav-group,#breadcrumb,.field,.tab,h2,.label'))continue;
  const next=L10N.translate(raw);if(n.textContent!==next)n.textContent=next;
 }
 for(const el of document.querySelectorAll('[placeholder],[aria-label],[title],[alt]'))for(const attr of ['placeholder','aria-label','title','alt']){
  if(!el.hasAttribute(attr))continue;let saved=L10N.attrs.get(el);if(!saved){saved={};L10N.attrs.set(el,saved)}saved[attr]??=el.getAttribute(attr);const v=L10N.translate(saved[attr]);if(el.getAttribute(attr)!==v)el.setAttribute(attr,v);
 }
 document.getElementById('nav').setAttribute('aria-label',L10N.translate(T.role==='mentor'?'教师模块导航':'学生模块导航'));
 document.querySelector('.avatar').textContent=T.role==='mentor'?'T':'S';
 L10N.observer?.observe(document.body,{childList:true,subtree:true,characterData:true});
};
const modalBase=M3.modal;M3.modal=(...args)=>{modalBase(...args);L10N.apply()};
L10N.observer=new MutationObserver(records=>{for(const r of records)if(r.type==='characterData')L10N.original.delete(r.target);if(!L10N.pending){L10N.pending=true;queueMicrotask(()=>{L10N.pending=false;L10N.apply()})}});
const reviewParams=new URLSearchParams(location.search);let reviewPreset=false;
if(['zh','en','ru'].includes(reviewParams.get('lang'))){M3.data.preferences.language=reviewParams.get('lang');reviewPreset=true}
if(['light','dark','system'].includes(reviewParams.get('theme'))){M3.data.preferences.theme=reviewParams.get('theme');reviewPreset=true}
if(reviewPreset){M3.save();M3.render()}
L10N.apply();
