"""Local Kubernetes catalogue; no ingress, registry, or embedded credentials."""
import re
import yaml
from app.services.local_deployment_assets import DATABASE_IMAGES, compose


def manifests(service_name, db_engine='POSTGRESQL', image=None):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', service_name):
        raise ValueError('Nombre Kubernetes invalido (maximo 40 caracteres)')
    engine = db_engine.upper()
    if engine not in DATABASE_IMAGES:
        raise ValueError('Motor Kubernetes no admitido')
    image = image or f'{service_name}:local'
    if not re.fullmatch(r'[a-zA-Z0-9_./:@-]+', image):
        raise ValueError('Imagen local invalida')
    labels = {'app.kubernetes.io/part-of': service_name}
    def resource(kind, name, spec=None, **fields):
        item = {'apiVersion': 'apps/v1' if kind in {'Deployment', 'StatefulSet'} else 'v1',
                'kind': kind, 'metadata': {'name': name, 'labels': labels.copy()}, **fields}
        if spec is not None:
            item['spec'] = spec
        return item
    app_config = compose(service_name, engine)
    app_env = yaml.safe_load(app_config)['services'][service_name]['environment']
    app_env.pop('SPRING_DATASOURCE_PASSWORD', None)
    if engine != 'H2':
        app_env['SPRING_DATASOURCE_URL'] = app_env['SPRING_DATASOURCE_URL'].replace('//db:', f'//{service_name}-db:')
    config = resource('ConfigMap', service_name + '-config', data=app_env)
    app_labels = {**labels, 'app': service_name}
    app = {'name': service_name, 'image': image, 'imagePullPolicy': 'Never',
           'ports': [{'containerPort': 8080, 'name': 'http'}],
           'envFrom': [{'configMapRef': {'name': service_name + '-config'}}],
           'resources': {'requests': {'cpu': '100m', 'memory': '256Mi'},
                         'limits': {'cpu': '1', 'memory': '1Gi'}},
           'volumeMounts': [{'name': 'data', 'mountPath': '/app/data'}]}
    for probe, path in [('startupProbe', '/actuator/health'),
                        ('readinessProbe', '/actuator/health/readiness'),
                        ('livenessProbe', '/actuator/health/liveness')]:
        app[probe] = {'httpGet': {'path': path, 'port': 'http'}, 'periodSeconds': 5,
                      'timeoutSeconds': 3, 'failureThreshold': 60 if probe == 'startupProbe' else 6}
    if engine != 'H2':
        app['env'] = [{'name': 'SPRING_DATASOURCE_PASSWORD', 'valueFrom': {
            'secretKeyRef': {'name': service_name + '-credentials', 'key': 'DB_PASSWORD'}}}]
    deployment = resource('Deployment', service_name, {
        'replicas': 1, 'strategy': {'type': 'Recreate'},
        'selector': {'matchLabels': {'app': service_name}},
        'template': {'metadata': {'labels': app_labels}, 'spec': {
            'securityContext': {'runAsNonRoot': True, 'runAsUser': 10001,
                                'runAsGroup': 10001, 'fsGroup': 10001},
            'containers': [app], 'volumes': [{'name': 'data', 'persistentVolumeClaim': {
                'claimName': service_name + '-appdata'}}]}}})
    service = resource('Service', service_name + '-service', {
        'type': 'ClusterIP', 'selector': {'app': service_name},
        'ports': [{'name': 'http', 'port': 8080, 'targetPort': 'http'}]})
    def pvc(name):
        return resource('PersistentVolumeClaim', name, {
            'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': '1Gi'}}})
    result = {'deployment.yaml': deployment, 'service.yaml': service,
              'configmap.yaml': config, 'app-pvc.yaml': pvc(service_name + '-appdata')}
    # Compatibility filename carries an empty List, without requiring an ingress controller/DNS.
    result['ingress.yaml'] = {'apiVersion': 'v1', 'kind': 'List', 'items': []}
    if engine != 'H2':
        db_name = service_name.replace('-', '_') + '_db'
        db_id = service_name + '-db'
        pg = engine == 'POSTGRESQL'
        env = [{'name': 'POSTGRES_DB' if pg else 'MYSQL_DATABASE', 'value': db_name},
               {'name': 'POSTGRES_USER' if pg else 'MYSQL_USER', 'value': 'app'}]
        for key, variable in [('DB_PASSWORD', 'POSTGRES_PASSWORD' if pg else 'MYSQL_PASSWORD')] + ([] if pg else [('DB_ROOT_PASSWORD', 'MYSQL_ROOT_PASSWORD')]):
            env.append({'name': variable, 'valueFrom': {'secretKeyRef': {
                'name': service_name + '-credentials', 'key': key}}})
        probe_cmd = ['pg_isready', '-U', 'app', '-d', db_name] if pg else ['sh', '-c', 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -h 127.0.0.1 -u app -e "SELECT 1"']
        db_container = {'name': 'db', 'image': DATABASE_IMAGES[engine], 'imagePullPolicy': 'Never',
                        'env': env, 'ports': [{'containerPort': 5432 if pg else 3306, 'name': 'db'}],
                        'resources': {'requests': {'cpu': '100m', 'memory': '256Mi'},
                                      'limits': {'cpu': '1', 'memory': '1Gi'}},
                        'volumeMounts': [{'name': 'data', 'mountPath': '/var/lib/postgresql/data' if pg else '/var/lib/mysql'}]}
        for probe in ['startupProbe', 'readinessProbe']:
            db_container[probe] = {'exec': {'command': probe_cmd}, 'periodSeconds': 5,
                                   'timeoutSeconds': 3, 'failureThreshold': 60 if probe == 'startupProbe' else 6}
        result['database.yaml'] = resource('StatefulSet', db_id, {
            'serviceName': db_id, 'replicas': 1, 'selector': {'matchLabels': {'app': db_id}},
            'template': {'metadata': {'labels': {**labels, 'app': db_id}}, 'spec': {
                'containers': [db_container], 'volumes': [{'name': 'data',
                    'persistentVolumeClaim': {'claimName': service_name + '-dbdata'}}]}}})
        result['database-service.yaml'] = resource('Service', db_id, {
            'type': 'ClusterIP', 'selector': {'app': db_id},
            'ports': [{'name': 'db', 'port': 5432 if pg else 3306, 'targetPort': 'db'}]})
        result['database-pvc.yaml'] = pvc(service_name + '-dbdata')
    return {name: yaml.safe_dump(value, sort_keys=False) for name, value in result.items()}


def validate_catalogue(catalogue, engine):
    """Validate the supported local topology offline, including cross-resource references."""
    expected_kinds = {'Deployment', 'StatefulSet', 'Service', 'ConfigMap', 'PersistentVolumeClaim', 'List'}
    objects = {}
    for filename, content in catalogue.items():
        doc = yaml.safe_load(content)
        if not isinstance(doc, dict) or doc.get('kind') not in expected_kinds:
            raise ValueError('Recurso no admitido: ' + filename)
        if doc['kind'] == 'List':
            if doc.get('items') != []:
                raise ValueError('List debe estar vacia')
            continue
        key = (doc['kind'], doc['metadata']['name'])
        if key in objects:
            raise ValueError('Recurso duplicado')
        objects[key] = doc
    deployments = [v for (k, _), v in objects.items() if k == 'Deployment']
    if len(deployments) != 1:
        raise ValueError('Se requiere una aplicacion')
    name = deployments[0]['metadata']['name']
    # Canonical profile is also a frozen schema for this restricted generated topology.
    app = deployments[0]['spec']['template']['spec']['containers'][0]
    canonical = manifests(name, engine, app['image'])
    normalized = {k: yaml.safe_dump(yaml.safe_load(v), sort_keys=True) for k, v in catalogue.items()}
    wanted = {k: yaml.safe_dump(yaml.safe_load(v), sort_keys=True) for k, v in canonical.items()}
    if normalized != wanted:
        raise ValueError('Catalogo incompatible: referencias, probes, recursos, motor o credenciales modificados')
    return {'status': 'PASSED', 'scope': 'SUPPORTED_LOCAL_CATALOGUE',
            'runtime': 'NOT_EXECUTED', 'databaseEngine': engine.upper(), 'resources': len(objects)}
