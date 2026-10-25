/* Same-origin adapter; capability checks never imply authentication. */
'use strict';
window.MMPlatformAPI=(()=>{
  let capabilities={auth:false,email:false,tracking:false,storage:false,ai:false},checked=false;
  async function request(path,{method='GET',body,timeout=20000}={}){
    if(!/^\/api\//.test(path))throw new Error('接口地址无效。');
    const headers={'Accept':'application/json'};
    if(window.MMPlatformAPI?.user)headers['X-MM-Account']=window.MMPlatformAPI.user.id;
    if(body!==undefined)headers['Content-Type']='application/json';
    if(method!=='GET'){
      const csrf=document.cookie.split('; ').find(row=>row.startsWith('csrftoken='))?.slice(10);
      if(csrf)headers['X-CSRFToken']=decodeURIComponent(csrf);
    }
    const response=await fetch(path,{method,headers,credentials:'same-origin',body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(timeout)});
    let data;try{data=await response.json();}catch{throw new Error('服务返回的格式无效。');}
    if(!response.ok){const error=new Error(data.error?.message||data.detail||'请求未完成，请稍后重试。');error.status=response.status;throw error;}
    return data;
  }
  async function refresh(){try{const value=await request('/api/capabilities');capabilities={...value,...Object.fromEntries(['auth','email','tracking','storage','ai'].map(k=>[k,value[k]===true]))};}catch{capabilities={auth:false,email:false,tracking:false,storage:false,ai:false};}checked=true;return capabilities;}
  function requireFeature(feature){if(!capabilities[feature])throw new Error('对应后端尚未接入，请先确认后端方案。');}
  return {request,refresh,get capabilities(){return capabilities;},get checked(){return checked;},requireFeature};
})();
