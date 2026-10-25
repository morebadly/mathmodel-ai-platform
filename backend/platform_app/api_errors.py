"""Turn DRF error containers into user-facing text without Python repr output."""
import re


FIELD_LABELS = {'title': '标题', 'name': '名称', 'body': '正文', 'content': '内容', 'text': '文本', 'source': '来源'}
TITLE_LABELS = {'projects': '项目标题', 'papers': '论文标题', 'tasks': '任务标题', 'competitions': '模拟竞赛标题', 'conversations': '对话标题', 'writingDrafts': '文稿标题', 'supervisionPlans': '监督计划标题', 'reminderDrafts': '提醒草稿标题'}
FALLBACK_MESSAGE = '请求未能完成，请检查输入后重试。'
SERVER_ERROR_MESSAGE = '服务暂时无法完成请求，请稍后重试。'


def _field_labels(context):
    labels = dict(FIELD_LABELS)
    request = (context or {}).get('request')
    # Read only DRF's already-parsed cache. Error rendering must not parse a bad
    # body again or include any supplied field values in the response.
    data = getattr(request, '__dict__', {}).get('_full_data')
    if getattr(request, 'path', '').rstrip('/') == '/api/workspace' and isinstance(data, dict):
        changes = data.get('changes')
        if isinstance(changes, dict):
            active = [key for key, rows in changes.items() if isinstance(rows, list) and rows]
            if len(active) == 1:
                labels['title'] = TITLE_LABELS.get(active[0], labels['title'])
    return labels


def error_message(detail, context=None):
    labels = _field_labels(context)
    messages = []

    def collect(value, path=''):
        if isinstance(value, dict):
            for field, child in value.items():
                if not isinstance(field, (str, int)):
                    continue
                field = str(field)
                child_path = path if field == 'non_field_errors' else (path + '.' if path else '') + field
                collect(child, child_path)
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                collect(child, path + f'[{index}]' if isinstance(child, (dict, list, tuple)) else path)
        elif isinstance(value, str) and value.strip():
            message = value.strip()
            invalid_field = re.fullmatch(r'字段无效[：:]\s*([A-Za-z][A-Za-z0-9_]*)', message)
            if invalid_field:
                field = invalid_field.group(1)
                message = labels.get(field, field) + '无效，请检查是否已填写并符合长度要求。'
            if path:
                message = labels.get(path, path) + '：' + message
            if message not in messages:
                messages.append(message)

    collect(detail)
    return '；'.join(messages) or FALLBACK_MESSAGE
