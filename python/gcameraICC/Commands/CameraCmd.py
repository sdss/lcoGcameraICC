#!/usr/bin/env python

""" CameraCmd.py -- wrap camera functions. """

import glob
import math
import os
import re
import time

import pyfits
import numpy as np

import opscore.protocols.keys as opsKeys
import opscore.protocols.types as types

import RO.Astro.Tm.MJDFromPyTuple as astroMJD

from opscore.utility.qstr import qstr

import actorcore.utility.fits as actorFits
import actorcore.utility.svn

class CameraCmd(object):
    """ Wrap camera commands.  """

    def __init__(self, actor):
        self.actor = actor
        self.cam = actor.name[:4]
        self.version = actorcore.utility.svn.simpleVersionName(actor.headURL)

        # ecamera files should not be gzipped, to make processing in IRAF easier.
        if 'ecamera' in actor.name:
            self.doCompress = False
            self.ext = ''
        else:
            self.doCompress = True
            self.ext = '.gz'

        self.dataRoot = self.actor.config.get(self.actor.name, 'dataRoot')
        self.filePrefix = self.actor.config.get(self.actor.name, 'filePrefix')

        # We track the names of any currently valid dark and flat files.
        self.darkFile = None
        self.darkTemp = 99.9
        self.flatFile = None
        self.flatCartridge = -1

        self.simRoot = None
        self.simSeqno = 1

        self.resync(actor.bcast, doFinish=False)

        self.keys = opsKeys.KeysDictionary("gcamera_camera", (1, 1),
                                           opsKeys.Key("time", types.Float(), help="exposure time."),
                                           opsKeys.Key("mjd", types.String(), help="MJD for simulation sequence"),
                                           opsKeys.Key("cartridge", types.Int(), help="cartridge number; used to bind flats to images."),
                                           opsKeys.Key("seqno", types.Int(),
                                                       help="image number for simulation sequence."),
                                           opsKeys.Key("filename", types.String(),
                                                       help="the filename to write to"),
                                           opsKeys.Key("stack", types.Int(), help="number of exposures to take and stack."),
                                           opsKeys.Key("temp", types.Float(), help="camera temperature setpoint."),
                                           opsKeys.Key("n", types.Int(), help="number of times to loop status queries."),
                                           )

        self.vocab = [
            ('ping', '', self.pingCmd),
            ('status', '', self.status),
            ('deathStatus', '<n>', self.deathStatus),
            ('setBOSSFormat', '', self.setBOSSFormat),
            ('setFlatFormat', '', self.setFlatFormat),
            ('simulate', '(off)', self.simulateOff),
            ('simulate', '<mjd> <seqno>', self.simulateFromSeq),
            ('setTemp', '<temp>', self.setTemp),
            ('expose', '<time> [<cartridge>] [<filename>] [<stack>] [force]', self.expose),
            ('dark', '<time> [<filename>] [<stack>]', self.expose),
            ('flat', '<time> [<cartridge>] [<filename>] [<stack>]', self.expose),
            ('reconnect', '', self.reconnect),
            ('resync', '', self.resync),
            ('shutdown', '[force]', self.shutdown)
            ]

    def pingCmd(self, cmd):
        """ Top-level "ping" command handler, responds if the actor is alive."""

        cmd.finish('text="Pong."')

    def resync(self, cmd, doFinish=True):
        """ Resynchronize with the current guider frame numbers and find the correct dark and flat. """
        try:
            dirname, filename = self.genNextRealPath(cmd)
            self.findDarkAndFlat(dirname, self.seqno)
        except Exception, e:
            cmd.fail('text="failed to set directory, or dark and flat names: %s' % (e))

        cmd.respond('text="set dark, flat to %s,%s, cart=%d"' % (self.darkFile, self.flatFile,
                                                                 self.flatCartridge))
        self.status(cmd, doFinish=doFinish)

    def status(self, cmd, doFinish=True):
        """ Generate all status keywords. """

        self.actor.sendVersionKey(cmd)

        try:
            cam = self.actor.cam
        except:
            cam = None
        cmd.respond("stack=1")
        if cam:
            cmd.respond('cameraConnected=%s' % (cam != None))
            cmd.respond('binning=%d,%d' % (cam.m_pvtRoiBinningV, cam.m_pvtRoiBinningH))
            cmd.respond('dataDir=%s; nextSeqno=%d' % (self.dataDir, self.seqno))
            cmd.respond('flatCartridge=%s; darkFile=%s; flatFile=%s' % \
                            (self.flatCartridge, self.darkFile, self.flatFile))
            self.coolerStatus(cmd, doFinish=False)
        else:
            cmd.warn('cameraConnected=%s' % (cam != None))

        self.sendSimulatingKey(cmd.inform)

        if doFinish:
            cmd.finish()

    def deathStatus(self, cmd, doFinish=True):
        """ Generate some status keywords, n times (default=1). Useful for continuously monitoring the state of the gcamera. """

        cmdKeys = cmd.cmd.keywords
        nloops = cmdKeys['n'].values[0]

        self.actor.sendVersionKey(cmd)

        cam = self.actor.cam
        if cam and nloops > 0:
            self.coolerStatus(cmd, doFinish=False)
            self.actor.callCommand("deathStatus n=%d" % (nloops-1))
        else:
            cmd.warn('cameraConnected=%s' % (cam != None))

        if doFinish:
            cmd.finish()

    def findFileMatch(self, files, seqno):
        """ Return the filename in the list whose sequence is closest below the given seqno. """

        files = files[:]
        names = [os.path.basename(f) for f in files]
        names = [n.split('-')[1] for n in names]
        names = [int(n.split('.')[0]) for n in names]
        names.sort()
        files.sort()
        names.reverse()
        files.reverse()

        match = None
        for i in range(len(names)):
            if names[i] < seqno:
                return files[i]
                break

        return match

    def findDarkAndFlat(self, dirname, forSeqno):
        """
        Find most recent dark and flats images in the given directory.
        Set .darkFile, .flatFile, .flatCartridge
        """

        darkFiles = glob.glob(os.path.join(dirname, 'dark-*'))
        darkNote = self.findFileMatch(darkFiles, forSeqno)
        if darkNote:
            m = re.search('.*/dark-(\d+)\.dat$', darkNote)
            if m:
                darkSeq = int(m.group(1))
            else:
                darkSeq = 0
        else:
            darkSeq = 0

        self.darkFile = os.path.join(dirname, 'gimg-%04d.fits%s' % (darkSeq,self.ext)) if darkSeq else None

        flatFiles = glob.glob(os.path.join(dirname, 'flat-*'))
        flatNote = self.findFileMatch(flatFiles, forSeqno)
        if flatNote:
            m = re.search('.*/flat-(\d+)-(\d+)\.dat$', flatNote)
            if m:
                flatSeq, flatCartridge = int(m.group(1)), int(m.group(2))
            else:
                flatSeq, flatCartridge = 0, -1
        else:
            flatSeq, flatCartridge = 0, -1

        self.flatFile = os.path.join(dirname, 'gimg-%04d.fits%s' % (flatSeq,self.ext)) if flatSeq else None
        self.flatCartridge = flatCartridge

    def setBOSSFormat(self, cmd, doFinish=True):
        """ Configure the camera for guiding images. """

        self.actor.cam.setBOSSFormat()
        self.status(cmd, doFinish=False)

        if doFinish:
            cmd.finish()

    def setFlatFormat(self, cmd, doFinish=True):
        """ Configure the camera for flat images. """

        self.actor.cam.setFlatFormat()
        self.status(cmd, doFinish=False)

        if doFinish:
            cmd.finish()

    def reconnect(self, cmd, doFinish=True):
        """ (re-)connect to the camera, and print status. """

        self.actor.connectCamera()
        self.status(cmd, doFinish=False)

        if doFinish:
            cmd.finish()

    def sendSimulatingKey(self, cmdFunc):
        state = 'On' if self.simRoot else 'Off'
        resp = 'simulating=%s,%s,%d' % (state, self.simRoot, self.simSeqno)
        cmdFunc(resp)

    def simulateOff(self, cmd):
        """ Turn off gcamera simulation: stop reading image files from disk. """

        self.sendSimulatingKey(cmd.finish)
        self.simRoot = None

    def simulateFromSeq(self, cmd):
        """ define a MJD+image number to start reading image files from.

        CmdArgs:
            mjd     - a string indicating the directory under the data root.
            seqno   - an integer indicating which image to start returning.
        """

        cmdKeys = cmd.cmd.keywords
        mjd = cmdKeys['mjd'].values[0]
        seqno = cmdKeys['seqno'].values[0]

        simRoot = os.path.join(self.dataRoot, str(mjd))
        if not os.path.isdir(simRoot):
            cmd.fail('text="%s is not an existing directory"' % (simRoot))
            return

        simPath = os.path.join(simRoot, self.genFilename(seqno)+self.ext)
        if not os.path.isfile(simPath):
            cmd.fail('text="%s is not an existing file"' % (simPath))
            return

        self.simRoot = simRoot
        self.simSeqno = seqno

        self.sendSimulatingKey(cmd.finish)

    def genFilename(self, seqno):
        return '%s-%04d.fits' % (self.filePrefix, seqno)

    def genNextRealPath(self, cmd):
        """ Return the next filename to use. Exposures are numbered from 1 for each night. """

        gimgPattern = '^gimg-(\d{4})\.fits*'

        mjd = astroMJD.mjdFromPyTuple(time.gmtime())
        fmjd = str(int(mjd + 0.3))

        dataDir = os.path.join(self.dataRoot, fmjd)
        if not os.path.isdir(dataDir):
            cmd.respond('text="creating new directory %s"' % (dataDir))
            os.mkdir(dataDir,0775)
        self.dataDir = dataDir

        imgFiles = glob.glob(os.path.join(dataDir, 'gimg-*.fits*'))
        imgFiles.sort()
        if len(imgFiles) == 0:
            seqno = 1
        else:
            lastFile = os.path.basename(imgFiles[-1])
            m = re.match(gimgPattern, lastFile)
            if not m:
                cmd.warn('text="no files matching %s in %s (last=%s)"' % (gimgPattern,
                                                                          dataDir, lastFile))
                seqno = 1
            else:
                seqno = int(m.group(1)) + 1

        self.seqno = seqno
        return dataDir, self.genFilename(seqno)

    def genNextSimPath(self, cmd):
        """ Return the next filename to use.

        Returns:
          dirname     - the full path of the file
          filename    - the name of the disk file.
         """

        filename = self.genFilename(self.simSeqno)
        self.simSeqno += 1

        pathname = os.path.join(self.simRoot, filename)
        if glob.glob(pathname+'*'):#os.path.isfile(pathname):
            return self.simRoot, filename
        else:
            return None, None

    def getNextPath(self, cmd):
        if self.simRoot:
            return self.genNextSimPath(cmd)
        else:
            return self.genNextRealPath(cmd)

    def exposeStack(self, itime, stack, cmd, expType='expose'):
        """ Return a single exposure dict median-combined from stack * itime integrations.

        Note the unwarranted chumminess with the camera data, compounded by not wanting to push
        non-u2 data up to the guider. So we pretend that we took a single itime exposure, and
        scale the pixels back into a pretend itime.

        expType: 'dark' or 'expose'
        """
        if expType == 'expose':
            exposeCmd = self.actor.cam.expose
        elif expType == 'dark':
            exposeCmd = self.actor.cam.dark
        else:
            raise ValueError('Invalid gcamera exposure type in exposeStack: %s'%expType)

        imDict = exposeCmd(itime, cmd)

        if stack > 1:
            imList = [imDict['data'],]
            for i in range(2, stack+1):
                cmd.inform('text="taking stacked integration %d of %d"' % (i, stack))
                imDict1 = exposeCmd(itime, cmd)
                imList.append(imDict1['data'])
            imData = np.median(imList,axis=0).astype('u2')
            imDict['data'] = imData
            imDict['stack'] = stack
            imDict['exptimen'] = itime*stack

        return imDict

    def expose(self, cmd, doFinish=True):
        """ expose/dark/flat - take an exposure

        dark: take a dark frame and set it as the currently active dark.
        flat: take a flat frame and set it as the currently active flat.

        Args:
            time=SEC            - number of seconds per exposure.
            [filename=FILENAME] - write frame to this file (full path).
            [cartridge=N]       - set/override active cartridge number.
            [stack=N]           - stack this many exposures (total time: stack*time).
        """

        expType = cmd.cmd.name
        cmdKeys = cmd.cmd.keywords
        itime = cmdKeys['time'].values[0]
        if 'filename' in cmdKeys:
            pathname = cmdKeys['filename'].values[0]
        else:
            dirname, filename = self.getNextPath(cmd)
            pathname = os.path.join(dirname, filename)

        stack = cmdKeys['stack'].values[0] if 'stack' in cmdKeys else 1

        if stack > 1 and itime > 8 and expType != 'dark':
            cmd.warn('text="Do you really mean to stack %0.1fs exposures?"' % (itime))

        if self.simRoot:
            if not filename:
                self.sendSimulatingKey('Off', cmd.respond)
                self.simRoot = False
                cmd.fail('exposureState="done",0.0,0.0; text="Ran off the end of the simulated data"')
                return
            else:
                cmd.warn('text="Simulating a %ds exposure"' % itime)
                time.sleep(itime)
        else:
            if expType == 'flat':
                self.setFlatFormat(cmd, doFinish=False)
            else:
                self.setBOSSFormat(cmd, doFinish=False)

            self.findDarkAndFlat(dirname, self.seqno)
            cmd.diag('text="found flat=%s dark=%s cart=%s"' % (self.flatFile,
                                                               self.darkFile,
                                                               self.flatCartridge))
            cmd.respond("stack=%d" % (stack))
            doForce = 'force' in cmd.cmd.keywords
            try:
                if expType == 'dark':
                    imDict = self.exposeStack(itime, stack, cmd=cmd, expType='dark')
                else:
                    # We need to know about the dark to put it in the header.
                    if not self.darkFile:
                        if doForce:
                            cmd.warn('text="no available dark frame for '
                                     'this MJD, but overriding because '
                                     'force=True"')
                        else:
                            cmd.fail('exposureState="failed",0.0,0.0; text="no available dark frame for this MJD."')
                            return

                    if expType != 'flat' and not self.flatFile and not doForce:
                        if doForce:
                            cmd.warn('text="no available flat frame for '
                                     'this MJD, but overriding because '
                                     'force=True"')
                        else:
                            cmd.fail('exposureState="failed",0.0,0.0; text="no available flat frames for this MJD."')
                            return

                    imDict = self.exposeStack(itime, stack, cmd=cmd)
            except Exception, e:
                cmd.warn('exposureState="failed",0.0,0.0')
                cmd.fail('text=%s' % (qstr("exposure failed: %s" % e)))
                return

            imDict['type'] = 'object' if (expType == 'expose') else expType
            imDict['filename'] = pathname
            imDict['ccdTemp'] = self.actor.cam.ccdTemp
            if expType == 'expose':
                imDict['flatFile'] = self.flatFile
            if expType != "dark":
                imDict['darkFile'] = self.darkFile

            self.writeFITS(imDict,cmd)

        if expType == 'dark':
            self.darkFile = pathname + self.ext
            self.darkTemp = self.actor.cam.ccdTemp
            if not self.simRoot:
                darknote = open(os.path.join(dirname, 'dark-%04d.dat' % (self.seqno)), 'w+')
                darknote.write('filename=%s\n' % (self.darkFile))
                darknote.write('temp=%0.2f\n' % (self.darkTemp))
                darknote.close()
                cmd.respond('text="setting dark file for %0.1fC: %s"' % (self.darkTemp, self.darkFile))

        elif expType == 'flat':
            self.flatFile = pathname + self.ext
            self.flatCartridge = cmdKeys['cartridge'].values[0] if ('cartridge' in cmdKeys) else 0
            self.setBOSSFormat(cmd, doFinish=False)
            if not self.simRoot:
                flatnote = open(os.path.join(dirname, 'flat-%04d-%02d.dat' % (self.seqno, self.flatCartridge)), 'w+')
                flatnote.write('filename=%s\n' % (self.flatFile))
                flatnote.write('cartridge=%d\n' % (self.flatCartridge))
                flatnote.close()
                cmd.respond('text="setting flat file for cartridge %d: %s"' % (self.flatCartridge, self.flatFile))

        cmd.finish('exposureState="done",0.0,0.0; filename=%s' % (os.path.join(dirname, filename+self.ext)))

    def coolerStatus(self, cmd, doFinish=True):
        """ Generate gcamera cooler status keywords. Does NOT finish the command. """

        if self.actor.cam:
            coolerStatus = self.actor.cam.cooler_status()
            cmd.respond(coolerStatus)

        if doFinish:
            cmd.finish()

    def setTemp(self, cmd, doFinish=True):
        """ Adjust the cooling loop.

        Args:
           temp - the new setpoint, or None if the loop should be turned off. """

        cmdKeys = cmd.cmd.keywords
        temp = cmdKeys['temp'].values[0]

        cmd.inform('text="setting camera cooler setpoint to %0.1f degC"' % (temp))

        self.actor.cam.set_cooler(temp)
        self.coolerStatus(cmd, doFinish=doFinish)

    def ping(self, cmd):
        """ Top-level "ping" command handler. Query all the controllers for liveness/happiness. """

        cmd.finish('text="Pong."')

    def shutdown(self, cmd):
        """"Shutdown the camera connection safely (letting it warm up slowly): you must supply force."""
        if 'force' not in cmd.cmd.keywords:
            cmd.fail("text='You must specify force when attempting to shut down the guide camera.'")
            return

        self.actor.cam.shutdown(cmd)
        self.status(cmd, doFinish=True)

    def getTS(self, t=None, format="%Y-%m-%d %H:%M:%S", zone="Z"):
        """ Return a proper ISO timestamp for t, or now if t==None. """

        if t == None:
            t = time.time()

        if zone == None:
            zone = ''

        return time.strftime(format, time.gmtime(t)) \
               + ".%01d%s" % (10 * math.modf(t)[0], zone)

    def addPixelWcs(self, header, wcsName=""):
            """Add a WCS that sets the bottom left pixel's centre to be (0.5, 0.5)"""
            header.update("CRVAL1%s" % wcsName, 0, "(output) Column pixel of Reference Pixel")
            header.update("CRVAL2%s" % wcsName, 0, "(output) Row pixel of Reference Pixel")
            header.update("CRPIX1%s" % wcsName, 0.5, "Column Pixel Coordinate of Reference")
            header.update("CRPIX2%s" % wcsName, 0.5, "Row Pixel Coordinate of Reference")
            header.update("CTYPE1%s" % wcsName, "LINEAR", "Type of projection")
            header.update("CTYPE1%s" % wcsName, "LINEAR", "Type of projection")
            header.update("CUNIT1%s" % wcsName, "PIXEL", "Column unit")
            header.update("CUNIT2%s" % wcsName, "PIXEL", "Row unit")

    def writeFITS(self, imDict, cmd):
        """ Write the FITS frame for the current image. """
        filename = imDict['filename']
        directory,basename = os.path.split(filename)
        darkFile = imDict.get('darkFile', "")
        flatFile = imDict.get('flatFile', "")

        hdu = pyfits.PrimaryHDU(imDict['data'])
        hdr = hdu.header
        hdr.update('V_'+self.cam.upper(), self.version)
        hdr.update('IMAGETYP', imDict['type'])
        hdr.update('EXPTIME',  imDict['iTime'], 'exposure time of single integration')
        hdr.update('TIMESYS', 'TAI')
        hdr.update('DATE-OBS', self.getTS(imDict['startTime']), 'start of integration')
        hdr.update('CCDTEMP', imDict.get('ccdTemp', 999.0), 'degrees C')
        hdr.update('FILENAME', filename)
        hdr.update("OBJECT", os.path.splitext(os.path.split(filename)[1])[0], "")
        if imDict['type'] != "dark" and darkFile:
            hdr.update('DARKFILE', darkFile)
            hdr.update('FLATCART', self.flatCartridge)
        if imDict['type'] == 'object' and flatFile:
            hdr.update('FLATFILE', flatFile)

        if 'stack' in imDict:
            hdr.update('STACK', imDict['stack'], 'number of stacked integrations')
            hdr.update('EXPTIMEN', imDict['exptimen'], 'exposure time for all integrations')

