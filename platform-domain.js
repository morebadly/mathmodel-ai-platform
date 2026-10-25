/* Shared domain rules. No credentials or network access. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.MMEmailDomain=api;})(typeof window==='object'?window:globalThis,function(){
  'use strict';
  const normalizeEmail=value=>String(value||'').trim().toLowerCase();
  const validEmail=value=>typeof value==='string'&&value.length<=254&&/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  const validDate=value=>typeof value==='string'&&Number.isFinite(Date.parse(value));
  function resumeConversation(rows,explicitId='',rememberedId=''){
    const conversations=Array.isArray(rows)?rows:[];
    if(explicitId==='new')return '';
    for(const id of [explicitId,rememberedId])if(id&&conversations.some(row=>row.id===id))return id;
    const activity=row=>Math.max(Date.parse(row.createdAt)||0,...(row.messages||[]).map(message=>Date.parse(message.at)||0));
    return [...conversations].sort((a,b)=>activity(b)-activity(a))[0]?.id||'';
  }
  function upgrade(state){
    state.taskSubmissions??=[];
    state.emailPreferences??={captureEnabled:false};
    state.emailPreferences.journalId??='local-v1';
    for(const person of state.participants||[]){person.email??='';person.emailVerified??=false;}
    for(const reminder of state.reminderDrafts||[]){
      if(reminder.channel!=='email'){reminder.legacyChannel??=reminder.channel;reminder.channel='email';reminder.needsEmailReview=true;}
    }
    return state;
  }
  function validate(state){
    const people=state.participants||[],students=new Set(people.filter(p=>p.role==='student').map(p=>p.id));
    const emails=people.map(p=>normalizeEmail(p.email)).filter(Boolean);
    if(new Set(emails).size!==emails.length)throw new Error('邮箱重复，请核对人员资料。');
    for(const person of people){if(person.email!==undefined&&person.email!==''&&!validEmail(person.email))throw new Error('人员邮箱无效。');if(person.emailVerified!==undefined&&typeof person.emailVerified!=='boolean')throw new Error('邮箱验证状态无效。');}
    if(state.emailPreferences!==undefined&&(!state.emailPreferences||typeof state.emailPreferences.captureEnabled!=='boolean'))throw new Error('学习记录设置无效。');
    const tasks=new Set((state.tasks||[]).map(t=>t.id)),projects=new Set((state.projects||[]).map(p=>p.id));
    if(state.taskSubmissions!==undefined&&!Array.isArray(state.taskSubmissions))throw new Error('训练提交集合无效。');
    const ids=new Set();
    for(const row of state.taskSubmissions||[]){
      if(!row||typeof row.id!=='string'||!/^[A-Za-z0-9_-]{8,100}$/.test(row.id)||ids.has(row.id)||!students.has(row.personId)||!tasks.has(row.taskId)||!projects.has(row.projectId)||typeof row.notes!=='string'||!validDate(row.submittedAt)||!['submitted','reviewed','returned'].includes(row.status)||!Number.isInteger(row.version)||row.version<1||typeof row.feedback!=='string')throw new Error('训练提交或关联无效。');
      if(row.snapshot!==undefined&&(!row.snapshot||!Array.isArray(row.snapshot.stages)||row.snapshot.stages.length!==8||row.snapshot.stages.some(s=>!s||typeof s.title!=='string'||typeof s.content!=='string'||typeof s.done!=='boolean')||!Array.isArray(row.snapshot.resourceIds)||row.snapshot.resourceIds.some(id=>!(state.resources||[]).some(r=>r.id===id))))throw new Error('训练提交快照无效。');
      ids.add(row.id);
    }
    for(const paper of state.papers||[]){const reviewIds=new Set();if(paper.aiReviews!==undefined&&!Array.isArray(paper.aiReviews))throw new Error('论文 AI 评阅记录无效。');for(const row of paper.aiReviews||[]){if(!row||typeof row.id!=='string'||!/^[A-Za-z0-9_-]{8,100}$/.test(row.id)||reviewIds.has(row.id)||typeof row.output!=='string'||typeof row.input!=='string'||typeof row.instruction!=='string'||typeof row.model!=='string'||typeof row.provider!=='string'||!validDate(row.at))throw new Error('论文 AI 评阅记录不完整。');reviewIds.add(row.id);}}
    return state;
  }
  function reminderEligibility(people,ids){
    return ids.map(id=>{const p=people.find(row=>row.id===id);let reason='';if(!p||p.role!=='student')reason='学生不存在';else if(!validEmail(p.email))reason='未登记有效邮箱';else if(p.contactConsent!=='granted')reason='尚未同意学习提醒';else if(!p.emailVerified)reason='邮箱尚未通过服务端验证';return {id,name:p?.name||'未知学生',email:p?.email||'',eligible:!reason,reason};});
  }
  function parseReview(output,input){
    const clean=output.trim().replace(/^```(?:json)?\s*/i,'').replace(/\s*```$/,'');let parsed;
    try{parsed=JSON.parse(clean);}catch{return {summary:'模型未返回有效的结构化结果，请查看原始回复并人工核验。',issues:[],structured:false};}
    if(!parsed||typeof parsed.summary!=='string'||!Array.isArray(parsed.issues))return {summary:'回复结构不完整，请查看原始回复。',issues:[],structured:false};
    const issues=parsed.issues.slice(0,60).filter(row=>row&&['quote','dimension','problem','suggestion'].every(k=>typeof row[k]==='string')).map(row=>({...row,verifiedQuote:!!row.quote.trim()&&input.includes(row.quote)}));
    return {summary:parsed.summary,issues,structured:true};
  }
  function trackingStep(current,{personId,module,activity,at,visible=true,enabled=true,idleMs=300000,newId}){
    if(!enabled||!visible||!personId)return {record:current,changed:false};
    if(!current||current.personId!==personId||at-Date.parse(current.endedAt)>=idleMs||new Date(current.startedAt).toDateString()!==new Date(at).toDateString()){return {record:{id:newId(),personId,startedAt:new Date(at).toISOString(),endedAt:new Date(at).toISOString(),activity,module,source:'本机自动采集 · 资料预览身份未验证',createdAt:new Date(at).toISOString(),capture:'browser-preview'},changed:true};}
    const next={...current,endedAt:new Date(Math.max(at,Date.parse(current.endedAt))).toISOString(),activity:current.activity==='training'||activity==='training'?'training':'learning'};
    const modules=new Set(current.module.split('、'));modules.add(module);next.module=[...modules].join('、');return {record:next,changed:true};
  }
  return {normalizeEmail,validEmail,upgrade,validate,reminderEligibility,parseReview,trackingStep,resumeConversation};
});
