"""The production worker loop must outlive transient database outages."""
import unittest
from unittest.mock import patch

import psycopg
from apps.api.app import worker


class StopLoop(Exception):
    pass


class WorkerReconnectTests(unittest.TestCase):
    def test_cleanup_connection_failure_does_not_stop_queued_work(self):
        with patch('sys.argv', ['worker']), \
             patch.object(worker, 'retention_cleanup', side_effect=[psycopg.OperationalError('private details'), None]), \
             patch.object(worker, 'process_once', return_value=True) as process, \
             patch.object(worker.time, 'sleep', side_effect=[None, StopLoop]) as sleep:
            with self.assertRaises(StopLoop):
                worker.main()
        process.assert_called_once_with()
        self.assertEqual(sleep.call_args_list[0].args, (1,))
        self.assertEqual(sleep.call_args_list[1].args, (.1,))

    def test_claim_disconnect_recovers_with_bounded_backoff_then_resets(self):
        results = [psycopg.InterfaceError('closed connection')] * 7 + [False, psycopg.OperationalError('down again')]
        with patch('sys.argv', ['worker']), \
             patch.object(worker, 'retention_cleanup'), \
             patch.object(worker, 'process_once', side_effect=results), \
             patch.object(worker.time, 'sleep', side_effect=[None] * 8 + [StopLoop]) as sleep:
            with self.assertRaises(StopLoop):
                worker.main()
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2, 4, 8, 16, 30, 30, .5, 1])

    def test_once_reports_database_failure_without_silent_retry(self):
        with patch('sys.argv', ['worker', '--once']), \
             patch.object(worker, 'retention_cleanup', side_effect=psycopg.OperationalError('down')), \
             patch.object(worker.time, 'sleep') as sleep:
            with self.assertRaises(psycopg.OperationalError):
                worker.main()
        sleep.assert_not_called()

    def test_unexpected_code_error_is_not_hidden_by_reconnection(self):
        with patch('sys.argv', ['worker']), \
             patch.object(worker, 'retention_cleanup', side_effect=ValueError('bug')), \
             patch.object(worker.time, 'sleep') as sleep:
            with self.assertRaises(ValueError):
                worker.main()
        sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
