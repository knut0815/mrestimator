import numpy as np
import os
import matplotlib
if os.environ.get('DISPLAY', '') == '':
    print('No display found. Using non-interactive Agg backend for plotting')
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import namedtuple
import scipy
import neo
import time
import glob
import inspect

def input_handler(items):
    """
    Helper function that attempts to detect provided input and convert it to the
    format used by the toolbox. Ideally, you provide the native format, a numpy
    `ndarray` of :code:`shape(numtrials, datalength)`.

    *Not implemented yet*:
    All trials should have the same data length, otherwise they will be padded.

    Whenever possible, the toolbox uses two dimensional `ndarrays` for
    providing and returning data to/from functions. This allows to consistently
    access trials and data via the first and second index, respectively.

    Parameters
    ----------
    items : ndarray, string or list
        Ideally, provide the native format `ndarray`.
        A `string` is assumed to be the path to
        file(s) that are then imported as pickle or plain text.
        Wildcards should work.
        Alternatively, you can provide a `list` of data or strings.

    Returns
    -------
    preparedsource : ndarray[trial, data]
        the `ndarray` has two dimensions: trial and data

    Example
    -------
    .. code-block:: python

        import numpy as np
        import matplotlib.pyplot as plt
        import mre

        # branching process with 3 trials, 10000 measurement points
        raw = mre.simulate_branching(numtrials=3, length=10000)
        print(raw.shape)

        # the bp returns data already in the right format
        prepared = mre.input_handler(raw)
        print(prepared.shape)

        # plot the first two trials
        plt.plot(prepared[0])     # first trial
        plt.plot(prepared[1])     # second trial
        plt.show()
    ..

    To load a single timeseries from the harddrive

    .. code-block:: python

        import numpy as np
        import matplotlib.pyplot as plt
        import mre

        prepared = mre.input_handler('/path/to/yourfiles/trial_1.csv')
        print(prepared.shape)
    ..

    """


    inv_str = '\n  Invalid input, please provide one of the following:\n' \
              '    - path to pickle or plain file,' \
              '     wildcards should work "/path/to/filepattern*"\n' \
              '    - numpy array or list containing spike data or filenames\n'

    situation = -1
    if isinstance(items, np.ndarray):
        if items.dtype.kind in ['i', 'f', 'u']:
            print('input_handler() detected ndarray of numbers')
            situation = 0
        elif items.dtype.kind == 'S':
            print('input_handler() detected ndarray of strings')
            situation = 1
            temp = set()
            for item in items: temp.update(glob.glob(item))
            if len(items) != len(temp):
                print('  {} duplicate files were excluded' \
                    .format(len(items)-len(temp)))
            items = temp
        else:
            raise Exception('  Numpy.ndarray is neither data nor file path.\n',
                            inv_str)
    elif isinstance(items, list):
        if all(isinstance(item, str) for item in items):
            print('input_handler() detected list of strings')
            try:
                print('  parsing to numpy ndarray as float')
                items = np.asarray(items, dtype=float)
                situation = 0
            except Exception as e:
                print('  {}, parsing as file path'.format(e))
            situation = 1
            temp = set()
            for item in items: temp.update(glob.glob(item))
            if len(items) != len(temp):
                print('  {} duplicate files were excluded' \
                    .format(len(items)-len(temp)))
            items = temp
        elif all(isinstance(item, np.ndarray) for item in items):
            print('input_handler() detected list of ndarrays')
            situation = 0
        else:
            try:
                print('input_handler() detected list\n',\
                      ' parsing to numpy ndarray as float')
                situation = 0
                items = np.asarray(items, dtype=float)
            except Exception as e:
                print('  {}\n'.format(e), inv_str)
                exit()
    elif isinstance(items, str):
        # items = [items]
        items = glob.glob(items)
        print(items)
        situation = 1
    else:
        raise Exception(inv_str)


    if situation == 0:
        retdata = np.stack((items), axis=0)
        if len(retdata.shape) == 1: retdata = retdata.reshape((1, len(retdata)))
    elif situation == 1:
        data = []
        for idx, item in enumerate(items):
            try:
                result = np.load(item)
                print('  {} loaded'.format(item))
                data.append(result)
            except Exception as e:
                print('  {}, loading as text'.format(e))
                result = np.loadtxt(item)
                data.append(result)
        # for now truncate. todo: add padding and check for linear increase to
        # detect spiketimes
        minlen = min(len(l) for l in data)
        retdata = np.ndarray(shape=(len(data), minlen), dtype=float)
        for idx, dat in enumerate(data):
            retdata[idx] = dat[:minlen]
        # retdata = np.stack(data, axis=0)
    else:
        raise Exception('  Unknown situation!\n', inv_str)

    # final check
    if len(retdata.shape) == 2:
        print('  Returning ndarray with {} trial(s) and {} datapoints'\
              .format(retdata.shape[0], retdata.shape[1]))
        return retdata
    else:
        print('  Warning: Guessed data type incorrectly to shape {},' \
            ' please try something else'.format(retdata.shape))
        return retdata

