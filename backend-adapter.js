/* Django session and resource adapter. Local preview remains an explicit, separate mode. */
'use strict';
window.MMBackend=(()=>{
  const API=window.MMPlatformAPI;
  let base=null,active=false;
  const collections=['projects','resources','papers','tasks','competitions','conversations','writingDrafts','teams','supervisionPlans','reminderDrafts','scoreRecords','usageRecords','taskSubmissions'];
  const normalize=value=>Array.isArray(value)?value.map(normalize):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).filter(([key])=>!key.startsWith('_')).sort(([a],[b])=>a.localeCompare(b)).map(([key,v])=>[key,normalize(v)])):value;
  const same=(a,b)=>JSON.stringify(normalize(a))===JSON.stringify(normalize(b));
  const owns=(value,key)=>Object.prototype.hasOwnProperty.call(value,key);
  const changedFields=(before,after)=>[...new Set([...Object.keys(before),...Object.keys(after)])].filter(key=>!key.startsWith('_')&&(owns(before,key)!==owns(after,key)||!same(before[key],after[key])));
  const parserFields=new Set(['text','parseStatus','parseWarning','parseEngine','parseSegments','durationSeconds']);
  function parserMerge(changes,ancestor,latest,state){
    const updates=[];
    const resources=[];
    for(const row of changes.resources||[]){
      const before=ancestor.resources?.find(value=>value.id===row.id),remote=latest.resources?.find(value=>value.id===row.id);
      if(remote?._revision===row._revision){resources.push(row);continue;}
      // Only nonoverlapping changes limited to extraction fields may be rebased.
      // Missing rows, changed ownership, manual text conflicts and ordinary
      // metadata conflicts remain errors; the retry enforces server permissions.
      if(!before||!remote||!before._ownerId||before._ownerId!==remote._ownerId||row._ownerId!==before._ownerId)return null;
      const remoteChanges=changedFields(before,remote),localChanges=changedFields(before,row);
      if(!remoteChanges.length||remoteChanges.some(key=>!parserFields.has(key))||localChanges.some(key=>remoteChanges.includes(key)))return null;
      const merged=structuredClone(remote);
      for(const key of localChanges){if(owns(row,key))merged[key]=structuredClone(row[key]);else delete merged[key];}
      resources.push(merged);
      updates.push({id:row.id,before:structuredClone(state.resources.find(value=>value.id===row.id)),after:merged});
    }
    return updates.length?{changes:{...changes,resources},updates}:null;
  }
  const csrf=()=>document.cookie.split('; ').find(row=>row.startsWith('csrftoken='))?.slice(10)||'';
  async function bootstrap(){
    const account=API.user;
    await API.refresh();
    if(!API.capabilities.auth){if(active||account||sessionStorage.getItem('mm-formal-account'))throw new Error('账号服务连接中断，已停止同步。请保留页面并导出未同步草稿。');active=false;API.user=null;return false;}
    const session=await API.request('/api/auth/session');
    if(account&&account.id!==session.user?.id)throw new Error('登录账号已变化，请保留草稿并刷新核对账号。');
    API.user=session.user||null;
    if(API.user)sessionStorage.setItem('mm-formal-account',API.user.id);else sessionStorage.removeItem('mm-formal-account');
    active=!!API.user;return active;
  }
  async function open({accept=()=>true}={}){const state=await API.request('/api/workspace'),canonical=structuredClone(state),next=window.MMEmailDomain.upgrade(state);if(!accept())throw new Error('读取期间有新的编辑或页面变化，已停止覆盖当前草稿');base=canonical;return next;}
  async function save(state,files=[]){
    const ancestor=structuredClone(base||{});
    ancestor.resources=ancestor.resources||[];
    for(const entry of files){
      const metadata=state.resources.find(row=>row.id===entry.id);if(!metadata)throw new Error('附件元数据不存在。');
      // An idempotent upload may return an existing parsed original after an
      // earlier batch failed. Keep this submission's explicit metadata edits,
      // but always take original-file and extraction fields from the server.
      const submittedMetadata=Object.fromEntries(['category','scope','tags','description'].filter(key=>owns(metadata,key)&&metadata[key]!==undefined).map(key=>[key,structuredClone(metadata[key])]));
      const form=new FormData();form.append('metadata',JSON.stringify(metadata));form.append('file',entry.blob,metadata.name);
      const response=await fetch('/api/files',{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':decodeURIComponent(csrf()),'X-MM-Account':API.user.id},body:form});
      const result=await response.json();if(!response.ok){const error=new Error(result.error?.message||'文件上传未完成。');error.status=response.status;throw error;}
      for(const key of Object.keys(metadata))if(!owns(result,key))delete metadata[key];
      Object.assign(metadata,result,submittedMetadata);const index=ancestor.resources.findIndex(row=>row.id===result.id);if(index<0)ancestor.resources.push(structuredClone(result));else ancestor.resources[index]=structuredClone(result);
    }
    const changes={};
    for(const key of collections){
      const previous=new Map((ancestor[key]||[]).map(row=>[row.id,row]));
      const changed=(state[key]||[]).filter(row=>row.capture!=='server'&&!same(row,previous.get(row.id))).map(row=>({...row,_revision:previous.get(row.id)?._revision||row._revision||0}));
      if(changed.length)changes[key]=changed;
    }
    const preferences={weights:state.settings.weights,integritySettings:state.integritySettings};
    let response,merged=null;
    try{response=await API.request('/api/workspace',{method:'PATCH',body:{changes,preferences}});}
    catch(error){
      if(error.status!==409||!changes.resources?.length)throw error;
      const latest=await API.request('/api/workspace');
      merged=parserMerge(changes,ancestor,latest,state);
      if(!merged)throw error;
      // Replay the same atomic batch once, changing only the safely merged
      // resource rows. A second conflict or any permission failure is surfaced.
      response=await API.request('/api/workspace',{method:'PATCH',body:{changes:merged.changes,preferences}});
      const updates=new Map(merged.updates.map(update=>[update.id,update.after]));
      state.resources=state.resources.map(row=>updates.has(row.id)?structuredClone(updates.get(row.id)):row);
    }
    for(const key of collections){for(const row of state[key]||[]){
      const revision=response.versions?.[key+'/'+row.id];
      if(revision)row._revision=revision;
      else{
        // A queued snapshot may predate the preceding save's response. For an
        // unchanged row retain only metadata already confirmed by that save.
        const previous=ancestor[key]?.find(value=>value.id===row.id);
        if(previous&&same(previous,row)){if(previous._revision)row._revision=previous._revision;if(previous._ownerId)row._ownerId=previous._ownerId;}
      }
    }}
    // Ownership is assigned only from the authenticated server response, never
    // inferred from the account that happened to submit the browser snapshot.
    const recordMetadata=(Array.isArray(response.recordMetadata)?response.recordMetadata:[]).filter(meta=>meta&&collections.includes(meta.collection)&&typeof meta.id==='string'&&typeof meta.ownerId==='string'&&!!meta.ownerId&&Number.isInteger(meta.revision)&&meta.revision>0&&response.versions?.[meta.collection+'/'+meta.id]===meta.revision&&(state[meta.collection]||[]).some(row=>row.id===meta.id));
    for(const meta of recordMetadata){const row=state[meta.collection].find(value=>value.id===meta.id);row._ownerId=meta.ownerId;row._revision=meta.revision;}
    base=structuredClone(state);
    return {recordMetadata:structuredClone(recordMetadata),resourceUpdates:(merged?.updates||[]).map(update=>({...update,after:structuredClone(state.resources.find(row=>row.id===update.id))}))};
  }
  async function getFile(id){const response=await fetch('/api/files/'+encodeURIComponent(id),{credentials:'same-origin',headers:{'X-MM-Account':API.user.id}});if(!response.ok)throw new Error('文件不存在、登录账号已变化或无权访问。');return response.blob();}
  async function restore(value){
    throw new Error('账号数据由服务端统一维护。浏览器备份仅用于独立预览；服务端恢复请使用管理员备份流程。');
  }
  return {bootstrap,open,save,getFile,restore,revision:(collection,id)=>base?.[collection]?.find(r=>r.id===id)?._revision,get active(){return active;}};
})();
