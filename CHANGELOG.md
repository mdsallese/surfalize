## v0.4.0:
- Reduced file load times by >90% using numpy.fromfile to read the height data
- Leveling now no longer also centers the data around the mean
- Fixed wrong alignment direction in Surface.align
- Reverted to binning with default of 10,000 bins for AbbottFirestoneCurve due to large performance bottleneck of
  functional parameter calculations based on whole dataset
- Added support for multiple return values in the Batch class
- Surface.align now takes axis argument to specify with which axis to align the texture
- Surface.depth now considers orientation of the structure and uses correct period in x or y depending on it. It also
  now uses either horizontal or vertical profiles depending on the orientation. Moreover, it doesn't compute the period
  initial guess from each profile anymore but only once from the fourier transform.
- Reworked file loading code and added support for .sur files
- Added basic operator overloading for arithmetic operations to Surface, e.g. "surface + 5.2" or "surface1 - surface2"
- Added Gaussian filter and removed FFT-filter. Surface.filter now invokes a Gaussian filter. 
## v0.3.0:
- Removed underscore from Surface._data, ._step_x, ._step_y, ._width_um, ._height_um since they are supposed to be
  public attributes
- Fixed bug in Surface.zoom
- Reworked Batch processing: now implements lazy loading and dispatch to multiple processes for faster load time
- Operations and Parameters now are constructured as a pipeline on the Batch object, with the actual execution only
  taking place once Batch.execute is called
- Dataframe is now constructed after all processing is completed, which reduces complexity
- Added keyword argument for saving dataframe to excel upon completion of Batch.execute
- Additional data is now loaded directly when initializing Batch object and raises ValueError if column with name file
  doesn't exist
- Updated readme with examples for batch processing
- Added cropping method to Surface
- Fixed bug in plotting of depth analysis
- Added thresholding method based on material ratio to Surface
- Added outlier removal method based on sigma criterion
- Added support for operation on data which contains non-measured points to thresholding and outlier removal methods
- Added remove_outliers and threshold to Batch
- Removed binning from AbbottFirestoneCurve. Instead, now calculates the curve from all available points with unequal
  spacing.
- Fixed errors in homogeneity calculation and added parameter to specify roughness parameters for evaluation on method
  call.
- tqdm is now a non-optional dependency
## v0.2.0:
- Added Sdq parameter -> tested against LeicaMap
- Removed width_um and height_um as initialization parameters for Surface, since they are redundant
- Added lru_cache to some functions to save computation time
- Added cache clearing mechanism as well as recalculation of width_um and height_um upon inplace modification of data
- Replaced default method for calculation of surface area with the one proposed by ISO 25178-2. The method used by
  Gwyddion is now available by keyword argument. Sdr values now match the values computed by MountainsMap and its
  derivative software packages.
- Added correct tests for ISO Sdr values
- Added Smr(c), Smc(mr) and Sxp to the functional parameters
- Moved functional parameter calculation to new class AbbottFirestoneCurve
- Added functional volume parameters Vmp, Vmc, Vvv, Vvc
- Added tests for functional volume parameters
- Added Fourier transform plotting method to Surface
- Fixed a bug with surface area calculation in the Cython code that would result in negative Sdr for some edgecases
- Added autocorrelation function and the derived spatial parameters Sal and Str
- Added tests for spatial parameters
- Restructuring of modules: Profile, AbbottFirestoneCurve, AutocorrelationFunction now in speparate modules
- Fixed filtering method: Now filters at the correct frequencies in all axes. Added note in docstring that warns about
  the side effects of zeroing bins
## v0.1.0:
- Added option to Batch to supply additional parameters associated with each file that can be merged into the
  computed parameters
- Fixed bug where Surface.rotate() would leave a border of nan values
- Fixed bug in profile averaging
- Fixed calculation of Surface._get_fourier_peak_dx_dy(), now returns correct angles with correct sign
- Fixed Surface.orientation(), now considers edgecases where either dy or dx are 0
- Added calculation of areal material ratio curve
- Fixed Abbott-Firestone curve display
- Added calculation fundament for functional parameters
- Added some functional parameters: Sk, Spk, Svk, Smr1, Smr2
- Added utils module with some helper functions
- Fixed bug in depth calculation due to renaming of sinusoid function
- Added aspect ratio parameter to Surface
- Added tests for roughness parameters
- Added script to generate tests for roughness parameters for a set of example surfaces
