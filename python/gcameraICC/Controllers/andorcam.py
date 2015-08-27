"""Python OO interface for controlling an Andor Ikon camera."""
import sys
import numpy as np

import BaseCam
import andor

class AndorError(BaseCam.CameraError):
    pass

class AndorCam(BaseCam.BaseCam):

    # index on [result[0] - andor.DRV_TEMPERATURE_OFF]
    coolerStatusNames = ('Off', 'NotStabilized', 'Stabilized',
                         'NotReached', 'OutOfRange', 'NotSupported',
                         'WasStableNowDrifting')

    def __init__(self):
        """ Connect to an Andor ikon and start to initialize it. """

        self.camName = 'Andor iKon'

        BaseCam.BaseCam.__init__(self)

    def connect(self):
        """ (Re-)initialize and already open connection. """

        super(AndorCam,self).doInit()

        self.camHandle = self.safe_call(andor.GetCameraHandle,0)
        self.safe_call(andor.SetCurrentCamera,self.camHandle)
        self.safe_call(andor.Initialize,"/usr/local/etc/andor")
        self.width,self.height = self.safe_call(andor.GetDetector)
        self.ok = True

        self._checkSelf()

        # Turn off LEDs
        # self.write_LedMode(0)

    def safe_call(self,func,*args):
        """
        Call func with args, check return for success, return actual result, if any.
        
        Raises descriptive exception on call failure.
        """
        result = func(*args)
        # unpack the result: could be a single return value,
        # return value + one thing, or return value + many things.
        if type(result) == list:
            retval = result[0]
            if len(result[1:]) == 1:
                result = result[1]
            else:
                result = result[1:]
        else:
            retval = result
        if retval != andor.DRV_SUCCESS:
            # TBD: convert "result" into something useful, or at least return the
            # TBD: full DRV_* name of it, so it's easier to interpret.
            raise AndorError('Error number {} calling {} with arguments {}'.format(retval,func,args))
        return result

    def status(self):
        """Get the status of the camera."""
        pass

    def cooler_status(self):
        self._checkSelf()

        self._check_temperature()
        super(AndorCam,self).cooler_status()

    def set_cooler(self, setpoint):
        self._checkSelf()

        self.setpoint = setpoint

        if setpoint is None:
            self.setpoint = 0
            self.safe_call(andor.CoolerOFF)
            self.cooler_status()
            return

        # not safe_call: we need the return value
        result = andor.GetTemperature()
        if result[0] == andor.DRV_TEMPERATURE_OFF:
            self.safe_call(andor.CoolerON)
        andor.SetTemperature(setpoint)

        self.cooler_status()

    def set_binning(self, x, y=None):
        pass

    def Unbinned(self):
        """Set the default binning for this camera/location."""
        self._checkSelf()

        self.safe_call(andor.SetReadMode,4)
        self.safe_call(andor.SetImage,1,1,1,1024,1,1024)

    def _prep_exposure(self):

        self.safe_call(andor.SetAcquisitionMode, 1)
        self.safe_call(andor.SetExposureTime, self.itime)
        # Internal trigger mode is the default: no need to set anything.

    def _start_exposure(self):
        self.safe_call(andor.StartAcquisition)

    def _safe_fetchImage(self,cmd=None):
        """Wrap a call to GetAcquiredData16 in case of bad reads."""
        image = np.zeros((self.height,self.width), dtype='uint16')
        ret = andor.GetAcquiredData16(image)
        if ret != 0:
            print >> sys.stderr, 'IMAGE READ FAILED: %s\n' % (ret)
            if cmd:
                cmd.warn('text="IMAGE READ FAILED: %s"' % (ret))
            return None
        return image

    def _cooler_off(self):
        self.safe_call(andor.CoolerOFF)

    def _check_temperature(self):
        # NOTE: apparently this function doesn't actually exist?
        # SensorTemp, TargetTemp, AmbientTemp, CoolerVolts = self.safe_call(andor.GetTemperatureStatus)

        result = andor.GetTemperature()
        if result[0] == andor.DRV_ACQUIRING:
            # just update the temperature, don't change the status text
            self.ccdTemp = result[1]
        elif result[0] == andor.DRV_ERROR_ACK:
            self.ok = False
            raise AndorError('Communication error when getting temperature!')
        else:
            self.ccdTemp = result[1]
            self.set_status_text(result[0] - andor.DRV_TEMPERATURE_OFF)

    def _shutdown(self):
        andor.ShutDown()
