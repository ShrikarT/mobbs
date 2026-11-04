import unittest
from unittest.mock import patch
import psycopg
from apps.api.app import worker


class PersistenceRecoveryTests(unittest.TestCase):
    def test_database_outage_during_analysis_remains_recoverable(self):
        # Production error path must preserve the leased job and dispatched guards,
        # rather than turn a temporary database outage into a terminal scan error.
        lease = {'kind': 'analysis', 'video_id':'v', 'id':'j', 'generation':1, 'run_id':'r'}
        with patch.object(worker, 'claim', return_value=lease), patch.object(worker, 'process_analysis', side_effect=psycopg.OperationalError('unavailable')), patch.object(worker, 'connection') as connect:
            with self.assertRaises(psycopg.OperationalError):
                worker.process_once()
            connect.assert_not_called()
