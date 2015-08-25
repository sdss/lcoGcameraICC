#!/usr/bin/env python
"""unittests for the various gcamera Controllers."""

import sys
import unittest
import numpy as np

# TBD: #python3: python3 has unittest.mock.
import mock

DRV_SUCCESS = 20002

# Need to be able test without having the _andor.so compiled library available.
# NOTE: this mock doesn't do anything: we have to patch each function individually.
# spec = ['GetCameraHandle', 'SetCurrentCamera', 'Initialize', 'GetDetector',
#         'SetAcquisitionMode','SetExposureTime', 'GetAcquiredData16']
attrs = {'GetCameraHandle.return_value':[DRV_SUCCESS,1234],
         'SetCurrentCamera.return_value':DRV_SUCCESS,
         'Initialize.return_value':DRV_SUCCESS,
         'GetDetector.return_value':[DRV_SUCCESS,1111,2222],
         'SetAcquisitionMode.return_value':DRV_SUCCESS,
         'SetExposureTime.return_value':DRV_SUCCESS,
         'StartAcquisition.return_value':DRV_SUCCESS,
         'GetAcquiredData16.return_value':[DRV_SUCCESS,np.ones((10,10))]}
andor = mock.Mock(**attrs)
andor.DRV_SUCCESS = 20002

sys.modules['andor'] = andor
import andor
from gcameraICC.Controllers import andorcam

import gcameraTester

class TestBaseCam(gcameraTester.GcameraTester):
    """Subclass this to get the tests for common functions."""
    pass

class TestAndorCam(unittest.TestCase,TestBaseCam):
    """Tests for the Andor Ikon camera for LCO."""

    def tearDown(self):
        andor.reset_mock()
        # reset the return values to their default.
        andor.configure_mock(**attrs)

    def test_connect(self):
        self.cam = andorcam.AndorCam()
        self.assertEqual(self.cam.errMsg,'')
        self.assertTrue(self.cam.ok)
        andor.GetCameraHandle.assert_called_once_with(0)
        andor.SetCurrentCamera.assert_called_once_with(self.cam.camHandle)
        andor.Initialize.assert_called_once_with("/usr/local/etc/andor")
        andor.GetDetector.assert_called_once_with()
        self.assertEqual(self.cam.width,1111)
        self.assertEqual(self.cam.height,2222)

    def test_connect_fails_GetCameraHandle(self,*funcs):
        newattr = {'GetCameraHandle.return_value':12345}
        andor.configure_mock(**newattr)
        self.cam = andorcam.AndorCam()
        self.assertFalse(self.cam.ok)
        self.assertIn('Error number 12345',self.cam.errMsg)
        andor.GetCameraHandle.assert_called_once_with(0)

    def test_connect_fails_Initialize(self,*funcs):
        newattr = {'Initialize.return_value':54321}
        andor.configure_mock(**newattr)
        self.cam = andorcam.AndorCam()
        self.assertFalse(self.cam.ok)
        self.assertIn('Error number 54321',self.cam.errMsg)
        andor.GetCameraHandle.assert_called_once_with(0)
        andor.SetCurrentCamera.assert_called_once_with(self.cam.camHandle)
        andor.Initialize.assert_called_once_with("/usr/local/etc/andor")


    def test_prep_exposure(self):
        self.cam = andorcam.AndorCam()
        self.cam.itime = 100
        self.cam._prep_exposure()
        andor.SetAcquisitionMode.assert_called_once_with(1)
        andor.SetExposureTime.assert_called_once_with(100)


    def test_start_exposure(self):
        self.cam = andorcam.AndorCam()
        self.cam._start_exposure()
        andor.StartAcquisition.assert_called_once_with()

    def test_start_exposure_fails(self):
        newattr = {'StartAcquisition.return_value':54321}
        andor.configure_mock(**newattr)
        self.cam = andorcam.AndorCam()
        with self.assertRaises(andorcam.AndorError) as cm:
            self.cam._start_exposure()
        self.assertIn('Error number 54321', cm.exception.message)
        andor.StartAcquisition.assert_called_once_with()


if __name__ == '__main__':
    verbosity = 2
    
    unittest.main(verbosity=verbosity)
