import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
try:
    from PySide6.QtWidgets import QApplication
    from apk_revival.launcher.mods import ModsDialog
except ImportError:QApplication=None  # The CI unit job installs no Qt.
from apk_revival.launcher.jobs import Jobs
from apk_revival.launcher.service import Launcher
from apk_revival.util import RevivalError


@unittest.skipIf(QApplication is None,'PySide6 is not installed')
class ModsUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = Mock()
        self.service.jobs = Jobs(Path(self.temp.name))
        self.service.mod_timers.return_value = [dict(title='Storage: construction', seconds=45, token='selected-generation')]
        self.service.skip_timer.return_value = 'Storage: construction'
        self.dialog = ModsDialog(self.service, 'meego')
        self.dialog.show()
        self.app.processEvents()

    def tearDown(self):
        self.wait()
        self.dialog.close()
        self.app.processEvents()
        self.temp.cleanup()

    def wait(self):
        end = time.monotonic() + 5
        while self.dialog.worker and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(.01)
        self.assertIsNone(self.dialog.worker)

    def test_skip_is_opt_in_and_sends_only_selected_generation(self):
        self.assertFalse(self.dialog.skip_button.isEnabled())
        self.dialog.skip_button.click()
        self.service.skip_timer.assert_not_called()
        self.dialog.enabled.setChecked(True)
        self.dialog.choices.setCurrentIndex(0)
        self.dialog.skip_button.click()
        self.assertFalse(self.dialog.close_button.isEnabled())
        self.wait()
        self.service.skip_timer.assert_called_once()
        self.assertEqual(self.service.skip_timer.call_args.args[:2], ('meego', 'selected-generation'))
        self.assertIn('Skipped:', self.dialog.status.text())
        self.assertEqual(self.service.jobs.history[-1].state, 'succeeded')

    def test_stale_timer_failure_visible_and_can_refresh(self):
        self.service.skip_timer.side_effect = RevivalError('Timer changed; refresh')
        self.dialog.enabled.setChecked(True)
        self.dialog.choices.setCurrentIndex(0)
        self.dialog.skip_button.click()
        self.wait()
        self.assertEqual(self.dialog.status.text(), 'Timer changed; refresh')
        self.assertEqual(self.service.jobs.history[-1].state, 'failed')
        self.service.mod_timers.return_value = []
        self.dialog.refresh_button.click()
        self.assertFalse(self.dialog.skip_button.isEnabled())
        self.assertIn('No supported', self.dialog.status.text())

    def test_no_backend_shows_actionable_error(self):
        self.service.mod_timers.side_effect = RevivalError('Press Play before using Mods')
        self.dialog.refresh()
        self.assertIn('Press Play', self.dialog.status.text())
        self.assertFalse(self.dialog.skip_button.isEnabled())

    def test_service_rejects_another_game_and_absent_backend(self):
        service = Launcher.__new__(Launcher)
        service.store = Mock()
        service.store.load.return_value = {'adapter':'ordinary-apk'}
        service.active = None
        service.android = None
        with self.assertRaisesRegex(RevivalError, 'Meego only'):service.mod_timers('other')
        service.store.load.return_value = {'adapter':'meego-1.32'}
        with self.assertRaisesRegex(RevivalError, 'Press Play'):service.mod_timers('meego')
        service.active = {'game':'other'}
        with self.assertRaisesRegex(RevivalError, 'Press Play'):service.mod_timers('meego')
        service.active = {'game':'meego'}
        with self.assertRaisesRegex(RevivalError, 'unavailable'):service.mod_timers('meego')
        service.store.load.assert_called_with('meego', check=False)

    def test_new_baby_appears_automatically_without_reopening_or_resetting(self):
        self.service.mod_timers.return_value = []
        self.dialog.refresh()
        self.assertEqual(self.dialog.choices.count(), 0)
        self.dialog.enabled.setChecked(True)
        self.service.mod_timers.return_value = [dict(title='Nooni: baby to child', seconds=7100, token='baby-6')]
        self.dialog.refresh_timer.setInterval(10)
        end = time.monotonic() + 2
        while self.dialog.choices.count() == 0 and time.monotonic() < end:
            self.app.processEvents();time.sleep(.01)
        self.assertEqual(self.dialog.choices.itemData(0), 'baby-6')
        self.assertIn('Nooni', self.dialog.choices.itemText(0))
        self.assertFalse(self.dialog.skip_button.isEnabled())
        self.dialog.choices.setCurrentIndex(0)
        self.assertTrue(self.dialog.skip_button.isEnabled())
        self.service.skip_timer.assert_not_called()

    def test_refresh_preserves_selection_and_never_substitutes_different_task(self):
        self.dialog.enabled.setChecked(True)
        self.dialog.choices.setCurrentIndex(0)
        self.dialog.refresh(automatic=True)
        self.assertEqual(self.dialog.choices.currentData(), 'selected-generation')
        self.service.mod_timers.return_value = [dict(title='Other task', seconds=15, token='unselected-task')]
        self.dialog.refresh(automatic=True)
        self.assertIsNone(self.dialog.choices.currentData())
        self.assertFalse(self.dialog.skip_button.isEnabled())
        self.assertIn('finished or changed', self.dialog.status.text())
        self.service.skip_timer.assert_not_called()

    def test_closing_mods_stops_background_refresh(self):
        self.assertTrue(self.dialog.refresh_timer.isActive())
        self.dialog.reject()
        self.assertFalse(self.dialog.refresh_timer.isActive())
