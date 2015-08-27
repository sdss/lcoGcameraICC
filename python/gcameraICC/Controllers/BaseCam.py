"""Base class for controlling guide cameras."""

import abc
import time
import sys
import math
import traceback

import numpy as np

class CameraError(RuntimeError):
    def __str__(self):
        return self.__class__.__name__ + ': ' + self.message

class BaseCam(object):
    __metaclass__ = abc.ABCMeta

    # a tuple enum for responses from your camera's temperature status output
    coolerStatusNames = ('Off','On')

    def __init__(self, hostname="", verbose=True):
        """Connect to a guide camera and initialize it."""

        self.verbose = verbose
        self.cmd = None

        self.hostname = hostname
        if not getattr(self,'camName',None):
            self.camName = 'unknown'

        self.ok = False
        # safely manage errors during initialization, and save any messages
        try:
            self.connect()
        except Exception as e:
            self.handle_error(e)
        self.bin_x, self.bin_y = 1,1 # default binning
        self.x0, self.y0 = 0, 0 # 0 point of the image
        self.ow,self.oh = 24, 0 # overscan size, unbinned pixels

        self.safe_temp = 0 # the temperature where we can safely turn off the camera.

        self.setpoint = None
        self.drive = np.nan
        self.ccdTemp = np.nan
        self.heatsinkTemp = np.nan
        self.fan = np.nan
        self.statusText = 'Unknown'

        # TBD: The stuff below here is only in place for testing.
        # TBD: It should be removed once I've got full tests in place for
        # TBD: CameraCmd and the hardcoded values it has.

        self.m_pvtRoiBinningV, self.m_pvtRoiBinningH = 1,1

    def handle_error(self,e):
        """Handle an error, either outputting to a cmdr, or saving for later."""
        if self.verbose:
            traceback.print_exc()
        if self.cmd is not None:
            msg = str(e)
            msg += '. Last message: {}'.format(self.errMsg)
            self.cmd.error(msg)
        else:
            self.ok = False
            self.errMsg = str(e)

    def _checkSelf(self):
        """Always call this before communicating with the camera."""
        
        if not self.ok:
            msg = "{} camera connection is down".format(self.camName)
            if self.errMsg:
                msg += '. Last message: {}'.format(self.errMsg)
            raise CameraError(msg)

    def doInit(self):
        """Initialize the camera."""
        self.errMsg = "" # clear last error messsage

    def cooler_status(self):
        """Return the cooler status keywords."""
        status = "{},{:.1f},{:.1f},{:.1f},{},{}".format(self.setpoint,
                                                        self.ccdTemp, self.heatsinkTemp,
                                                        self.drive, self.fan, self.statusText)
        return "cooler={}".format(status)

    def set_status_text(self,value):
        """Set self.statusText from coolerStusNames, safely."""
        try:
            self.statusText = self.coolerStatusNames[value]
        except:
            self.statusText = 'Invalid'

    @abc.abstractmethod
    def set_cooler(self, setpoint):
        """
        Set the cooler temperature setpoint.

        Args:
           setpoint (float): degC to use as the TEC setpoint. If None, turn off cooler.

        Returns:
           the cooler status keyword.
        """
        pass

    @abc.abstractmethod
    def set_binning(self, x, y=None):
        """ Set the readout binning.

        Args:
            x (int): binning factor along rows.

        Kwargs:
            y (int): binning factor along columns. If not passed in, same as x.
        """
        pass

    def expose(self, itime, cmd=None):
        return self._expose(itime, True, cmd=cmd)
    def dark(self, itime, cmd=None):
        return self._expose(itime, False, cmd=cmd)
    def bias(self, cmd=None):
        return self._expose(0.0, False, cmd=cmd)

    def _expose(self, itime, openShutter, cmd=None):
        """
        Take an exposure and return a dict of the image and related data.

        Args:
            itime (float): exposure duration in seconds
            openShutter (bool): open the shutter.

        Kwargs:
            cmd (Cmdr): Commander for passing response messages.

        """
        self._checkSelf()

        self.itime = itime
        self.openShutter = openShutter
        self.cmd = cmd
        self.start = time.time()
        try:
            self._prep_exposure(itime)
            self._take_exposure(itime)
            self._wait_on_exposure()
            self._get_exposure()
        except Exception as e:
            self.handle_error(e)

    @abc.abstractmethod
    def _prep_exposure(self, itime):
        """Prep for an exposure to start."""
        pass

    @abc.abstractmethod
    def _start_exposure(self, itime):
        """Start the exposure acquisition."""
        pass

    def _wait_on_exposure(self):
        """
        Wait for an exposure to finish.
        First, wait most of the exposure time via sleep, then watch more closely.
        """

        if self.itime > self.t_wait:
            time.sleep(self.itime - self.t_wait)

        while self.exposure():
            time.sleep(0.1)

    def _get_exposure(self):
        """Read the exposure and return a dict describing it."""
        imageDict = {}

        self._safe_fetchImage()
        if self.openShutter:
            fitsType = 'obj'
        elif self.itime == 0:
            fitsType = 'zero'
        else:
            fitsType = 'dark'

        imageDict['iTime'] = self.itime
        imageDict['type'] = fitsType
        imageDict['startTime'] = self.start

        imageDict['data'] = self.image

        return imageDict

    @abc.abstractmethod
    def _cooler_off(self):
        """Turn off the camera's cooler."""
        pass
    @abc.abstractmethod
    def _check_temperature(self):
        """Check the camera's temperature, but don't send keywords."""
        pass
    @abc.abstractmethod
    def _shutdown(self):
        """Command the camera to shut off."""
        pass

    def shut_down(self):
        """
        Safely shut down the camera, by turning off cooling, waiting for the
        temperature to stabilize, and then shutting down the connection and camera.
        """
        self._checkSelf()

        self._cooler_off()
        # check temperature to within half a degree
        while not np.isclose(self.ccdTemp, self.safe_temp, atol=0.5):
            self._check_temperature()
        self._shutdown()

    def _expose_old(self, itime, openShutter, filename, cmd=None, recursing=False):
        """
        Take an exposure.

        Args:
            itime (float): exposure duration in seconds
            openShutter (bool): open the shutter.
            filename (str): a full pathname. If None, the image is returned
            recursing (bool): have we called ourself? To prevent recursing more than once.

        Returns:
            dict - type:     FITS IMAGETYP
                   iTime:    integration time
                   filename: the given filename, or None
                   data:     the image data as an ndarray
        """

        self._checkSelf()

        # Is the camera alive and flushing?
        for i in range(2):
            state = self.read_ImagingStatus()
            if state == 4:
                break;
            # print "starting state=%d, RESETTING" % (state)
            self.ResetSystem()

        if state != 4 or state < 0: 
            raise RuntimeError("bad imaging state=%d; please try gcamera reconnect before restarting the ICC" % (state))

        d = {}

        # Block while we expose. But sleep if we have to wait a long time.
        # TBD: And what is the flush time of this device?
        start = time.time()
        if cmd:
            cmd.respond('exposureState="integrating",%0.1f,%0.1f' % (itime, itime))
        self.prep_expose()
        self.expose(itime, openShutter)
        if itime > 0.25:
            time.sleep(itime - 0.2)

        # We are close to the end of the exposure. Start polling the camera
        for i in range(50):
            now = time.time()
            state = self.read_ImagingStatus()
            if state < 0:
                raise RuntimeError("bad state=%d; please try gcamera reconnect before restarting the ICC" % (state))
            if state == 3:
                break
            print "state=%d time=%0.2f waiting to read" % (state, now - (start + itime))
            time.sleep(0.1)

        if openShutter:
            fitsType = 'obj'
        elif itime == 0:
            fitsType = 'zero'
        else:
            fitsType = 'dark'

        if cmd:
            cmd.respond('exposureState="reading",2.0,2.0')
        t0 = time.time()
        image = self.fetchImage(cmd=cmd)
        if image == None:
            if not recursing:
                return self._expose(itime, openShutter, filename, cmd=cmd, recursing=True)
            raise RuntimeError("failed to read image from camera; please try gcamera reconnect before restarting the ICC")
        t1 = time.time()

        state = self.read_ImagingStatus()
        print >> sys.stderr, "state=%d readoutTime=%0.2f" % (state,t1-t0)

        d['iTime'] = itime
        d['type'] = fitsType
        d['startTime'] = start

        # fake the data?  if not, then set real filename and write it out
        d['filename'] = filename
        d['data'] = image

        return d

    def getTS(self, t=None, format="%Y-%m-%d %H:%M:%S", zone="Z"):
        """ Return a proper ISO timestamp for t, or now if t==None. """
        
        if t == None:
            t = time.time()
            
        if zone == None:
            zone = ''
            
        return time.strftime(format, time.gmtime(t)) \
               + ".%01d%s" % (10 * math.modf(t)[0], zone)
