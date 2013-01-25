#!/usr/bin/env python

import os

import opscore
import opscore.utility.sdss3logging as sdss3logging
import logging

from twisted.internet import reactor

import actorcore.Actor as coreActor
import gcameraICC.alta.altacam as alta

class GCamera(coreActor.Actor):
    def __init__(self, name, productName=None, configFile=None, doConnect=True, 
                 debugLevel=30):
        self.headURL = "$HeadURL$"

        self.cam = None
        coreActor.Actor.__init__(self, name, productName=productName, 
                                 configFile=os.path.join('$GCAMERAICC_DIR/etc', configFile))

        self.logger.setLevel(debugLevel)

        # generate the models for other actors, so we can access their information
        # when generating more detailed fits cards.
        self.models = {}
        for actor in ['mcp','tcc']:
            self.models[actor] = opscore.actor.model.Model(actor)
        
        self.run()

    def connectCamera(self):
        altaHostname = self.config.get('alta', 'hostname')

        if self.cam:
            del self.cam
            self.cam = None

        self.bcast.inform('text="trying to connect to camera at %s...."' % (altaHostname))
        reactor.doSelect(1)

        try:
            self.cam = alta.AltaCam(altaHostname)
        except Exception, e:
            self.bcast.warn('text="BAD THING: could not connect to camera: %s"' % (e))

        if self.cam:
            # OK, try to set the cooler.
            try:
                setPoint = float(self.config.get('alta', 'setTemp'))
                self.callCommand("setTemp temp=%g" % (setPoint))
            except Exception, e:
                self.bcast.warn('text="could not get/parse alta.tempSetpoint config variable: %s"' % (e))

            self.statusCheck()
        else:
            self.bcast.warn('text="BAD THING: failed to connect to camera! Try \'gcamera reconnect\', I suppose."' % (e))

        return self.cam

    def statusCheck(self):
        self.callCommand("status")

        try:
            statusPeriod = int(self.config.get('alta', 'statusPeriod'))
        except:
            statusPeriod = 5*60

        reactor.callLater(statusPeriod, self.statusCheck)

    def connectionMade(self):
        reactor.callLater(3, self.connectCamera)

def gcameraMain():
    gcamera = GCamera('gcamera', productName='gcameraICC', configFile='gcamera.cfg', doConnect=True)
    
def ecameraMain():
    gcamera = GCamera('ecamera', productName='gcameraICC', configFile='ecamera.cfg', doConnect=True)
    
if __name__ == "__main__":
    # Need to add command line opts.
    import os
    import sys

    name = os.path.basename(sys.argv[0])
    if name.startswith('gcamera'):
        gcameraMain()
    elif name.startswith('ecamera'):
        ecameraMain()


