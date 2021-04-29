import json
from datetime import date, datetime
from decimal import Decimal

from dateutil import parser

DATETIME_AWARE = "%m/%d/%Y %I:%M:%S %p %z"
DATE_ONLY = "%m/%d/%Y"

ONE_HOUR_IN_SECONDS = 3600
ONE_DAY_IN_SECONDS = ONE_HOUR_IN_SECONDS * 24
ONE_WEEK_IN_SECONDS = ONE_DAY_IN_SECONDS * 7
ONE_MONTH_IN_SECONDS = ONE_DAY_IN_SECONDS * 30
ONE_YEAR_IN_SECONDS = ONE_DAY_IN_SECONDS * 365

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
        else:  # pragma: no cover
            return super().default(obj)


def object_hook(obj):
    if "_spec_type" not in obj:
        return obj
    _spec_type = obj["_spec_type"]
    if _spec_type not in SERIALIZE_OBJ_MAP:  # pragma: no cover
        raise TypeError(f'"{obj["val"]}" (type: {_spec_type}) is not JSON serializable')
    return SERIALIZE_OBJ_MAP[_spec_type](obj["val"])


def serialize_json(json_dict):
    return json.dumps(json_dict, cls=BetterJsonEncoder)


def deserialize_json(json_str):
    return json.loads(json_str, object_hook=object_hook)
