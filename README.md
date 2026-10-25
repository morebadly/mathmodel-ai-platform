# MathModel AI · 邮箱版教学与建模平台

现有 Django 平台的可部署源码，提供学生、导师和固定管理员三个空间。账号与业务数据由后端保存，用户代码只在远程沙箱执行。

## 先下载有内容的知识库

**[完整知识库与原始附件 ZIP（约1.53 GB）](https://github.com/morebadly/mathmodel-ai-platform/releases/download/v0.1.0-mvp-trial/MathModel-AI-Knowledge-1494-with-files.zip)**

包含原知识库 **1,494 条资料记录、562 条可读正文、401 个去重原始附件（含331份本地PDF）**。其中部分记录是来源入口或索引，不代表每条都有论文全文。资料来源与原始说明随包保留，不对第三方资料另行授予开源许可。

GitHub 的 Code / Source code ZIP 仅为本项目源码。完整资料在上面的 Release 附件中；不会在启动时伪造或自动填充知识。

ZIP SHA-256：`c6ffdc8b2aa279b3dfd7cfd379e490276c225262d140454397d19560995a0ae7`。

## 已实现的流程

- 邮箱注册、6位验证码、重置密码；导师共享密钥和邮箱验证；三个固定管理员由后台单独初始化。
- 管理员维护公共知识，项目、论文、文稿、学习记录和团队资料按权限隔离。
- 导师团队、训练任务、题目文件导入、提交版本、反馈、学习监督和邮件提醒。
- 持久化实时聊天、附件、未读、断线补齐和成员撤销后的访问检查。
- AI对话历史与上次会话恢复；模型在后端统一配置。没有Key时明确显示待配置。
- 文档解析、OCR、音频转写与公式展示；保留原件及任务错误状态。
- E2B远程执行适配、异步状态、日志、输入和结果文件；需自行配置有效E2B账户。
- 文稿及资料回收站、恢复、并发保存与权限校验。

MATLAB和商业求解器仍需相应环境及合法授权；不能以Octave或开源求解器充当验收。当前检索以关键词为主，未把它当作向量RAG。自部署RAG和自建沙箱留待服务器阶段。

## 本地运行

使用Python 3.13或更新版本。Linux部署镜像使用锁定依赖；本地环境可先使用依赖清单。

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r backend/requirements.txt
# 将 .env.example 复制为 .env.local，保持本地 MAIL_TRANSPORT=local
python run_local.py --port 8765
```

首次启动会迁移数据库并初始化三个独立管理员和导师共享密钥。**初始化凭证只保存在本机 `.data/private-access/access-credentials.json`，仓库不含任何可登录账号或真实密钥。**

本地开发邮件箱只用于联调，不会投递到真实邮箱。真实SMTP、模型和E2B需要在后端的秘密配置中填写，不写进前端或提交到Git。

## 把原知识库导入Django

解压完整资料包后，来源数据库位于 `MathModel-AI/.data/library.sqlite`，附件位于其同级 `files/`。首次运行本平台并初始化固定管理员后：

```sh
python backend/manage.py import_shared_library --source /absolute/path/MathModel-AI/.data/library.sqlite --owner admin01 --dry-run
python backend/manage.py import_shared_library --source /absolute/path/MathModel-AI/.data/library.sqlite --owner admin01
```

导入器只读来源，并校验、复制正文和去重原件。导入后为1,494条知识条目及401条原件资源，共1,895条资源记录；不包含旧账号、用户资料或学习记录。再次执行会保留管理员已维护的记录。

## 部署与验证

见 [部署说明](docs/DEPLOYMENT.md) 和 [验收范围](docs/VALIDATION.md)。默认 `deploy/compose.yaml` 是完整服务模板，**不能按其全部服务上限直接套到2核4GB机器**；小规模试运行应采用限制并发、拆分任务队列的试运行覆盖配置，并据实际负载评估。

本源码不含生产数据库、用户上传文件、账号密码、SMTP授权码、API Key、模型缓存或许可证。
