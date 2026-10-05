"""The offline profile uses installed Gradle, never downloads a wrapper distribution."""
import re
from app.services.dependency_inputs import dependency_contents
from app.services.build_layout import build_layout

PREPARED_GRADLE_VERSION = '8.10.2'


def validate_gradle_version(workspace):
    if build_layout(workspace)[0] != 'gradle':
        return
    for name, content in dependency_contents(workspace).items():
        if not name.endswith('gradle-wrapper.properties'):
            continue
        urls = re.findall(r'^\s*distributionUrl\s*=\s*(\S+)\s*$', content.decode('utf-8'), re.MULTILINE)
        match = re.search(r'(?:^|/)gradle-([0-9]+(?:\.[0-9]+){1,2})-(?:bin|all)\.zip(?:[?#].*)?$', urls[0]) if len(urls) == 1 else None
        if not match or match[1] != PREPARED_GRADLE_VERSION:
            raise ValueError(f'Gradle incompatible en {name}: el perfil preparado usa {PREPARED_GRADLE_VERSION}. Ajuste explícitamente el proyecto y regenere/prepare, o continúe sin Docker; no se descarga el wrapper.')


POWERSHELL_COMPATIBILITY = r'''
function Assert-GradleCompatibility([string]$BuildTool) {
  if ($BuildTool -ne 'gradle') { return }
  foreach ($file in @(Get-DependencyInputs | Where-Object { $_.Name -eq 'gradle-wrapper.properties' })) {
    $urls = @(Get-Content -LiteralPath $file.FullName | Where-Object { $_ -match '^\s*distributionUrl\s*=\s*\S+\s*$' })
    if ($urls.Count -ne 1 -or $urls[0] -notmatch '(?:^|/)gradle-(?<version>[0-9]+(?:\.[0-9]+){1,2})-(?:bin|all)\.zip(?:[?#].*)?\s*$' -or $Matches.version -ne '__VERSION__') {
      throw 'Gradle incompatible: el perfil preparado usa __VERSION__. Ajuste explicitamente el proyecto y regenere/prepare, o continue con -SourcesOnly. No se descarga el wrapper.'
    }
  }
}
'''.replace('__VERSION__', PREPARED_GRADLE_VERSION)
