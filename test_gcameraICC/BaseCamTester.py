#!/usr/bin/env python
"""unittests for the various gcamera Controllers."""

import numpy as np

from gcameraICC.Controllers import BaseCam

import gcameraTester


class BaseCamTester(gcameraTester.GcameraTester):
    """Subclass this to get the tests for common functions."""
    def test_checkSelf_not_ok(self):
        self.cam.ok = False
        with self.assertRaises(BaseCam.CameraError) as cm:
            self.cam._checkSelf()
        self.assertIn('camera connection is down', cm.exception.message)

    def test_checkSelf_with_errMsg(self):
        errMsg = 'blahblahblahblahblah'
        self.cam.ok = False
        self.cam.errMsg = errMsg
        with self.assertRaises(BaseCam.CameraError) as cm:
            self.cam._checkSelf()
        self.assertIn('camera connection is down', cm.exception.message)
        self.assertIn('Last message: {}'.format(errMsg), cm.exception.message)

    def test_checkSelf_ok(self):
        """Nothing should happen."""
        self.cam.ok = True
        self.cam._checkSelf()

    def _cooler_status(self, setpoint=np.nan, ccdTemp=np.nan, statusText='Unknown'):
        self.assertEqual(self.cam.setpoint, setpoint)
        self.assertEqual(self.cam.ccdTemp, ccdTemp)
        self.assertEqual(self.cam.statusText, statusText)
