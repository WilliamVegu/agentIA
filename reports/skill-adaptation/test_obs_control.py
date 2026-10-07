"""Verificación aislada: no inicia OBS ni modifica la sesión del usuario."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("obs_control", Path(__file__).parent / "obs-screen-recorder/scripts/obs_control.py")
obs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(obs)


class ControlTests(unittest.TestCase):
    def args(self, command, **kw):
        return SimpleNamespace(command=command, name=kw.get("name"), output=kw.get("output"))

    def state(self, active=True, paused=False):
        return SimpleNamespace(output_active=active, output_paused=paused,
                               output_timecode="00:00:01.000", output_duration=1000)

    def test_start_requires_confirmed_state(self):
        client = Mock()
        client.get_record_status.return_value = self.state(False)
        with patch.object(obs.time, "sleep"), self.assertRaises(RuntimeError):
            obs.execute(client, self.args("start"))
        client.start_record.assert_called_once()

    def test_pause_resume_report_observed_state(self):
        for command, paused in [("pause", True), ("resume", False)]:
            client = Mock()
            client.get_record_status.side_effect = [self.state(paused=not paused), self.state(paused=paused)]
            result = obs.execute(client, self.args(command))
            self.assertEqual(result["is_paused"], paused)

    def test_start_is_idempotent(self):
        client = Mock()
        client.get_record_status.return_value = self.state()
        self.assertEqual(obs.execute(client, self.args("start"))["status"], "already_recording")
        client.start_record.assert_not_called()

    def test_stop_accepts_mkv_and_checks_exact_file(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "video.mkv"
            output.write_bytes(b"video")
            client = Mock()
            client.get_record_status.side_effect = [self.state(), self.state(False)]
            client.stop_record.return_value = SimpleNamespace(output_path=str(output))
            result = obs.execute(client, self.args("stop"))
            self.assertEqual(result["output_path"], str(output.resolve()))
            self.assertEqual(result["size_bytes"], 5)

    def test_missing_output_does_not_guess_old_file(self):
        with self.assertRaises(RuntimeError):
            obs.verify_file(None)

    def test_screenshot_uses_native_size_and_verifies_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "frame.png"
            client = Mock()
            def save(request, payload):
                self.assertEqual(request, "SaveSourceScreenshot")
                self.assertNotIn("imageWidth", payload)
                self.assertNotIn("imageHeight", payload)
                Path(payload["imageFilePath"]).write_bytes(b"frame")
            client.send.side_effect = save
            result = obs.execute(client, self.args("screenshot", name="Fuente", output=str(output)))
            self.assertEqual(client.send.call_args.args[1]["sourceName"], "Fuente")
            self.assertEqual(result["size_bytes"], 5)

    def test_config_reads_credentials_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            original = '{"server_enabled":false,"server_password":"test-secret","server_port":4455}'
            config.write_text(original)
            with patch.object(obs, "config_path", return_value=config):
                data = obs.load_config()
                diagnostic = obs.doctor(obs.DEFAULT_EXE)
            self.assertFalse(data["enabled"])
            self.assertNotIn("test-secret", str(diagnostic))
            self.assertEqual(config.read_text(), original)


if __name__ == "__main__":
    unittest.main()
