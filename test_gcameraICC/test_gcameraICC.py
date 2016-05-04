#!/usr/bin/env python
"""unittests for gcameraICC itself"""

import unittest

from actorcore import Actor, ICC
from opscore.actor import Model, KeyVarDispatcher

from actorcore import TestHelper

from gcameraICC import GcameraICC

import gcameraTester

logDirBase = 'temp/'

class TestGcameraICC(gcameraTester.GcameraTester,unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # can only configure the dispatcher once.
        Model.setDispatcher(KeyVarDispatcher())
        Actor.setupRootLogger = TestHelper.setupRootLogger
        ICC.makeOpsFileLogger = TestHelper.fakeOpsFileLogger

    def setUp(self):
        # have to clear any actors that were registered previously.
        Model._registeredActors = set()

    def tearDown(self):
        # close the connection: requires handling the deferred.
        # see here for more details:
        #     https://jml.io/pages/how-to-disconnect-in-twisted-really.html
        if getattr(self,'gcamera',None) is not None:
            deferred = self.gcamera.commandSources.port.stopListening()
            deferred.callback(None)

    def test_init_apo(self):
        self.gcamera = GcameraICC.GcameraICC.newActor(location='apo',makeCmdrConnection=False)
        self.assertIsInstance(self.gcamera,GcameraICC.GcameraAPO)
        self.assertEqual(TestHelper.logBuffer.basedir,'/data/logs/actors/gcamera')
        logged = TestHelper.logBuffer.getvalue()
        self.assertIn('attaching command set CameraCmd',logged)
        # self.assertIn('attaching command set CameraCmd_APO',logged)

    def test_init_lco(self):
        self.gcamera = GcameraICC.GcameraICC.newActor(location='lco',makeCmdrConnection=False)
        self.assertIsInstance(self.gcamera,GcameraICC.GcameraLCO)
        self.assertEqual(TestHelper.logBuffer.basedir,'/data/logs/actors/gcamera')
        logged = TestHelper.logBuffer.getvalue()
        self.assertIn('attaching command set CameraCmd',logged)
        # self.assertIn('attaching command set CameraCmd_LCO',logged)


if __name__ == '__main__':
    verbosity = 2
    
    unittest.main(verbosity=verbosity)
