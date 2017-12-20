#!/usr/bin/env python
"""
Start the gcameraICC to operate the APO or LCO guider.
"""

import os
import sys

import gcameraICC import GcameraICC


def pick_gcamera():
    """Start either gcamera or ecamera, depending on our name."""

    name = os.path.basename(sys.argv[0])
    if name.startswith('gcamera'):
        return gcamera()
    elif name.startswith('ecamera'):
        return ecamera()


def gcamera():
    # LCOHACK: default location should be APO.
    return GcameraICC.GcameraICC.newActor('gcamera', location='lco', doConnect=True)


def ecamera():
    # LCOHACK: default location should be APO.
    return GcameraICC.GcameraICC.newActor('ecamera', location='lco', doConnect=True)


def main():
    gcamera = pick_gcamera()
    try:
        gcamera.run()
    finally:
        # Makes sure we have shutdown the camera before exiting.
        # This is useful when the gcamera process dies dramatically without the
        # user issuing the gcamera shutdown force command. This won't
        # force the cooler to switch off but at least will improve our chances
        # of reconnecting to the camera later on. This is specially critical
        # for AndorCam, which is pretty sensitive about not shutting it down.
        print('Shutting down the camera ... ')
        gcamera.cam._shutdown()


if __name__ == "__main__":
    main()
