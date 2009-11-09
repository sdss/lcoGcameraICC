.KEEP_STATE:
CC =	g++
SWIG = swig

INCDIR		= $(DEVHOME)
PRIVATEINCDIR	= ../../include
ALTAINC		= -I$(APOGEE_DIR)/src/apogee -I$(APOGEE_DIR)/src/apogee/ApogeeNet -I$(APOGEE_DIR)/src/apogee/FpgaRegs -DHAVE_STRERROR 
INCLUDES	= $(ALTAINC) $(shell python-config --includes) -I$(shell echo 'import numpy; print numpy.get_include()' | python)
CPPFLAGS	= -g -fpic -DWall -DLINUX -I../../include -I. $(INCLUDES) -DALTA_STANDALONE
SWIGFLAGS	= -python -c++ $(INCLUDES) -I$(SDSS3TOOLS_DIR)/python -DALTA_STANDALONE
LDFLAGS		= -shared -g
CONFIGTARGETS	= _alta.so alta.py

all: $(CONFIGTARGETS)

alta.py alta_wrap.o: alta.i
	$(SWIG) $(SWIGFLAGS) alta.i
	$(CC) $(CPPFLAGS) $(ALTAINC) -c alta_wrap.cxx

_alta.so: alta_wrap.o 
	$(CC) $(LDFLAGS) alta_wrap.o $(APOGEE_DIR)/src/apogee/_apogee_net.so -lcurl -lz -o _alta.so

install: $(CONFIGTARGETS) FORCE
	cp $(CONFIGTARGETS) $(INSTALL_DIR)

clean:
	rm -f tags TAGS .make.state .nse_depinfo *.o *.so *.pyc alta_wrap.cxx alta_wrap.cpp alta.py *~ *.fits

tags:
	ctags $(LIBSOURCES)

FORCE:



