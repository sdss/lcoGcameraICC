"""
Help with setting up/tearing down gcameraICC tests.
"""
from actorcore import TestHelper

class GcameraTester(TestHelper.ActorTester):
    def setUp(self):
        self.name = "boss"
        self.verbose=2
        super(GcameraTester,self).setUp()
