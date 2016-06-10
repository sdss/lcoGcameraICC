#!/usr/bin/env python
"""unittests for the various gcamera Controllers."""

import sys
import unittest
import numpy as np

# TODO: #python3: python3 has unittest.mock.
import mock

# ===================
# alta mocking stuff

alta_attrs = {
    
}
alta = mock.Mock(**alta_attrs)
sys.modules['_alta'] = alta

# We have to put these imports after the mock is defined, so our mocked "alta"
# overrides any actual alta.
from gcameraICC.Controllers import BaseCam
from gcameraICC.Controllers import altacam

import BaseCamTester


class TestAltaCam(BaseCamTester.BaseCamTester, unittest.TestCase):
    """Tests for the Andor Ikon camera for LCO."""
    def setUp(self):
        super(TestAltaCam, self).setUp()
        self.cam = altacam.AltaCam()
        alta.reset_mock()  # clear any function calls that init produced.
        self.cmd.clear_msgs()  # clear startup messages

    def tearDown(self):
        alta.reset_mock()
        # clear all side_effects. NOTE: this is not very pretty, but it works...
        # TBD: there's a unittest ticket about making this an option for reset_mock()
        for x in dir(alta):
            old = getattr(getattr(alta, x), 'side_effect', None)
            if old is not None:
                setattr(getattr(alta, x), 'side_effect', None)
        # reset the return values to their default.
        alta.configure_mock(**alta_attrs)

    def test_binning(self):
        binning = 10
        self.cam.binning = binning
        self.assertEqual(self.cam.binning, binning)
        alta.write_RoiBinningH.assert_called_once_with(binning)
        alta.write_RoiBinningV.assert_called_once_with(binning)
        alta.write_RoiPixelsH.assert_called_once_with(11)
        alta.write_RoiPixelsV.assert_called_once_with(11)
        alta.SetImage.assert_called_once_with(binning, binning, 1, self.cam.width, 1, self.cam.height)


if __name__ == '__main__':
    verbosity = 2

    suite = None
    # to test just one piece
    # suite = unittest.TestLoader().loadTestsFromName('test_Controllers.TestAltaCam.test_binning')
    if suite:
        unittest.TextTestRunner(verbosity=verbosity).run(suite)
    else:
        unittest.main(verbosity=verbosity)
