#!/usr/bin/env python
"""
Start the gcameraICC to operate the APO or LCO guider.
"""

import os
import sys

import GcameraICC

def pick_gcamera():
    """Start either gcamera or ecamera, depending on our name."""

    name = os.path.basename(sys.argv[0])
    if name.startswith('gcamera'):
        return gcamera()
    elif name.startswith('ecamera'):
        return ecamera()

def gcamera():
     return GcameraICC.GcameraICC.newActor('gcamera', location='lco', doConnect=True)
    
def ecamera():
    return GcameraICC.GcameraICC('ecamera', doConnect=True)


def main():
    gcamera = pick_gcamera()
    gcamera.run()
    
if __name__ == "__main__":
    main()

