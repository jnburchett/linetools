"""Module containing the XSpectrum1D class which overloads Spectrum1D
"""
from __future__ import print_function, absolute_import, division, unicode_literals

import numpy as np
import os, pdb
import json
import warnings

import astropy as apy
from astropy import units as u
from astropy.units import Quantity
from astropy import constants as const
from astropy.io import fits
from astropy.nddata import StdDevUncertainty
from astropy.table import Table, QTable

import linetools.utils as liu
import linetools.spectra.io as lsio

from .plotting import get_flux_plotrange

from ..analysis.interactive_plot import InteractiveCoFit
from ..analysis.continuum import prepare_knots
from ..analysis.continuum import find_continuum

eps = np.finfo(float).eps

try:
    from specutils import Spectrum1D
except ImportError:
    #raise Warning('specutils is not present, so spectra io functionality will not work.')
    class Spectrum1D(object): pass


#from xastropy.xutils import xdebug as xdb

# Child Class of specutils/Spectrum1D
#    Generated by JXP to add functionality before it gets ingested in the specutils distribution
class XSpectrum1D(Spectrum1D):
    '''Class to over-load Spectrum1D for new functionality not yet in specutils

    Instantiate with the same parameters as specutils.spectrum1d.Spectrum1D:

    Parameters
    ----------
    data : `~numpy.ndarray`
        flux of the spectrum

    wcs : `spectrum1d.wcs.specwcs.BaseSpectrum1DWCS`-subclass
        transformation between pixel coordinates and "dispersion" coordinates
        this carries the unit of the dispersion

    unit : `~astropy.unit.Unit` or None, optional
        unit of the flux, default=None

    mask : `~numpy.ndarray`, optional
        Mask for the data, given as a boolean Numpy array with a shape
        matching that of the data. The values must be ``False`` where
        the data is *valid* and ``True`` when it is not (like Numpy
        masked arrays). If `data` is a numpy masked array, providing
        `mask` here will causes the mask from the masked array to be
        ignored.

    meta : `dict`-like object, optional
        Metadata for this object.  "Metadata" here means all information that
        is included with this object but not part of any other attribute
        of this particular object.  e.g., creation date, unique identifier,
        simulation parameters, exposure time, telescope name, etc.
    '''

    @classmethod
    def from_file(self, ifile):
        ''' From file

        Parameters
        ----------
        ifile : str
          Filename
        '''
        slf = lsio.readspec(ifile)
        return slf

    @classmethod
    def from_spec1d(cls, spec1d):
        """ Input Spectrum1D
        """
        # Giddy up
        slf = cls(flux=spec1d.flux, wcs=spec1d.wcs, unit=spec1d.unit,
                   uncertainty=spec1d.uncertainty, mask=spec1d.mask,
                   meta=spec1d.meta.copy())
        return slf

    @classmethod
    def from_tuple(cls,ituple):
        """Make an XSpectrum1D from a tuple of arrays.

        Parameters
        ----------
        ituple : (wave,flux), (wave,flux,sig) or (wave,flux,sig,cont)
          If wave is unitless, Angstroms are assumed
        """
        # Units
        try:
            wv_unit = ituple[0].unit
        except AttributeError:
            wv_unit = u.AA
        else:
            if wv_unit is None:
                wv_unit = u.AA
        uwave = u.Quantity(ituple[0], unit=wv_unit)
        # Generate
        if len(ituple) == 2:  # wave, flux
            spec = cls.from_array(uwave, u.Quantity(ituple[1]))
        elif len(ituple) == 3:
            spec = cls.from_array(uwave, u.Quantity(ituple[1]),
                uncertainty=StdDevUncertainty(ituple[2]))
        else:
            spec = cls.from_array(uwave, u.Quantity(ituple[1]),
                uncertainty=StdDevUncertainty(ituple[2]))
            spec.co = ituple[3]

        spec.filename = 'none'
        # Return
        return spec

    def copy(self):
        flux = np.array(self.flux.value, copy=True)
        uncer = StdDevUncertainty(self.uncertainty, copy=True)
        mask = np.array(self.mask, copy=True)

        # don't make a copy of the wcs. I think this should be ok...
        spec = XSpectrum1D(flux=flux, wcs=self.wcs, unit=self.flux.unit,
                   uncertainty=uncer, mask=mask,
                   meta=self.meta.copy())
        if hasattr(self, 'co'):
            spec.co = self.co
            if spec.co is not None:
                spec.co = np.array(spec.co, copy=True)

        return spec

    @property
    def sig(self):
        """ Return a standard 1sigma error array
        """
        if isinstance(self.uncertainty,StdDevUncertainty):
            return self.uncertainty.array
        else:
            return None

    @property
    def wvmin(self):
        '''Minimum wavelength '''
        try:
            return self._wvmin 
        except AttributeError:
            self.set_diagnostics()
            return self._wvmin

    @property
    def wvmax(self):
        '''Maximum wavelength '''
        try:
            return self._wvmax 
        except AttributeError:
            self.set_diagnostics()
            return self._wvmax

    # overload dispersion to work around a bug in specutils that sets
    # the first dispersion value to NaN for wavelength lookup tables.
    @property
    def dispersion(self):
        #returning the disp
        pixel_indices = np.arange(len(self.flux))
        out = self.wcs(self.indexer(pixel_indices))
        if (abs(pixel_indices[0]) < eps):
            try:
                out.value[0] = self.wcs.lookup_table_parameter.value[0]
            except AttributeError:
                pass
        return out

    def set_diagnostics(self):
        """Generate simple diagnostics on the spectrum.

        As a default, the method cuts on `good' pixels.  Useful for
        plotting, quick comparisons, etc. It currently generates only
        the minimum and maximum wavelengths. Sets attributes `_wvmin`
        and `_wvmax`.
        """
        # Cut on good pixels
        if self.sig is not None:
            gdpx = self.sig > 0.
        else:
            gdpx = np.array([True]*self.flux.size)
        # Fill in attributes
        self._wvmin = np.min(self.dispersion[gdpx])
        self._wvmax = np.max(self.dispersion[gdpx])

    #  Add noise
    def add_noise(self, seed=None, s2n=None):
        '''Add noise to the spectrum.

        Uses the uncertainty array unless otherwise specified.
        Converts flux to float64.

        Parameters
        ----------
        seed : int [None]
          Seed for the random number generator
        s2n : float [None]
          S/N per pixel for the output spectrum. If None, use the
          uncertainty array.
        '''
        # Seed
        np.random.seed(seed=seed)
        #
        npix = len(self.flux)
        # Random numbers
        rand = np.random.normal(size=npix)

        # Modify the flux
        if s2n is not None:
            sig =  1./s2n
        else:
            sig = self.sig
        #
        self.flux = self.flux + (rand * sig)*self.flux.unit

    def constant_sig(self, sigv=0.):
        """Set the uncertainty array to a constant value.

        Parameters
        ----------
        sigv : float [0]
          Scalar sigma value to use.
        """
        self.uncertainty = StdDevUncertainty(np.ones(self.flux.size)*sigv)


    #  Normalize
    def normalize(self, conti=None, verbose=False, no_check=False):
        """ Normalize the spectrum with an input continuum

        Parameters
        ----------
        conti: numpy array [None]
          Continuum. Use XSpectrum1D.co if None is given.
        verbose: bool [False]
        no_check: bool [False]
          Check size of array?
        """
        # Sanity check
        if conti is None:
            if hasattr(self, 'co') and self.co is not None:
                conti = self.co
            else:
                raise ValueError('Must specify a continuum with conti keyword.')
        if (len(conti) != len(self.flux)):
            if no_check:
                print('WARNING: Continuum length differs from flux')
                if len(conti) > len(self.flux):
                    self.flux /= conti[0:len(self.flux)]
                    if self.uncertainty is not None:
                        self.uncertainty.array /= conti[0:len(self.flux)]
                    return
                else:
                    raise ValueError('normalize: Continuum needs to be longer!')
            else:
                raise ValueError('normalize: Continuum needs to be same length as flux array')

        # Adjust the flux
        self.flux /= conti
        if self.uncertainty is not None:
            self.uncertainty.array /= conti
        if verbose:
            print('spec.utils: Normalizing the spectrum')


    #### ###############################
    #  Grabs spectrum pixels in a velocity window
    def pix_minmax(self, *args):
        """Find pixels in wavelength or velocity range

        Parameters
        ----------
        Option 1: wvmnx
          * wvmnx: Tuple of 2 floats
            wvmin, wvmax in spectral units

        Option 2: zabs, wrest, vmnx  [not as a tuple or list!]
          * zabs : Absorption redshift
          * wrest : Rest wavelength  (with Units!)
          * vmnx : Tuple/array/list of 2 Quantities
            vmin, vmax in km/s

        Returns
        -------
        gdpix, wvmnx, pixmnx
          * gdpix: Pixel indices satisfying the cut
          * wvmnx: Tuple of the min and max wavelengths
          * pixmnx: Tuple of the min and max pixels
        """

        if len(args) == 1: # Option 1
            wvmnx = args[0]
        elif len(args) == 3: # Option 2
            from astropy import constants as const
            # args = zabs, wrest, vmnx
            wvmnx = (args[0]+1) * (args[1] + (args[1] * args[2] / const.c.to('km/s')) )
            wvmnx.to(u.AA)

        # Locate the values
        pixmin = np.argmin( np.fabs( self.dispersion-wvmnx[0] ) )
        pixmax = np.argmin( np.fabs( self.dispersion-wvmnx[1] ) )

        gdpix = np.arange(pixmin,pixmax+1, dtype=int)

        # Fill + Return
        self.sub_pix = gdpix
        return gdpix, wvmnx, (pixmin, pixmax)

    #### ###############################

    # Splice spectrum + Normalize
    # Quick plot
    def plot(self, **kwargs):
        ''' Plot the spectrum

        Parameters
        ----------
        show : bool
          If True (the default), then run the matplotlib.pyplot show
          command to display the plot. Disable this if you are running
          from a script and wish to delay showing the plot.

        Other keyword arguments are passed to the matplotlib plot
        command.
        '''
        import matplotlib.pyplot as plt
        from ..analysis.interactive_plot import PlotWrapNav

        ax = plt.gca()
        fig = plt.gcf()

        artists = {}
        ax.axhline(0, color='k', lw=0.5)

        show = kwargs.pop('show', True)

        kwargs.update(color='0.5')
        artists['fl'] = ax.plot(self.wavelength, self.flux,
                                drawstyle='steps-mid', **kwargs)[0]

        if self.sig is not None:
            kwargs.update(color='g')
            ax.plot(self.wavelength, self.sig, **kwargs)

        if hasattr(self, 'co'):
            if self.co is not None:
                kwargs.update(color='r')
                ax.plot(self.wavelength, self.co, **kwargs)

        ax.set_ylim(*get_flux_plotrange(self.flux))
        ax.set_xlim(self.wavelength.value[0], self.wavelength.value[-1])

        if plt.get_backend() == 'MacOSX':
            warnings.warn("""\
Looks like you're using the MacOSX matplotlib backend. Switch to the TkAgg
or QtAgg backends to enable all interactive plotting commands.
""")
        else:
            # Enable xspecplot-style navigation (i/o for zooming, etc).
            # Need to save this as an attribute so it doesn't get
            # garbage-collected.
            self._plotter = PlotWrapNav(fig, ax, self.wavelength,
                                        self.flux, artists, printhelp=False)

            if show:
                plt.show()

    #  Rebin
    def rebin(self, new_wv):
        """ Rebin the existing spectrum rebinned to a new wavelength array
        Uses simple linear interpolation.  The default (and only) option
        conserves counts (and flambda).

        WARNING: Do not trust either edge pixel of the new array
        WARNING: Does not act on the Error array!  Nor does it generate one

        Parameters
        ----------
        new_wv : Quantity array
          New wavelength array

        Returns
        -------
        XSpectrum1D of the rebinned spectrum (without error array)
        """
        from scipy.interpolate import interp1d

        # Endpoints of original pixels
        npix = len(self.wavelength)
        wvh = (self.wavelength + np.roll(self.wavelength, -1))/2.
        wvh[npix-1] = self.wavelength[npix-1] + (self.wavelength[npix-1] - self.wavelength[npix-2])/2.
        dwv = wvh - np.roll(wvh,1)
        dwv[0] = 2*(wvh[0]-self.wavelength[0])

        # Cumulative Sum
        cumsum = np.cumsum(self.flux * dwv)

        # Interpolate (loses the units)
        fcum = interp1d(wvh, cumsum, fill_value=0., bounds_error=False)

        # Endpoints of new pixels
        nnew = len(new_wv)
        nwvh = (new_wv + np.roll(new_wv, -1))/2.
        nwvh[nnew-1] = new_wv[nnew-1] + (new_wv[nnew-1] - new_wv[nnew-2])/2.
        # Pad starting point
        bwv = np.zeros(nnew+1) * new_wv.unit
        bwv[0] = new_wv[0] - (new_wv[1] - new_wv[0])/2.
        bwv[1:] = nwvh

        # Evaluate and put unit back
        newcum = fcum(bwv) * dwv.unit

        # Endpoint
        if (bwv[-1] > wvh[-1]):
            newcum[-1] = cumsum[-1]

        # Rebinned flux
        new_fx = (np.roll(newcum,-1)-newcum)[:-1]

        # Normalize (preserve counts and flambda)
        new_dwv = bwv - np.roll(bwv,1)
        #import pdb
        #pdb.set_trace()
        new_fx = new_fx / new_dwv[1:]

        # Return new spectrum
        return XSpectrum1D.from_array(new_wv, new_fx, meta=self.meta.copy())

    # Velo array
    def relative_vel(self, wv_obs):
        ''' Return a velocity array relative to an input wavelength.

        Should consider adding a velocity array to this Class,
        i.e. self.velo

        Parameters
        ----------
        wv_obs : Quantity
          Wavelength to set the zero of the velocity array.
          Often (1+z)*wrest

        Returns
        -------
        velo : Quantity array (km/s)
        '''
        if not isinstance(wv_obs, Quantity):
            raise ValueError('Input wavelength needs to be a Quantity')
        return ((self.wavelength-wv_obs) * const.c / wv_obs).to('km/s')

    #  Box car smooth
    def box_smooth(self, nbox, preserve=False):
        """ Box car smooth spectrum and return a new one
        Is a simple wrapper to the rebin routine

        Parameters
        ----------
        nbox: integer
          Number of pixels to smooth over
        preserve: bool (False)
          If True, perform a convolution to ensure the new spectrum
          has the same number of pixels as the original.

        Returns
        -------
          XSpectrum1D of the smoothed spectrum
        """
        if preserve:
            from astropy.convolution import convolve, Box1DKernel
            new_fx = convolve(self.flux, Box1DKernel(nbox))
            new_sig = convolve(self.sig, Box1DKernel(nbox))
            new_wv = self.wavelength
        else:
            # Truncate arrays as need be
            npix = len(self.flux)
            try:
                new_npix = npix // nbox # New division
            except ZeroDivisionError:
                raise ZeroDivisionError('Dividing by zero..')
            orig_pix = np.arange( new_npix * nbox )

            # Rebin (mean)
            new_wv = liu.scipy_rebin( self.wavelength[orig_pix], new_npix )
            new_fx = liu.scipy_rebin( self.flux[orig_pix], new_npix )
            new_sig = liu.scipy_rebin( self.sig[orig_pix], new_npix ) / np.sqrt(nbox)

        # Return
        return XSpectrum1D.from_array(
            new_wv, new_fx, meta=self.meta.copy(),
            uncertainty=apy.nddata.StdDevUncertainty(new_sig))

    # Splice two spectra together
    def gauss_smooth(self, fwhm, **kwargs):
        ''' Smooth a spectrum with a Gaussian

        Need to consider smoothing the uncertainty array

        Parameters
        ----------
        fwhm : float
          FWHM of the Gaussian in pixels (unitless)

        Returns
        -------
        XSpectrum1D of the smoothed spectrum
        '''
        # Import
        from linetools.spectra import convolve as lsc

        # Apply to flux
        new_fx = lsc.convolve_psf(self.flux.value, fwhm, **kwargs)*self.flux.unit

        # Return
        return XSpectrum1D.from_array(
            self.wavelength, new_fx, meta=self.meta.copy(),
            uncertainty=self.uncertainty)

    # Splice two spectra together
    def splice(self, spec2, wvmx=None, scale=1.):
        ''' Combine two overlapping spectra

        It is assumed that the internal spectrum is *bluer* than
        the input spectrum.

        Parameters
        ----------
        spec2 : Spectrum1D
          Second spectrum
        wvmx : Quantity, optional
          Wavelength to begin splicing *after*
        scale : float, optional
          Scale factor for flux and error array.
          Mainly for convenience of plotting

        Returns
        -------
        spec3 : Spectrum1D
          Spliced spectrum
        '''
        # Begin splicing after the end of the internal spectrum
        if wvmx is None:
            wvmx = np.max(self.wavelength)
        #
        gdp = np.where(spec2.wavelength > wvmx)[0]
        # Concatenate
        new_wv = np.concatenate( (self.wavelength.value,
            spec2.wavelength.value[gdp]) )
        uwave = u.Quantity(new_wv, unit=self.wcs.unit)
        new_fx = np.concatenate( (self.flux.value,
            spec2.flux.value[gdp]*scale) )
        if self.sig is not None:
            new_sig = np.concatenate( (self.sig, spec2.sig[gdp]*scale) )
        # Generate
        spec3 = XSpectrum1D.from_array(
            uwave, u.Quantity(new_fx), meta=self.meta.copy(),
            uncertainty=StdDevUncertainty(new_sig))
        # Return
        return spec3

    # Write to fits
    def write_to_ascii(self, outfil, format='ascii.ecsv'):
        ''' Write to a text file.

        Parameters
        ----------
        outfil: str
          Filename.
        '''
        # Convert to astropy Table 
        table = QTable([self.wavelength, self.flux, self.sig], 
            names=('WAVE','FLUX','ERROR'))

        # Write
        table.write(outfil,format=format)

    # Write to fits
    def write_to_fits(self, outfil, clobber=True, add_wave=False):
        ''' Write to a FITS file.

        Note that this does not generate a binary FITS table format.

        Parameters
        ----------
        outfil : str
          Name of the FITS file
        clobber : bool (True)
          Clobber existing file?
        add_wave : bool (False)
          Force writing of wavelengths as array, rather than 
        '''
        # TODO
        #  1. Add unit support for wavelength arrays

        from specutils.wcs.specwcs import Spectrum1DPolynomialWCS, Spectrum1DLookupWCS
        from specutils.io import write_fits as sui_wf
        prihdu = sui_wf._make_hdu(self.data)  # Not for binary table format
        prihdu.name = 'FLUX'

        hdu = fits.HDUList([prihdu])

        # Type
        if type(self.wcs) is Spectrum1DPolynomialWCS:  # CRVAL1, etc. WCS
            # WCS
            wcs = self.wcs
            wcs.write_fits_header(prihdu.header)
            # Error array?
            if self.sig is not None:
                sighdu = fits.ImageHDU(self.sig)
                sighdu.name='ERROR'
                hdu.append(sighdu)
                #
            if add_wave:
                wvhdu = fits.ImageHDU(self.wavelength.value)
                wvhdu.name = 'WAVELENGTH'
                hdu.append(wvhdu)

        elif type(self.wcs) is Spectrum1DLookupWCS:
            # Wavelengths as an array (without units for now)
            # Add sig, wavelength to HDU
            if self.sig is not None:
                sighdu = fits.ImageHDU(self.sig)
                sighdu.name = 'ERROR'
                hdu.append(sighdu)
            wvhdu = fits.ImageHDU(self.wavelength.value)
            wvhdu.name = 'WAVELENGTH'
            hdu.append(wvhdu)
        else:
            raise ValueError('write_to_fits: Not ready for this type of spectrum wavelengths')

        if hasattr(self, 'co') and self.co is not None:
            cohdu = fits.ImageHDU(self.co)
            cohdu.name = 'CONTINUUM'
            hdu.append(cohdu)

        # Deal with header
        if hasattr(self, 'head'):
            hdukeys = list(prihdu.header.keys())
            # Append ones to avoid
            hdukeys = hdukeys + ['BUNIT','COMMENT','', 'NAXIS2', 'HISTORY']
            for key in self.head.keys():
                # Use new ones
                if key in hdukeys:
                    continue
                # Update unused ones
                try:
                    prihdu.header[key] = self.head[key]
                except ValueError:
                    raise ValueError('l.spectra.utils: Bad header key card')
            # History
            if 'HISTORY' in self.head.keys():
                # Strip \n
                tmp = str(self.head['HISTORY']).replace('\n',' ')
                try:
                    prihdu.header.add_history(str(tmp))
                except ValueError:
                    import pdb
                    pdb.set_trace()

        if self.meta is not None and len(self.meta) > 0:
            d = liu.jsonify_dict(self.meta)
            prihdu.header['METADATA'] = json.dumps(d)

        hdu.writeto(outfil, clobber=clobber)
        print('Wrote spectrum to {:s}'.format(outfil))


    def fit_continuum(self, knots=None, edges=None, wlim=None, dw=10.,
                      kind=None, **kwargs):
        """ Interactively fit a continuum.

        This set the following attributes
          * spec.co: the new continuum
          * spec.meta['contpoints']: knots defining the continuum
        Use linetools.analysis.interp.AkimaSpline to regenerate the
        continuum from the knots.

        Parameters
        ----------
        spec : XSpectrum1D
        wlim : (float, float), optional
          Start and end wavelengths for fitting the continuum. Default is
          None, which fits the entire spectrum.
        knots: list of (x, y) pairs, optional
          A list of spline knots to use for the continuum.
        edges: list of floats, optional
          A list of edges defining wavelength chunks. Spline knots
          will be placed at the centre of these chunks.
        dw : float, optional
          The approximate distance between spline knots in
          Angstroms.
        kind : {'QSO', None}, optional
          If not None, generate spline knots using
          linetools.analysis.continuum.find_continuum.
        **kwargs
          Other keyword arguments are passed to find_continuum.
          For kind='QSO', allowed keywords are `redshift`, `divmult`,
          `forest_divmult`.

        """
        import matplotlib.pyplot as plt
        if plt.get_backend() == 'MacOSX':
            warnings.warn("""\
Looks like you're using the MacOSX matplotlib backend. Switch to the TkAgg
or QtAgg backends to enable all interactive plotting commands.
""")
            return 

        wa = self.wavelength.value

        anchor = False
        if wlim is None:
            wmin, wmax = wa[0], wa[-1]
        else:
            wmin, wmax = wlim
            if wmax < wmin:
                wmin, wmax = wmax, wmin
            anchor = True
                
        if kind is not None:
            _, knots = find_continuum(self, kind=kind, **kwargs)
            # only keep knots between wmin and wmax
            knots = [[x,y] for (x,y) in knots if wmin <= x <= wmax]
        else:
            if edges is None:
                nchunks = max(3, (wmax - wmin) / float(dw))
                edges = np.linspace(wmin, wmax, nchunks + 1)
    
        if knots is None:
            knots, indices, masked = prepare_knots(
                wa, self.flux.value, self.uncertainty.array, edges)
        else:
            knots = [list(k) for k in knots]
    
        co = (self.co if hasattr(self, 'co') else None)
        if co is not None:
            x = [k[0] for k in knots]
            ynew = np.interp(x, wa, co)
            for i in range(len(knots)):
                knots[i][1] = ynew[i]
    
        contpoints = [k[:2] for k in knots]
        import matplotlib.pyplot as plt
        fig = plt.figure(figsize=(11, 7))
        fig.subplots_adjust(left=0.05, right=0.95, bottom=0.1, top=0.95)
        wrapper = InteractiveCoFit(wa, self.flux.value, self.uncertainty.array,
                                   contpoints, co=co, fig=fig, anchor=anchor)

        # wait until the interactive fitting has finished
        while not wrapper.finished:
            plt.waitforbuttonpress()

        print('Updating continuum')
        self.co = wrapper.continuum
        if 'contpoints' not in self.meta:
            self.meta['contpoints'] = []
        self.meta['contpoints'].extend(
            [tuple(pts) for pts in wrapper.contpoints])
        self.meta['contpoints'].sort()

    # Output
    def __repr__(self):
        txt = '< {:s}: '.format(self.__class__.__name__)
        # Name
        try:
            txt = txt+'file={:s},'.format(self.filename)
        except:
            pass
        # wrest
        txt = txt + ' wvmin={:g}, wvmax={:g}'.format(
            self.wvmin, self.wvmax)
        txt = txt + ' >'
        return (txt)

