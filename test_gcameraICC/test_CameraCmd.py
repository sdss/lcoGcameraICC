#!/usr/bin/env python
"""unittests for gcamera CamCmd."""

import unittest

from actorcore import TestHelper

from gcameraICC import GcameraICC
from gcameraICC.Commands import CamCmd

verbose = True

class TestCamCmd(TestHelper.ActorTester, unittest.TestCase):
    def setUp(self):
        self.verbose = verbose
        self.name = 'gcamera'
        self.productName = 'gcamera'
        super(TestCamCmd,self).setUp()
        icc = GcameraICC.GcameraICC()
        icc.attachAllControllers()

        # so we can call camCmds, but init things silently.
        # self.cmd.verbose = False
        self.icc = icc
        self.camCmd = CamCmd.CamCmd(icc)
        # self.cmd.clear_msgs()
        # self.cmd.verbose = self.verbose

    def test_ackErrors(self):
        """The deferred ackErrors send a warning per camera, and should finish."""
        self.camCmd.ackErrors(self.cmd)
        self.check_cmd(0,0,2,0,finish=True)


if __name__ == '__main__':
    verbosity = 1
    if verbose:
        verbosity = 2
    
    unittest.main(verbosity=verbosity)
