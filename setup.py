import distutils
from distutils.core import setup, Extension

import sdss3tools
import numpy
import os

apogee_dir = os.getenv('APOGEE_DIR')
apogee_src_dir = os.path.join(apogee_dir, 'src/apogee')
numpy_incl_dir = numpy.get_include()

# Where we have put numpy.i -- in time this may come from swig or numpy.
sdss3tools_numpy_incl_dir = os.path.join(os.getenv('SDSS3TOOLS_DIR'), 'python')

sdss3tools.setup(
        description = "ICC to control SDSS3 Alta guide camera",
        name = "gcameraICC",
        packages = ['python/gcameraICC'],
        ext_modules=[Extension('_alta', ['python/gcameraICC/alta/alta.i'],
                               swig_opts=['-c++', '-I'+apogee_src_dir, '-I'+sdss3tools_numpy_incl_dir, '-DALTA_STANDALONE'],
                               include_dirs=[apogee_src_dir, numpy_incl_dir],
                               define_macros=[('ALTA_STANDALONE', None)],
                               extra_objects=[os.path.join(apogee_src_dir, '_apogee_net.so')])],
        )

