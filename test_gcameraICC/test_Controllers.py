#!/usr/bin/env python
"""unittests for the various gcamera Controllers."""

import sys
import unittest
import numpy as np

# TBD: #python3: python3 has unittest.mock.
import mock

DRV_SUCCESS = 20002

DRV_TEMPERATURE_OFF = 20034
DRV_TEMPERATURE_NOT_STABILIZED = 20035
DRV_TEMPERATURE_STABILIZED = 20036
DRV_TEMPERATURE_NOT_REACHED = 20037
DRV_TEMPERATURE_OUT_RANGE = 20038
DRV_TEMPERATURE_NOT_SUPPORTED = 20039
DRV_TEMPERATURE_DRIFT = 20040

DRV_ACQUIRING = 20072
DRV_ERROR_ACK = 20013

# Need to be able test without having the _andor.so compiled library available.
# NOTE: the Mock object doesn't do anything: we have to patch each function individually.
# spec = ['GetCameraHandle', 'SetCurrentCamera', 'Initialize', 'GetDetector',
#         'SetAcquisitionMode','SetExposureTime', 'GetAcquiredData16']
attrs = {'GetCameraHandle.return_value':[DRV_SUCCESS,1234],
         'SetCurrentCamera.return_value':DRV_SUCCESS,
         'Initialize.return_value':DRV_SUCCESS,
         'GetDetector.return_value':[DRV_SUCCESS,1111,2222],
         'SetAcquisitionMode.return_value':DRV_SUCCESS,
         'SetExposureTime.return_value':DRV_SUCCESS,
         'StartAcquisition.return_value':DRV_SUCCESS,
         'GetAcquiredData16.return_value':[DRV_SUCCESS,np.ones((10,10))],
         'CoolerOFF.return_value':DRV_SUCCESS,
         'CoolerON.return_value':DRV_SUCCESS,
         'SetTemperature.return_value':DRV_SUCCESS,
         'GetTemperature.return_value':[DRV_TEMPERATURE_OFF,10],
         'ShutDown.return_value':DRV_SUCCESS,
         }
         # this appears not to be implemented yet...
         # 'GetTemperatureStatus.return_value':[DRV_SUCCESS,-80,-100,10,5],
andor = mock.Mock(**attrs)
# TBD: It would be better to automate the process of setting these constants...
andor.DRV_SUCCESS = DRV_SUCCESS
andor.DRV_TEMPERATURE_OFF = DRV_TEMPERATURE_OFF
andor.DRV_ACQUIRING = DRV_ACQUIRING
andor.DRV_ERROR_ACK = DRV_ERROR_ACK

FAKE_FAIL = 123456

sys.modules['andor'] = andor
import andor
from gcameraICC.Controllers import BaseCam
from gcameraICC.Controllers import andorcam

import gcameraTester

class TestBaseCam(gcameraTester.GcameraTester):
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
        self.assertEqual(self.cam.setpoint,setpoint)
        self.assertEqual(self.cam.ccdTemp,ccdTemp)
        self.assertEqual(self.cam.statusText,statusText)

