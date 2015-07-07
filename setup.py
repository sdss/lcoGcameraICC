import distutils.command.install as distInstall
from distutils.core import Extension

import sdss3tools
import numpy
import os

def build_for_apogee_guider(apogee_dir):
    """Build the alta libraries for the Apogee camera at APO."""
    apogee_src_dir = os.path.join(apogee_dir, 'src/apogee')
    numpy_incl_dir = numpy.get_include()

    # Where we have put numpy.i -- in time this may come from swig or numpy.
    sdss3tools_numpy_incl_dir = os.path.join(os.getenv('SDSS3TOOLS_DIR'), 'python')

    class my_install(distInstall.install):
        def run(self):
            distInstall.install.run(self)
            os.symlink(os.path.join(self.install_lib, 'gcameraICC'),
                       os.path.join(self.install_lib, 'ecameraICC'))
            
    sdss3tools.setup(
        description = "ICC to control SDSS3 Alta guide camera",
        name = "gcameraICC",
        ext_modules=[Extension('_alta', ['python/gcameraICC/alta/alta.i'],
                               swig_opts=['-c++', '-I'+apogee_src_dir, '-I'+sdss3tools_numpy_incl_dir, '-DALTA_STANDALONE'],
                               include_dirs=[apogee_src_dir, numpy_incl_dir],
                               define_macros=[('ALTA_STANDALONE', None)],
                               extra_objects=[os.path.join(apogee_src_dir, '_apogee_net.so')])],
        cmdclass=dict(install=my_install),
        )

def build_for_andor_guider(andor_dir):
    """Build the ??? libraries to communicate with the Andor camera at LCO."""
    pass

apogee_dir = os.getenv('APOGEE_DIR')
andor_dir = os.getenv('ANDOR_GUIDER_DIR')
if apogee_dir is not None:
    build_for_apogee_guider(apogee_dir)
if andor_dir is not None:
    build_for_andor_guider(apogee_dir)

if apogee_dir is None and andor_dir is None:
    raise Exception('Cannot build gcameraICC: neither apogee_guider nor andor_guider is available. Is one of them setup?')
