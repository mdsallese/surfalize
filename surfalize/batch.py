import multiprocessing as mp
from functools import partial
from pathlib import Path
import logging
logger = logging.getLogger(__name__)
import numpy as np
import pandas as pd
from tqdm.auto import tqdm
from .surface import Surface
from .utils import is_list_like

class BatchError(Exception):
    pass

class Operation:
    """
    Class that holds the identifier and arguments to register a call to a surface method that operates on its data.
    This class is used to implement lazy processing of topography files.

    Parameters
    ----------
    identifier: str
        Name of the method. Must be identical to a method of the Surface class.
    args: tuple
        Tuple of positional arguments that should be passed to the Surface method.
    kwargs: dict
        Dictionary of keyword arguments that should be passed to the Surface method.
    """
    def __init__(self, identifier, args=None, kwargs=None):
        self.identifier = identifier
        self.args = tuple() if args is None else args
        self.kwargs = dict() if kwargs is None else kwargs

    def execute_on(self, surface):
        """
        Executes the registered method from the surface file the positional and keyword arguments.

        Parameters
        ----------
        surface: surfalize.Surface
            surface object on which to execute the registered method.

        Returns
        -------
        None.
        """
        method = getattr(surface, self.identifier)
        method(*self.args, **self.kwargs)

class Parameter:
    """
    Class that holds the identifier and arguments to register a call to a surface method that returns a parameter.
    This class is used to implement lazy processing of topography files.

    Parameters
    ----------
    identifier: str
    Name of the method. Must be identical to a method of the Surface class.
    args: tuple
    Tuple of positional arguments that should be passed to the Surface method.
    kwargs: dict
    Dictionary of keyword arguments that should be passed to the Surface method.
    """
    def __init__(self, identifier, args=None, kwargs=None):
        self.identifier = identifier
        self.args = tuple() if args is None else args
        self.kwargs = dict() if kwargs is None else kwargs

    def calculate_from(self, surface):
        """
        Executes the registered method from the surface file the positional and keyword arguments. Returns a dictionary
        containing the identifier as a key and the value returned from the method as value. If a method returns multiple
        values, this method must be supplied with a decorator that registers labels for the different return values in
        the order they are returned. Each value in the return dictionary will then have a key that consists of the
        identifier as well as the corresponding return value label joined by an underscore:

        Example:

        @register_returnlabels(('value1, value2'))
        def example_parameter(self, arg, kwarg=None):
            # do computation
            return val1, val2

        >>> parameter = Parameter('exmaple_parameter', args=(1, ), kwargs=dict(kwarg=True))
        >>> parameter.calculate_from(surface)
        {'example_parameter_value1': 1.25, 'example_parameter_value2': 2.56}

        Parameters
        ----------
        surface: surfalize.Surface
            surface object on which to execute the registered method.

        Returns
        -------
        None.
        """
        method = getattr(surface, self.identifier)
        result = method(*self.args, **self.kwargs)
        if is_list_like(result):
            try:
                labels = method.return_labels
            except AttributeError:
                raise BatchError(f"No return labels registered for Surface.{self.identifier}.")
            if len(result) != len(labels):
                raise BatchError("Number of registered return labels do not match number of returned values.")
            return {f'{self.identifier}_{label}': value for value, label in zip(result, labels)}
        return {self.identifier: result}

def _task(filepath, operations, parameters):
    """
    Task that loads a surface from file, executes a list of operations and calculates a list of parameters.
    This function is used to split the processing load of a Batch between CPU cores.

    Parameters
    ----------
    filepath: str | pathlib.Path
        Filepath pointing to the measurement file.
    operations: list[Operation]
        List of operations to execute on the surface.
    parameters: list[Parameter]
        List of parameters to calculate from the surface.

    Returns
    -------
    results: dict[str: value]
        Dictionary containing the values for each invokes parameter, with the parameter's method identifier as
        key.
    """
    surface = Surface.load(filepath)
    for operation in operations:
        operation.execute_on(surface)
    results = dict(file=filepath.name)
    for parameter in parameters:
        result = parameter.calculate_from(surface)
        results.update(result)
    return results