def simulate_branching(length=10000,
                       m=0.9,
                       activity=100,
                       numtrials=1,
                       subp=1):
    """
    Simulates a branching process with Poisson input.

    Parameters
    ----------
    length : int, optional
        Number of steps for the process, thereby sets the total length of the
        generated time series.

    m : float, optional
        Branching parameter.

    activity : float, optional
        Mean activity of the process.

    numtrials : int, optional
        Generate more than one trial.

    subp : float, optional
        Subsample the activity to the specified probability.

    Returns
    -------
    timeseries : ndarray
        ndarray with :code:`numtrials` time series,
        each containging :code:`length` entries of activity.
        If no arguments are provided, one trial is created with
        10000 measurements.

    """

    A_t = np.ndarray(shape=(numtrials, length), dtype=int)
    h = activity * (1 - m)

    print('Generating branching process with {}'.format(length),
          'time steps, m={}'.format(m),
          'and drive rate h={0:.2f}'.format(h))

    if subp <= 0 or subp > 1:
        raise Exception('  Subsampling probability should be between 0 and 1')
    if subp != 1:
        print('  Applying subsampling to proabability {} probability'
              .format(subp))
        a_t = np.copy(A_t)

    for trial in range(0, numtrials):
        # if not trial == 0: print('Starting trial ', trial)
        A_t[trial, 0] = np.random.poisson(lam=activity)

        for idx in range(1, length):
            tmp = 0
            tmp += np.random.poisson(lam=h)
            if m > 0:
                tmp += np.random.poisson(lam=m*A_t[trial, idx - 1])
            A_t[trial, idx] = tmp

            # binomial subsampling
            if subp != 1:
                a_t[trial, idx] = scipy.stats.binom.rvs(tmp, subp)

        print('  Branching process created with mean activity At={}'
              .format(A_t[trial].mean()),
              'subsampled to at={}'
              .format(a_t[trial].mean()) if subp != 1 else '')

    if subp < 1: return a_t
    else: return A_t


# ------------------------------------------------------------------ #
# correlation_coefficients to calculate r_k
# ------------------------------------------------------------------ #

# this is equivalent to CoefficientResult = namedtuple(... but
# we can provide documentation
class CoefficientResult(namedtuple('CoefficientResult',
                                   ['coefficients', 'steps',
                                    'offsets', 'stderrs',
                                    'trialactivies',
                                    'samples'])):
    """
    `Namedtuple` returned by :func:`correlation_coefficients`

    Attributes
    ----------

    coefficients : array
        Contains the coefficients :math:`r_k`, has length
        ``maxstep - minstep + 1``. Access via
        ``coefficients[step]``

    steps : array
        Array of the :math:`k` values matching `coefficients`.

    stderrs : array
        Standard errors of the :math:`r_k`.

    trialactivities : array
        Mean activity of each trial in the provided data.
        To get the global mean activity, use ``np.mean(trialactivities)``.

    samples : :class:`CoefficientResult`
        Contains the information on the separate (or resampled) trials,
        grouped in the same.

    samples.coefficients : ndarray
        Coefficients of each separate trial (or sample). Access via
        ``samples.coefficients[trial, step]``

    samples.trialactivies : array
        Individual activites of each trial. If ``bootsrap`` was enabled, this
        containts the activities of the resampled data (not the original ones).


    Example
    -------

    .. code-block:: python

        import mre

        bp = mre.simulate_branching(numtrials=3)
        rk = mre.correlation_coefficients(bp)

        # list available fields
        print(rk._fields)

        # print the coefficients
        print(rk.coefficients)

        # print all entries as a dict
        print(rk._asdict())

        # get this documentation
        help(rk)
    ..

    """

