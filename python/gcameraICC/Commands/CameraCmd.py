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
import opscore.protocols.keys as keys
import opscore.protocols.types as types

import RO.Astro.Tm.MJDFromPyTuple as astroMJD

import Commands.CmdSet
from opscore.utility.qstr import qstr

class CameraCmd(Commands.CmdSet.CmdSet):
    """ Wrap camera commands.  """
    
    def __init__(self, actor):
        Commands.CmdSet.CmdSet.__init__(self, actor)

        self.dataRoot = self.actor.config.get('gcamera', 'dataRoot')
        self.filePrefix = self.actor.config.get('gcamera', 'filePrefix')
        
        self.simRoot = None
        self.simSeqno = 1

        self.keys = keys.CmdKey.setKeys(
            keys.KeysDictionary("gcamera_camera", (1, 1),
                                keys.Key("time", types.Float(), help="exposure time."),
                                keys.Key("mjd", types.Int(), help="MJD for simulation sequence"),
                                keys.Key("seqno", types.Int(), 
                                         help="image number for simulation sequence."),
                                keys.Key("filename", types.String(),
                                         help="the filename to write to"),
                                )
            )

        self.vocab = [
            ('status', '', self.statusCmd),
            ('setFormat', '', self.setFormatCmd),
            ('simulate', '(off)', self.simulateOffCmd),
            ('simulate', '<mjd> <seqno>', self.simulateFromSeqCmd),
#            ('setTemp', '<temp>', self.setTemp)
            ('expose', '<time> [<filename>]', self.exposeCmd),
            ]

    def statusCmd(self, cmd, doFinish=True):
        """ Generate all status keywords. """

        self.coolerStatusCmd(cmd, doFinish=False)
        
        if doFinish:
            cmd.finish()

    def setFormatCmd(self, cmd, doFinish=True):
        """ Configure ourselves. """

        self.actor.cam.setBOSSformat()
        
        if doFinish:
            cmd.finish()

    def sendSimulatingKey(self, state, cmdFunc):
        resp = 'simulating=%s,%s,%d' % (state, self.simRoot, self.simSeqno)
        cmdFunc(resp)
    
    def simulateOffCmd(self, cmd):
        self.sendSimulatingKey('Off', cmd.finish)
        self.simRoot = None

    def simulateFromSeqCmd(self, cmd):
        mjd = cmd.cmd.keywords['mjd'].values[0]
        seqno = cmd.cmd.keywords['seqno'].values[0]

        simRoot = os.path.join(self.dataRoot, str(mjd))
        if not os.path.isdir(simRoot):
            cmd.fail('text="%s is not an existing directory"' % (simRoot))
            return

        simPath = self.genFilename(simRoot, seqno)
        if not os.path.isfile(simPath):
            cmd.fail('text="%s is not an existing file"' % (simPath))
            return

        self.simRoot = simRoot
        self.simSeqno = seqno

        self.sendSimulatingKey('On', cmd.finish)

    def genFilename(self, root, seqno):
        filename = os.path.join(root, '%s-%04d.fits' % (self.filePrefix, seqno))
        return filename
                                
    def genNextRealPath(self, cmd):
        """ Return the next filename to use. """

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
            
        return self.genFilename(dataDir, seqno)
            
    def genNextSimPath(self, cmd):
        """ Return the next filename to use. """

        filename = self.genFilename(self.simRoot, self.simSeqno)
        self.simSeqno += 1
    
        return filename if os.path.isfile(filename) else None

    def getNextPath(self, cmd):
        if self.simRoot:
            return self.genNextSimPath(cmd)
        else:
            return self.genNextRealPath(cmd)

    def exposeCmd(self, cmd, doFinish=True):
        """ expose time=SEC [filename=FILENAME] """

        itime = cmd.cmd.keywords['time'].values[0]
        if 'filename' in cmd.cmd.keywords:
            filename = cmd.cmd.keywords['filename'].values[0]
        else:
            filename = self.getNextPath(cmd)
            
        readTimeEstimate = 2.0
        cmd.respond('exposureState="integrating",%0.1f,%0.1f' % (itime,itime))

        if self.simRoot:
            if not filename:
                self.sendSimulatingKey('Off', cmd.respond)
                self.simRoot = False
                cmd.fail('exposureState="done",0.0,0.0; text="Ran off the end of the simulated data"')
                return
            else:
                time.sleep(itime)
        else:
            imDict = self.actor.cam.expose(itime)
            imDict['filename'] = filename

            #cmd.respond('exposureState="finishing",0.0,0.0')
            self.writeFITS(imDict)
        
            # Try hard to recover image memory. 
            del imDict

        cmd.finish('exposureState="done",0.0,0.0; filename="%s"' % (filename))

    def coolerStatusCmd(self, cmd, doFinish=True):
        """ Generate status keywords. Does NOT finish the command.
        """

        coolerStatus = self.actor.cam.coolerStatus()
        cmd.respond(coolerStatus)

        if doFinish:
            cmd.finish()

    def setTempCmd(self, cmd, doFinish=True):
        """ Adjust the cooling loop.

        Args:
           cmd  - the controlling command.
           temp - the new setpoint, or None if the loop should be turned off. """

        self.cam.setCooler(temp)
        self.coolerStatusCmd(cmd, doFinish=doFinish)

    def pingCmd(self, cmd):
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

    def writeFITS(self, d):
        filename = d['filename']

        # pdb.set_trace()

        hdu = pyfits.PrimaryHDU(d['data'])
        hdr = hdu.header

        hdr.update('IMAGETYP', d['type'])
        hdr.update('EXPTIME',  d['iTime'])
        hdr.update('TIMESYS', 'TAI')
        hdr.update('DATE-OBS', self.getTS(d['startTime']), 'start of integration')
        hdr.update('CCDTEMP', d.get('ccdTemp', 999.0), 'degrees C')
        hdr.update('FILENAME', filename)
#        hdr.update('FULLX', self.m_ImagingCols)
#        hdr.update('FULLY', self.m_ImagingRows)
        hdr.update('BEGX', d.get('begx', 0))
        hdr.update('BEGY', d.get('begy', 0))
        hdr.update('BINX', d.get('binx', 1))
        hdr.update('BINY', d.get('biny', 1))

        # pyfits now does the right thing with uint16
        hdu.writeto(filename)

        del hdu
        del hdr
