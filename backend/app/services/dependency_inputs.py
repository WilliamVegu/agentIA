"""Shared catalogue of local build configuration used by prepared image and scripts."""
import hashlib
from pathlib import Path

EXCLUDED = {'.git', 'target', 'build', '.gradle', '.m2', 'node_modules', '.agentia-runtime', '.run', '.venv', '.idea', '__pycache__'}
NAMES = {'pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle', 'settings.gradle.kts',
         'gradle.properties', 'gradlew', 'gradlew.bat', 'mvnw', 'mvnw.cmd'}


def is_dependency_input(relative):
    path = Path(relative)
    return (not any(part in EXCLUDED for part in path.parts)
            and path.name not in {'.DS_Store', 'Thumbs.db'} and not path.name.endswith('.pyc')
            and (not path.name.startswith('.env') or path.name == '.env.example')
            and (path.name in NAMES or path.name.endswith(('.gradle', '.gradle.kts', '.lockfile'))
                 or any(part in {'.mvn', 'gradle', 'buildSrc'} for part in path.parts)))


def dependency_contents(workspace):
    root = Path(workspace).resolve()
    result = {}
    for file in sorted(root.rglob('*')):
        relative = file.relative_to(root)
        if not is_dependency_input(relative):
            continue
        if file.is_symlink() or not file.resolve().is_relative_to(root):
            raise ValueError('Entrada de build enlazada o fuera del proyecto; no se reutiliza preparación.')
        if file.is_file():
            result[relative.as_posix()] = file.read_bytes()
    return result


def dependency_manifest(workspace):
    return {name: hashlib.sha256(content).hexdigest() for name, content in dependency_contents(workspace).items()}


# Same selector as Python, generated into standalone scripts. Reads no Docker state.
POWERSHELL_SELECTOR = r'''
function Get-DependencyInputs {
  @(Get-ChildItem -LiteralPath $PSScriptRoot -File -Recurse | Where-Object {
    $relative = $_.FullName.Substring($PSScriptRoot.Length+1).Replace('\','/')
    $included = $relative -notmatch '(^|/)(\.git|target|build|\.gradle|\.m2|node_modules|\.agentia-runtime|\.run|\.venv|\.idea|__pycache__)(/|$)' -and
      $_.Name -notin @('.DS_Store','Thumbs.db') -and $_.Name -notmatch '\.pyc$' -and ($_.Name -notlike '.env*' -or $_.Name -eq '.env.example') -and (
      $_.Name -in @('pom.xml','build.gradle','build.gradle.kts','settings.gradle','settings.gradle.kts','gradle.properties','gradlew','gradlew.bat','mvnw','mvnw.cmd') -or
      $_.Name -match '\.(gradle|gradle\.kts|lockfile)$' -or $relative -match '(^|/)(\.mvn|gradle|buildSrc)(/|$)')
    if ($included -and ($_.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Entrada de build enlazada no admitida' }
    $included
  })
}
'''
