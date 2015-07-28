"""
Module for utilites related to spectra
  -- Main item is a Class XSpectrum1D which overloads Spectrum1D
"""
from __future__ import print_function, absolute_import, division, unicode_literals

import numpy as np
import os

import astropy as apy
from astropy import units as u
from astropy import constants as const
from astropy.io import fits
from astropy.nddata import StdDevUncertainty

from linetools import utils as liu


#from xastropy.xutils import xdebug as xdb

# Child Class of specutils/Spectrum1D
#    Generated by JXP to add functionality before it gets ingested in the specutils distribution
def dummy():
    '''Class to over-load Spectrum1D for new functionality not yet in specutils
    '''
    return None