def correlation_coefficients(data,
                             minstep=1,
                             maxstep=1000,
                             method='trialseparated',
                             bootstrap=True):
    """
    Calculates the coefficients of correlation :math:`r_k`.

    Parameters
    ----------
    data : ndarray
        Input data, containing the time series of activity in the trial
        structure. If a one dimensional array is provieded instead, we assume
        a single trial and reshape the input.

    minstep : int, optional
        The smallest autocorellation step :math:`k` to use.

    maxstep : int, optional
        The largest autocorellation step :math:`k` to use. All :math:`k` values
        between `minstep` and `maxstep` are processed (stride 1).

    method : str, optional
        The estimation method to use, either `'trialseparated'` or
        `'stationarymean'`. The default, `'trialseparated'` calculates
        the :math:`r_k` for each trial separately and averaged
        over. Each trials contribution is weighted with its variance.
        `'stationarymean'` assumes the mean activity and its variance to be
        constant across all trials.

    bootstrap : bool, optional
        Only considered if using the `'stationarymean'` method.
        Enable bootstrapping to generate multiple (resampled)
        series of trials from the provided one. This allows to approximate the
        returned error statistically, (as opposed to the fit errors).
        *Not implemented yet*


    :return: The output is grouped into a `namedtuple` and can be accessed \
        using the attributes listed for :class:`CoefficientResult`, below the \
        example.


    Example
    -------
    .. code-block:: python

        import numpy as np
        import matplotlib.pyplot as plt
        import mre

        # branching process with 15 trials
        bp = mre.simulate_branching(numtrials=15)

        # the bp returns data already in the right format
        rk = mre.correlation_coefficients(bp)

        # separate trials, swap indices to comply with the pyplot layout
        plt.plot(rk.steps, np.transpose(rk.samples.coefficients),
                 color='C0', alpha=0.1)

        # estimated coefficients
        plt.plot(rk.steps, rk.coefficients,
                 color='C0', label='estimated r_k')

        plt.xlabel(r'$k$')
        plt.ylabel(r'$r_k$')
        plt.legend(loc='upper right')
        plt.show()
    ..

    """

    # ------------------------------------------------------------------ #
    # checking arguments to offer some more convenience
    # ------------------------------------------------------------------ #

    if method not in ['trialseparated', 'stationarymean']:
        raise NotImplementedError('Unknown method: "{}"'.format(method))
        return
    else:
        print('correlation_coefficients() using "{}" method:'.format(method))

    dim = -1
    try:
        dim = len(data.shape)
        if dim == 1:
            print('  Warning: You should provide an ndarray of ' \
                  'shape(numtrials, datalength).\n' \
                  '           Continuing with one trial, reshaping your input.')
            data = np.reshape(data, (1, len(data)))
        elif dim >= 3:
            print('  Exception: Provided ndarray is of dim {}.\n'.format(dim),
                  '            Please provide a two dimensional ndarray.')
            exit()
    except IndexError as e:
        print('  Exception: {}.\n'.format(e),
              '            Please provide a two dimensional ndarray.')
        return

    if minstep > maxstep:
        print('  Warning: minstep > maxstep, setting minstep=1')
        minstep = 1

    if maxstep > data.shape[1]:
        maxstep = data.shape[1]-2
        print('  Warning: maxstep is larger than your data, adjusting to {}' \
              .format(maxstep))

    steps     = np.arange(minstep, maxstep+1)
    numsteps  = len(steps)        # number of steps for rks
    numtrials = data.shape[0]     # number of trials
    numels    = data.shape[1]     # number of measurements per trial

    print('  {} trials, length {}'.format(numtrials, numels))

    sepres = CoefficientResult(
        coefficients  = np.zeros(shape=(numtrials, numsteps), dtype='float64'),
        offsets       = np.zeros(shape=(numtrials, numsteps), dtype='float64'),
        stderrs       = np.zeros(shape=(numtrials, numsteps), dtype='float64'),
        steps         = steps,
        trialactivies = np.mean(data, axis=1),
        samples = None)

    if method == 'trialseparated':
        # ------------------------------------------------------------------ #
        # ToDo:
        # fulres.offsets are zeros
        # fulres.samples are mostly unused, only the coefficients are filled
        # ------------------------------------------------------------------ #
        trialmeans = np.mean(data, axis=1, keepdims=True)  # (numtrials, 1)
        trialvars  = np.var(data, axis=1, ddof=1)          # (numtrials)

        for idx, k in enumerate(steps):
            if not idx%100: print('\r  {}/{} steps' \
                .format(idx+1, numsteps), end="")

            sepres.coefficients[:, idx] = \
                np.mean((data[:,  :-k] - trialmeans) * \
                        (data[:, k:  ] - trialmeans), axis=1) \
                * ((numels-k)/(numels-k-1)) / trialvars

        print('\x1b[2K\r  {} steps: done'.format(numsteps))

        if numtrials > 1:
            stderrs = np.sqrt(np.var(sepres.coefficients, axis=0, ddof=1))
        else :
            stderrs = np.zeros(numsteps, dtype='float64')

        fulres = CoefficientResult(
            steps         = steps,
            coefficients  = np.mean(sepres.coefficients, axis=0),
            offsets       = np.mean(sepres.offsets, axis=0),
            stderrs       = stderrs,
            trialactivies = np.mean(data, axis=1),
            samples       = sepres)


    elif method == 'stationarymean':
        # ------------------------------------------------------------------ #
        # ToDo:
        # fulres.offsets are zeros
        # fulres.stderrs are zeros, will be done via bootstrapping
        # fulres.samples are completely unused
        # ------------------------------------------------------------------ #
        coefficients = np.zeros(numsteps, dtype='float64')
        offsets      = np.zeros(numsteps, dtype='float64')
        stderrs      = np.zeros(numsteps, dtype='float64')

        # numbers this time, shape=(1)
        fulmean  = np.mean(data)
        fulvar   = np.var(data, ddof=numtrials)
        # fulvar = np.mean((data[:]-fulmean)**2)*(numels/(numels-1))

        for idx, k in enumerate(steps):
            if not idx%100: print('\r  {}/{} steps' \
                .format(idx+1, numsteps), end="")

            coefficients[idx] = \
                np.mean((data[:,  :-k] - fulmean) * \
                        (data[:, k:  ] - fulmean)) \
                * ((numels-k)/(numels-k-1)) / fulvar

        print('\x1b[2K\r  {} steps: done'.format(numsteps))

        fulres = CoefficientResult(
            steps         = steps,
            coefficients  = coefficients,
            offsets       = offsets,
            stderrs       = stderrs,
            trialactivies = np.mean(data, axis=1),
            samples       = sepres)

    return fulres


