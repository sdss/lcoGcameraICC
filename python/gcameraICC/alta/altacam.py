__all__ = ['AltaCam']

import pdb

import alta
import numpy as np
import pyfits

import sys
import math
import socket
import time
from traceback import print_exc

class AltaCam(alta.CApnCamera):
    # The CoolerStatus enum values, with slightly shortened names.
    coolerStatusNames = ('Off', 'RampingToSetPoint', 'Correcting', 'RampingToAmbient', 
                         'AtAmbient', 'AtMax', 'AtMin', 'AtSetPoint')

    def __init__(self, hostname):
        """ Connect to an Alta-E at the given IP address and start to initialize it. """

        alta.CApnCamera.__init__(self)

        self.hostname = hostname

        self.ok = False
        self.doInit()
        self.bin_x, self.bin_y = 1,1
        self.x0, self.y0 = 0, 0

    def __del__(self):
        self.CloseDriver()
        
    def __addr2ip(self, addr):
        """ Convert an IP address in string form (192.41.211.69) to an integer. """

        o1, o2, o3, o4 = map(int, addr.split('.'))
        return (o1 << 24) | (o2 << 16) | (o3 << 8) | o4

    def __checkSelf(self):
        """ Single point to call before communicating with the camera. """
        
        if not self.ok:
            raise RuntimeError("Alta camera connection is down")
        
    def doOpen(self):
        """ (Re-)open a connection to the camera at self.hostname. """

        sys.stderr.write("trying to re-open a camera connection....\n")
        try:
            self.CloseDriver()
        except Exception, e:
            sys.stderr.write("failed to re-open a camera connection: %s\n" % (e))
        self.doInit()
    
    def doInit(self):
        """ (Re-)initialize and already open connection. """

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
    
    def coolerStatus(self):
        """ Return a cooler status keywords. """

        self.__checkSelf()

        setpoint = self.read_CoolerSetPoint()
        drive = self.read_CoolerDrive()
        ccdTemp = self.read_TempCCD()
        heatsinkTemp = self.read_TempHeatsink()
        fan = self.read_FanMode()

        #
        status = self.read_CoolerStatus()
        try:
            statusName = self.coolerStatusNames[int(status)]
        except:
            statusName = 'Invalid'

        return "cooler=%0.1f,%0.1f,%0.1f,%0.1f,%d,%s" % (setpoint,
                                                         ccdTemp, heatsinkTemp,
                                                         drive, fan, statusName)
    def setCooler(self, setPoint):
        """ Set the cooler setpoint.

        Args:
           setPoint - degC to use as the TEC setpoint. If None, turn off cooler.

        Returns:
           the cooler status keyword.
        """

        self.__checkSelf()

        if setPoint == None:
            self.write_CoolerEnable(0)
            return

        self.write_CoolerSetPoint(setPoint)
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
        self.__checkSelf()

        w = 1024
        h = 1024
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
        self.__checkSelf()

        w = 1024
        h = 1024
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

    def expose(self, itime, filename=None, cmd=None):
        return self._expose(itime, True, filename, cmd=cmd)
    def dark(self, itime, filename=None, cmd=None):
        return self._expose(itime, False, filename, cmd=cmd)
    def bias(self, filename=None, cmd=None):
        return self._expose(0.0, False, filename, cmd=cmd)
        
    def _expose(self, itime, openShutter, filename, cmd=None):
        """ Take an exposure.

        Args:
            itime        - seconds
            openShutter  - True to open the shutter.
            filename     - a full pathname. If None, the image is returned

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
        image = self.fetchImage()
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

    def fetchImage(self):
        """ Return the current image. """

        # I _think_ this is the right way to get the window size...
        h = self.GetExposurePixelsV()
        w = self.GetExposurePixelsH()

        print >> sys.stderr, "reading image (w,h) = (%d,%d)" % (w,h)
        image = np.ndarray((h,w), dtype='uint16')
        self.FillImageBuffer(image)

        return image

    def getTS(self, t=None, format="%Y-%m-%d %H:%M:%S", zone="Z"):
        """ Return a proper ISO timestamp for t, or now if t==None. """
        
        if t == None:
            t = time.time()
            
        if zone == None:
            zone = ''
            
        return time.strftime(format, time.gmtime(t)) \
               + ".%01d%s" % (10 * math.modf(t)[0], zone)

    def WriteFITS(self, d):
        filename = d['filename']

        hdu = pyfits.PrimaryHDU(d['data'])
        hdr = hdu.header

        hdr.update('IMAGETYP', d['type'])
        hdr.update('EXPTIME',  d['iTime'])
        hdr.update('TIMESYS', 'TAI')
        hdr.update('DATE-OBS', self.getTS(d['startTime']), 'start of integration')
        hdr.update('CCDTEMP', self.read_TempCCD(), 'degrees C')
        hdr.update('FILENAME', filename)
#        hdr.update('FULLX', self.m_ImagingCols)
#        hdr.update('FULLY', self.m_ImagingRows)
        hdr.update('BEGX', self.x0+1)
        hdr.update('BEGY', self.y0+1)
        hdr.update('BINX', self.bin_x)
        hdr.update('BINY', self.bin_y)

        # pyfits now does the right thing with uint16
        hdu.writeto(filename)

        del hdu
        del hdr

if __name__ == "__main__":
    an = AltaCam('sdss-guider.apo.nmsu.edu')
    an.bias('bias.fits')
    del an
