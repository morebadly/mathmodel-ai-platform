/* Formal-account UI extensions, composed with the independently usable local preview. */
'use strict';
{
  const create=window.MMEmail.create;
  window.MMEmail.create=ctx=>{
    const local=create(ctx),API=window.MMPlatformAPI,M=window.MM,E=M.esc;
    const {act,badge,notice,pageHead,field,showDialog,toast}=ctx;
    const S=()=>ctx.state();
    let status=null,statusBusy=false,jobs=null,jobsBusy=false;
    function loadStatus(){if(statusBusy||status)return;statusBusy=true;API.request('/api/admin/readiness').then(value=>{status=value;ctx.render();}).catch(error=>{status={error:error.message};ctx.render();});}
    function loadJobs(){if(jobsBusy||jobs)return;jobsBusy=true;API.request('/api/mail-jobs').then(value=>{jobs=value.jobs;ctx.render();}).catch(()=>{jobs=[];ctx.render();});}
    function accountExport(){return `<section class="panel" style="margin-top:20px"><h2>账号数据导出</h2><p>导出当前账号可见的记录和非公共库附件。公共库保留条目信息，原件请单独下载；整库由管理员在服务端备份。</p>${act('server-export','导出账号资料与附件','download','primary small')}</section>`;}
    function personalWeights(){return `<details class="panel" style="margin-top:20px"><summary>人工评价权重</summary><p>仅用于本账号人工评分的加权展示，不改变平台模型服务。</p><form id="weights-form"><div class="weights">${M.dimensions.map((d,i)=>`<label class="weight-row">${E(d)} (%)<input name="w${i}" type="number" min="0" max="100" required value="${S().settings.weights[i]}"></label>`).join('')}</div><button class="btn primary small">保存权重</button></form><p class="field-note">合计100%，仅计算已填写的人工分数。</p></details>`;}
    function modelService(){const c=API.capabilities;return `<section class="panel" style="margin-bottom:20px"><div class="section-head"><h2>统一模型服务</h2>${badge(c.ai?'已配置 · 由平台统一提供':'待管理员配置',c.ai?'green':'amber')}</div><p>学生与导师共用平台提供的模型服务，无需自行填写地址或密钥。</p><p>当前模型：<strong>${E(c.model||'尚未配置')}</strong></p><p class="field-note">由管理员在服务器秘密配置中维护 AI_BASE_URL、AI_MODEL 和 AI_API_KEY_FILE，更新服务后生效。密钥仅保存在后端；Django 管理后台不提供模型密钥编辑表单。</p></section>`;}
    function readiness(){loadStatus();const c=API.capabilities;return `${pageHead('PLATFORM CONFIGURATION','平台配置','模型、邮件和运行服务由管理员统一维护。')}${modelService()}<div class="email-service-grid">${[['公共知识库',`当前账号可见 ${S().resources.filter(r=>r.kind==='knowledge'&&r.scope==='公共知识库').length} 条公共知识。管理员维护，所有已登录账号可读；在线索引不等于全文。`,'已接入'],['邮箱账号与权限','邮箱验证、导师注册密钥、三个独立管理员账号与服务端权限已接入。','已接入'],['文件与解析',c.collaboration?'原件保存在服务端；Office/PDF提取、扫描件OCR、音视频转写和公式展示已加入，能力与限制以实际样例为准。':'原件保存在服务端；支持PDF、Word、Excel、PPT与文本解析。','已接入'],['邮箱任务',c.emailTransport==='local'?'使用本地邮件箱；验证、邀请、提醒均不向外部投递。':'使用 SMTP 队列，支持限额、退订和失败重试。',c.emailTransport==='local'?'本地联调':'SMTP']].map(([title,body,label])=>`<section class="panel"><h2>${title}</h2><p>${body}</p>${badge(label,label==='待配置'?'amber':'green')}</section>`).join('')}</div><section class="panel" style="margin-top:20px"><h2>当前运行情况</h2>${!status?'<p>正在读取服务状态…</p>':status.error?notice(E(status.error),'amber'):`<ul class="detail-list">${[['数据库',status.database],['任务处理',status.queue],['任务循环',status.workerHealthy?'运行中 · '+M.fullDate(status.workerLastSeen):'尚无近期成功运行记录'],['待解析文件',status.pendingFiles],['待处理邮件',status.queuedMail],['需人工核对邮件',status.uncertainMail],['审计记录',status.auditEvents]].map(([k,v])=>`<li><span>${k}</span><strong>${E(v)}</strong></li>`).join('')}</ul>`}${act('server-status-refresh','刷新状态','clock','small')}${c.devMailbox?'<a class="btn small" href="/dev-mailbox/" target="_blank" rel="noopener">本地邮件箱</a>':''}${API.capabilities.instance?.kind!=='production'?'<a class="btn small" href="/admin/" target="_blank" rel="noopener">Django 管理后台</a>':'<p class="field-note">服务端后台通过管理员维护通道访问。</p>'}</section><section class="panel" style="margin-top:20px"><h2>上线前仍需完成</h2>${c.collaboration?`<p>${c.emailTransport==='local'?'真实 SMTP 投递、':''}${c.ai?'模型效果仍需结合实际教学内容评估；':'模型尚未配置；'}MATLAB/商业求解器授权及目标并发容量验收仍需完成。${location.protocol==='https:'?'当前网页通过 HTTPS 访问。':'正式公网部署需要 HTTPS。'}OCR、音视频转写和实时聊天已加入；向量 RAG 留服务器阶段。</p>${status?.mediaCapabilities?`<p>OCR：${status.mediaCapabilities.ocr?'工具已安装，样例验收另见记录':'未安装'}；语音模型：${E(status.mediaCapabilities.speechLanguages.join('、')||'未安装')}；聊天：${E(status.chatBackend)}</p><p>${status.executionRuntimes.map(r=>E(r.id)+'：'+E(r.executionVerified?'有成功运行记录':({awaiting_credentials:'待凭证',awaiting_authorization:'待授权',ready_for_remote_test:'已配置待真实验收'}[r.status]||r.status))).join('；')}</p>`:''}<p><a class="btn small" href="#admin/execution">运行环境与任务</a> <a class="btn small" href="#admin/documents">解析与公式</a></p>`:'<p>真实SMTP、模型服务、Linux部署与向量RAG待完成。当前进程需切换至新版ASGI后使用新增协作功能。</p>'}</section>${accountExport()}`;}
    function directory(){return `${pageHead('EMAIL ACCOUNTS','学生与导师账号','学生使用邮箱注册；导师需统一密钥与邮箱验证。管理员使用三个独立的固定账号。')}<section class="panel"><div class="table-wrap"><table class="resource-table"><thead><tr><th>名称 / 邮箱</th><th>角色</th><th>验证 / 状态</th><th>权限管理</th></tr></thead><tbody>${S().participants.map(p=>`<tr><td>${E(p.name)}<small class="table-note">${E(p.adminLogin||p.email)}</small></td><td>${E({student:'学生',mentor:'导师',admin:'建设者'}[p.accountRole])}${p.requestedRole==='mentor'&&p.accountRole==='student'?'<small class="table-note">申请导师权限</small>':''}</td><td>${p.accountRole==='admin'?'固定管理账号':p.emailVerified?'邮箱已验证':'待验证'} · ${p.isActive?'启用':'停用'}</td><td>${p.accountRole!=='admin'?act('server-account-role','管理角色与状态','edit','small',`data-id="${E(p.id)}"`):'管理账号由 Django 后台维护'}</td></tr>`).join('')}</tbody></table></div></section>`;}
    function mailHistory(){loadJobs();const names={queued:'等待处理',retry:'等待重试',sending:'处理中',local:'进入本地邮件箱',accepted:'服务已受理',failed:'处理失败',cancelled:'已取消',uncertain:'状态不确定，需核对'};return `<section class="panel" style="margin-top:20px"><div class="section-head"><h2>真实邮件任务记录</h2>${act('server-jobs-refresh','刷新邮件任务','clock','small')}</div>${jobs===null?'<p>正在读取…</p>':jobs.length?`<div class="table-wrap"><table class="resource-table"><thead><tr><th>邮件 / 收件邮箱</th><th>计划时间</th><th>状态</th><th>说明</th></tr></thead><tbody>${jobs.map(j=>`<tr><td>${E(j.subject)}<small class="table-note">${E(j.recipient)}</small></td><td>${M.fullDate(j.plannedAt)}</td><td>${E(names[j.status]||j.status)}</td><td>${E(j.detail)}</td></tr>`).join('')}</tbody></table></div>`:'<p>暂无邮件任务。</p>'}</section>`;}
    function formalize(html){
      if(!API.user)return html;if(API.user.role==='admin')html=html.replace('邮箱账号已登录 · 服务端权限已启用','管理账号已登录 · 服务端权限已启用').replaceAll('邮箱已验证 · 服务端权限','固定管理账号 · 服务端权限').replace('建设者管理端 · 邮箱账号','建设者管理端 · 固定管理账号');
      const labels={
        '模拟计时与团队分工记录在本机。AI 规则会限制本平台内的调用入口；跨设备协作、正式提交与服务端规则校验待后续接入。':'模拟计时与分工备注由服务器按账号保存。分工备注不会创建或邀请真实成员；团队协作请使用团队功能。',
        'EMAIL EDITION · V1.3':'EMAIL EDITION · V2.0',
        '本地训练任务':'训练任务',
        '论文、数据与代码仅保存在本机，不会自动进入共享知识库，也不会自动发送到模型服务。':'论文、数据与代码按账号保存到服务器，不会自动进入公共知识库或发送给模型。',
        'TXT、Markdown、LaTeX、CSV 和代码等 UTF-8 文本可直接检索（文本读取上限 5 MB）。PDF、Word、PPT、视频等先保存原件，待接入解析服务。':'文件上传后保留原件；可在“解析与公式”查看提取进度、结果与失败原因。',
        '一个项目连接八个建模阶段。阶段笔记、附件和完成状态会保存到本地。':'一个项目连接八个建模阶段。阶段笔记、附件和完成状态按账号保存到服务器。',
        '本地知识库':'知识库',
        '本地框架版 <span aria-hidden="true">·</span> 内容由您导入':'邮箱账号版 <span aria-hidden="true">·</span> 服务端保存',
        '先登记学生，再导入真实使用记录与成绩。监督目标由导师自行制定。':'先邀请学生加入团队，平台记录真实学习会话，导师录入实际成绩并制定监督目标。',
        '来自本地登记，不代表注册账号':'已验证并接受团队邀请的账号',
        '按实际录入记录计算':'按服务端会话与人工来源记录计算',
        '未发送 · 通道待接入':'待手动确认入队的邮件草稿',
        '依据已导入或录入记录':'依据服务端记录与导师目标',
        '当前提交保存在本浏览器，资料身份未验证。跨设备提交与账号权限等待后端接入。':'提交快照由服务端保存；任务导师可以跨浏览器查看原始提交并填写反馈。',
        '本机资料：':'邮箱账号：',
        '当前支持本机学习会话自动记录，以及手动录入 / 导入。资料预览记录标明身份未验证；正式账号和跨设备统计等待后端。':'显示已接受团队邀请的学生；会话由服务端记录并标明来源，人工记录单独保留来源。',
        '先建立真实学生名单':'先邀请学生加入团队',
        '登记后，可录入使用记录、制定目标和准备提醒。':'在“我的团队”中发送邮箱邀请，学生接受后会进入此监督名单。',
        '本机可生成邮箱草稿，实际定时发送等待后端。':'任务循环按真实账号记录检查目标；邮件仅发给已验证且同意接收的学生。',
        '邮件服务待接入':API.capabilities.emailTransport==='local'?'本地邮件箱联调':'SMTP 邮件队列',
        '当前只保存邮件草稿，没有实际发信。后端框架与邮件服务经确认后接入。':API.capabilities.emailTransport==='local'?'草稿不会自动入队。确认后进入本地邮件箱，未向外部投递。监督计划可按目标生成邮件任务。':'草稿不会自动入队。确认后由 SMTP 队列发送到真实邮箱；可查看受理、失败与重试状态。监督计划可按目标生成邮件任务。',
        '真实结果由邮件服务回执确认。尚未发送，不生成成功率或已读率；服务受理不等于学生已阅读。':'下方展示后台邮件任务的真实状态；进入本地邮件箱不等于发往外部邮箱，服务受理也不等于已读。',
        '业务后端等待确认：成员由教师手动录入，消息保留为草稿，文件保存在当前浏览器。真实登录、邀请入队与跨设备发送尚未接入。':'先发送邮箱邀请，学生接受后建立团队关系。消息草稿仅导师可见，发布后指定成员可查看通知；邮件提醒遵循接收意愿。',
        '本地模式 · 未连接账号服务':'已验证导师账号',
        '本地教师档案':'服务端导师资料',
        '本地团队':'我的团队',
        '本地管理 · 可导出备份':'服务端保存 · 邮箱邀请入队',
        '手动录入，不代表真实账号':'成员信息与邮箱邀请分别管理',
        '尚未发送到成员设备':'包含草稿和已发布通知',
        '账号邀请待后端接入。':'使用邮箱邀请建立真实成员关系。',
        '原件仅保存在本机。单文件 ≤ 50 MB，每批 ≤ 150 MB；不会自动发送给成员。':'原件保存在服务端；团队成员可查看共享文件。单文件 ≤ 50 MB，每批 ≤ 150 MB。',
        '准备好内容与附件，后续由你自行发送':'保存草稿后，可发布给选定的已加入成员',
        '保存后仍为本地草稿。':'保存后仅为导师可见草稿。',
        '创建本地团队后可录入成员、准备消息、上传文件。邀请真实账号加入将在后端接入后开放。':'创建团队后发送邮箱邀请；学生使用受邀邮箱验证并接受后加入。',
        '原件与手动记录会保存在当前浏览器。':'原件与评阅记录会保存在服务端。',
        '论文、数据与代码仅保存在本机，不会自动进入共享知识库，也不会自动发送到模型服务。':'原件保存在服务端个人空间，不会自动发送到模型服务。关联训练提交后，任务导师可查看该次提交的论文。',
        'PDF、Word、PPT、视频等先保存原件，待接入解析服务。':API.capabilities.collaboration?'PDF与Office提取正文，图片/扫描PDF使用OCR，音视频按语言转写；保留原件与真实处理状态。':'PDF、Word、Excel与PPT在后台提取文本；其他格式保留原件。',
        '当前支持文件名、标签及可读取文本的关键词检索。PDF、Word、PPT 与视频保留原文件；专业解析和语义索引待后续接入。':API.capabilities.collaboration?'支持已解析正文的关键词检索、原件引用和字符定位；OCR已加入，向量RAG留服务器阶段。':'支持文件名、标签和已解析正文的关键词检索；向量检索待接入。',
        '资料分区用于组织本地文件。当前是单机框架，视图切换不构成访问权限；多人隔离需接入后端认证与权限服务。':'个人资料仅本人可见；校内 / 公开分区向已验证账号开放；教师私有资料仅所属导师可见，显式团队共享和提交授权除外。',
        '当前可查看本浏览器保存的全部内容。跨账号、跨设备实时查看与权限审计，等待业务后端接入。':'建设者可查看服务端账号、记录与文件。角色授权和关键操作保留后台审计。',
        '本机实际记录汇总':'服务端实际记录汇总',
        '条本地记录':'条服务端记录',
        '本地登记':'已注册账号',
        '建设者可检索学生端与导师端在本机保存的内容，打开记录查看详情。':'建设者可检索服务端已保存内容并查看记录详情。',
        '历史资料未自动归属任何账号。可手动登记内容归属；这不等同于正式访问权限。未来应由后端按真实账号保存和审计访问。':'记录归属由服务端确定，目录页不能改写实际账号归属。',
        '以下包含本机自动采集和人工录入的会话，均标明来源。资料预览不等于真实账号登录；正式账号统计等待后端。':'以下包含服务端自动记录与人工录入的会话，按账号关联并标明来源。会话跨度不等于专注时长。',
        '后端接入规划':'平台配置',
        '填写本地模型或兼容服务配置后使用智能指导。':'平台管理员配置模型服务后使用智能指导。',
        '已保存到本地':'已保存',
      };
      for(const [from,to] of Object.entries(labels))html=html.split(from).join(to);
      html=html.replace(/<button[^>]*data-action="(?:register-student|register-mentor|import-space-data)"[^>]*>[\s\S]*?<\/button>/g,'');
      if(ctx.route()==='reminders')html=html.replace('<footer class="page-footer">',mailHistory()+'<footer class="page-footer">');
      return html;
    }
    function accountProfile(){const u=API.user;return `${pageHead('EMAIL ACCOUNT','我的账号','管理个人资料、记录意愿和账号资料导出。')}<section class="panel"><h2>${E(u.displayName||u.email)}</h2><p>${E(u.email)} ${badge('邮箱已验证','green')}</p><form id="server-profile-form">${field('显示名称','displayName','text',u.displayName||'','可使用昵称，最多120个字符。',true,120)}${field('班级 / 单位（可选）','cohort','text',u.cohort||'','最多120个字符。',false,120)}${u.role==='student'?`<label class="email-choice"><input type="checkbox" name="reminderConsent" ${u.reminderConsent?'checked':''}>通过邮箱接收学习与训练提醒</label>`:''}<label class="email-choice"><input type="checkbox" name="trackUsage" ${u.trackUsage?'checked':''}>记录本账号的学习与训练会话，供进度与导师跟进使用</label><button class="btn primary">保存账号资料</button></form></section>${u.role==='student'?`<section class="panel" style="margin-top:20px"><h2>导师学习目标</h2>${S().supervisionPlans.length?S().supervisionPlans.map(p=>`<article class="space-plan"><div><h3>${E(p.title)}</h3><p>${E(p.content)}</p><small>近7天会话目标：${p.minWeeklySessions??'未设置'} · 未活跃提醒：${p.maxInactiveDays??'未设置'} 天</small></div></article>`).join(''):'<p>导师尚未为你设置学习目标。</p>'}</section>`:''}${accountExport()}${personalWeights()}${u.requestedRole==='mentor'&&u.role==='student'?notice('当前为学生权限。导师注册需提供统一密钥并完成邮箱验证，管理员也可调整角色。','amber'):''}`;}
    function notifications(){const rows=S().notifications||[];return `${pageHead('TEAM NOTICES','团队通知','查看导师发布的通知、附件与训练反馈。')}<section class="panel">${rows.length?rows.map(row=>`<article class="email-issue"><h3>${E(row.title)}</h3><p>${E(row.body)}</p><small>${M.fullDate(row.createdAt)}</small><div class="file-chips">${(row.attachmentIds||[]).map(id=>S().resources.find(r=>r.id===id)).filter(Boolean).map(r=>act('view-resource',E(r.name),'file','small',`data-id="${E(r.id)}"`)).join('')}</div></article>`).join(''):'<p>暂无已发布给你的通知。</p>'}</section>`;}
    function pendingAction(){const params=new URLSearchParams(location.search),invite=params.get('invite'),unsubscribe=params.get('unsubscribe');if(invite)return `${pageHead('TEAM INVITATION','接受团队邀请','请确认是否使用当前邮箱加入邀请中的团队。')}<section class="panel"><p>当前邮箱：${E(API.user.email)}</p>${act('server-accept-invite','接受邀请','school','primary')}</section>`;if(unsubscribe)return `${pageHead('EMAIL PREFERENCES','取消学习提醒','确认后停止此账号的学习提醒，账号验证和密码重置邮件仍可使用。')}<section class="panel">${act('server-unsubscribe','确认取消学习提醒','message','primary')}</section>`;return null;}
    // Reload after the submit handler restores its in-flight/unload guards.
    async function refresh(){setTimeout(()=>location.reload(),0);}
    async function actions(name,id){
      if(name==='preview-space'){if(API.capabilities.instance?.kind==='production')return true;sessionStorage.setItem('mm-explicit-preview','1');return false;}
      if(name==='server-logout'){const loginRole=API.user.role;await API.request('/api/auth/logout',{method:'POST',body:{}});sessionStorage.removeItem('mm-explicit-preview');sessionStorage.removeItem('mm-formal-account');history.replaceState(null,'','/#login/'+loginRole);location.reload();return true;}
      if(name==='server-unsubscribe'){await API.request('/api/reminders/unsubscribe',{method:'POST',body:{token:new URLSearchParams(location.search).get('unsubscribe')}});history.replaceState(null,'','/#login/student');toast('已取消学习提醒。');location.reload();return true;}
      if(!API.user)return local.actions(name,id);
      if(name==='server-export-draft'){M.download(JSON.stringify({format:'mathmodel-ai-unsynced-draft',version:1,account:API.user.adminLogin||API.user.email,exportedAt:M.now(),state:S()},null,2),'MathModel-当前未同步草稿.json');return true;}
      if(name==='server-sync'){await refresh();return true;}
      if(name==='server-accept-invite'){await API.request('/api/invitations/accept',{method:'POST',body:{token:new URLSearchParams(location.search).get('invite')}});location.href='/#student/home';return true;}
      if(name==='server-status-refresh'){status=null;statusBusy=false;ctx.render();return true;}
      if(name==='server-jobs-refresh'){jobs=null;jobsBusy=false;ctx.render();return true;}
      if(name==='teacher-profile'){showDialog('导师账号资料',field('显示名称','displayName','text',API.user.displayName,'最多120个字符。',true,120)+field('单位（可选）','cohort','text',API.user.cohort,'最多120个字符。',false,120),{formId:'server-teacher-profile-form',submit:'保存'});return true;}
      if(['register-student','register-mentor','edit-person','import-space-data','restore-backup'].includes(name))throw new Error('账号与负责关系通过邮箱注册、角色审核和团队邀请维护。');
      if(name==='export-backup'||name==='server-export'){const exportState=await API.request('/api/workspace'),files=[];for(const r of exportState.resources.filter(r=>r.scope!=='公共知识库')){const blob=await window.MMBackend.getFile(r.id);const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob);});files.push({id:r.id,type:blob.type,data});}M.download(JSON.stringify({format:'mathmodel-ai-server-export',version:1,exportedAt:M.now(),account:API.user.adminLogin||API.user.email,state:exportState,files,publicLibraryOriginals:'not-included'},null,2),'MathModel-账号数据留档.json');toast('账号记录与非公共库附件已导出；公共库原件请单独下载。');return true;}
      if(name==='server-account-role'){const p=S().participants.find(p=>p.id===id);showDialog('账号角色与状态',`<p>${E(p.name)} · ${E(p.email)}</p><label class="form-field">角色<select name="role"><option value="student" ${p.accountRole==='student'?'selected':''}>学生</option><option value="mentor" ${p.accountRole==='mentor'?'selected':''}>导师</option></select></label><label class="email-choice"><input type="checkbox" name="isActive" ${p.isActive?'checked':''}>启用此账号</label>`,{formId:'server-role-form',submit:'保存权限',context:{id}});return true;}
      if(name==='inspect-content'){const [collection,rid]=id.split('/'),row=S()[collection]?.find(r=>r.id===rid);showDialog('服务端内容记录',`<pre class="admin-record-preview">${E(JSON.stringify(row,null,2))}</pre>`,{wide:true});return true;}
      if(name==='server-invite'){showDialog('通过邮箱邀请团队成员',field('收件邮箱','email','email','','需要对方注册并接受邀请。',true),{formId:'server-invite-form',submit:'发送邮箱邀请',context:{id}});return true;}
      if(name==='server-publish'){const [teamId,messageId]=id.split('/');const result=await API.request('/api/teams/'+encodeURIComponent(teamId)+'/publish',{method:'POST',body:{messageId,revision:window.MMBackend.revision('teams',teamId)}});toast('团队通知已发布给 '+(result.recipients||0)+' 位成员。');await refresh();return true;}
      if(name==='server-send-reminder'){const result=await API.request('/api/reminders/'+encodeURIComponent(id)+'/send',{method:'POST',body:{}});toast('已加入 '+result.queued.length+' 项邮件任务；'+result.skipped.length+' 位收件人未满足条件。');jobs=null;jobsBusy=false;ctx.render();return true;}
      return local.actions(name,id);
    }
    async function submit(form,data,context){
      if(form.id==='server-role-form'){await API.request('/api/admin/accounts/'+encodeURIComponent(context.id)+'/role',{method:'POST',body:{role:String(data.get('role')),isActive:data.has('isActive')}});await refresh();return true;}
      if(form.id==='server-teacher-profile-form'){const result=await API.request('/api/profile',{method:'PATCH',body:{displayName:String(data.get('displayName')||'').trim(),cohort:String(data.get('cohort')||'').trim()}});API.user=result.user;await refresh();return true;}
      if(form.id==='server-profile-form'){const result=await API.request('/api/profile',{method:'PATCH',body:{displayName:String(data.get('displayName')||'').trim(),cohort:String(data.get('cohort')||'').trim(),reminderConsent:API.user.role==='student'?data.has('reminderConsent'):API.user.reminderConsent,trackUsage:data.has('trackUsage')}});API.user=result.user;toast('账号资料已保存。');await refresh();return true;}
      if(form.id==='server-invite-form'){const result=await API.request('/api/teams/'+encodeURIComponent(context.id)+'/invite',{method:'POST',body:{email:String(data.get('email')||'').trim()}});ctx.close();toast(result.accepted?'该成员已经加入团队。':'邮箱邀请已加入发送队列。');await refresh();return true;}
      return local.submit(form,data,context);
    }
    const unsubscribeView=()=>`${pageHead('EMAIL PREFERENCES','取消学习提醒','确认后停止此账号的学习提醒。')}<section class="panel">${act('server-unsubscribe','确认取消学习提醒','message','primary')}</section>`;
    return {...local,actions,submit,formalize,mailHistory,authMarkup(role){return new URLSearchParams(location.search).has('unsubscribe')?unsubscribeView():local.authMarkup(role);},view(){if(new URLSearchParams(location.search).has('unsubscribe'))return unsubscribeView();if(API.user){const pending=pendingAction();if(pending)return pending;if(['settings','admin-config'].includes(ctx.route()))return API.user.role==='admin'?readiness():accountProfile();if(ctx.route()==='accounts')return directory();if(ctx.route()==='account'||ctx.route()==='student-profile')return accountProfile();if(ctx.route()==='notifications')return notifications();}return local.view();}};
  };
}

/* Load optional workflow code only from a backend that advertises the API. */
{
 const baseCreate=window.MMEmail.create;
 window.MMEmail.create=ctx=>{
  const base=baseCreate(ctx);let extension=null,loading=false,loadError='';
  function ensure(){if(!window.MMPlatformAPI.user||!window.MMPlatformAPI.capabilities.collaboration||extension||loading)return;loading=true;const script=document.createElement('script');script.src='/workflow-ui.js';script.onload=()=>{extension=window.MMWorkflows.create(ctx);ctx.render();};script.onerror=()=>{loadError='协作功能资源未加载，请刷新重试。';ctx.render();};document.head.append(script);}
  return {...base,view(){ensure();const route=ctx.route();if(extension){const result=extension.view();if(result!==null)return result;}if(['chat','execution','documents','grades','retrieval'].includes(route))return ctx.pageHead('WORKFLOWS','协作与任务',loadError||'正在加载功能…');return base.view();},async actions(name,id){ensure();if(extension&&await extension.actions(name,id))return true;return base.actions(name,id);},async submit(form,data,context){if(extension&&await extension.submit(form,data,context))return true;return base.submit(form,data,context);}};
 };
}
