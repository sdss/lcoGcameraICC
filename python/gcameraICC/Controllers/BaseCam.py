"""Base class for controlling guide cameras."""

import abc
import time
import sys
import math
import traceback

import pyfits

class CameraError(RuntimeError):
    def __str__(self):
        return self.__class__.__name__ + ': ' + self.message

class BaseCam(object):
    __metaclass__ = abc.ABCMeta

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

    @abc.abstractmethod
    def coolerStatus(self):
        """Return the cooler status keywords. """
        pass

    @abc.abstractmethod
    def setCooler(self, setPoint):
        """
        Set the cooler temperature setpoint.

        Args:
           setPoint (float): degC to use as the TEC setpoint. If None, turn off cooler.

        Returns:
           the cooler status keyword.
        """
        pass

    @abc.abstractmethod
    def setBinning(self, x, y=None):
        """ Set the readout binning.

        Args:
            x (int): binning factor along rows.

        Kwargs:
            y (int): binning factor along columns. If not passed in, same as x.
        """
        pass

    def expose(self, itime, filename=None, cmd=None):
        return self._expose(itime, True, filename, cmd=cmd)
    def dark(self, itime, filename=None, cmd=None):
        return self._expose(itime, False, filename, cmd=cmd)
    def bias(self, filename=None, cmd=None):
        return self._expose(0.0, False, filename, cmd=cmd)

    def _expose(self, itime, openShutter, filename, cmd=None):
        """
        Take an exposure.

        Args:
            itime (float): exposure duration in seconds
            openShutter (bool): open the shutter.
            filename (str): a full pathname. If None, the image is returned

        Kwargs:
            cmd (Cmdr): Commander for passing response messages.
        """
        self.itime = itime
        self.openShutter = openShutter
        self.filename = filename
        self.cmd = cmd
        self.start = time.time()
        try:
            self._prep_exposure(itime)
            self._take_exposure(itime)
            self._wait_on_exposure()
            self._get_exposure(filename)
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

    def _get_exposure(self, filename):
        """Read the exposure from the chip, process and write to on-disk FITS."""
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

        # fake the data?  if not, then set real filename and write it out
        imageDict['filename'] = filename
        imageDict['data'] = self.image

        if filename:
            try:
                self.WriteFITS(imageDict)
            except:
                traceback.print_exc()

        return imageDict


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

        if filename:
            try:
                self.WriteFITS(d)
            except:
                traceback.print_exc()

        return d

    def getTS(self, t=None, format="%Y-%m-%d %H:%M:%S", zone="Z"):
        """ Return a proper ISO timestamp for t, or now if t==None. """
        
        if t == None:
            t = time.time()
            
        if zone == None:
            zone = ''
            
        return time.strftime(format, time.gmtime(t)) \
               + ".%01d%s" % (10 * math.modf(t)[0], zone)

    def WriteFITS(self, dataDict):
        """
        Write dataDict['data'] to a fits file given by dataDict['filename'].
        """
        filename = dataDict['filename']

        hdu = pyfits.PrimaryHDU(dataDict['data'])
        hdr = hdu.header

        hdr.update('IMAGETYP', dataDict['type'])
        hdr.update('EXPTIME',  dataDict['iTime'])
        hdr.update('TIMESYS', 'TAI')
        hdr.update('DATE-OBS', self.getTS(dataDict['startTime']), 'start of integration')
        hdr.update('CCDTEMP', self.read_TempCCD(), 'degrees C')
        hdr.update('FILENAME', filename)
        hdr.update('BEGX', self.x0+1)
        hdr.update('BEGY', self.y0+1)
        hdr.update('BINX', self.bin_x)
        hdr.update('BINY', self.bin_y)

        hdu.writeto(filename)

        del hdu
        del hdr

