import logging
import os

from twisted.internet import reactor

import opscore.actor.model as opsModel
import actorcore.Actor as coreActor
import actorcore.CmdrConnection as coreCmdr

import gcameraICC.alta.altacam as alta

import pdb

class GCamera(coreActor.Actor):
    def __init__(self, name, productName=None, configFile=None, doConnect=True, 
                 debugLevel=30):
        self.headURL = "$HeadURL$"
        coreActor.Actor.__init__(self, name, productName=productName, 
                                 configFile=configFile)

        self.logger.setLevel(debugLevel)

        self.cmdr = coreCmdr.Cmdr(name, self)
        self.cmdr.connectionMade = self.connectionMade
        self.cmdr.connect()

        self.cam = None
        if doConnect:
            self.connectCamera()

        self.run()

    def connectionMade(self):
        self.bcast.warn('text="%s actor is connected."' % (self.name))

    def connectCamera(self):
        altaHostname = self.config.get('alta', 'hostname')

        if self.cam:
            del self.cam
            self.cam = None

        self.cam = alta.AltaCam(altaHostname)

        return self.cam
        
def test1():
    gcamera = GCamera('gcamera', productName='gcameraICC', doConnect=True)
    
if __name__ == "__main__":
    test1()
