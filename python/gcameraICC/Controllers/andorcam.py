"""Python OO interface for controlling an Andor Ikon camera."""
import sys
import numpy as np

import BaseCam
import andor

class AndorError(BaseCam.CameraError):
    pass

class AndorCam(BaseCam.BaseCam):
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

    def coolerStatus(self):
        pass

    def setCooler(self, setPoint):
        pass

    def setBinning(self, x, y=None):
        pass

    def Unbinned(self):
        """Set the default binning for this camera/location."""

        self.safe_call(andor.SetReadMode,4)
        self.safe_call(andor.SetImage,1,1,1,1024,1,1024)

    def _prep_exposure(self):
        self.safe_call(andor.SetAcquisitionMode, 1)
        self.safe_call(andor.SetExposureTime, self.itime)
        # Internal trigger mode is the default: no need to set anything.

    def _start_exposure(self):
        self.safe_call(andor.StartAcquisition)

    def _safe_fetchImage(self,h,w,cmd=None):
        """Wrap a call to GetAcquiredData16 in case of bad reads."""
        image = np.zeros((h,w), dtype='uint16')
        ret = andor.GetAcquiredData16(image)
        if ret != 0:
            print >> sys.stderr, 'IMAGE READ FAILED: %s\n' % (ret)
            if cmd:
                cmd.warn('text="IMAGE READ FAILED: %s"' % (ret))
            return None
        return image
