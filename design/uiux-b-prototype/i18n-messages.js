'use strict';
L10N.add(`
围绕所带团队的任务、提交和反馈安排工作。|Organize work around your teams' tasks, submissions and feedback.|Организуйте работу с заданиями, работами и отзывами своих команд.
只含所带团队的任务相关记录。优先顺序：逾期、临近截止、重交、普通待评阅；同类按等待时间。|Only your teams' task records. Priority: overdue, due soon, resubmissions, then other reviews; oldest first within each group.|Только задания ваших команд. Приоритет: просроченные, близкие к сроку, повторные работы, остальные проверки; внутри группы — по времени ожидания.
只管理本人有权团队；加入团队不会自动公开个人项目或AI对话。|Manage authorized teams only. Joining never shares personal projects or AI chats automatically.|Управляйте только доступными командами. Вступление не открывает личные проекты и диалоги с ИИ.
草稿可编辑；发布后的变化先确认、通知并保留历史。|Edit drafts freely. Published changes require confirmation, notification and history.|Черновики можно редактировать. Изменения после публикации подтверждаются, сохраняются и сопровождаются уведомлением.
按学生、任务和版本评阅；草稿不会提前出现在学生端。|Review by student, task and version. Review drafts remain private.|Проверяйте по студентам, заданиям и версиям. Черновики отзывов студентам недоступны.
只依据团队任务的提交、版本、反馈和快照阶段记录。|Based only on team task submissions, versions, feedback and submitted stages.|Только сданные работы, версии, отзывы и снимки этапов командных заданий.
没有学习时长、登录频率或私人阅读统计；缺少记录不判定学生懈怠。|No study-time, login or private reading statistics. Missing records do not imply poor effort.|Время учёбы, входы и личное чтение не учитываются. Отсутствие записей не означает недостаток старания.
手动确认或计划执行，执行前再次校验权限与接收意愿。|Confirm now or schedule; permissions and consent are checked again at execution.|Подтвердите отправку или задайте время; при выполнении доступ и согласие проверяются снова.
所有发送均为本机模拟，不连接真实邮件服务。关闭页面后没有后台进程；返回原型时才重新检查到期计划。|Sending is simulated locally. Nothing runs while the page is closed; due plans are checked on return.|Отправка моделируется локально. После закрытия страницы фоновой работы нет; планы проверяются при возвращении.
先选择任务和收件对象，预览后再确认。|Choose a task and recipients, preview, then confirm.|Выберите задание и получателей, проверьте результат и подтвердите.
展示来源与任务记录，不推断使用行为导致成绩变化。|Show sources and task records without inferring the causes of grade changes.|Источники и записи по заданиям без выводов о причинах изменения оценок.
暂无成绩，导入后显示；不会生成虚构分数。|No grades yet. Import entered scores to display them.|Оценок пока нет. После импорта будут показаны введённые баллы.
统计按学生、考核、日期和来源区分。不包含学习时长或私人对话。|Separate records by student, assessment, date and source. No study time or private chats.|Записи разделяются по студенту, работе, дате и источнику. Время учёбы и личные диалоги не учитываются.
六列CSV，先预览与校验，冲突阻止整批导入。|Six-column CSV. Preview first; a conflict blocks the entire batch.|CSV из шести столбцов. Сначала проверка; конфликт блокирует весь пакет.
列名与顺序：email,assessment,assessmentDate,score,maxScore,source。日期YYYY-MM-DD；最多1000行、1MB。|Columns: email,assessment,assessmentDate,score,maxScore,source. Date: YYYY-MM-DD. Limit: 1,000 rows, 1 MB.|Столбцы: email,assessment,assessmentDate,score,maxScore,source. Дата: YYYY-MM-DD. Не более 1000 строк и 1 МБ.
仅查看学生主动提交的论文或文稿快照，不读取私人原件。|Only explicitly submitted paper or draft snapshots are visible, never private originals.|Доступны только сданные снимки статей и текстов, без личных оригиналов.
学生把论文或文稿关联到项目并提交后，才能在这里查看。|Papers appear after a student attaches them to a project and submits it.|Статья появится после того, как студент приложит её к проекту и сдаст работу.
区分公共、团队与教师个人资料；公共维护仍属于管理员。|Separate public, team and teacher-private resources. Administrators maintain public resources.|Общие, командные и личные материалы преподавателя разделены. Общие материалы поддерживает администратор.
限本人有权团队，消息可关联任务。|Chat within authorized teams, with task context.|Общайтесь в доступных командах с привязкой к заданиям.
教师自己的演示运行记录，不读取学生私人代码。|Teacher-owned demo runs; student-private code is never read.|Демонстрационные запуски преподавателя. Личный код студентов недоступен.
只模拟运行，不实际执行输入的代码。|Runs are simulated; entered code is never executed.|Запуск моделируется; введённый код не выполняется.
教师自有资料的解析状态演示，不读取真实文件。|Simulated parsing of teacher resources, without reading real files.|Демонстрация разбора материалов преподавателя без чтения реальных файлов.
文档、图片或音频结果均使用明确标记的演示。|Document, image and audio results are clearly marked demos.|Результаты для документов, изображений и аудио явно помечены как демонстрационные.
只检索教师有权访问的演示资料，不扩大权限。|Search authorized demo resources only; access is never expanded.|Поиск только в доступных демоматериалах, без расширения прав.
不生成虚构引用，不宣称向量检索。|No invented citations or claimed vector search.|Без вымышленных ссылок и заявлений о векторном поиске.
教师身份、邮箱验证与显示偏好。|Teacher identity, email verification and display preferences.|Профиль преподавателя, проверка почты и настройки отображения.
只允许@example.invalid演示邮箱；不读取或修改真实教师账号。|Only @example.invalid addresses. Real teacher accounts are not accessed.|Только адреса @example.invalid. Реальные аккаунты преподавателей не используются.
仅管理本人有权团队，不查看学生个人项目、AI对话、修改清单或私人备注。|Manage authorized teams only. Student projects, AI chats, personal checklists and notes remain private.|Управляйте только доступными командами. Личные проекты, диалоги с ИИ, списки исправлений и заметки студентов недоступны.
从上次的位置继续，或从一个新问题开始。|Pick up where you left off, or begin with a new question.|Продолжите с того же места или начните с нового вопроса.
学生自勾完成不代表教师认可。|Your completion checks do not mean teacher approval.|Отметка студента о выполнении не означает одобрения преподавателя.
分模式获得方向提示，保留来源与对话 →|Explore guided modes with sources and chat history →|Выберите режим подсказок с источниками и историей диалога →
阅读原件，定位批注与关联文稿 →|Read originals, locate annotations and linked drafts →|Читайте оригиналы, находите замечания и связанные тексты →
查看公共、个人和团队资料 →|Browse public, personal and team resources →|Просматривайте общие, личные и командные материалы →
区分教师任务与个人练习，按要求开始、提交和复盘。|Separate teacher tasks from personal practice. Start, submit and reflect on each.|Разделяйте задания преподавателя и личную практику. Выполняйте, сдавайте и анализируйте результат.
按任务和版本保留成果、反馈与修改记录。|Keep results, feedback and revisions by task and version.|Сохраняйте результаты, отзывы и доработки по заданиям и версиям.
个人与团队限时训练，明确分工、规则与成果。|Timed individual and team practice with clear roles, rules and outcomes.|Практика на время для одного участника или команды с ролями, правилами и результатами.
队长配置规则与分工；成员更新进度并参与协作。|The captain sets rules and assignments; members update progress and collaborate.|Капитан задаёт правила и распределяет задачи; участники обновляют прогресс и работают вместе.
展示实际记录与反馈，不用时长或提交次数推断能力。|Show recorded work and feedback without inferring ability from time or submission counts.|Показывайте записи и отзывы без оценки способностей по времени или числу работ.
教师只查看所带团队的任务提交、版本、反馈处理与提交快照中的阶段记录；不统计学习时长。|Teachers see only their teams' task submissions, versions, feedback and submitted stages; study time is not tracked.|Преподаватели видят только работы своих команд, версии, отзывы и сданные этапы; время учёбы не учитывается.
目前没有经长期验证的能力画像。个人完成标记和论文自评不会自动生成能力排名。|No validated ability profile is available. Completion marks and paper self-assessments do not generate rankings.|Подтверждённого профиля способностей пока нет. Отметки о выполнении и самооценка статей не формируют рейтинг.
这些仅是演示操作记录，不是生产环境的学生行为统计。|These are demo actions, not production student-behavior statistics.|Это действия в демо, а не статистика поведения студентов в рабочей системе.
八阶段记录项目过程，个人内容默认私有。|Record eight project stages. Personal content is private by default.|Фиксируйте восемь этапов проекта. Личные материалы по умолчанию закрыты.
私人对话默认不向教师共享。真实模型调用不在本原型中执行。|Private chats are not shared with teachers. This prototype does not call a live AI model.|Личные диалоги преподавателю недоступны. Прототип не обращается к реальной модели ИИ.
支持保存问题、模拟等待／停止／失败与重试。演示回复不会被当作真实模型输出。|Save questions and try waiting, stopping, failure and retry states. Replies are demos, not live AI output.|Сохраняйте вопросы, проверяйте ожидание, остановку, ошибку и повтор. Ответы демонстрационные, а не вывод реального ИИ.
阅读原文、记录依据，关联写作文稿与训练提交。|Read originals, record evidence and link drafts to task submissions.|Читайте оригиналы, фиксируйте основания и связывайте тексты со сданными работами.
文稿语言与界面语言分别设置；中文、英文或俄文内容不会被自动覆盖。|Document and interface languages are independent. Chinese, English or Russian text is never overwritten automatically.|Языки текста и интерфейса независимы. Китайский, английский и русский текст автоматически не заменяется.
区分公共、个人和团队资料，保留来源与访问范围。|Separate public, personal and team resources, retaining source and access scope.|Разделяйте общие, личные и командные материалы, сохраняя источник и права доступа.
关键词检索演示资料，来源可追溯，不声称向量RAG。|Keyword search over traceable demo resources; no vector RAG is claimed.|Поиск по ключевым словам в демоматериалах с источниками; векторный RAG не заявляется.
检索范围为当前账号有权访问的演示资料。|Search is limited to demo resources accessible to this account.|Поиск ограничен демоматериалами, доступными этому аккаунту.
查看文档、OCR或转写的状态与原文依据。|View document, OCR or transcription states with original evidence.|Просматривайте состояния разбора документов, OCR и расшифровки с исходными данными.
可选择文档、图片或音频演示场景。|Choose a document, image or audio demo.|Выберите демонстрацию документа, изображения или аудио.
配置输入、查看日志与结果，保留失败和取消路径。|Configure input, inspect logs and results, and try failure or cancellation.|Настраивайте ввод, изучайте журналы и результаты, проверяйте ошибки и отмену.
本原型不执行用户代码，也不连接远程沙箱；成功结果为固定演示内容。|No user code is executed and no remote runner is connected. Successful output is a fixed demo.|Код пользователя не выполняется, удалённая среда не подключена. Успешный вывод — фиксированная демонстрация.
开始一次演示，检查排队、日志、取消与结果的交互。|Start a demo to review queueing, logs, cancellation and results.|Запустите демонстрацию для проверки очереди, журнала, отмены и результатов.
任务、提交与反馈有明确去向，不再显示首页正文。|Notifications link directly to tasks, submissions and feedback.|Уведомления ведут прямо к заданиям, работам и отзывам.
仅有权成员可查看会话，关联任务不丢失上下文。|Only authorized members can read conversations, with linked task context.|Диалоги доступны только участникам с правами, с контекстом связанных заданий.
管理个人资料、团队和偏好，不把本机演示当作真实身份。|Manage your profile, teams and preferences. Demo identity is not real authentication.|Управляйте профилем, командами и настройками. Демоидентификация не является реальной авторизацией.
仅用于原型，不投递邮件。|Prototype only; no mail is sent.|Только для прототипа; письма не отправляются.
邮箱已演示验证 · 个人项目、文稿与AI对话默认不共享。|Demo email verified · Personal projects, drafts and AI chats are private by default.|Демонстрационная почта проверена · Личные проекты, тексты и диалоги с ИИ по умолчанию закрыты.
右上角可切换中英俄界面、亮色、暗色和跟随系统；个人正文保留原语言。|Use the top-right controls for Chinese, English or Russian and light, dark or system theme. Personal text keeps its language.|Справа вверху выберите китайский, английский или русский язык и светлую, тёмную или системную тему. Личные тексты сохраняют свой язык.
愿意接收所带团队任务的提醒（演示设置，不实际发信）|Receive reminders for my teams' tasks (demo only; no mail sent)|Получать напоминания о заданиях моих команд (только демо, без отправки писем)
教师只看任务相关提交及约定统计|Teachers see only task submissions and agreed statistics|Преподаватель видит только работы по заданиям и согласованную статистику
仅保存此独立原型的演示资料，用于测试刷新恢复与计时。不读取正式项目数据库或凭证。可导出或重置。|This independent prototype stores demo data for reload and timer tests. It never reads project databases or credentials. Export or reset it at any time.|Прототип сохраняет демоданные для проверки восстановления и таймеров. Рабочие базы и учётные данные не читаются. Данные можно экспортировать или сбросить.
注册、邮箱验证和找回均为演示，不创建真实账号。|Registration, verification and recovery are simulations; no real account is created.|Регистрация, проверка и восстановление моделируются; реальные аккаунты не создаются.
请勿输入真实密码。原型不存储密码，教师密钥只是固定演示值。|Do not enter real passwords. Passwords are not stored; the teacher key is a fixed demo value.|Не вводите реальные пароли. Пароли не сохраняются; ключ преподавателя — фиксированное демозначение.
固定演示值：TEACH-DEMO；不是真实共享密钥。|Fixed demo value: TEACH-DEMO. Not a real shared key.|Фиксированное значение: TEACH-DEMO. Это не реальный общий ключ.
演示码123456，不发真实邮件。|Demo code: 123456. No email is sent.|Демонстрационный код: 123456. Письмо не отправляется.
仅演示账号流程，不发送邮件、不创建真实账号。请使用 student@example.invalid 等演示邮箱，不输入真实密码。|Account-flow demo only: no email or real accounts. Use a demo address such as student@example.invalid and no real password.|Это демонстрация: без писем и реальных аккаунтов. Используйте адрес вроде student@example.invalid и не вводите реальный пароль.
任意6位以上演示文字，不验证真实账号。|Any demo text of at least six characters; no real account is verified.|Любой демонстрационный текст от шести символов; реальный аккаунт не проверяется.
至少6位，不会存储密码。|At least six characters. Passwords are never stored.|Не менее шести символов. Пароль не сохраняется.
仅演示：123456；输入其他内容可查看错误状态。|Demo code: 123456. Try another value to inspect an error.|Демонстрационный код: 123456. Другое значение покажет ошибку.
暂无发布后变更。|No changes since publication.|После публикации изменений не было.
仅查看提交快照和修改说明，不读取学生私人工作区、修改清单或个人备注。|Only submission snapshots and revision summaries are visible, never private workspaces, checklists or notes.|Доступны только снимки работ и описания доработки, без личного пространства, списков исправлений и заметок.
允许补交，逾期提交会标记为补交。|Late submissions are allowed and marked late.|Поздняя сдача разрешена и помечается как просроченная.
本轮退回有独立重交截止，以该时间为准。|This revision has its own deadline, which takes precedence.|Для этой доработки установлен отдельный срок; применяется именно он.
私人工作区，提交时生成快照|Private workspace; a snapshot is made on submission|Личное пространство; при сдаче создаётся снимок
自勾仅记录个人进展，不代表教师认可。个人备注不向教师展示。|Checks record personal progress, not teacher approval. Personal notes are private.|Отметки фиксируют личный прогресс, а не одобрение преподавателя. Личные заметки недоступны преподавателю.
从上方反馈中手动添加事项。|Add items manually from the feedback above.|Добавляйте пункты вручную из отзыва выше.
个人工作区默认私有；教师只看到主动提交的快照或明确共享的资料。|Your workspace is private. Teachers see only submitted snapshots or explicitly shared resources.|Ваше пространство личное. Преподаватель видит только сданные снимки или явно открытые материалы.
原件保留不变；改写时创建关联文稿。|The original is preserved; revisions use a linked draft.|Оригинал сохраняется; для изменений создаётся связанный текст.
演示解析已就绪 · 此处为示例文本，不是实际文件解析。|Demo parsing ready · Sample text, not a parsed real file.|Деморазбор готов · Это пример текста, а не разбор реального файла.
个人自评不等于教师成绩；没有输入分数时不生成总分或能力画像。|Self-assessment is not a teacher grade. Without entered scores, no totals or ability profiles are generated.|Самооценка не равна оценке преподавателя. Без введённых баллов итог и профиль способностей не создаются.
暂无个人批注。|No private annotations yet.|Личных комментариев пока нет.
保留原论文与历史版本，导出或提交前由你确认。|Preserve the original and history. You confirm before export or submission.|Оригинал и история сохраняются. Экспорт и сдача требуют вашего подтверждения.
建议必须主动采纳。采纳后可撤销，不替你覆盖上传原件。|Suggestions require explicit acceptance and can be undone. They never overwrite the original.|Рекомендации принимаются явно и могут быть отменены. Оригинал не заменяется.
暂未保存命名版本。|No named versions saved yet.|Именованных версий пока нет.
只创建本机邀请，不发送真实邮件。学生切换到账号页接受。|Local invitation only. Students accept it on their account page; no email is sent.|Создаётся локальное приглашение. Студент принимает его в профиле; письмо не отправляется.
先保存草稿，再预览发布。|Save a draft, then preview and publish.|Сначала сохраните черновик, затем проверьте и опубликуйте.
只使用任务相关证据，不采集学习时长或私人活动。|Use task evidence only, without study-time or private-activity tracking.|Только данные по заданиям, без учёта времени учёбы и личной активности.
先保存为教师个人资料，后续明确共享。|Save privately first; share explicitly later.|Сначала сохраните как личный материал; доступ откройте отдельно.
不读取真实文档或音频。|No real documents or audio are read.|Реальные документы и аудио не читаются.
该操作的业务边界已在界面中说明。|The scope of this action is described on the page.|Границы этого действия описаны на странице.
已取消本次发送，输入仍保留在当前页面。|Sending cancelled; your input remains on this page.|Отправка отменена; введённый текст остался на странице.
关闭页面不暂停；到时锁定已保存成果。团队协作仅使用演示成员。|Closing does not pause the timer. Saved results lock at expiry. Team members are simulated.|Закрытие страницы не останавливает таймер. По истечении времени сохранённые результаты блокируются. Участники демонстрационные.
只创建演示原件记录，不读取真实文件。|Create a demo original record only; no real file is read.|Создаётся только демонстрационная запись оригинала; реальный файл не читается.
只输入演示资料，不读取本机文件。公共资料由管理员维护。|Enter demo resources only; local files are not read. Administrators maintain public resources.|Вводите только демоматериалы; локальные файлы не читаются. Общие материалы поддерживает администратор.
不执行输入代码，不发送远程请求。结果与日志用于交互演示。|No code execution or remote requests. Results and logs demonstrate interaction only.|Код не выполняется, запросы не отправляются. Результаты и журналы служат только для демонстрации взаимодействия.
只使用固定演示内容，不读取任何真实原件或音频。|Fixed demo content only; no real originals or audio are read.|Только фиксированные демоданные; реальные оригиналы и аудио не читаются.
记录不存在或不属于本人所带团队。|The record is missing or outside your teams.|Запись отсутствует или не относится к вашим командам.
当前教师登录、验证或角色权限不可用。|Teacher sign-in, verification or role access is unavailable.|Вход, проверка или права преподавателя недоступны.
评审状态不删除原有记录，受限时不显示业务正文。|Review states retain data and hide restricted content.|Проверочные состояния сохраняют данные и скрывают недоступное содержимое.
保存失败演示：输入保留，记录不写入。|Save-failure demo: input remains; records are not written.|Демоошибка сохранения: ввод остаётся, запись не сохраняется.
将记录历史、通知受影响学生；已有提交快照不改写。|History is kept and affected students are notified. Existing snapshots stay unchanged.|История сохраняется, студенты получают уведомление. Существующие снимки не меняются.
移出后撤销该团队访问与教师查看范围，历史内容不删除。|Removal revokes team access and teacher visibility; history is retained.|Удаление отзывает доступ к команде и видимость для преподавателя; история сохраняется.
学生提交后才会出现在这里。|Submissions appear after students submit.|Работы появятся после сдачи студентами.
教师评阅关联具体提交版本，不改写学生原件。|Reviews link to a submission version and never rewrite originals.|Проверка привязана к версии работы и не изменяет оригинал.
只共享本资料副本，不公开其他教师个人资料。|Share a copy of this resource only, not other private materials.|Открывается только копия этого материала, а не другие личные материалы.
当前为保存失败评审状态；操作不写入演示存储，输入留在页面。|Save-failure review: no data is written; input remains.|Проверка ошибки сохранения: данные не записываются, ввод остаётся.
可能尚未加入团队，或资料访问权已撤销。不会展示受限正文。|You may not have joined the team, or access was revoked. Restricted text is hidden.|Возможно, вы не вступили в команду или доступ отозван. Недоступный текст скрыт.
已有记录未删除。请重试，或返回上一个可用页面。|Existing records are safe. Retry or return to a working page.|Существующие записи сохранены. Повторите попытку или вернитесь на доступную страницу.
这是评审用空状态，不会清除实际演示记录。|This review-only empty state does not delete demo records.|Это пустое состояние для проверки; демозаписи не удаляются.
请返回列表重新选择，原型不会静默跳转首页。|Return to the list and choose again; no silent redirect occurs.|Вернитесь к списку и выберите снова; скрытого перенаправления нет.
教师端没有这个入口。|This page is not available in the teacher area.|В кабинете преподавателя такой страницы нет.
目标任务、团队或提交不属于当前学生。|This task, team or submission does not belong to the current student.|Это задание, команда или работа не относятся к текущему студенту.
当前只演示账号流程，不创建真实账号。|Account-flow demo only; no real accounts are created.|Только демонстрация входа; реальные аккаунты не создаются.
登录后保留原来的页面目标。|Your destination is retained after signing in.|После входа целевая страница сохраняется.
账号页面不存在。|Account page not found.|Страница аккаунта не найдена.
请从左侧导航重新进入。|Choose a page from the sidebar.|Выберите страницу в боковом меню.
不会静默跳回首页。|No silent redirect to home.|Без скрытого возврата на главную.
真实运行环境、额度与资源限制由服务端决定，原型不提供实际计算能力。|The server defines runtime, quotas and limits. This prototype provides no actual computing.|Среда, квоты и ограничения определяются сервером. Прототип не предоставляет вычисления.
演示解析失败。原件名称保留，可重试，不伪造结果。|Demo parsing failed. The name is retained; retry is available. No result is invented.|Деморазбор не удался. Имя сохранено, доступен повтор. Результат не выдумывается.
演示解析处理中，请稍候。|Demo parsing in progress. Please wait.|Выполняется демонстрационный разбор. Подождите.
公式仅检验显示，不检验数学正确性。原型没有读取真实文件或音频。|Formulas demonstrate display, not mathematical correctness. No real file or audio was read.|Формулы демонстрируют отображение, а не математическую корректность. Реальные файлы и аудио не читались.
固定演示内容：研究问题、变量、数据来源与约束。|Fixed demo: research question, variables, data sources and constraints.|Фиксированный пример: вопрос исследования, переменные, источники данных и ограничения.
演示解析失败，原件名称保留。|Demo parsing failed; original name retained.|Деморазбор не удался; имя оригинала сохранено.
请换一个关键词。无匹配时不生成虚构引用。|Try another keyword. Missing matches never produce invented citations.|Попробуйте другое слово. При отсутствии совпадений ссылки не выдумываются.
可以更换关键词或范围。未授权内容不会因检索而开放。|Change the keyword or scope. Search never grants access to restricted content.|Измените ключевое слово или область. Поиск не открывает недоступные материалы.
新任务与反馈通知会在这里出现。|New task and feedback notifications appear here.|Здесь появятся уведомления о заданиях и отзывах.
先完成关联项目，再确认并提交成果。|Complete the linked project, then confirm and submit.|Завершите связанный проект, затем подтвердите и сдайте результат.
该版本没有附件。|This version has no attachments.|В этой версии нет вложений.
已提交，等待教师评阅。没有反馈时不生成虚构建议。|Submitted, awaiting review. No suggestions are invented without feedback.|Работа сдана и ожидает проверки. Без отзыва рекомендации не выдумываются.
`);
