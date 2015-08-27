"""
Help with setting up/tearing down gcameraICC tests.
"""
from actorcore import TestHelper

class GcameraTester(TestHelper.ActorTester):
    def setUp(self):
        self.name = "gcamera"
        self.verbose = 2
        self.cmd = TestHelper.Cmd()
        super(GcameraTester,self).setUp()
