"""Shared identifier information for the native Java generators."""
def identifier(entity):
    attributes = entity.get('attributes', [])
    declared = [item for item in attributes if item.get('isPrimaryKey') or item.get('is_identifier')]
    if len(declared) > 1:
        raise ValueError('Composite primary keys require an explicit implementation')
    attribute = declared[0] if declared else next((item for item in attributes if item.get('name') == 'id'), {'name': 'id', 'type': 'Long'})
    value_type = str(attribute.get('type', 'Long')).lower()
    types = {'uuid': 'java.util.UUID', 'string': 'String', 'str': 'String', 'long': 'Long', 'id': 'Long', 'integer': 'Integer', 'int': 'Integer'}
    if value_type not in types:
        raise ValueError('Unsupported primary key type: ' + value_type)
    return attribute.get('name', 'id'), types[value_type]