# ------------------------------------------------------------------ #
# function definitions, starting values and bounds for correlation_fit
# ------------------------------------------------------------------ #

def f_exponential(k, tau, A):
    """A e^(-k/tau)"""
    return A*np.exp(-k/tau)

def f_exponential_offset(k, tau, A, O):
    """A e^(-k/tau) + O"""
    return A*np.exp(-k/tau)+O*np.ones_like(k)

def f_complex(k, tau, A, O, tosc, B, gam, nu, tgs, C):
    """A e^(-k/tau) + B e^-(k/tosc)^gam cos(2 pi nu k) """ \
    """+ C e^-(k/tgs)^2 + O"""

    return A*np.exp(-(k/tau)) \
        + B*np.exp(-(k/tosc)**gam)*np.cos(2*np.pi*nu*k) \
        + C*np.exp(-(k/tgs)**2) \
        + O*np.ones_like(k)

def default_fitpars(fitfunc, dt=1):
    """
    Called to get the default parameters of built in fitfunctions that are
    used to initialise the fitting routine

    Parameters
    ----------
    fitfunc : callable
        The builtin fitfunction

    dt : number
        The time scale, usually time bin size of your data.

    Returns
    -------
    pars : array like
        The default parameters of the given function, may be a 2d array for
        multiple sets of initial conditions are useful
    """
    if fitfunc == f_exponential:
        return np.array([20/dt, 1])
    elif fitfunc == f_exponential_offset:
        return np.array([20/dt, 1, 0])
    elif fitfunc == f_complex:
        res = np.array(
            #  tau     A       O    tosc      B    gam      nu  tgs      C
            [(  10,  0.1  ,  0    ,  300,  0.03 ,  1.0, 1./200,  10,  0.03 ),
             ( 400,  0.1  ,  0    ,  200,  0.03 ,  2.5, 1./250,  25,  0.03 ),
             (  20,  0.1  ,  0.03 ,  100,  0.03 ,  1.5, 1./50 ,  10,  0.03 ),
             ( 300,  0.1  ,  0.03 ,  100,  0.03 ,  1.5, 1./50 ,  10,  0.03 ),
             (  20,  0.03 ,  0.01 ,  100,  0.03 ,  1.0, 1./150,   5,  0.03 ),
             (  20,  0.03 ,  0.01 ,  100,  0.03 ,  1.0, 1./150,   5,  0.03 ),
             (  10,  0.05 ,  0.03 ,  300,  0.03 ,  1.5, 1./100,   5,  0.1  ),
             ( 300,  0.05 ,  0.03 ,  300,  0.03 ,  1.5, 1./100,  10,  0.1  ),
             (  56,  0.029,  0.010,  116,  0.010,  2.0, 1./466,   5,  0.03 ),
             (  56,  0.029,  0.010,  116,  0.010,  2.0, 1./466,   5,  0.03 ),
             (  56,  0.029,  0.010,  116,  0.010,  2.0, 1./466,   5,  0.03 ),
             (  19,  0.078,  0.044,  107,  0.017,  1.0, 1./478,   5,  0.1  ),
             (  19,  0.078,  0.044,  107,  0.017,  1.0, 1./478,   5,  0.1  ),
             (  10,  0.029,  0.045,  300,  0.067,  2.0, 1./127,  10,  0.03 ),
             ( 210,  0.029,  0.012,  50 ,  0.03 ,  1.0, 1./150,  10,  0.1  ),
             ( 210,  0.029,  0.012,  50 ,  0.03 ,  1.0, 1./150,  10,  0.1  ),
             ( 210,  0.029,  0.012,  50 ,  0.03 ,  1.0, 1./150,  10,  0.03 ),
             ( 210,  0.029,  0.012,  50 ,  0.03 ,  1.0, 1./150,  10,  0.03 ),
             ( 310,  0.029,  0.002,  50 ,  0.08 ,  1.0, 1./34 ,   5,  0.03 ),
             ( 310,  0.029,  0.002,  50 ,  0.08 ,  1.0, 1./34 ,   5,  0.03 ),
             ( 310,  0.029,  0.002,  50 ,  0.08 ,  1.0, 1./64 ,   5,  0.03 ),
             ( 310,  0.029,  0.002,  50 ,  0.08 ,  1.0, 1./64 ,   5,  0.03 )])
        res[:, [0, 3, 7]] /= dt    # noremalize time scale
        res[:, 6] *= dt            # and frequency
        return res
    else:
        print('Requesting default arguments for unknown fitfunction.')
        return None

