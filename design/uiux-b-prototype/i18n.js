'use strict';
const L10N=window.L10N={dict:{},original:new WeakMap(),attrs:new WeakMap(),missing:new Set()};
L10N.add=text=>{for(const line of text.trim().split('\n')){const [zh,en,ru]=line.split('|');if(zh&&en&&ru)L10N.dict[zh]=[en,ru]}};
L10N.add(`
跳至主要内容|Skip to content|Перейти к содержимому
双端原型 · 阶段 4 与 5|Student & teacher prototype · Stages 4–5|Прототип для студентов и преподавателей · Этапы 4–5
仅演示数据 · 不连接正式服务|Demo data · No live services|Демоданные · Без подключения к рабочим службам
查看状态|Review state|Состояние для проверки
正常|Normal|Обычное
空白|Empty|Пустое
加载中|Loading|Загрузка
加载失败|Loading failed|Ошибка загрузки
无权限|No access|Нет доступа
保存失败|Save failed|Ошибка сохранения
重置演示|Reset demo|Сбросить демо
深圳北理莫斯科大学|Shenzhen MSU–BIT University|Университет МГУ-ППИ в Шэньчжэне
数学建模协会|Mathematical Modeling Association|Ассоциация математического моделирования
深圳北理莫斯科大学 · 数学建模协会|SMBU · Mathematical Modeling Association|МГУ-ППИ · Ассоциация математического моделирования
教师端 · 演示账号|Teacher · Demo account|Преподаватель · Демоаккаунт
学生端 · 演示账号|Student · Demo account|Студент · Демоаккаунт
教学管理|Teaching|Учебная работа
教学总览|Teaching overview|Обзор учебной работы
我的团队|My teams|Мои команды
训练任务|Learning tasks|Учебные задания
提交与反馈|Submissions & feedback|Работы и отзывы
学习监督|Task progress|Ход выполнения заданий
邮箱提醒|Email reminders|Напоминания по почте
任务与成绩对照|Tasks & grades|Задания и оценки
成绩导入|Import grades|Импорт оценок
教学资料与评阅|Resources & review|Материалы и проверка
论文评阅|Paper review|Проверка статей
知识中心|Knowledge center|Центр знаний
团队协作|Teamwork|Командная работа
团队聊天|Team chat|Чат команды
资料与工具|Resources & tools|Материалы и инструменты
代码运行|Code runner|Запуск кода
解析与公式|Parsing & formulas|Разбор и формулы
引用检索|Source search|Поиск источников
账号与设置|Account & settings|Аккаунт и настройки
我的账号|My account|Мой аккаунт
教师端|Teacher|Преподаватель
学生端|Student|Студент
中文|Chinese|Китайский
英文|English|Английский
俄文|Russian|Русский
亮色|Light|Светлая
暗色|Dark|Тёмная
跟随系统|System|Системная
把指导落到每一次进步|Turn guidance into progress|Помогайте двигаться вперёд
发布训练任务|Publish a task|Опубликовать задание
管理团队|Manage teams|Управление командами
待评阅|Awaiting review|Ожидает проверки
退回后待跟进|Revision follow-up|Контроль доработки
所带团队|Your teams|Ваши команды
授权学生|Students in scope|Доступные студенты
教师待办|Teaching to-do|Задачи преподавателя
排序|Sort by|Сортировка
可解释优先级|Explained priority|Приоритет с пояснением
提交时间先后|Submission time|Время сдачи
临近截止（小时）|Due soon threshold (hours)|Порог приближения срока (часы)
学生与任务|Student & task|Студент и задание
版本与提交时间|Version & submission time|Версия и время сдачи
状态与依据|Status & reason|Статус и основание
操作|Actions|Действия
退回修改|Revision requested|На доработке
反馈后待跟进|Follow up after feedback|Контроль после отзыва
进入评阅|Review submission|Проверить работу
校园概念装饰 · 数据仅供交互演示|Concept campus artwork · Demo data|Концептуальный декор кампуса · Демоданные
学生模块导航|Student navigation|Навигация студента
教师模块导航|Teacher navigation|Навигация преподавателя
切换演示角色|Switch demo role|Сменить роль
界面语言|Interface language|Язык интерфейса
外观|Appearance|Оформление
关闭|Close|Закрыть
创建团队|Create team|Создать команду
管理成员|Manage members|Участники
创建任务|Create task|Создать задание
已发布|Published|Опубликовано
草稿|Draft|Черновик
查看任务|View task|Открыть задание
编辑|Edit|Редактировать
全部|All|Все
已评阅|Reviewed|Проверено
制定任务跟进计划|Create follow-up plan|Создать план контроля
学生任务进展|Student task progress|Прогресс по заданиям
学生|Student|Студент
任务相关记录|Task records|Записи по заданиям
提交快照阶段|Submitted stages|Этапы сданной работы
查看证据|View evidence|Посмотреть основание
暂无任务提交|No task submissions|Нет сданных работ
数据不足|Insufficient data|Недостаточно данных
查看团队|View team|Открыть команду
任务跟进计划|Follow-up plans|Планы контроля
准备任务提醒|Prepare reminder|Подготовить напоминание
还没有提醒记录|No reminders yet|Напоминаний пока нет
成绩与任务记录|Grades & task records|Оценки и задания
考核与日期|Assessment & date|Работа и дата
得分|Score|Баллы
依据|Evidence|Основание
下载CSV模板|Download CSV template|Скачать шаблон CSV
CSV内容|CSV content|Содержимое CSV
预览并校验|Preview & validate|Просмотр и проверка
取消|Cancel|Отмена
暂无有权评阅的论文|No papers available for review|Нет доступных для проверки статей
查看训练提交|View task submissions|Открыть сданные работы
添加教学资料|Add teaching resource|Добавить учебный материал
公共|Public|Общие
团队|Team|Командные
个人|Personal|Личные
教师个人|Teacher-private|Личные материалы преподавателя
阅读与共享|Read & share|Читать и поделиться
消息|Message|Сообщение
发送演示消息|Send demo message|Отправить демосообщение
配置演示运行|Configure demo run|Настроить демозапуск
没有教师运行记录|No teacher runs yet|Запусков пока нет
开始演示|Start demo|Начать демонстрацию
添加演示解析|Add parsing demo|Добавить демонстрацию разбора
没有教师解析记录|No teacher parsing records|Нет записей разбора
检索来源|Search sources|Найти источники
先输入关键词|Enter a keyword first|Введите ключевое слово
输入关键词|Enter keywords|Введите ключевые слова
检索关键词|Search keywords|Ключевые слова поиска
退出教师演示账号|Sign out of teacher demo|Выйти из демоаккаунта преподавателя
教师资料|Teacher profile|Профиль преподавателя
显示名称|Display name|Отображаемое имя
演示邮箱|Demo email|Демонстрационная почта
保存演示资料|Save demo profile|Сохранить демопрофиль
我的学习|My learning|Моя учёба
学习工作台|Learning dashboard|Учебная панель
训练中心|Training center|Центр практики
我的提交与反馈|My submissions & feedback|Мои работы и отзывы
模拟竞赛|Mock competition|Тренировочное соревнование
成长档案|Progress record|История прогресса
建模与写作|Modeling & writing|Моделирование и текст
建模工作台|Modeling workspace|Рабочее пространство
AI 建模导师|AI modeling tutor|ИИ-наставник по моделированию
论文实验室|Paper lab|Лаборатория статей
写作工作室|Writing studio|Студия текстов
团队通知|Team notifications|Уведомления команды
让思考继续发生|Keep your ideas moving|Продолжайте развивать идеи
新建建模项目|New modeling project|Новый проект моделирования
我的项目|My projects|Мои проекты
教师任务|Teacher task|Задание преподавателя
待查看通知|Unread notifications|Непрочитанные уведомления
待修改提交|Revisions needed|Работы на доработке
当前任务|Current task|Текущее задание
全部任务|All tasks|Все задания
任务详情|Task details|Описание задания
开始 / 继续|Start / Continue|Начать / Продолжить
教师反馈|Teacher feedback|Отзыв преподавателя
查看反馈与修改清单|View feedback & checklist|Открыть отзыв и список исправлений
最近项目|Recent projects|Недавние проекты
关联任务|Linked task|Связанное задание
继续项目|Continue project|Продолжить проект
导出记录|Export record|Экспортировать запись
自主项目|Independent project|Самостоятельный проект
创建个人练习|Create personal practice|Создать личную практику
个人练习|Personal practice|Личная практика
前往训练中心|Go to training center|Перейти в центр практики
任务|Task|Задание
版本与时间|Version & time|Версия и время
状态|Status|Статус
查看详情|View details|Подробнее
配置模拟竞赛|Configure mock competition|Настроить соревнование
开启一次模拟训练|Begin a practice session|Начать тренировку
创建模拟竞赛|Create mock competition|Создать соревнование
导出我的成长记录|Export my progress|Экспортировать прогресс
个人项目|Personal projects|Личные проекты
手动完成阶段|Stages marked complete|Этапы, отмеченные выполненными
已提交版本|Submitted versions|Сданные версии
教师已评阅|Teacher-reviewed|Проверено преподавателем
项目过程|Project history|История проекта
查看|View|Открыть
能力评价依据|Assessment evidence|Основания оценки
反馈与修订|Feedback & revisions|Отзывы и доработки
回看|Revisit|Пересмотреть
本机原型操作记录|Local prototype activity|Действия в прототипе
新建项目|New project|Новый проект
开始新对话|New conversation|Новый диалог
历史对话|Conversation history|История диалогов
指导模式|Guidance mode|Режим помощи
基础解释|Basic explanation|Базовое объяснение
方法探索|Explore methods|Поиск подходов
分步指导|Step-by-step guidance|Пошаговая помощь
深度研究|Deeper exploration|Углублённое исследование
问题与当前思路|Question & current ideas|Вопрос и текущие идеи
查看演示回复|Show demo response|Показать демоответ
保存问题不生成回复|Save question without a response|Сохранить вопрос без ответа
模拟生成失败|Simulate generation failure|Смоделировать ошибку генерации
添加演示论文|Add demo paper|Добавить демостатью
个人原件|Private original|Личный оригинал
阅读与批注|Read & annotate|Читать и комментировать
创建关联文稿|Create linked draft|Создать связанный текст
新建文稿|New draft|Новый текст
关联论文|Linked paper|Связанная статья
继续写作|Continue writing|Продолжить работу над текстом
导出|Export|Экспорт
添加个人资料|Add personal resource|Добавить личный материал
全部范围|All scopes|Все области доступа
搜索|Search|Поиск
建模方法|Modeling methods|Методы моделирования
阅读与引用|Read & cite|Читать и цитировать
收藏|Save favorite|В избранное
已收藏|Favorited|В избранном
数据资料|Data resources|Данные
教学训练|Teaching & practice|Обучение и практика
搜索方法、案例或关键词|Search methods, cases or keywords|Найти метод, пример или слово
搜索资料|Search resources|Поиск материалов
资料范围|Resource scope|Область доступа
先输入检索关键词|Enter search keywords first|Сначала введите ключевые слова
浏览知识中心|Browse knowledge center|Открыть центр знаний
例如：约束 或 数据|For example: constraints or data|Например: ограничения или данные
引用关键词|Source keywords|Ключевые слова источников
添加演示解析任务|Add demo parsing task|Добавить демозадачу разбора
还没有解析任务|No parsing tasks yet|Задач разбора пока нет
添加演示任务|Add demo task|Добавить демозадачу
还没有运行记录|No runs yet|Запусков пока нет
全部标为已读|Mark all as read|Отметить всё прочитанным
全部通知|All notifications|Все уведомления
未读通知|Unread notifications|Непрочитанные уведомления
查看通知|View notification|Открыть уведомление
查看成员|View members|Участники
关联教学任务：|Linked teaching tasks:|Связанные учебные задания:
演示附件名称（不上传）|Demo attachment name (no upload)|Имя демовложения (без загрузки)
发送|Send|Отправить
退出演示账号|Sign out of demo|Выйти из демоаккаунта
演示账号资料|Demo profile|Демонстрационный профиль
保存个人资料|Save profile|Сохранить профиль
演示重新验证|Repeat demo verification|Повторить демопроверку
语言与外观|Language & appearance|Язык и оформление
我的教学团队|My teaching teams|Мои учебные команды
进入聊天|Open chat|Открыть чат
本机演示数据|Local demo data|Локальные демоданные
导出演示数据|Export demo data|Экспортировать демоданные
重置原型演示|Reset prototype data|Сбросить данные прототипа
教师账号|Teacher account|Аккаунт преподавателя
教师登录|Teacher sign-in|Вход преподавателя
管理员入口|Administrator entry|Вход администратора
演示密码|Demo password|Демонстрационный пароль
进入教师端|Enter teacher area|Открыть кабинет преподавателя
教师注册|Teacher registration|Регистрация преподавателя
找回演示密码|Recover demo password|Восстановить демопароль
教师演示密钥|Demo teacher key|Демонстрационный ключ преподавателя
下一步 验证邮箱|Next: verify email|Далее: проверить почту
演示验证码|Demo verification code|Демонстрационный код
完成验证|Complete verification|Завершить проверку
继续重设|Continue to reset|Продолжить сброс
演示码123456|Demo code: 123456|Демонстрационный код: 123456
新演示密码|New demo password|Новый демопароль
确认密码|Confirm password|Подтвердить пароль
完成演示重设|Complete demo reset|Завершить демонстрационный сброс
学生账号|Student account|Аккаунт студента
登录后继续个人学习|Sign in to continue learning|Войдите, чтобы продолжить учёбу
学生登录|Student sign-in|Вход студента
教师入口说明|Teacher sign-in|Вход преподавателя
进入学生工作区|Enter student workspace|Открыть кабинет студента
注册演示账号|Register demo account|Зарегистрировать демоаккаунт
注册与邮箱验证|Registration & email verification|Регистрация и проверка почты
验证演示邮箱|Verify demo email|Проверить демонстрационную почту
完成演示验证|Complete demo verification|Завершить демонстрационную проверку
重新显示演示验证码|Show demo code again|Снова показать демокод
找回与重设|Recovery & reset|Восстановление и сброс
继续验证|Continue verification|Продолжить проверку
重设演示密码|Reset demo password|Сбросить демопароль
确认演示密码|Confirm demo password|Подтвердить демопароль
返回任务|Back to tasks|К заданиям
编辑任务|Edit task|Редактировать задание
要求与评价|Requirements & assessment|Требования и оценивание
评价依据|Assessment criteria|Критерии оценивания
变更记录|Change history|История изменений
返回提交列表|Back to submissions|К списку работ
学生提交快照|Student submission snapshot|Снимок сданной работы
问题理解|Problem understanding|Понимание задачи
数据探索|Data exploration|Исследование данных
模型设计|Model design|Проектирование модели
算法实现|Algorithm implementation|Реализация алгоритма
实验验证|Experimental validation|Экспериментальная проверка
论文撰写|Paper writing|Написание статьи
论文评价|Paper evaluation|Оценка статьи
迭代优化|Iterative refinement|Итерационное улучшение
本次提交附件|Attachments in this submission|Вложения этой работы
已发布反馈历史|Published feedback history|История опубликованных отзывов
评阅与反馈|Review & feedback|Проверка и отзыв
教师原评语|Teacher's original comment|Исходный отзыв преподавателя
必须修改（每行一项）|Required changes (one per line)|Обязательные исправления (по одному в строке)
建议优化（每行一项）|Suggestions (one per line)|Рекомендации (по одной в строке)
关联阶段（可选）|Linked stage (optional)|Связанный этап (необязательно)
不关联具体阶段|No specific stage|Без привязки к этапу
评阅处理|Review outcome|Результат проверки
已评阅，不自动表示通过|Reviewed; not automatically passed|Проверено; не означает зачёта
退回时的独立重交截止（北京时间）|Revision deadline (Beijing time)|Срок повторной сдачи (пекинское время)
得分（可空）|Score (optional)|Баллы (необязательно)
满分（填得分时必填）|Maximum score (required with score)|Максимальный балл (обязателен при оценке)
考核名称|Assessment name|Название контрольной работы
保存教师草稿|Save private review draft|Сохранить черновик отзыва
预览反馈再发布|Preview feedback before publishing|Проверить отзыв перед публикацией
成员与权限|Members & access|Участники и доступ
邀请演示学生|Invite demo student|Пригласить демостудента
移出团队|Remove from team|Удалить из команды
待加入邀请|Pending invitations|Ожидающие приглашения
发布团队任务|Publish team task|Опубликовать задание команды
返回知识中心|Back to knowledge center|В центр знаний
复制来源引用|Copy source citation|Скопировать ссылку на источник
返回训练中心|Back to training center|В центр практики
开始 / 关联项目|Start / Link project|Начать / Связать проект
任务要求|Task requirements|Требования задания
时间与提交规则|Deadlines & submission rules|Сроки и правила сдачи
关联项目|Linked project|Связанный проект
继续|Continue|Продолжить
查看提交与反馈|View submission & feedback|Открыть работу и отзыв
回到项目|Back to project|К проекту
提交快照 · 不随项目编辑改变|Submission snapshot · Unchanged by project edits|Снимок работы · Не меняется при редактировании проекта
本次提交|This submission|Эта работа
本阶段未填写|No content for this stage|Этап не заполнен
提交附件|Submitted attachments|Сданные вложения
必须修改|Required change|Обязательное исправление
加入修改清单|Add to my checklist|Добавить в мой список исправлений
定位项目阶段|Go to project stage|Перейти к этапу проекта
建议优化|Suggestion|Рекомендация
我的修改清单|My revision checklist|Мой список исправлений
修改后重新提交|Resubmit after revision|Сдать повторно после доработки
历史版本|Version history|История версий
返回项目|Back to project|К проекту
编辑信息|Edit details|Редактировать сведения
已手动完成|Marked complete|Отмечено выполненным
阶段笔记|Stage notes|Заметки этапа
保存笔记|Save notes|Сохранить заметки
取消完成标记|Unmark completion|Снять отметку о выполнении
标记完成|Mark complete|Отметить выполненным
项目附件|Project attachments|Вложения проекта
关联已有资料|Attach existing resource|Приложить существующий материал
查看任务与提交要求|View task & submission rules|Открыть задание и правила сдачи
提交成果快照|Submit result snapshot|Сдать снимок результата
返回论文列表|Back to papers|К списку статей
关联到项目|Attach to project|Приложить к проекту
创建 / 打开关联文稿|Create / Open linked draft|Создать / Открыть связанный текст
论文原件|Original paper|Оригинал статьи
下载演示原文文本|Download demo original text|Скачать демонстрационный исходный текст
评价与批注|Evaluation & annotations|Оценка и комментарии
人工记录|Manual records|Ручные записи
规范检查|Format checks|Проверка оформления
AI建议|AI suggestions|Подсказки ИИ
记录人工评价|Record manual evaluation|Записать ручную оценку
添加个人批注|Add private annotation|Добавить личный комментарий
完整填写的维度|Completed dimensions|Заполненные критерии
返回文稿列表|Back to drafts|К списку текстов
导出文稿|Export draft|Экспортировать текст
正文编辑|Text editor|Редактор текста
正文|Text|Текст
保存草稿|Save draft|Сохранить черновик
保存命名版本|Save named version|Сохранить именованную версию
来源与建议|Sources & suggestions|Источники и рекомендации
查看保留的论文原件|View preserved original|Открыть сохранённый оригинал
查看演示AI建议|View demo AI suggestions|Открыть демоподсказки ИИ
命名版本|Named versions|Именованные версии
收藏资料|Favorite resource|В избранное
公共资料|Public resources|Общие материалы
知识条目|Knowledge entry|Статья базы знаний
引用到AI提问|Cite in AI question|Добавить ссылку в вопрос ИИ
复制引用|Copy citation|Скопировать ссылку
创建教学团队|Create teaching team|Создать учебную команду
团队名称|Team name|Название команды
演示学生|Demo student|Демонстрационный студент
创建邀请|Create invitation|Создать приглашение
编辑训练任务|Edit learning task|Редактировать учебное задание
任务标题|Task title|Название задания
所属团队|Assigned team|Команда задания
截止时间（北京时间）|Deadline (Beijing time)|Срок (пекинское время)
补交规则|Late submission rule|Правило поздней сдачи
允许补交并标记|Allow and mark late|Разрешить и отметить просрочку
截止后拒收|Reject after deadline|Не принимать после срока
变更原因（将通知学生）|Reason for change (students notified)|Причина изменения (студенты получат уведомление)
保存并预览|Save & preview|Сохранить и проверить
新建训练任务|New learning task|Новое учебное задание
计划标题|Plan title|Название плана
跟进条件|Follow-up condition|Условие контроля
未提交|Not submitted|Не сдано
待修改|Revision pending|Ожидает доработки
临近截止|Due soon|Скоро срок
保存计划|Save plan|Сохранить план
主题|Subject|Тема
提醒正文|Reminder body|Текст напоминания
演示收件人|Demo recipients|Демонстрационные получатели
已验证|Verified|Подтверждено
未验证|Unverified|Не подтверждено
同意接收|Opted in|Согласие получено
未同意接收|Not opted in|Согласия нет
执行方式|Execution mode|Способ выполнения
手动确认后模拟发送|Simulate sending after confirmation|Смоделировать отправку после подтверждения
计划模拟发送|Schedule simulated sending|Запланировать демонстрационную отправку
计划时间（北京时间）|Scheduled time (Beijing time)|Время выполнения (пекинское время)
预览收件结果|Preview recipient results|Проверить результаты по получателям
添加教师个人资料|Add teacher-private resource|Добавить личный материал преподавателя
资料名称|Resource name|Название материала
来源|Source|Источник
演示正文|Demo text|Демонстрационный текст
保存教学资料|Save teaching resource|Сохранить учебный материал
教师演示运行|Teacher demo run|Демозапуск преподавателя
运行名称|Run name|Название запуска
代码（不实际执行）|Code (not executed)|Код (не выполняется)
演示状态|Demo state|Демонстрационное состояние
成功|Success|Успешно
失败|Failed|Ошибка
生成演示记录|Create demo record|Создать демонстрационную запись
教师演示解析|Teacher parsing demo|Демонстрация разбора для преподавателя
文件名称|File name|Имя файла
结果|Result|Результат
保存演示记录|Save demo record|Сохранить демонстрационную запись
创建建模项目|Create modeling project|Создать проект моделирования
项目名称|Project name|Название проекта
问题描述（可后补）|Problem description (optional)|Описание задачи (можно добавить позже)
保存项目|Save project|Сохранить проект
竞赛名称|Competition name|Название соревнования
参与方式|Participation mode|Формат участия
时长（分钟）|Duration (minutes)|Продолжительность (минуты)
AI规则|AI policy|Правила использования ИИ
关闭AI|AI disabled|ИИ отключён
仅基础知识查询|Basic knowledge only|Только базовые знания
开放辅助|AI assistance allowed|Помощь ИИ разрешена
题目、要求与规则|Problem, requirements & rules|Задача, требования и правила
创建竞赛|Create competition|Создать соревнование
论文名称|Paper title|Название статьи
原件名称|Original file name|Имя оригинального файла
演示解析状态|Demo parsing state|Состояние демонстрационного разбора
解析成功（示例正文）|Parsing success (sample text)|Успешный разбор (пример текста)
解析失败|Parsing failed|Ошибка разбора
添加论文|Add paper|Добавить статью
新建写作文稿|New writing draft|Создать текст
文稿标题|Draft title|Название текста
正文语言|Text language|Язык текста
初始正文（可空）|Initial text (optional)|Начальный текст (необязательно)
创建文稿|Create draft|Создать текст
添加个人演示资料|Add personal demo resource|Добавить личный демоматериал
名称|Name|Название
类别|Category|Категория
论文写作|Paper writing|Написание статей
来源说明|Source description|Описание источника
添加资料|Add resource|Добавить материал
演示环境|Demo environment|Демонстрационная среда
Python · 演示环境|Python · Demo environment|Python · Демонстрационная среда
代码（不会执行）|Code (will not execute)|Код (не будет выполнен)
演示结果|Demo result|Демонстрационный результат
成功结果|Successful result|Успешный результат
运行错误|Runtime error|Ошибка выполнения
开始演示任务|Start demo task|Запустить демозадачу
类型|Type|Тип
文档|Document|Документ
图片OCR|Image OCR|OCR изображения
音频转写|Audio transcription|Расшифровка аудио
完成|Complete|Готово
开始演示解析|Start demo parsing|Начать демонстрационный разбор
保存|Save|Сохранить
重试|Retry|Повторить
返回首页|Back to home|На главную
返回列表|Back to list|К списку
未设置|Not set|Не задано
补交|Late submission|Поздняя сдача
未填写|Not filled|Не заполнено
已取消|Cancelled|Отменено
处理中|Processing|Обработка
排队中|Queued|В очереди
运行中|Running|Выполняется
演示成功|Demo success|Успешная демонстрация
演示失败|Demo failed|Демонстрационная ошибка
重试演示解析|Retry demo parsing|Повторить демонстрационный разбор
演示解析完成|Demo parsing complete|Демонстрационный разбор завершён
下载演示结果|Download demo result|Скачать деморезультат
查看结果|View result|Открыть результат
查看来源|View source|Открыть источник
共享到团队|Share with team|Поделиться с командой
确认共享|Confirm sharing|Подтвердить доступ
接受团队邀请|Accept team invitation|Принять приглашение в команду
团队邀请|Team invitations|Приглашения в команды
暂无访问权限|Access unavailable|Нет доступа
记录不可访问|Record unavailable|Запись недоступна
页面不存在|Page not found|Страница не найдена
返回正常演示|Return to normal demo|Вернуться к обычной демонстрации
需要验证教师身份|Teacher verification required|Требуется проверка преподавателя
已过截止，需跟进|Overdue; follow up|Срок прошёл; нужен контроль
接近截止|Approaching deadline|Приближается срок
收到修改后重交|Revised work resubmitted|Доработанная работа сдана повторно
按等待时间处理|Process by waiting time|Обрабатывать по времени ожидания
预览反馈|Preview feedback|Предпросмотр отзыва
确认发布反馈|Publish feedback|Опубликовать отзыв
确认发布并通知|Publish & notify|Опубликовать и уведомить
返回修改|Back to editing|Вернуться к редактированию
返回检查|Review again|Проверить ещё раз
确认发布后变更|Confirm published-task changes|Подтвердить изменения задания
确认变更并通知|Confirm changes & notify|Подтвердить изменения и уведомить
学生视角发布预览|Student-view preview|Предпросмотр для студента
确认本批导入|Import this batch|Импортировать пакет
取消预览|Cancel preview|Отменить предпросмотр
导入预览|Import preview|Предпросмотр импорта
确认移出团队|Confirm removal from team|Подтвердить удаление из команды
确认移出|Remove member|Удалить участника
未知学生|Unknown student|Неизвестный студент
没有匹配提交|No matching submissions|Нет подходящих работ
没有附件|No attachments|Нет вложений
尚未发布教师反馈|No teacher feedback published|Отзыв ещё не опубликован
仅任务记录|Task records only|Только записи по заданиям
已计划|Scheduled|Запланировано
已处理|Processed|Обработано
执行失败|Execution failed|Ошибка выполнения
模拟发送成功|Simulated sending succeeded|Демонстрационная отправка выполнена
已跳过|Skipped|Пропущено
取消计划|Cancel schedule|Отменить план
关联评阅|Linked review|Связанная проверка
提交附件快照|Submitted attachment snapshot|Снимок сданного вложения
进入对应提交与反馈|Open linked submission & feedback|Открыть связанную работу и отзыв
返回论文评阅|Back to paper review|К проверке статей
阅读提交快照|Read submitted snapshot|Прочитать сданный снимок
确认共享到团队|Confirm team sharing|Подтвердить доступ команды
目标团队|Target team|Команда-получатель
来源引用|Source citation|Ссылка на источник
无匹配来源|No matching sources|Подходящих источников нет
数学建模协会会标原图|Original association logo|Оригинальная эмблема ассоциации
访问权限状态|Access state|Состояние доступа
加载失败状态|Loading-failure state|Ошибка загрузки
暂时无法加载|Temporarily unable to load|Временно не удаётся загрузить
重试加载|Retry loading|Повторить загрузку
正在加载|Loading|Загрузка
正在加载演示内容…|Loading demo content…|Загрузка демосодержимого…
完成本次加载演示|Finish loading demo|Завершить демонстрацию загрузки
空内容状态|Empty-content state|Пустое состояние
这里暂时没有内容|No content here yet|Здесь пока нет содержимого
返回正常内容|Return to content|Вернуться к содержимому
记录访问状态|Record access state|Доступ к записи
记录不存在或已不可访问|Record missing or inaccessible|Запись отсутствует или недоступна
登录后继续|Sign in to continue|Войдите, чтобы продолжить
需要先登录演示账号|Demo sign-in required|Требуется вход в демоаккаунт
进入演示登录|Open demo sign-in|Открыть демонстрационный вход
访客 · 尚未登录|Guest · Signed out|Гость · Вход не выполнен
账号流程|Account flow|Сценарий аккаунта
找不到这个入口|Page unavailable|Страница недоступна
个人备注|Private note|Личная заметка
仅自己可见|Only visible to you|Видно только вам
保存备注|Save note|Сохранить заметку
依据本版本教师反馈|Based on this version's feedback|По отзыву к этой версии
取消运行|Cancel run|Отменить запуск
查看日志与结果|View logs & results|Открыть журнал и результаты
返回运行记录|Back to runs|К списку запусков
运行状态|Run state|Состояние запуска
排队|Queued|В очереди
复制代码重新配置|Copy code & reconfigure|Скопировать код и настроить заново
返回解析任务|Back to parsing tasks|К задачам разбора
解析结果|Parsing result|Результат разбора
演示结果就绪|Demo result ready|Демонстрационный результат готов
解析失败，原件保留|Parsing failed; original retained|Разбор не удался; оригинал сохранён
没有找到匹配来源|No matching sources found|Подходящих источников не найдено
阅读原条目|Read original entry|Прочитать исходную запись
引用到AI问题|Cite in AI question|Добавить ссылку в вопрос ИИ
没有匹配资料|No matching resources|Нет подходящих материалов
清除筛选|Clear filters|Сбросить фильтры
没有匹配通知|No matching notifications|Нет подходящих уведомлений
去训练中心|Open training center|Открыть центр практики
暂无匹配提交|No matching submissions|Нет подходящих работ
未填写修改说明|No revision summary|Описание изменений не заполнено
已读|Read|Прочитано
未读|Unread|Не прочитано
标为已读|Mark as read|Отметить прочитанным
前往关联内容|Open linked content|Открыть связанное содержимое
团队通知详情|Notification details|Описание уведомления
`);
