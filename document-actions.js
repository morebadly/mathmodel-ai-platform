/* Reversible document removal. Files and text remain server-owned. */
'use strict';
window.MMRecordActions=(()=>{
  const names={writingDrafts:'文稿',papers:'论文',resources:'资料',projects:'项目',competitions:'模拟竞赛',conversations:'对话'};
  const pages={writingDrafts:'writing',papers:'papers',resources:'knowledge',projects:'workspace',competitions:'competition',conversations:'tutor'};
  const api=()=>window.MMPlatformAPI,E=value=>window.MM.esc(value);
  function allowed(collection,row){
    const user=api().user;if(!user||!row||!names[collection])return false;
    return row._ownerId===user.id||(collection==='resources'&&user.role==='admin'&&row.scope==='公共知识库');
  }
  function button(collection,row){
    if(!allowed(collection,row))return '';
    return '<button type="button" class="btn small" data-action="record-delete" data-id="'+E(collection+'/'+row.id)+'">删除'+names[collection]+'</button>';
  }
  function trashButton(){return api().user?'<button type="button" class="btn small" data-action="records-trash">回收站</button>':'';}
  function detachButton(collection,row,fileId,name){
    const user=api().user,field={projects:'resourceIds',tasks:'attachmentIds',teams:'fileIds'}[collection];
    if(!user||!field||!row||(user.role!=='admin'&&row._ownerId!==user.id)||!row[field]?.includes(fileId))return '';
    return '<button type="button" class="btn small" data-action="record-detach" data-id="'+E(collection+'/'+row.id+'/'+fileId)+'" aria-label="移除'+E(name||'附件')+'的关联">移除关联</button>';
  }
  function create(ctx){
    let trashRows=[],busy=false;
    const find=(collection,id)=>ctx.state()[collection]?.find(row=>row.id===id);
    async function updated(){const state=await window.MM.open();ctx.replaceState(state);}
    async function showTrash(){
      const result=await api().request('/api/records/trash');trashRows=result.records;
      const rows=trashRows.map(row=>'<tr><td>'+E(row.title||'未命名')+'</td><td>'+E(names[row.collection]||row.collection)+'</td><td>'+E(window.MM.fullDate(row.deletedAt))+'</td><td><button class="btn small" type="submit" name="restore" value="'+E(row.collection+'/'+row.id)+'">恢复</button></td></tr>').join('');
      ctx.showDialog('回收站','<p>删除的文稿和原件保留在服务器，可在这里恢复。被任务、提交或聊天引用的内容须先解除关联后才能删除。</p>'+(rows?'<div class="table-wrap"><table class="resource-table"><thead><tr><th>名称</th><th>类型</th><th>删除时间</th><th>操作</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p>回收站为空。</p>'),{formId:'records-trash-form',submit:'',wide:true});
    }
    async function actions(name,id){
      if(!['record-delete','records-trash','record-detach'].includes(name))return false;
      if(busy)return true;
      if(!api().user)throw new Error('请先登录邮箱账号。');
      if(!await ctx.flush())throw new Error('请先保存当前修改，再管理文档。');
      if(name==='records-trash'){await showTrash();return true;}
      if(name==='record-detach'){
        const [collection,key,fileId]=id.split('/'),row=find(collection,key),file=find('resources',fileId);
        if(!detachButton(collection,row,fileId,file?.name))throw new Error('当前没有管理这个附件关联的权限。');
        ctx.showDialog('移除附件关联','<p>从当前'+E({projects:'项目',tasks:'任务',teams:'团队'}[collection])+'移除“'+E(file?.name||'附件')+'”的关联？</p><p>原件会保留。已提交的版本、已发布通知、聊天与运行历史中的附件仍保留；没有历史引用的原件可另行移入回收站。</p>',{formId:'record-detach-form',submit:'移除关联',context:{collection,id:key,fileId}});
        return true;
      }
      const slash=id.indexOf('/'),collection=id.slice(0,slash),key=id.slice(slash+1),row=find(collection,key);
      if(!allowed(collection,row))throw new Error('只有文档所有者或公共知识库管理员可以删除。');
      ctx.showDialog('删除'+names[collection],'<p>将“'+E(row.title||row.name||'未命名')+'”移入回收站？</p><p>正文和原件会保留，可通过回收站恢复。'+(collection==='competitions'?'配套建模项目会保留，仅解除比赛关联。':'')+'若仍被任务、提交或文件消息引用，会提示先处理关联。</p>',{formId:'record-delete-form',submit:'移入回收站',context:{collection,id:key}});
      return true;
    }
    async function submit(form,data,context){
      if(!['record-delete-form','records-trash-form','record-detach-form'].includes(form.id))return false;
      if(busy)return true;
      if(!await ctx.flush(true))throw new Error('当前仍有未保存的修改，请先保存后重试。');
      busy=true;
      try{
        if(form.id==='record-detach-form'){
          const collection=context.collection,id=context.id,row=find(collection,id),fileId=context.fileId;
          if(!detachButton(collection,row,fileId))throw new Error('当前没有管理这个附件关联的权限。');
          await api().request('/api/records/'+encodeURIComponent(collection)+'/'+encodeURIComponent(id)+'/detach-file',{method:'POST',body:{fileId,revision:window.MMBackend.revision(collection,id)||row._revision}});
          await updated();ctx.close();ctx.render();ctx.toast('附件关联已移除，原件和历史提交仍保留。');
        }else if(form.id==='record-delete-form'){
          const collection=context.collection,id=context.id,row=find(collection,id);
          if(!allowed(collection,row))throw new Error('当前没有删除这份文档的权限。');
          const revision=window.MMBackend.revision(collection,id)||row._revision;
          await api().request('/api/records/'+encodeURIComponent(collection)+'/'+encodeURIComponent(id)+'/delete',{method:'POST',body:{revision}});
          await updated();ctx.close();ctx.go(pages[collection]);ctx.render();ctx.toast('已移入回收站，可随时恢复。');
        }else{
          const key=String(data.get('restore')||''),row=trashRows.find(row=>row.collection+'/'+row.id===key);
          if(!row)throw new Error('请选择需要恢复的文档。');
          await api().request('/api/records/'+encodeURIComponent(row.collection)+'/'+encodeURIComponent(row.id)+'/restore',{method:'POST',body:{revision:row.revision}});
          await updated();ctx.render();await showTrash();ctx.toast('文档已恢复。');
        }
      }finally{busy=false;}
      return true;
    }
    return {actions,submit};
  }
  return {create,button,trashButton,detachButton,allowed};
})();