def default_fitbnds(fitfunc, dt=1):
    if fitfunc == f_exponential:
        return None
    elif fitfunc == f_exponential_offset:
        return None
    elif fitfunc == f_complex:
        res = np.array(
            [(       5,      5000),     # tau
             (       0,         1),     # A
             (      -1,         1),     # O
             (       5,      5000),     # tosc
             (      -5,         5),     # B
             (   1./3.,         3),     # gamma
             (2./1000., 50./1000.),     # nu
             (       0,        30),     # tgs
             (      -5,         5)])    # C
        res = np.transpose(res)         # scipy curve-fit wants this layout
        res[:, [0, 3, 7]] /= dt         # noremalize time scale
        res[:, 6] *= dt                 # and frequency
        return res
    else:
        print('Requesting default bounds for unknown fitfunction.')
        return None


# ------------------------------------------------------------------ #
# correlation_fit and its return type definition
# ------------------------------------------------------------------ #

class CorrelationFitResult(namedtuple('CorrelationFitResult',
                                      ['tau', 'mre', 'fitfunc',
                                       'popt', 'pcov', 'ssres'])):
    """
    `Namedtuple` returned by :func:`correlation_fit`

    Attributes
    ----------

    tau : float
        The estimated autocorrelation time in miliseconds.

    mre : float
        The branching parameter estimated from the multistep regression.
        (Depends on the specified time bin size `dt`
         - which should match your data. Per default ``dt=1`` and
        `mre` is determined via the autocorrelationtime in units of bin size.)

    fitfunc : str
        Description of the used fitfunction as string.

    popt : array
        Final fitparameters obtained from the (best) underlying
        :func:`scipy.optimize.curve_fit`. Beware that these are not corrected
        for the time bin size, this needs to be done manually (for
        time and frequency variables).

    pcov : array
        Final covariance matrix obtained from the (best) underlying
        :func:`scipy.optimize.curve_fit`.

    ssres : float
        Sum of the squared residuals for the fit with `popt`. This is not yet
        normalised per degree of freedom.

    """

