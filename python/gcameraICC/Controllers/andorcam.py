"""Python OO interface for controlling an Andor Ikon camera."""

import BaseCam
import andor

class AndorException(Exception):
    pass

class AndorCam(BaseCam.BaseCam):
    def __init__(self, hostname):
        """ Connect to an Alta-E at the given IP address and start to initialize it. """

        BaseCam.BaseCam.__init__(self,hostname)

        self.camName = "Andor Ikon"

    def status(self):
        """Get the status of the camera."""

    def _parse_result(self,result):
        """Parse the return value of an Andor API function."""

    def safe_call(self,func,*args):
        """
        Call func with args, check return for success,
        raise descriptive  exception on failure.
        """
        result = func(*args)
        if result != andor.DRV_SUCCESS:
            # TBD: convert "result" into something useful, or at least return the
            # TBD: full DRV_* name of it, so it's easier to interpret.
            raise AndorException('Error {} calling {} with arguments {}'.format(result,func,args))

    def Unbinned(self):
        """Set the default binning for this camera/location."""

        self.safe_call(andor.SetReadMode,4)
        self.safe_call(andor.SetImage,1,1,1,1024,1,256)

    def expose(self,itime):
        self.StartAcquisition()

    def prep_expose(self,itime):
        """Prep for an exposure."""
        self.safe_call(andor.SetAcquisitionMode, 1)
        self.safe_call(andor.SetExposureTime, itime)
        # Internal trigger mode is the default: no need to set anything.
