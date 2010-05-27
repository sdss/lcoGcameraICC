import logging
import os

from twisted.internet import reactor

import opscore.actor.model as opsModel
import actorcore.Actor as coreActor

import gcameraICC.alta.altacam as alta

import pdb

class GCamera(coreActor.Actor):
    def __init__(self, name, productName=None, configFile=None, doConnect=True, 
                 debugLevel=30):
        self.headURL = "$HeadURL$"
        coreActor.Actor.__init__(self, name, productName=productName, 
                                 configFile=configFile)

        self.logger.setLevel(debugLevel)

        self.cam = None

        self.run()

    def connectCamera(self):
        altaHostname = self.config.get('alta', 'hostname')

        if self.cam:
            del self.cam
            self.cam = None

        self.bcast.inform('text="trying to connect to camera at %s...."' % (altaHostname))
        try:
            self.cam = alta.AltaCam(altaHostname)
        except Exception, e:
            self.bcast.warn('text="BAD THING: could not connect to camera: %s"' % (e))

        return self.cam

    def connectionMade(self):
        reactor.callLater(3, self.connectCamera)

def test1():
    gcamera = GCamera('gcamera', productName='gcameraICC', doConnect=True)
    
if __name__ == "__main__":
    test1()
