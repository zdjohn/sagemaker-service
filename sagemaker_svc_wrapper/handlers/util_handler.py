import re
import uuid
import sys
# from dateutils import parser
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from decimal import Decimal
from datetime import datetime

SAGEMAKER_NAMING_PATTERN = '^[a-zA-Z0-9](-*[a-zA-Z0-9])*'

def is_valid_sagemaker_naming(name):
    matched = re.match(SAGEMAKER_NAMING_PATTERN, name)
    if matched:
        return matched.group() == name
    return False

def json_serial(o):
    if isinstance(o, datetime):
        serial = o.strftime('%Y-%m-%dT%H:%M:%S.%f')
    elif isinstance(o, Decimal):
        if o % 1 > 0:
            serial = float(o)
        else:
            serial = int(o)
    elif isinstance(o, uuid.UUID):
        serial = str(o.hex)
    elif isinstance(o, set):
        serial = list(o)
    else:
        serial = o
    return serial


def dynamo_item_json_parser(item):
    if not isinstance(item, dict):
        return json_serial(item)
    for key in item:
        value = item[key]
        if isinstance(value, dict):
            item[key] = dynamo_item_json_parser(value)
        else:
            item[key] = json_serial(item[key])
    return item
