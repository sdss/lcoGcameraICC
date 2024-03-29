"""Python OO interface for controlling an Apogee Alta camera."""

__all__ = ['AltaCam']

import alta
import numpy as np

import sys
import socket
import time
from traceback import print_exc

import BaseCam

class AltaCam(BaseCam.BaseCam,alta.CApnCamera):
    # The CoolerStatus enum values, with slightly shortened names.
    coolerStatusNames = ('Off', 'RampingToSetPoint', 'Correcting', 'RampingToAmbient', 
                         'AtAmbient', 'AtMax', 'AtMin', 'AtSetPoint')

    def __init__(self, hostname=""):
        """ Connect to an Alta-E at the given IP address and start to initialize it. """

        self.camName = 'Apogee Alta'
        self.hostname = hostname

        alta.CApnCamera.__init__(self)
        BaseCam.BaseCam.__init__(self)

        self.IDLE = alta.DRV_IDLE

        # TBD: this is a guess
        self.shutter_time = 5 # in milliseconds
        self.read_time = 2.0


    def __del__(self):
        self.CloseDriver()

    def __addr2ip(self, addr):
        """ Convert an IP address in string form (192.41.211.69) to an integer. """

        o1, o2, o3, o4 = map(int, addr.split('.'))
        return (o1 << 24) | (o2 << 16) | (o3 << 8) | o4
        
    def doOpen(self):
        """ (Re-)open a connection to the camera at self.hostname. """

        sys.stderr.write("trying to re-open a camera connection....\n")
        try:
            self.CloseDriver()
        except Exception, e:
            sys.stderr.write("failed to re-open a camera connection: %s\n" % (e))
        self.doInit()
    
    def connect(self):
        """ (Re-)initialize an already open connection. """

        ip = socket.gethostbyname(self.hostname)
        ipAddr = self.__addr2ip(ip)
        count = 5
        while count > 0:
            self.ok = self.InitDriver(ipAddr, 80, 0)
            if self.ok:
                break
            self.CloseDriver()
            count -= 1
            time.sleep(1)

        self.__checkSelf()

        # Turn off LEDs
        self.write_LedMode(0)

        return self.ok
    
    def cooler_status(self):
        """ Return the cooler status keywords. """

        self.__checkSelf()

        self.setpoint = self.read_CoolerSetPoint()
        self.drive = self.read_CoolerDrive()
        self.ccdTemp = self.read_TempCCD()
        self.heatsinkTemp = self.read_TempHeatsink()
        self.fan = self.read_FanMode()

        #
        status = self.read_CoolerStatus()
        try:
            self.statusText = self.coolerStatusNames[int(status)]
        except:
            self.statusText = 'Invalid'

        super(AltaCam,self).cooler_status()

    def setCooler(self, setpoint):
        """ Set the cooler setpoint.

        Args:
           setpoint - degC to use as the TEC setpoint. If None, turn off cooler.

        Returns:
           the cooler status keyword.
        """

        self.__checkSelf()

        if setpoint == None:
            self.write_CoolerEnable(0)
            return

        self.write_CoolerSetPoint(setpoint)
        self.write_CoolerEnable(1)

        return self.coolerStatus()

    def setFan(self, level):
        """ Set the fan power.

        Args:
           level - 0=Off, 1=low, 2=medium, 3=high.
        """

        self.__checkSelf()

        if type(level) != type(1) or level < 0 or level > 3:
            raise RuntimeError("setFan level must be an integer 0..3")

        self.write_FanMode(level)

    
    def setBinning(self, x, y=None):
        """ Set the readout binning.

        Args:
            x = binning factor along rows.
            y ? binning factor along columns. If not passed in, same as x.
        """

        self.__checkSelf()

        if y == None:
            y = x

        self.write_RoiBinningH(x)
        self.write_RoiBinningV(y)
        self.bin_x = x
        self.bin_y = y

    def setWindow(self, x0, y0, x1, y1):
        """ Set the readout window, in binned pixels starting from 0,0. """

        self.__checkSelf()

        self.x0 = x0
        self.y0 = y0
        
        self.write_RoiPixelsH(x1 - x0)
        self.write_RoiPixelsV(y1 - y0)
        self.write_RoiStartX(x0 * self.bin_x)
        self.write_RoiStartY(y0 * self.bin_y)
        
    def setBOSSFormat(self):
        """Set up for 2x2 binning."""
        self.__checkSelf()

        w = 1024
        h = 1024
        # defines the overscan regions in each dimension
        ow = 24
        oh = 0
        binx = 2
        biny = 2

        self.write_RoiBinningH(binx)
        self.write_RoiBinningV(biny)

        self.write_RoiPixelsH((w + ow)/binx)
        self.write_RoiPixelsV((h + oh)/biny)
        self.write_RoiStartX(1)
        self.write_RoiStartY(1)
        oc = self.read_OverscanColumns()
        self.write_DigitizeOverscan(1)

    def setFlatFormat(self):
        """Set up for unbinned images."""
        self.__checkSelf()

        w = 1024
        h = 1024
        # defines the overscan regions in each dimension
        ow = 24
        oh = 0
        binx = 1
        biny = 1

        self.write_RoiBinningH(binx)
        self.write_RoiBinningV(biny)

        self.write_RoiPixelsH((w + ow)/binx)
        self.write_RoiPixelsV((h + oh)/biny)
        self.write_RoiStartX(1)
        self.write_RoiStartY(1)
        oc = self.read_OverscanColumns()
        self.write_DigitizeOverscan(1)
        
    def _expose(self, itime, openShutter, filename, cmd=None, recursing=False):
        """ Take an exposure.

        Args:
            itime        - seconds
            openShutter  - True to open the shutter.
            filename     - a full pathname. If None, the image is returned
            recursing    - have we called ourself? To prevent recursing more than once.

        Returns:
            dict         - type:     FITS IMAGETYP
                           iTime:    integration time
                           filename: the given filename, or None
                           data:     the image data as an ndarray
        """

        self.__checkSelf()

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
        # And what is the flush time of this device?
        start = time.time()
        if cmd:
            cmd.respond('exposureState="integrating",%0.1f,%0.1f' % (itime, itime))
        self.Expose(itime, openShutter)
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
            # print "state=%d time=%0.2f waiting to read" % (state, now - (start + itime))
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
                print_exc()

        return d

    def _safe_fetchImage(self,h,w,cmd=None):
        """Wrap a call to FillImageBuffer in case of bad reads."""
        image = np.zeros((h,w), dtype='uint16')
        ret = self.FillImageBuffer(image)
        if ret != 0:
            print >> sys.stderr, 'IMAGE READ FAILED: %s\n' % (ret)
            if cmd:
                cmd.warn('text="IMAGE READ FAILED: %s"' % (ret))
            return None
        return image
    
    def fetchImage(self, cmd=None):
        """ Return the current image. """

        # I _think_ this is the right way to get the window size...
        h = self.GetExposurePixelsV()
        w = self.GetExposurePixelsH()

        print >> sys.stderr, "reading image (w,h) = (%d,%d)" % (w,h)
        # Sometimes this fails, in a potentially recoverable way.
        image = self._safe_fetchImage(h,w,cmd=cmd)
        if image is None:
            image = self._safe_fetchImage(h,w,cmd=cmd)
        return image