#TODO batch image export
class Batch:
    """
   The batch class is used to perform operations and calculate quantitative surface parameters for a batch of
   topography files. The implementation allows to register operations and parameters for lazy calculation by invoking
   methods defined by this class. Every operation method that is defined by Surface can be invoked on the batch class,
   which then registers the method and the passed arguments for later execution. Similarly, every roughness parameter
   can be called on the Batch class. The __getattr__ method is responsible for checking if an invoked method constitutes
   a roughness parameter and if so, automatically wraps the method in a Parameter class, which is registered for later
   calculation. This means that roughness parameters can be invoked on the Batch object despite not being explicitly
   defined in the code.

   All methods can be chained, since they implement the builder design pattern, where every method returns the object
   itself. For exmaple, the operations levelling, filtering and aligning as well as the calculation of roughness
   parameters Sa, Sq and Sz can be registered for later calculation in the following manner:

   >>> batch = Batch(filespaths)
   >>> batch.level().filter(filter_type='lowpass', cutoff=10).align().Sa().Sq().Sz()

   Or on separate lines:
   >>> batch.level().filter(filter_type='lowpass', cutoff=10).align()
   >>> batch.Sa()
   >>> batch.Sq()
   >>> batch.Sz()

   Upon invoking the execute method, all registered operations and parameters are performed.
   >>> batch.execute()

   If the caller wants to supply additional parameters for each file, such as fabrication data, they can specify the
   path to an Excel file containing that data using the 'additional_data' keyword argument. The excel file should
   contain a column 'filename' of the format 'name.extension'. Otherwise, an arbitrary number of additional columns can
   be supplied.

   Parameters
   ----------
   filepaths: list[pathlib.Path | str]
       List of filepaths of topography files
   additional_data: str, pathlib.Path
       Path to an Excel file containing additional parameters, such as
       input parameters. Excel file must contain a column 'file' with
       the filename including the file extension. Otherwise, an arbitrary
       number of additional columns can be supplied.

    Examples
    --------
    >>> from pathlib import Path
    >>> files = Path().cwd().glob('*.vk4')
    >>> batch = Batch(filespaths, addition_data='additional_data.xlsx')
    >>> batch.level().filter('lowpass', 10).Sa().Sq().Sdr()
   """
    
    def __init__(self, filepaths, additional_data=None):
        self._filepaths = [Path(file) for file in filepaths]
        if additional_data is None:
            self._additional_data = None
        else:
            self._additional_data = pd.read_excel(additional_data)
            if 'file' not in self._additional_data.columns:
                raise ValueError("File specified by 'additional_data' does not contain column named 'file'.")
        self._operations = []
        self._parameters = []

    def _disptach_tasks(self, multiprocessing=True):
        """
        Dispatches the individual tasks between CPU cores if multiprocessing is True, otherwise executes them
        sequentially.

        Parameters
        ----------
        multiprocessing: bool, default True
            If True, dispatches the task among CPU cores, otherwise sequentially computes the tasks.

        Returns
        -------
        results: dict[str: value]
            Dictionary containing the values for each invokes parameter, with the parameter's method identifier as
            key.
        """
        results = []
        if multiprocessing:
            total_tasks = len(self._filepaths)
            description = f'Processing on {mp.cpu_count()} cores'
            with mp.Pool() as pool:
                task = partial(_task, operations=self._operations, parameters=self._parameters)
                with tqdm(total=len(self._filepaths), desc=description) as progress_bar:
                    for result in pool.imap_unordered(task, self._filepaths):
                        results.append(result)
                        progress_bar.update()
            return results

        for filepath in tqdm(self._filepaths, desc='Processing'):
            results.append(_task(filepath, self._operations, self._parameters))
        return results

    def _construct_dataframe(self, results):
        """
        Constructs a pandas DataFrame from the result dictionary of the _dispatch_tasks method. This method is also
        responsible for merging the additional data if specified.

        Parameters
        ----------
        results: dict[str: any]

        Returns
        -------
        pd.DataFrame
        """
        df = pd.DataFrame(results)
        if self._additional_data is not None:
            df = pd.merge(self._additional_data, df, on='file')
        return df

    def execute(self, multiprocessing=True, saveto=None):
        """
        Executes the Batch processing and returns the obtained data as a pandas DataFrame.

        Example
        -------
        >>> batch.execute(saveto='C:/users/example/documents/data.xlsx')

        Parameters
        ----------
        multiprocessing: bool, default True
            If True, dispatches the task among CPU cores, otherwise sequentially computes the tasks.
        saveto: str | pathlib.Path, default None
            Path to an excel file where the data is saved to. If the Excel file does already exist, it will be
            overwritten.

        Returns
        -------
        pd.DataFrame
        """
        if not self._parameters and not self._operations:
            raise BatchError('No operations of parameters defined.')
        results = self._disptach_tasks(multiprocessing=multiprocessing)
        df = self._construct_dataframe(results)
        if saveto is not None:
            df.to_excel(saveto)
        return df

    def zero(self):
        """
        Registers Surface.zero for later execution. Inplace is True by default.

        Returns
        -------
        self
        """
        operation = Operation('zero', kwargs=dict(inplace=True))
        self._operations.append(operation)
        return self

    def center(self):
        """
        Registers Surface.center for later execution. Inplace is True by default.

        Returns
        -------
        self
        """
        operation = Operation('center', kwargs=dict(inplace=True))
        self._operations.append(operation)
        return self

    def threshold(self, threshold=0.5):
        """
        Registers Surface.thresold for later execution. Inplace is True by default.

        Parameters
        ----------
        threshold: float, default 0.5
            Threshold argument from Surface.threshold

        Returns
        -------
        self
        """
        operation = Operation('threshold', kwargs=dict(threshold=threshold, inplace=True))
        self._operations.append(operation)
        return self

    def remove_outliers(self, n=3, method='mean'):
        """
        Registers Surface.remove_outliers for later execution. Inplace is True by default.

        Parameters
        ----------
        n: float, default 3
            n argument from Surface.remove_outliers
        method: {'mean', 'median'}, default 'mean'
            method argument from Surface.remove_outliers

        Returns
        -------
        self
        """
        operation = Operation('remove_outliers', kwargs = dict(n=n, method=method, inplace=True))
        self._operations.append(operation)
        return self
            
    def fill_nonmeasured(self, method='nearest'):
        """
        Registers Surface.fill_nonmesured for later execution. Inplace is True by default.

        Parameters
        ----------
        method: {'linear', 'nearest', 'cubic'}, default 'nearest'
            method argument from Surface.fill_nonmeasured

        Returns
        -------
        self
        """
        operation = Operation('fill_nonmeasured', kwargs=dict(method=method, inplace=True))
        self._operations.append(operation)
        return self
            
    def level(self):
        """
        Registers Surface.level for later execution. Inplace is True by default.

        Returns
        -------
        self
        """
        operation = Operation('level', kwargs=dict(inplace=True))
        self._operations.append(operation)
        return self
            
    def filter(self, filter_type, cutoff, cutoff2=None):
        """
        Registers Surface.filter for later execution. Inplace is True by default. The filter_type both cannot be used
        for batch analysis.

        Parameters
        ----------
        filter_type: str
            Mode of filtering. Possible values: 'highpass', 'lowpass', 'bandpass'.
        cutoff: float
            Cutoff frequency in 1/µm at which the high and low spatial frequencies are separated.
            Actual cutoff will be rounded to the nearest pixel unit (1/px) equivalent.
        cutoff2: float | None, default None
            Used only in mode='bandpass'. Specifies the lower cutoff frequency of the bandpass filter. Must be greater
            than cutoff.

        Returns
        -------
        self
        """
        operation = Operation('filter', args=(filter_type, cutoff),
                              kwargs=dict(cutoff2=cutoff2, inplace=True))
        self._operations.append(operation)
        return self
    
    def rotate(self, angle):
        """
        Registers Surface.rotate for later execution. Inplace is True by default.

        Parameters
        ----------
        angle: float
            Angle in degrees.

        Returns
        -------
        self
        """
        operation = Operation('rotate', args=(angle,), kwargs=dict(inplace=True))
        self._operations.append(operation)
        return self
    
    def align(self, axis='y'):
        """
        Registers Surface.align for later execution. Inplace is True by default.

        Parameters
        ----------
        axis: {'x', 'y'}, default 'y'
            The axis with which to align the texture with.

        Returns
        -------
        self
        """
        operation = Operation('align', kwargs=dict(inplace=True, axis=axis))
        self._operations.append(operation)
        return self

    def zoom(self, factor):
        """
        Registers Surface.zoom for later execution. Inplace is True by default.

        Parameters
        ----------
        factor: float
            Factor by which the surface is magnified

        Returns
        -------
        self
        """
        operation = Operation('zoom', args=(factor,), kwargs=dict(inplace=True))
        self._operations.append(operation)
        return self

    def __getattr__(self, attr):
        # This is probably a questionable implementation
        # The call to getattr checks if the attribute exists in this class and returns it if True. If not, it checks
        # whether the attribute is part of the available roughness parameters of the surfalize.Surface class. If it is
        # not, it raises the original AttributeError again. If it is a parameter of surfalize.Surface class though, it
        # constructs a dummy method that is returned to the caller which, instead of calling the actual method from the
        # Surface class, registers the parameter with the corresponding arguments in this class for later execution.
        try:
            return self.__dict__[attr]
        except KeyError:
            if attr not in Surface.AVAILABLE_PARAMETERS:
                raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")
        def parameter_dummy_method(*args, **kwargs):
            parameter = Parameter(attr, args=args, kwargs=kwargs)
            self._parameters.append(parameter)
            return self

        return parameter_dummy_method

    def roughness_parameters(self, parameters=None):
        """
        Registers multiple roughness parameters for later execution. Corresponds to Surface.roughness_parameters.
        If parameters is None, all available roughness and periodic parameters are registered. Otherwise, a list of
        parameters can be passed as argument, which contains the parameter method identifier, which must be equal to
        the method name of the parameter in the Surface class.
        If a parameter is given as a string, it is registered with its default keyword argument values. In the case that
        the user wants to specify a parameter with keyword arguments, there are two options. Either register that
        parameter explicitly by calling Batch.parameter(args, kwargs) or by passing a Parameter class to this method
        instead of a string.

        Examples
        --------
        Here, only the specified parameters will be calculated .
        >>> batch = Batch(filepaths)
        >>> batch.roughness_parameters(['Sa', 'Sq', 'Sz', 'Sdr', 'Vmc'])

        In this case, all available parameters will be calculated.
        >>> batch = Batch(filepaths)
        >>> batch.roughness_parameters()

        Here, we define a custom Parameter class that allows for the specification of keyword arguments. Note that we
        are passing the Parameter to the method instead of the string version.
        >>> from surfalize.batch import Parameter
        >>> Vmc = Parameter('Vmc', kwargs=dict(p=5, q=95))
        >>> batch.roughness_parameters(['Sa', 'Sq', 'Sz', 'Sdr', Vmc])

        Parameters
        ----------
        parameters: list[str | surfalize.batch.Parameter]
            List of parameters to be registered, either as a string identifier or as a Parameter class.

        Returns
        -------
        self
        """
        if parameters is None:
            parameters = list(Surface.AVAILABLE_PARAMETERS)
        for parameter in parameters:
            if isinstance(parameter, str):
                parameter = Parameter(parameter)
            self._parameters.append(parameter)
        return self