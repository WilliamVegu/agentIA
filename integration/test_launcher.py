import importlib.util
import json
from pathlib import Path
import socket
import unittest
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('dual_launcher', Path(__file__).with_name('launch.py'))
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_inherited_data_paths_cannot_make_studios_share_storage(self):
        with patch.dict('os.environ', {'DATABASE_URL': 'sqlite:///shared.db', 'WORKSPACE_DIR': 'shared', 'COST_STORE_PATH': 'shared.db', 'SPECIFICATION_DIR': 'shared'}):
            envs = {name: launcher.service_environment(name, system) for name, system in launcher.SYSTEMS.items()}
        for setting in ['DATABASE_URL', 'WORKSPACE_DIR', 'SPECIFICATION_DIR', 'COST_STORE_PATH', 'MLFLOW_EXPERIMENT', 'PYTHONPATH']:
            self.assertNotEqual(envs['springboot'][setting], envs['quarkus'][setting], setting)

    def test_browser_cookie_domains_and_cors_origins_are_distinct(self):
        hosts = {system['host'] for system in launcher.SYSTEMS.values()}
        self.assertEqual(hosts, {'localhost', '127.0.0.1'})
        for name, system in launcher.SYSTEMS.items():
            env = launcher.service_environment(name, system)
            self.assertEqual(json.loads(env['CORS_ORIGINS']), [f"http://{system['host']}:{system['frontend']}"])

    def test_occupied_port_aborts_without_stopping_existing_listener(self):
        with socket.socket() as existing:
            existing.bind(('127.0.0.1', 0))
            existing.listen()
            with patch.object(launcher, 'PORTAL_PORT', existing.getsockname()[1]):
                with self.assertRaisesRegex(RuntimeError, 'Puerto ocupado'):
                    launcher.require_free_ports()
            with socket.create_connection(existing.getsockname(), timeout=1):
                pass

    def test_dead_child_is_reported_without_waiting_for_timeout(self):
        child = unittest.mock.Mock()
        child.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, 'terminó antes'):
            launcher.wait_ready('http://127.0.0.1:1/healthz', child, timeout=90)

    def test_exited_child_is_not_killed(self):
        child = unittest.mock.Mock()
        child.poll.return_value = 0
        with patch.object(launcher.subprocess, 'run') as run:
            launcher.stop_child(child)
        run.assert_not_called()

    def test_failed_start_rolls_back_only_the_child_it_created(self):
        child = unittest.mock.Mock()
        with patch.object(launcher, 'python_for', return_value='python'), patch.object(Path, 'is_file', return_value=True), patch.object(launcher, 'require_free_ports'), patch.object(launcher.subprocess, 'Popen', return_value=child), patch.object(launcher, 'wait_ready', side_effect=RuntimeError('startup failed')), patch.object(launcher, 'stop_child') as stop:
            with self.assertRaisesRegex(RuntimeError, 'startup failed'):
                launcher.launch(open_browser=False)
        stop.assert_called_once_with(child)


    def test_python_preflight_rejects_store_alias_and_unsupported_versions(self):
        with self.assertRaisesRegex(RuntimeError, 'WindowsApps'):
            launcher.validate_python('C:/Users/fixture/AppData/Local/Microsoft/WindowsApps/python.exe')
        for version in ['[3, 9, 0]', '[3, 14, 0]']:
            with patch.object(launcher.subprocess, 'run', return_value=unittest.mock.Mock(returncode=0, stdout=version)):
                with self.assertRaisesRegex(RuntimeError, '3.11'):
                    launcher.validate_python('fixture-python')

    def test_missing_pip_bootstraps_only_selected_environment(self):
        probe = unittest.mock.Mock(returncode=1, stderr='No module named pip')
        with patch.object(launcher.subprocess, 'run', side_effect=[probe, unittest.mock.Mock(returncode=0)]) as run:
            launcher.ensure_pip('fixture-venv-python')
        self.assertEqual(run.call_args_list[1].args[0], ['fixture-venv-python', '-m', 'ensurepip', '--upgrade'])

    def test_npm_resolution_never_passes_windows_wrapper_to_node(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node = root / 'node.exe'; node.touch()
            wrapper = root / 'npm.cmd'; wrapper.touch()
            with self.assertRaisesRegex(RuntimeError, 'npm-cli'):
                launcher.npm_command(str(node), str(wrapper))
            cli = root / 'node_modules/npm/bin/npm-cli.js'
            cli.parent.mkdir(parents=True); cli.touch()
            self.assertEqual(launcher.npm_command(str(node), str(wrapper)), [str(node), str(cli)])


if __name__ == '__main__':
    unittest.main()