#        hdr.update('FULLX', self.m_ImagingCols)
#        hdr.update('FULLY', self.m_ImagingRows)
        hdr.update('BEGX', imDict.get('begx', 0))
        hdr.update('BEGY', imDict.get('begy', 0))
        hdr.update('BINX', imDict.get('binx', self.actor.cam.binning))
        hdr.update('BINY', imDict.get('biny', self.actor.cam.binning))

        hdr.update('GAIN',
                   self.actor.config.getfloat('camera', 'ccdGain'),
                   'The CCD gain.')
        hdr.update('READNOIS',
                   self.actor.config.getfloat('camera', 'readNoise'),
                   'The CCD read noise [ADUs].')
        hdr.update('PIXELSC',
                   self.actor.config.getfloat('camera', 'pixelScale'),
                   'The scale of an unbinned pixel on the sky [arcsec]')

        self.addPixelWcs(hdr)

        if self.actor.location == "LCO":
            lcoTCCCards = actorFits.lcoTCCCards(self.actor.models, cmd=cmd)
            actorFits.extendHeader(cmd, hdr, lcoTCCCards)
        else:
            # add in TCC and MCP cards, so the guider images have position and
            # lamp/FFS state recorded.
            tccCards = actorFits.tccCards(self.actor.models, cmd=cmd)
            actorFits.extendHeader(cmd, hdr, tccCards)
            mcpCards = actorFits.mcpCards(self.actor.models, cmd=cmd)
            actorFits.extendHeader(cmd, hdr, mcpCards)


        actorFits.writeFits(cmd,hdu,directory,basename,doCompress=self.doCompress)

        del hdu
        del hdr
