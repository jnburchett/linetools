# Module to run tests on Generating a LineList
#   Also tests some simple functionality

# TEST_UNICODE_LITERALS

import os
import pytest
import astropy.io.ascii as ascii
from astropy import units as u
import numpy as np

from linetools.lists.linelist import LineList

#import pdb
#pdb.set_trace()

# ISM LineList
def test_ism():
	ism = LineList('ISM')
	# 
	np.testing.assert_allclose(ism['HI 1215']['wrest'], 1215.6700*u.AA, rtol=1e-7)

# Test update_fval
def test_updfval():
	ism = LineList('ISM')
	# 
	np.testing.assert_allclose(ism['FeII 1144']['f'], 0.106)

# Strong ISM LineList
def test_strong():
	strng = LineList('Strong')
	# 
	assert len(strng._data) < 200

# HI LineList
def test_h1():
	HI = LineList('HI')
	# 
	for name in HI.name:
		assert name[0:2] == 'HI'

# H2 LineList
def test_h2():
	h2 = LineList('H2')
	# 
	np.testing.assert_allclose(h2[911.967*u.AA]['f'], 0.001315, rtol=1e-5)

# H2 LineList
def test_co():
	CO = LineList('CO')
	# 
	np.testing.assert_allclose(CO[1322.133*u.AA]['f'], 0.0006683439, rtol=1e-5)

# Set of Input lines
def test_gdlines():
	ism = LineList('ISM', gd_lines=[1215.6700, 1608.4511])
	# 
	assert len(ism._data) == 2
	np.testing.assert_allclose(ism['FeII 1608']['wrest'], 1608.4511*u.AA, rtol=1e-7)

# Unknown lines
def test_unknown():
	ism = LineList('ISM')
	unknown = ism.unknown_line()
	assert unknown['name'] == 'unknown', 'There is a problem in the LineList.unknown_line()'
	assert unknown['wrest'] == 0.*u.AA, 'There is a problem in the LineList.unknown_line()'
	print(ism['unknown'])
