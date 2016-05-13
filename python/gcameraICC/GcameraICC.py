"""
The Instrument Control Computer for the guide camera for APO and LCO.

Configures its location based on the hostname it is running on.
"""

import abc

from twisted.internet import reactor

import opscore
from actorcore import ICC

import ConfigParser
import os


class GcameraICC(ICC.SDSS_ICC):
    """An ICC to manage connections to a guide camera."""
    __metaclass__ = abc.ABCMeta

    @staticmethod
    def newActor(name='gcamera',location=None,**kwargs):
        """Return the version of the actor based on our location."""

        location = GcameraICC._determine_location(location)
        if location == 'apo':
            return GcameraAPO(name,productName='gcameraICC',**kwargs)
        elif location == 'lco':
            return GcameraLCO(name,productName='gcameraICC',**kwargs)
        else:
            raise KeyError("Don't know my location: cannot return a working Actor!")


    def __init__(self, name, productName=None, configFile=None, doConnect=True,
                 debugLevel=30, makeCmdrConnection=True):
        """
        Create an ICC to communicate with a guide camera.

        Args:
            name (str): the name we are advertised as to the hub.

        Kwargs:
            productName (str): the name of the product; defaults to name
            configFile (str): the full path of the configuration file; defaults
                to $PRODUCTNAME_DIR/etc/$name.cfg
            makeCmdrConnection (bool): establish self.cmdr as a command connection to the hub.
        """

        self.headURL = "$HeadURL: https://svn.sdss.org/repo/operations/general/iccs/gcameraICC/branches/lco/python/gcameraICC/gcameraICC_main.py $"

        self.cam = None
        super(GcameraICC,self).__init__(name, productName=productName, configFile=configFile, makeCmdrConnection=makeCmdrConnection)

        self.logger.setLevel(debugLevel)

        # generate the models for other actors, so we can access their information
        # when generating more detailed fits cards.
        self.models = {}
        for actor in ['mcp', 'tcc', 'gcamera']:
            self.models[actor] = opscore.actor.model.Model(actor)

    def prep_connectCamera(self,hostname=""):
        """Prepare to connect to the camera."""
        if self.cam:
            del self.cam
            self.cam = None

        self.bcast.inform('text="trying to connect to camera at %s...."' % (hostname))
        # Previously doSelect(1), which doesn't exist in the EPoll reactor on Linux
        # Craig said this is probably necessary because of how the altacam
        # C++ framework works (or doesn't).
        reactor.doIteration(1)

    def finish_connectCamera(self):
        """Finalize the camera connection."""
        if self.cam:
            # OK, try to set the cooler.
            try:
                setPoint = float(self.config.get('camera', 'setTemp'))
                # self.callCommand("setTemp temp=%g" % (setPoint))
                # self.callCommand("setTemp temp=5")
            except Exception, e:
                self.bcast.warn('text="could not get/parse alta.tempSetpoint config variable: %s"' % (e))

            self.statusCheck()
        else:
            self.bcast.warn('text="BAD THING: failed to connect to camera! Try \'gcamera reconnect\', I suppose. %s"' % (e))

        return self.cam

    def statusCheck(self):
        self.callCommand("status")

        try:
            statusPeriod = int(self.config.get('camera', 'statusPeriod'))
        except:
            statusPeriod = 5*60

        reactor.callLater(statusPeriod, self.statusCheck)

    def connectionMade(self):
        reactor.callLater(3, self.connectCamera)

    def isCameraExposing(self, cmd):
        """Returns whether the camera is actively taking an exposure."""

        exposureState = self.models['gcamera'].keyVarDict['exposureState']

        if exposureState[0] in ['integrating', 'reading']:
            return False
        else:
            return True


class GcameraAPO(GcameraICC):
    """APO version of this actor."""
    location='APO'

    def connectCamera(self):
        """Estabilish a connection with the camera's network port."""

        from Controllers import altacam

        altaHostname = self.config.get('camera', 'hostname')
        self.prep_connectCamera()

        try:
            self.cam = altacam.AltaCam(altaHostname)
        except Exception, e:
            self.bcast.warn('text="BAD THING: could not connect to camera: %s"' % (e))

        self.finish_connectCamera()


class GcameraLCO(GcameraICC):
    """LCO version of this actor."""
    location='LCO'

    def connectCamera(self):
        """Estabilish a connection with the camera's USB port."""

        from Controllers import andorcam


        self.prep_connectCamera()

        try:
            self.cam = andorcam.AndorCam()
        except Exception, e:
            self.bcast.warn('text="BAD THING: could not connect to camera: %s"' % (e))

        self.finish_connectCamera()
