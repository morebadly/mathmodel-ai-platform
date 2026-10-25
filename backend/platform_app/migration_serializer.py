"""Django JSON fixture with lossless datetime precision for portable migrations."""
import datetime
from django.core.serializers.json import Serializer as JSONSerializer,Deserializer,DjangoJSONEncoder

class FullPrecisionEncoder(DjangoJSONEncoder):
    def default(self,value):
        if isinstance(value,datetime.datetime):return value.isoformat()
        if isinstance(value,datetime.time) and value.tzinfo is None:return value.isoformat()
        return super().default(value)

class Serializer(JSONSerializer):
    def _init_options(self):super()._init_options();self.json_kwargs['cls']=FullPrecisionEncoder
