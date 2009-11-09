#!/usr/bin/env python

""" CameraCmd.py -- wrap camera functions. """

import glob
import logging
import math
import os
import re
import time

import pyfits

import opscore.protocols.validation as validation
import opscore.protocols.keys as opsKeys
import opscore.protocols.types as types

import RO.Astro.Tm.MJDFromPyTuple as astroMJD

from opscore.utility.qstr import qstr

class CameraCmd(object):
    """ Wrap camera commands.  """
    
    def __init__(self, actor):
        self.actor = actor

        self.dataRoot = self.actor.config.get('gcamera', 'dataRoot')
        self.filePrefix = self.actor.config.get('gcamera', 'filePrefix')

        # We track the names of any currently valid dark and flat files.
        self.darkFile = None
        self.darkTemp = 99.9
        self.flatFile = None
        self.flatCartridge = -1
        
        self.simRoot = None
        self.simSeqno = 1

        self.keys = opsKeys.CmdKey.setKeys(
            opsKeys.KeysDictionary("gcamera_camera", (1, 1),
                                   opsKeys.Key("time", types.Float(), help="exposure time."),
                                   opsKeys.Key("mjd", types.String(), help="MJD for simulation sequence"),
                                   opsKeys.Key("cartridge", types.Int(), help="cartridge number; used to bind flats to images."),
                                   opsKeys.Key("seqno", types.Int(), 
                                               help="image number for simulation sequence."),
                                   opsKeys.Key("filename", types.String(),
                                               help="the filename to write to"),
                                   opsKeys.Key("temp", types.Float(), help="camera temperature setpoint."),
                                   )
            )

        self.vocab = [
            ('status', '', self.status),
            ('setBOSSFormat', '', self.setBOSSFormat),
            ('setFlatFormat', '', self.setFlatFormat),
            ('simulate', '(off)', self.simulateOff),
            ('simulate', '<mjd> <seqno>', self.simulateFromSeq),
            ('setTemp', '<temp>', self.setTemp),
            ('expose', '<time> [<cartridge>] [<filename>]', self.expose),
            ('dark', '<time> [<filename>]', self.expose),
            ('flat', '<time> [<cartridge>] [<filename>]', self.expose),
            ]

    def status(self, cmd, doFinish=True):
        """ Generate all status keywords. """

        cam = self.actor.cam
        cmd.respond('cameraConnected=%s' % (cam != None))
        if cam:
            cmd.respond('binning=%d,%d' % (cam.m_pvtRoiBinningV, cam.m_pvtRoiBinningH))

        self.coolerStatus(cmd, doFinish=False)
        self.sendSimulatingKey(cmd.inform)

        if doFinish:
            cmd.finish()

    def findFileMatch(files, seqno):
        """ Return the filename in the list whose sequence is closest below the given seqno. """

        prefixLength = len(prefix)+1

        names = [os.basename(f) for f in files]
        names = [n.split('-')[1] for n in names]
        names.sort()
        names.reverse()

        seqStr = str(seqno)
        match = None
        for i in range(len(names)):
            if name[i] < seqno:
                match = i
                break

        return match
        
    def findDarkAndFlat(self, dirname, forSeqno):
        darkFiles = glob.glob(os.path.join(dirname, 'dark-*'))
        darkIdx = findFileMatch(darkFiles, forSeqno)
        dark = darkFiles[darkIdx] if darkIdx != None else None

        flatFiles = glob.glob(os.path.join(dirname, 'flat-*'))
        flatIdx = findFileMatch(flatFiles, forSeqno)
        flat = flatFiles[flatIdx] if flatIdx != None else None
        
        return dark, flat

    def setBOSSFormat(self, cmd, doFinish=True):
        """ Configure ourselves. """

        self.actor.cam.setBOSSFormat()
        self.status(cmd, doFinish=False)

        if doFinish:
            cmd.finish()

    def setFlatFormat(self, cmd, doFinish=True):
        """ Configure ourselves for flats. """

        self.actor.cam.setFlatFormat()
        self.status(cmd, doFinish=False)

        if doFinish:
            cmd.finish()

    def sendSimulatingKey(self, state, cmdFunc):
        resp = 'simulating=%s,%s,%d' % (state, self.simRoot, self.simSeqno)
        cmdFunc(resp)
    
    def simulateOff(self, cmd):
        """ stop reading image files from disk. """
        
        self.sendSimulatingKey('Off', cmd.finish)
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

        simPath = os.path.join(simRoot, self.genFilename(seqno))
        if not os.path.isfile(simPath):
            cmd.fail('text="%s is not an existing file"' % (simPath))
            return

        self.simRoot = simRoot
        self.simSeqno = seqno

        self.sendSimulatingKey('On', cmd.finish)

    def genFilename(self, seqno):
        return '%s-%04d.fits' % (self.filePrefix, seqno)
                       
    def genNextRealPath(self, cmd):
        """ Return the next filename to use. Exposures are numbered from 1 for each night. """

        gimgPattern = '^gimg-(\d{4})\.fits$'

        mjd = astroMJD.mjdFromPyTuple(time.gmtime())
        fmjd = str(int(mjd + 0.3))

        dataDir = os.path.join(self.dataRoot, fmjd)
        if not os.path.isdir(dataDir):
            cmd.respond('text="creating new directory %s"' % (dataDir))
            os.mkdir(dataDir)

        imgFiles = glob.glob(os.path.join(dataDir, 'gimg-*.fits'))
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
        if os.path.isfile(pathname):
            return self.simRoot, filename 
        else:
            return None, None

    def getNextPath(self, cmd):
        if self.simRoot:
            return self.genNextSimPath(cmd)
        else:
            return self.genNextRealPath(cmd)

    def expose(self, cmd, doFinish=True):
        """ expose time=SEC [filename=FILENAME] """

        expType = cmd.cmd.name
        cmdKeys = cmd.cmd.keywords
        itime = cmdKeys['time'].values[0]
        if 'filename' in cmdKeys:
            pathname = cmdKeys['filename'].values[0]
        else:
            dirname, filename = self.getNextPath(cmd)
            pathname = os.path.join(dirname, filename)

        readTimeEstimate = 2.0
        cmd.respond('exposureState="integrating",%0.1f,%0.1f' % (itime,itime))

        if expType == 'flat':
            self.setFlatFormat(cmd, doFinish=False)
        else:
            self.setBOSSFormat(cmd, doFinish=False)

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
            if expType == 'dark':
                imDict = self.actor.cam.dark(itime, cmd=cmd)
            else:
                imDict = self.actor.cam.expose(itime, cmd=cmd)
            imDict['type'] = 'object' if (expType == 'expose') else expType
            imDict['filename'] = pathname
            imDict['ccdTemp'] = self.actor.cam.read_TempCCD()
            if expType == 'expose':
                imDict['darkFile'] = self.darkFile
                imDict['flatFile'] = self.flatFile

            self.writeFITS(imDict)
        
        if expType == 'dark':
            self.darkFile = pathname
            self.darkTemp = self.actor.cam.read_TempCCD()
            if not self.simRoot:
                darknote = open(os.path.join(dirname, 'dark-%04d.dat' % (self.seqno)), 'w+')
                darknote.write('filename=%s\n' % (self.darkFile))
                darknote.write('temp=%0.2f\n' % (self.darkTemp))
                darknote.close()
                cmd.respond('text="setting dark file for %0.1fC: %s"' % (self.darkTemp, self.darkFile))
            
        elif expType == 'flat':
            self.flatFile = pathname
            self.flatCartridge = cmdKeys['cartridge'].values[0] if ('cartridge' in cmdKeys) else 0
            self.setBOSSFormat(cmd, doFinish=False)
            if not self.simRoot:
                flatnote = open(os.path.join(dirname, 'flat-%04d-%02d.dat' % (self.seqno, self.flatCartridge)), 'w+')
                flatnote.write('filename=%s\n' % (self.flatFile))
                flatnote.write('cartridge=%d\n' % (self.flatCartridge))
                flatnote.close()
                cmd.respond('text="setting flat file for cartridge %d: %s"' % (self.flatCartridge, self.flatFile))

        cmd.finish('exposureState="done",0.0,0.0; filename=%s' % (os.path.join(dirname, filename)))

    def coolerStatus(self, cmd, doFinish=True):
        """ Generate status keywords. Does NOT finish the command.
        """

        if self.actor.cam:
            coolerStatus = self.actor.cam.coolerStatus()
            cmd.respond(coolerStatus)

        if doFinish:
            cmd.finish()

    def setTemp(self, cmd, doFinish=True):
        """ Adjust the cooling loop.

        Args:
           cmd  - the controlling command.
           temp - the new setpoint, or None if the loop should be turned off. """

        cmdKeys = cmd.cmd.keywords
        temp = cmdKeys['temp'].values[0]

        self.actor.cam.setCooler(temp)
        self.coolerStatus(cmd, doFinish=doFinish)

    def ping(self, cmd):
        """ Top-level "ping" command handler. Query all the controllers for liveness/happiness. """

        cmd.finish('text="Pong."')

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

    def writeFITS(self, d):
        filename = d['filename']
        darkFile = d.get('darkFile', None)
        flatFile = d.get('flatFile', None)
        
        # pdb.set_trace()

        hdu = pyfits.PrimaryHDU(d['data'])
        hdr = hdu.header

        hdr.update('IMAGETYP', d['type'])
        hdr.update('EXPTIME',  d['iTime'])
        hdr.update('TIMESYS', 'TAI')
        hdr.update('DATE-OBS', self.getTS(d['startTime']), 'start of integration')
        hdr.update('CCDTEMP', d.get('ccdTemp', 999.0), 'degrees C')
        hdr.update('FILENAME', filename)
        hdr.update("OBJECT", os.path.splitext(os.path.split(filename)[1])[0], "")
        if d['type'] == 'object':
            if darkFile:
                hdr.update('DARKFILE', darkFile)
            if flatFile:
                hdr.update('FLATFILE', flatFile)
                hdr.update('FLATCART', self.flatCartridge)
            
#        hdr.update('FULLX', self.m_ImagingCols)
#        hdr.update('FULLY', self.m_ImagingRows)
        hdr.update('BEGX', d.get('begx', 0))
        hdr.update('BEGY', d.get('begy', 0))
        hdr.update('BINX', d.get('binx', 1))
        hdr.update('BINY', d.get('biny', 1))

        self.addPixelWcs(hdr)
        
        hdu.writeto(filename)

        del hdu
        del hdr
