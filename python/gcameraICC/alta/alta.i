/* alta.i - add a method to the Apogee-supplied class to read an image into a numpy array. */

%module alta
%{     
#define SWIG_FILE_WITH_INIT
#include "ApnCamera.h" 
%}

%include "numpy.i"
%init %{
import_array();
%}

// Apogee sugared up the camera class.
%include "ApnCamera.i"

// wrap an Apogee method with one which understands that it is getting a numpy array.
%extend CApnCamera {  
   void FillImageBuffer(unsigned short *INPLACE_ARRAY2, int DIM1, int DIM2) {
   	long ret;
	unsigned short w, h;
	unsigned long count;

	ret = $self->GetImageData(INPLACE_ARRAY2, w, h, count);
	if (h != DIM1 || w != DIM2) {
	   abort();
	}	   
   }
};

