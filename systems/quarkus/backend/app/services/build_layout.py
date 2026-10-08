"""Resolve the build entry point once for preparation and offline build."""
from pathlib import Path


def build_layout(workspace):
    root = Path(workspace)
    for directory in ('.', 'bootstrap'):
        base = root / directory
        gradle = [name for name in ('build.gradle', 'build.gradle.kts') if (base / name).is_file()]
        maven = (base / 'pom.xml').is_file()
        if len(gradle) > 1 or (maven and gradle):
            raise ValueError('Entrada de build ambigua; conserve una sola herramienta en ' + directory)
        if gradle:
            entry = '.' if directory == 'bootstrap' and any((root / name).is_file() for name in ('settings.gradle', 'settings.gradle.kts')) else directory
            return 'gradle', entry, base / gradle[0]
        if maven:
            return 'maven', directory, base / 'pom.xml'
    return 'maven', '.', root / 'pom.xml'
