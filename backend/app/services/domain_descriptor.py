"""Validated domain vocabulary shared by Java and relational emitters."""
import copy
import re

JAVA_RESERVED=set('abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while record var yield null true false'.split())
TYPES={'string':'String','str':'String','text':'String','int':'Integer','integer':'Integer','long':'Long','id':'Long',
       'float':'Float','double':'Double','decimal':'java.math.BigDecimal','bigdecimal':'java.math.BigDecimal',
       'boolean':'Boolean','bool':'Boolean','date':'java.time.LocalDate','localdate':'java.time.LocalDate',
       'datetime':'java.time.LocalDateTime','timestamp':'java.time.LocalDateTime','localdatetime':'java.time.LocalDateTime',
       'instant':'java.time.Instant','uuid':'java.util.UUID'}
PLAIN={'NotNull','NotBlank','NotEmpty','Email','Positive','PositiveOrZero','Negative','NegativeOrZero','AssertTrue','AssertFalse','Past','PastOrPresent','Future','FutureOrPresent','Null'}


def java_identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',value) or value in JAVA_RESERVED:
        raise ValueError('Identificador Java inválido: '+str(value))
    return value


def java_type(value):
    if '.' in str(value) and value not in {'java.lang.String','java.lang.Long','java.lang.Integer','java.lang.Float','java.lang.Double','java.lang.Boolean','java.util.UUID','java.math.BigDecimal','java.time.LocalDate','java.time.LocalDateTime','java.time.Instant'}:
        raise ValueError('FQN Java no soportado: '+str(value))
    key=str(value).rsplit('.',1)[-1].lower()
    if key not in TYPES:
        raise ValueError('Tipo Java no soportado: '+str(value))
    return TYPES[key]


def annotation(rule):
    value=str(rule).strip().removeprefix('@')
    if value in PLAIN:
        return '@'+value
    matched=re.fullmatch(r'(Size|Min|Max|DecimalMin|DecimalMax|Digits|Pattern)\((.*)\)',value)
    if not matched:
        raise ValueError('Restricción no soportada o sin parámetros: '+str(rule))
    name,parameters=matched.groups()
    # Parse only Java literals and known named parameters; never interpolate arbitrary Java.
    items=re.findall(r'(\w+)\s*=\s*("(?:[^"\\\r\n]|\\["\\])*"|true|false|-?\d+)',parameters)
    if not items and name in {'Min','Max'} and re.fullmatch(r'-?\d+',parameters.strip()):
        items=[('value',parameters.strip())]
    elif not items:
        raise ValueError('Parámetros de restricción inválidos: '+str(rule))
    else:
        remainder=re.sub(r'(\w+)\s*=\s*("(?:[^"\\\r\n]|\\["\\])*"|true|false|-?\d+)','',parameters).replace(',','').strip()
        if remainder:
            raise ValueError('Parámetros de restricción inválidos: '+str(rule))
    values=dict(items)
    allowed={'Size':{'min','max'},'Min':{'value'},'Max':{'value'},'DecimalMin':{'value','inclusive'},
             'DecimalMax':{'value','inclusive'},'Digits':{'integer','fraction'},'Pattern':{'regexp'}}[name]
    if len(values)!=len(items) or not set(values).issubset(allowed):
        raise ValueError('Parámetro desconocido o repetido: '+str(rule))
    if name in {'Min','Max'} and ('value' not in values or not re.fullmatch(r'-?\d+',values['value'])):
        raise ValueError('Min/Max necesita un entero')
    if name in {'DecimalMin','DecimalMax'} and ('value' not in values or not re.fullmatch(r'"-?\d+(\.\d+)?"',values['value'])):
        raise ValueError('DecimalMin/Max necesita un decimal literal')
    if name in {'Size','Digits'} and any(not re.fullmatch(r'\d+',v) for v in values.values()):
        raise ValueError('Size/Digits necesita enteros no negativos')
    if name=='Digits' and set(values)!={'integer','fraction'}:
        raise ValueError('Digits necesita integer y fraction')
    if name=='Size' and int(values.get('min','0'))>int(values.get('max','2147483647')):
        raise ValueError('Size min supera max')
    if 'inclusive' in values and values['inclusive'] not in {'true','false'}:
        raise ValueError('inclusive debe ser booleano')
    if name=='Pattern' and not values.get('regexp','').startswith('"'):
        raise ValueError('Pattern necesita un regexp literal')
    return '@'+name+'('+', '.join(key+' = '+value for key,value in items)+')'


