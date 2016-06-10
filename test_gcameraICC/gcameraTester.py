"""
Help with setting up/tearing down gcameraICC tests.
"""
from actorcore import TestHelper

class GcameraTester(TestHelper.ActorTester):
    def setUp(self):
        self.name = "gcamera"
        self.verbose = 2
        # TODO: we don't attach the command sets by default, because CameraCmd
        # does resync() on __init__(), which uses the config to look for the
        # file number and dark/flat. Those may not exist off mountain, so for testing
        # we'll just not attach the cmdSet and not deal with that.
        # This should really be fixed by taking most of the camera logic out of
        # CameraCmd and putting it into its own thread, including the dataRoot
        # and resync logic.
        self.attachCmdSets = False
        super(GcameraTester,self).setUp()