class TestAndorCam(TestBaseCam,unittest.TestCase):
    """Tests for the Andor Ikon camera for LCO."""
    def setUp(self):
        super(TestAndorCam,self).setUp()
        self.cam = andorcam.AndorCam()
        andor.reset_mock() # clear any function calls that init produced.

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
        newattr = {'GetCameraHandle.return_value':FAKE_FAIL}
        andor.configure_mock(**newattr)

        self.cam = andorcam.AndorCam()
        self.assertFalse(self.cam.ok)
        self.assertIn('Error number {}'.format(FAKE_FAIL),self.cam.errMsg)
        andor.GetCameraHandle.assert_called_once_with(0)

    def test_connect_fails_Initialize(self,*funcs):
        newattr = {'Initialize.return_value':FAKE_FAIL}
        andor.configure_mock(**newattr)

        self.cam = andorcam.AndorCam()
        self.assertFalse(self.cam.ok)
        self.assertIn('Error number {}'.format(FAKE_FAIL),self.cam.errMsg)
        andor.GetCameraHandle.assert_called_once_with(0)
        andor.SetCurrentCamera.assert_called_once_with(self.cam.camHandle)
        andor.Initialize.assert_called_once_with("/usr/local/etc/andor")


    def test_prep_exposure(self):
        self.cam.itime = 100
        self.cam._prep_exposure()
        andor.SetAcquisitionMode.assert_called_once_with(1)
        andor.SetExposureTime.assert_called_once_with(100)


    def test_start_exposure(self):
        self.cam._start_exposure()
        andor.StartAcquisition.assert_called_once_with()

    def test_start_exposure_fails(self):
        newattr = {'StartAcquisition.return_value':FAKE_FAIL}
        andor.configure_mock(**newattr)

        self.cam = andorcam.AndorCam()
        with self.assertRaises(andorcam.AndorError) as cm:
            self.cam._start_exposure()
        self.assertIn('Error number {}'.format(FAKE_FAIL), cm.exception.message)
        andor.StartAcquisition.assert_called_once_with()


    def test_cooler_status_off(self):
        self.cam.setpoint = -100
        self.cam.cooler_status()
        andor.GetTemperature.assert_called_once_with()
        super(TestAndorCam,self)._cooler_status(setpoint=-100, ccdTemp=10, statusText='Off')

    def test_cooler_status_acquiring(self):
        """The CCD temperature should update, but the status text should not."""
        newattr = {'GetTemperature.return_value':[DRV_ACQUIRING,-50]}
        andor.configure_mock(**newattr)

        self.cam.statusText = 'NotStabilized'
        self.cam.setpoint = -100
        self.cam.cooler_status()
        andor.GetTemperature.assert_called_once_with()
        super(TestAndorCam,self)._cooler_status(setpoint=-100, ccdTemp=-50, statusText='NotStabilized')

    def test_cooler_status_driver_error(self):
        newattr = {'GetTemperature.return_value':[DRV_ERROR_ACK,-50]}
        andor.configure_mock(**newattr)

        with self.assertRaises(andorcam.AndorError) as cm:
            self.cam.cooler_status()
        self.assertIn('Communication error when getting temperature',cm.exception.message)
        andor.GetTemperature.assert_called_once_with()

    def test_cooler_status_cooling(self):
        newattr = {'GetTemperature.return_value':[DRV_TEMPERATURE_NOT_STABILIZED,-50]}
        andor.configure_mock(**newattr)

        self.cam.setpoint = -100
        self.cam.cooler_status()
        andor.GetTemperature.assert_called_once_with()
        super(TestAndorCam,self)._cooler_status(setpoint=-100, ccdTemp=-50, statusText='NotStabilized')

    def test_cooler_status_stable(self):
        newattr = {'GetTemperature.return_value':[DRV_TEMPERATURE_STABILIZED,-100]}
        andor.configure_mock(**newattr)

        self.cam.setpoint = -100
        self.cam.cooler_status()
        andor.GetTemperature.assert_called_once_with()
        super(TestAndorCam,self)._cooler_status(setpoint=-100, ccdTemp=-100, statusText='Stabilized')


    def test_set_cooler_on_new_temp(self):
        # one call to check if cooler is on, one for cooler_status()
        side_effect = [[DRV_TEMPERATURE_STABILIZED,-20], [DRV_TEMPERATURE_NOT_STABILIZED,-25]]
        newattr = {'GetTemperature.side_effect':side_effect}
        andor.configure_mock(**newattr)

        temp = -40
        self.cam.set_cooler(temp)
        # one call to check if cooler is on, one for cooler_status()
        self.assertEqual(andor.GetTemperature.call_count,2)
        self.assertFalse(andor.CoolerON.called) # not called, since it was already on.
        andor.SetTemperature.assert_called_once_with(temp)
        super(TestAndorCam,self)._cooler_status(setpoint=-40, ccdTemp=-25, statusText='NotStabilized')

    def test_set_cooler_was_off(self):
        # return off first time, on and a colder temp second time.
        side_effect = [[DRV_TEMPERATURE_OFF,0], [DRV_TEMPERATURE_NOT_STABILIZED,-10]]
        newattr = {'GetTemperature.side_effect':side_effect}
        andor.configure_mock(**newattr)

        temp = -100
        self.cam.set_cooler(temp)
        # one call to check if cooler is on, one for cooler_status()
        self.assertEqual(andor.GetTemperature.call_count,2)
        andor.CoolerON.assert_called_once_with()
        andor.SetTemperature.assert_called_once_with(temp)
        super(TestAndorCam,self)._cooler_status(setpoint=-100, ccdTemp=-10, statusText='NotStabilized')

    def test_set_cooler_off(self):
        newattr = {'GetTemperature.return_value':[DRV_TEMPERATURE_NOT_STABILIZED,-100]}
        andor.configure_mock(**newattr)

        temp = None
        self.cam.set_cooler(temp)
        andor.CoolerOFF.assert_called_once_with()
        super(TestAndorCam,self)._cooler_status(setpoint=0, ccdTemp=-100, statusText='NotStabilized')


    def test_shut_down(self):
        """Check that we don't shut down until the camera has reached ~0 degrees."""
        N = 10
        retvals = [DRV_TEMPERATURE_NOT_STABILIZED]*(N+1) + [DRV_TEMPERATURE_STABILIZED,]
        temps = np.linspace(-110,0,N+2) + np.random.normal(0,.1,size=N+2)
        newattr = {'GetTemperature.side_effect':zip(retvals,temps)}
        andor.configure_mock(**newattr)

        self.cam.setpoint = -100
        self.cam.ccdTemp = -100
        self.cam.shut_down()
        andor.CoolerOFF.assert_called_once_with()
        self.assertEqual(andor.GetTemperature.call_count,12)
        andor.ShutDown.assert_called_once_with()

    def test_expose(self):
        self.cam.expose(1,cmd=self.cmd)
        self.assertTrue(False)

if __name__ == '__main__':
    verbosity = 2
    
    unittest.main(verbosity=verbosity)
