from rest_framework.parsers import JSONParser
from rest_framework.exceptions import ParseError
class ObjectJSONParser(JSONParser):
    def parse(self,stream,media_type=None,parser_context=None):
        value=super().parse(stream,media_type,parser_context)
        if not isinstance(value,dict):raise ParseError('请求正文必须是 JSON 对象。')
        return value