def correlation_fit(data,
                    dt=1,
                    fitfunc=f_exponential,
                    fitpars=None,
                    fitbnds=None,
                    maxfev=100000):
    """
    Estimate the Multistep Regression Estimator by fitting the provided
    correlation coefficients :math:`r_k`. The fit is performed using
    :func:`scipy.optimize.curve_fit` and can optionally be provided with
    (multiple) starting fitparameters and bounds.

    Parameters
    ----------
    data: :class:`CoefficientResult` or array
        Correlation coefficients to fit. Ideally, provide this as
        :class:`CoefficientResult` as obtained from
        :func:`correlation_coefficients`. If numpy arrays are provided,
        the function tries to match the data.

    dt : number, optional
        The size of the time bins of your data (in miliseconds). Default is 1.

    fitfunc : callable, optional
        The model function, f(x, …).
        Directly passed to `curve_fit()`:
        It must take the independent variable as
        the first argument and the parameters to fit as separate remaining
        arguments.
        Default is :obj:`mre.f_exponential`.
        Other builtin options are :obj:`mre.f_exponential_offset` and
        :obj:`mre.f_complex`.

    fitpars : array, optional
        The starting parameters for the fit. If the provided array is two
        dimensional, multiple fits are performed and the one with the least
        sum of squares of residuals is returned.

    fitbounds : array, optional
        Lower and upper bounds for each parameter handed to the fitting routine.
        Provide as numpy array of the form
        ``[[lowpar1, lowpar2, ...], [uppar1, uppar2, ...]]``

    maxfev : number, optional
        Maximum iterations for the fit.


    :return: The output is grouped into a `namedtuple` and can be accessed \
        using the attributes listed for :class:`CorrelationFitResult`, below \
        the example.


    Example
    -------
    .. code-block:: python

        import numpy as np
        import matplotlib.pyplot as plt
        import mre

        bp = mre.simulate_branching(numtrials=15)
        rk = mre.correlation_coefficients(bp)

        # compare the builtin fitfunctions
        m1 = mre.correlation_fit(rk, fitfunc=mre.f_exponential)
        m2 = mre.correlation_fit(rk, fitfunc=mre.f_exponential_offset)
        m3 = mre.correlation_fit(rk, fitfunc=mre.f_complex)

        plt.plot(rk.steps, rk.coefficients, label='data')
        plt.plot(rk.steps, mre.f_exponential(rk.steps, *m1.popt),
            label='exponential m={:.5f}'.format(m1.mre))
        plt.plot(rk.steps, mre.f_exponential_offset(rk.steps, *m2.popt),
            label='exp + offset m={:.5f}'.format(m2.mre))
        plt.plot(rk.steps, mre.f_complex(rk.steps, *m3.popt),
            label='complex m={:.5f}'.format(m3.mre))

        plt.legend()
        plt.show()
    ..
    """

    # ------------------------------------------------------------------ #
    # checking arguments to offer some more convenience
    # ------------------------------------------------------------------ #

    print('correlation_fit() calcultes the MR Estimator:')
    mnaive = 'not calculated in your step range'

    if fitfunc in ['f_exponential', 'exponential']:
        fitfunc = f_exponential
    elif fitfunc in ['f_exponential_offset', 'exponentialoffset']:
        fitfunc = f_exponential_offset
    elif fitfunc in ['f_complex', 'complex']:
        fitfunc = f_complex

    if isinstance(data, CoefficientResult):
        print('  Coefficients given in default format')
        coefficients = data.coefficients
        steps        = data.steps
        stderrs      = data.stderrs
        if steps[0] == 1: mnaive = coefficients[0]
    else:
        try:
            print('  Guessing provided format:')
            data = np.asarray(data)
            if len(data.shape) == 1:
                print('    1d array, assuming this to be ' \
                      'coefficients with minstep=1')
                coefficients = data
                steps        = np.arange(1, len(coefficients)+1)
                stderrs      = np.ones(len(coefficients))
                mnaive       = coefficients[0]
            elif len(data.shape) == 2:
                if data.shape[0] > data.shape[1]: data = np.transpose(data)
                if data.shape[0] == 1:
                    print('    nested 1d array, assuming this to be ' \
                          'coefficients with minstep=1')
                    coefficients = data[0]
                    steps        = np.arange(1, len(coefficients))
                    stderrs      = np.ones(len(coefficients))
                    mnaive       = coefficients[0]
                elif data.shape[0] == 2:
                    print('    2d array, assuming this to be ' \
                          'steps and coefficients')
                    steps        = data[0]
                    coefficients = data[1]
                    stderrs      = np.ones(len(coefficients))
                    if steps[0] == 1: mnaive = coefficients[0]
                elif data.shape[0] >= 3:
                    print('    2d array, assuming this to be ' \
                          'steps, coefficients, stderrs')
                    steps        = data[0]
                    coefficients = data[1]
                    stderrs      = np.ones(len(coefficients))
                    if steps[0] == 1: mnaive = coefficients[0]
                    if data.shape > 3: print('    Ignoring further rows')
        except Exception as e:
            raise Exception('{} Provided data has no known format'.foramt(e))


    if fitfunc not in [f_exponential, f_exponential_offset, f_complex]:
        print('  Custom fitfunction specified {}'. format(fitfunc))

    if fitpars is None: fitpars = default_fitpars(fitfunc, dt)
    if fitbnds is None: fitbnds = default_fitbnds(fitfunc, dt)

    # make this more robust
    if (len(fitpars.shape)<2): fitpars = fitpars.reshape(1, len(fitpars))

    if (fitpars.shape[0]>1):
        print('  Repeating fit with {} sets of initial parameters:'
              .format(fitpars.shape[0]))

    # ------------------------------------------------------------------ #
    # fit with compatible arguments via scipy.curve_fit
    # ------------------------------------------------------------------ #

    ssresmin = np.inf
    # fitpars: 2d ndarray
    # fitbnds: matching scipy.curve_fit: [lowerbndslist, upperbndslist]
    for idx, pars in enumerate(fitpars):
        if fitbnds is None:
            bnds = np.array([-np.inf, np.inf])
            outof = '{}/{} '.format(idx+1, len(fitpars)) \
                if len(fitpars)!=1 else ''
            print('    {}Unbound fit to {}:'.format(outof, fitfunc.__doc__))
            ic = list(inspect.signature(fitfunc).parameters)[1:]
            ic = ('{} = {:.3f}'.format(a, b) for a, b in zip(ic, pars))
            print('      Starting parameters:', ', '.join(ic))
        else:
            bnds = fitbnds
            outof = '{}/{} '.format(idx+1, len(fitpars)) \
                if len(fitpars)!=1 else ''
            print('    {}Bounded fit to {}'.format(outof, fitfunc.__doc__))
            ic = list(inspect.signature(fitfunc).parameters)[1:]
            ic = ('  {0:<5} = {1:8.3f} in ({2:9.4f}, {3:9.4f})' \
                .format(a, b, c, d) \
                for a, b, c, d in zip(ic, pars, fitbnds[0, :], fitbnds[1, :]))
            print('      Starting parameters:\n     ', '\n      '.join(ic))

        try:
            popt, pcov = scipy.optimize.curve_fit(
                fitfunc, steps, coefficients,
                p0 = pars, bounds = bnds, maxfev = maxfev, sigma = stderrs)

            residuals = coefficients - fitfunc(steps, *popt)
            ssres = np.sum(residuals**2)
        except Exception as e:
            print('      Exception: {}\n'.format(e),
                  '     Ignoring this fit')
            ssres = np.inf
            popt  = None
            pcov  = None

        if ssres < ssresmin:
            ssresmin = ssres
            fulpopt  = popt
            fulpcov  = pcov

    fulres = CorrelationFitResult(
        tau     = fulpopt[0]*dt,
        mre     = np.exp(-1/fulpopt[0]),
        fitfunc = fitfunc.__doc__,
        popt    = fulpopt,
        pcov    = fulpcov,
        ssres   = ssresmin)

    print('  Finished fitting, mre = {:.5f}, tau = {:.5f}, ssres = {:.5f}' \
          .format(fulres.mre, fulres.tau, fulres.ssres))

    return fulres