def constraints(attribute):
    values=[]
    kind=java_type(attribute.get('type','String'))
    if attribute.get('required',False) or not attribute.get('nullable',True):
        values.append('@NotBlank' if kind=='String' else '@NotNull')
    for rule in attribute.get('validationRules',[]):
        validated=annotation(rule)
        name=validated[1:].split('(')[0]
        if name in {'Email','NotBlank','Pattern'} and kind!='String':
            raise ValueError('Restricción de texto aplicada a '+kind)
        if name in {'Positive','PositiveOrZero','Negative','NegativeOrZero','Min','Max','DecimalMin','DecimalMax','Digits'} and kind not in {'Integer','Long','Float','Double','java.math.BigDecimal'}:
            raise ValueError('Restricción numérica aplicada a '+kind)
        if validated not in values:
            values.append(validated)
    return values


def identifier(entity):
    attributes=entity.get('attributes',[])
    declared=[item for item in attributes if item.get('isPrimaryKey') or item.get('is_identifier')]
    if len(declared)>1:
        raise ValueError('Claves compuestas requieren una implementación explícita')
    attribute=declared[0] if declared else next((item for item in attributes if item.get('name')=='id'),{'name':'id','type':'Long'})
    kind=java_type(attribute.get('type','Long'))
    if kind not in {'Long','Integer','String','java.util.UUID'}:
        raise ValueError('Tipo de clave primaria no soportado: '+kind)
    return java_identifier(attribute['name']),kind


def normalize_blueprint(blueprint):
    result=copy.deepcopy(blueprint)
    package=result.get('packageName') or result.get('package_name') or 'com.corp.service'
    if not isinstance(package,str) or any(not part or java_identifier(part)!=part for part in package.split('.')):
        raise ValueError('Paquete Java inválido')
    result['packageName']=package
    entities=result.get('entities',[])
    names=set();tables=set()
    for entity in entities:
        name=java_identifier(entity['name'])
        table=entity.get('tableName') or entity.get('table_name') or name.lower()+'s'
        java_identifier(table)
        if name in names or table in tables:
            raise ValueError('Entidad o tabla duplicada')
        names.add(name);tables.add(table);entity['tableName']=table
        id_name,id_type=identifier(entity)
        attributes=entity.get('attributes',[])
        if not any(item.get('name')==id_name for item in attributes):
            attributes.insert(0,{'name':id_name,'type':id_type,'isPrimaryKey':True,'nullable':False})
        seen=set();columns=set()
        for item in attributes:
            field=java_identifier(item['name'])
            if field in seen:
                raise ValueError('Atributo duplicado')
            seen.add(field)
            java_type(item.get('type','String'))
            column=item.get('columnName') or re.sub(r'(?<!^)(?=[A-Z])','_',field).lower()
            java_identifier(column)
            if column.lower() in columns: raise ValueError('Columna SQL duplicada')
            columns.add(column.lower())
            if field==id_name:
                item['isPrimaryKey']=True
            constraints(item)
    by_name={entity['name']:entity for entity in entities}
    for entity in entities:
        for item in entity.get('attributes',[]):
            target_name=item.get('referencesEntity')
            if not target_name:
                if item.get('referencesAttribute'):
                    raise ValueError('Una referencia necesita entidad destino')
                continue
            if item.get('isPrimaryKey'):
                raise ValueError('Una clave primaria compartida requiere implementación explícita')
            target=by_name.get(target_name)
            if target is None:
                raise ValueError('Entidad FK inexistente: '+str(target_name))
            target_id,target_type=identifier(target)
            if item.get('referencesAttribute') not in (None,target_id):
                raise ValueError('La referencia debe apuntar a la clave primaria destino')
            if java_type(item.get('type','String'))!=target_type:
                raise ValueError('Tipo FK incompatible con la clave primaria destino')
            item['referencesAttribute']=target_id
            property_name=item['name']+'Reference'
            if property_name in {attribute['name'] for attribute in entity['attributes']}:
                raise ValueError('Nombre de propiedad FK en conflicto: '+property_name)
    return result


def sample_expression(attribute):
    kind=java_type(attribute.get('type','String'))
    if kind=='String':
        return '"user@example.com"' if any('Email' in rule for rule in attribute.get('validationRules',[])) else '"sample"'
    return {'Long':'1L','Integer':'1','Float':'1.5f','Double':'1.5','java.math.BigDecimal':'new java.math.BigDecimal("1.00")',
        'Boolean':'true','java.time.LocalDate':'java.time.LocalDate.of(2024, 1, 1)',
        'java.time.LocalDateTime':'java.time.LocalDateTime.of(2024, 1, 1, 12, 0)',
        'java.time.Instant':'java.time.Instant.parse("2024-01-01T12:00:00Z")',
        'java.util.UUID':'java.util.UUID.fromString("00000000-0000-0000-0000-000000000001")'}[kind]
