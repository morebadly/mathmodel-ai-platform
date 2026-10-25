# 部署与秘密配置

保留现有Django、PostgreSQL、Redis、Celery后台任务和Channels实时聊天。源码中的部署文件是模板，须在自己的服务器核验域名、证书、存储和资源。

1. 复制 `deploy/runtime.env.example` 为未跟踪的 `deploy/runtime.env`，填写站点URL、允许的主机及SMTP等非公开运行参数。
2. 在 `deploy/secrets/` 单独生成Django和PostgreSQL秘密文件，限制目录和文件权限；其他Key使用 `*_FILE` 或专用秘密管理服务注入。
3. `docker compose -f deploy/compose.yaml --profile setup run --rm init` 执行数据库迁移。
4. 在应用容器运行 `python backend/manage.py provision_access` 初始化三个管理员和导师共享密钥。凭证保存在持久化数据卷，不输出到公开日志。
5. 启动web、maintenance、media、execution、beat及反向代理；HTTPS必须覆盖WebSocket升级，数据库和Redis只走内部网络。
6. 检查 `/health` 与 `/health/ready`，真实验证注册、邮件投递、两账号聊天、附件和任务结果。SMTP服务受理不等于用户已读。

`deploy/compose.trial.yaml` 等文件用于参考试运行的资源和队列边界。根据自己的服务器调整，不能复用他人的qa.env、服务器路径或生产秘密。公网IP证书、反向代理和续证配置也须按实际环境重新核验。

数据库与原件需一起备份。使用 `backup_platform` / `restore_platform` 管理命令并参阅 `--help`；迁移覆盖账号权限、数据库、知识原件和用户上传资料。写入期间使用一致性备份，恢复到独立环境核验后再切换。升级前保留旧镜像与数据库/文件备份，回滚时不得用旧数据库覆盖新产生的用户数据。

OCR/转写模型、后续向量检索模型、MATLAB及求解器许可证应独立保存。未配置的能力保持待配置或待授权，不在业务进程中执行用户代码。
