import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.api.app.config import settings, get_effective_runtime_path
from apps.api.app.worker import get_operational_pause_marker_path, ROOT


class TestMobbsConfig(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

        # Base mock config
        self.base_config = {
            'database_url': 'postgresql://test:test@localhost:5432/test_db',
            's3_endpoint': 'http://localhost:9000',
            's3_access_key': 'test_key',
            's3_secret_key': 'test_secret',
            's3_bucket': 'test-bucket',
            'provider_evidence_root': str(self.tmp_path / 'evidence'),
            'origin': 'http://127.0.0.1:58000',
        }

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _write_config(self, filename: str, extra: dict = None) -> Path:
        data = dict(self.base_config)
        if extra:
            data.update(extra)
        p = self.tmp_path / filename
        p.write_text(json.dumps(data), encoding='utf-8')
        return p

    def test_mobbs_runtime_precedence_over_viralist_runtime(self):
        mobbs_file = self._write_config('mobbs_runtime.json', {'origin': 'http://mobbs.local'})
        viralist_file = self._write_config('viralist_runtime.json', {'origin': 'http://viralist.local'})

        with patch.dict(os.environ, {
            'MOBBS_RUNTIME': f'  {mobbs_file}  ',
            'VIRALIST_RUNTIME': f'  {viralist_file}  ',
        }, clear=True):
            eff_path = get_effective_runtime_path()
            self.assertEqual(eff_path, str(mobbs_file))
            s = settings()
            self.assertEqual(s.origin, 'http://mobbs.local')
            pause_marker = get_operational_pause_marker_path()
            self.assertEqual(pause_marker, mobbs_file.parent / 'operational_pause.marker')

    def test_viralist_runtime_fallback_when_mobbs_runtime_unset(self):
        viralist_file = self._write_config('legacy_runtime.json', {'origin': 'http://legacy.local'})

        with patch.dict(os.environ, {
            'MOBBS_RUNTIME': '   ',  # whitespace only
            'VIRALIST_RUNTIME': f'  {viralist_file}  ',
        }, clear=True):
            eff_path = get_effective_runtime_path()
            self.assertEqual(eff_path, str(viralist_file))
            s = settings()
            self.assertEqual(s.origin, 'http://legacy.local')
            pause_marker = get_operational_pause_marker_path()
            self.assertEqual(pause_marker, viralist_file.parent / 'operational_pause.marker')

    def test_default_paths_fallback_when_env_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, 'home', return_value=self.tmp_path):
                # When neither exists, default mobbs path returned
                eff_path = get_effective_runtime_path()
                expected_mobbs = self.tmp_path / '.codex/private-runs/mobbs-v02-local/runtime.json'
                self.assertEqual(eff_path, str(expected_mobbs))

                # When legacy viralist file exists, it falls back to it
                legacy_dir = self.tmp_path / '.codex/private-runs/viralist-v02-local'
                legacy_dir.mkdir(parents=True, exist_ok=True)
                legacy_file = legacy_dir / 'runtime.json'
                legacy_file.write_text(json.dumps(self.base_config), encoding='utf-8')

                eff_path2 = get_effective_runtime_path()
                self.assertEqual(eff_path2, str(legacy_file))

                # When new mobbs file also exists, new mobbs takes precedence
                mobbs_dir = self.tmp_path / '.codex/private-runs/mobbs-v02-local'
                mobbs_dir.mkdir(parents=True, exist_ok=True)
                mobbs_file = mobbs_dir / 'runtime.json'
                mobbs_file.write_text(json.dumps(self.base_config), encoding='utf-8')

                eff_path3 = get_effective_runtime_path()
                self.assertEqual(eff_path3, str(mobbs_file))

    def test_mobbs_provider_mode_precedence_and_trim(self):
        cfg_file = self._write_config('cfg.json')
        with patch.dict(os.environ, {
            'MOBBS_RUNTIME': str(cfg_file),
            'MOBBS_PROVIDER_MODE': '  standard  ',
            'VIRALIST_PROVIDER_MODE': 'recorded',
            'MODEL_API_KEY': 'test_secret_key',
        }, clear=True):
            s = settings()
            self.assertEqual(s.provider_mode, 'standard')
            self.assertEqual(s.model_api_key, 'test_secret_key')

    def test_viralist_provider_mode_fallback_when_mobbs_mode_unset(self):
        cfg_file = self._write_config('cfg.json')
        with patch.dict(os.environ, {
            'MOBBS_RUNTIME': str(cfg_file),
            'MOBBS_PROVIDER_MODE': '',
            'VIRALIST_PROVIDER_MODE': '  standard  ',
            'MODEL_API_KEY': 'legacy_secret_key',
        }, clear=True):
            s = settings()
            self.assertEqual(s.provider_mode, 'standard')
            self.assertEqual(s.model_api_key, 'legacy_secret_key')

    def test_recorded_mode_never_reads_credentials(self):
        cfg_file = self._write_config('cfg.json', {'model_api_key': 'embedded_secret'})
        # Case 1: default recorded
        with patch.dict(os.environ, {
            'MOBBS_RUNTIME': str(cfg_file),
            'MODEL_API_KEY': 'env_secret',
        }, clear=True):
            s = settings()
            self.assertEqual(s.provider_mode, 'recorded')
            self.assertEqual(s.model_api_key, '')

        # Case 2: explicit MOBBS_PROVIDER_MODE=recorded
        with patch.dict(os.environ, {
            'MOBBS_RUNTIME': str(cfg_file),
            'MOBBS_PROVIDER_MODE': 'recorded',
            'MODEL_API_KEY': 'env_secret',
        }, clear=True):
            s = settings()
            self.assertEqual(s.provider_mode, 'recorded')
            self.assertEqual(s.model_api_key, '')

        # Case 3: explicit VIRALIST_PROVIDER_MODE=recorded
        with patch.dict(os.environ, {
            'MOBBS_RUNTIME': str(cfg_file),
            'VIRALIST_PROVIDER_MODE': 'recorded',
            'MODEL_API_KEY': 'env_secret',
        }, clear=True):
            s = settings()
            self.assertEqual(s.provider_mode, 'recorded')
            self.assertEqual(s.model_api_key, '')


if __name__ == '__main__':
    unittest.main()
