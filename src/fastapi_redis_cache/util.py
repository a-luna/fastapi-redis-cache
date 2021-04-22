import json
from datetime import date, datetime
from decimal import Decimal

from dateutil import parser

DATETIME_AWARE = "%m/%d/%Y %I:%M:%S %p %z"
DATE_ONLY = "%m/%d/%Y"

SERIALIZE_OBJ_MAP = {
    str(datetime): parser.parse,
    str(date): parser.parse,
    str(Decimal): Decimal,
}


class BetterJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return {"val": obj.strftime(DATETIME_AWARE), "_spec_type": str(datetime)}
        elif isinstance(obj, date):
            return {"val": obj.strftime(DATE_ONLY), "_spec_type": str(date)}
        elif isinstance(obj, Decimal):
            return {"val": str(obj), "_spec_type": str(Decimal)}
        else:
            return super().default(obj)


def object_hook(obj):
    if "_spec_type" not in obj:
        return obj
    _spec_type = obj["_spec_type"]
    if _spec_type not in SERIALIZE_OBJ_MAP:
        raise TypeError(f'"{obj["val"]}" (type: {_spec_type}) is not JSON serializable')
    return SERIALIZE_OBJ_MAP[_spec_type](obj["val"])


def serialize_json(json_dict):
    return json.dumps(json_dict, cls=BetterJsonEncoder)


def deserialize_json(json_str):
    return json.loads(json_str, object_hook=object_hook)
