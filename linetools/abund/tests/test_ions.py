# Module to run tests on ion code

from __future__ import print_function, absolute_import, division, unicode_literals

# TEST_UNICODE_LITERALS

import pytest
from linetools.abund import ions

#import pdb
#pdb.set_trace()
# Set of Input lines

def test_ion_to_name():
    # Normal
    ionnm = ions.ion_name((6,2))
    assert ionnm == 'CII'
    # Latex
    ionnm = ions.ion_name((6,2), flg=1)
    assert ionnm == '{\\rm C}^{+}'
    # as dict
    ion = dict(ion=2, Z=6)
    ionnm = ions.ion_name(ion)
    assert ionnm == 'CII'
    # latex not ready yet
    with pytest.raises(ValueError):
        ionnm = ions.ion_name((6,0), flg=1)
    for ii in [1,2,3,4]:
        ionnm = ions.ion_name((6,ii), flg=1)
    # bad flag
    with pytest.raises(ValueError):
        ionnm = ions.ion_name((6,2), flg=99)


# def test_name_to_ion():
if 1:
    Zion = ions.name_ion('Si II')
    assert Zion == (14,2)
    # bad input
    with pytest.raises(ValueError):
        aux = ions.name_ion(4)  # not a string
    # Deuterium
    aux = ions.name_ion('DI')

