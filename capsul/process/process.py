##########################################################################
# CAPSUL - Copyright (C) CEA, 2013
# Distributed under the terms of the CeCILL-B license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL-B_V1-en.html
# for details.
##########################################################################

# System import
import os
import operator
from socket import getfqdn
from datetime import datetime as datetime
from copy import deepcopy
import json
try:
    import subprocess32 as subprocess
except ImportError:
    import subprocess
import six
import sys
import functools

# Trait import
from traits.trait_base import _Undefined
from traits.api import Directory, Undefined, Int, List, Bool, File
from traits.trait_handlers import BaseTraitHandler

# Soma import
from soma.controller import Controller
from soma.controller import trait_ids
from soma.controller.trait_utils import is_trait_value_defined
from soma.controller.trait_utils import is_trait_pathname
from soma.controller.trait_utils import get_trait_desc

# Capsul import
from capsul.utils.version_utils import get_tool_version

if sys.version_info[0] <= 3:
    unicode = str
    basestring = str


class ProcessMeta(Controller.__class__):
    """ Class used to complete a process docstring

    Use a class and not a function for inheritance.
    """
    @staticmethod
    def complement_doc(name, docstr):
        """ complement the process docstring
        """
        docstring = docstr.split("\n")

        # we have to indent the note properly so that the docstring is
        # properly displayed, and correctly processed by sphinx
        indent = -1
        for line in docstring[1:]:
            lstrip = line.strip()
            if not lstrip:  # empty lines do not influence indent
                continue
            lindent = line.index(line.strip())
            if indent == -1 or lindent < indent:
                indent = lindent
        if indent < 0:
            indent = 0

        # Complete the docstring
        docstring += [' ' * indent + line for line in [
            "",
            ".. note::",
            "",
            "    * Type '{0}.help()' for a full description of "
            "this process parameters.".format(name),
            "    * Type '<{0}>.get_input_spec()' for a full description of "
            "this process input trait types.".format(name),
            "    * Type '<{0}>.get_output_spec()' for a full description of "
            "this process output trait types.".format(name),
            ""
        ]]

        return "\n".join(docstring)

    def __new__(mcls, name, bases, attrs):
        """ Method to print the full help.

        Parameters
        ----------
        mcls: meta class (mandatory)
            a meta class.
        name: str (mandatory)
            the process class name.
        bases: tuple (mandatory)
            the direct base classes.
        attrs: dict (mandatory)
            a dictionnary with the class attributes.
        """
        # Update the class docstring with the full process help
        docstring = ProcessMeta.complement_doc(
            name, attrs.get("__doc__", ""))
        attrs["__doc__"] = docstring

        # Find all traits definitions in the process class and ensure that
        # it has a boolean value for attributes "output" and "optional".
        # If no value is given at construction, False will be used.
        for n, possible_trait_definition in six.iteritems(attrs):
            if isinstance(possible_trait_definition, BaseTraitHandler):
                possible_trait_definition._metadata['output'] \
                    = bool(possible_trait_definition.output)
                possible_trait_definition._metadata['optional'] \
                    = bool(possible_trait_definition.optional)

        return super(ProcessMeta, mcls).__new__(
            mcls, name, bases, attrs)


class Process(six.with_metaclass(ProcessMeta, Controller)):
    """ A process is an atomic component that contains a processing.

    A process is typically an object with typed parameters, and an execution
    function. Parameters are described using Enthought
    `traits <http://docs.enthought.com/traits/>`_ through Soma-Base
    :somabase:`Controller <api.html#soma.controller.controller.Controller>`
    base class.

    In addition to describing its parameters, a Process must implement its
    execution function, either through a python method, by overloading
    :meth:`_run_process`, or through a commandline execution, by overloading
    :meth:`get_commandline`. The second way allows to run on a remote
    processing machine which has not necessary capsul, nor python, installed.

    Parameters are declared or queried using the traits API, and their values
    are in the process instance variables:

    ::

        from __future__ import print_function
        from capsul.api import Process
        import traits.api as traits

        class MyProcess(Process):

            # a class trait
            param1 = traits.Str('def_param1')

            def __init__(self):
                super(MyProcess, self).__init__()
                # declare an input param
                self.add_trait('param2', traits.Int())
                # declare an output param
                self.add_trait('out_param', traits.File(output=True))

            def _run_process(self):
                with open(self.out_param, 'w') as f:
                    print('param1:', self.param1, file=f)
                    print('param2:', self.param2, file=f)

        # run it with parameters
        MyProcess()(param2=12, out_param='/tmp/log.txt')

    Attributes
    ----------
    `name`: str
        the class name.
    `id`: str
        the string description of the class location (ie., module.class).
    `log_file`: str (default None)
        if None, the log will be generated in the current directory
        otherwise it will be written in log_file path.

    Methods
    -------
    __call__
    _run_process
    _get_log
    add_trait
    save_log
    help
    get_input_help
    get_output_help
    get_commandline
    get_log
    get_input_spec
    get_output_spec
    get_inputs
    get_outputs
    set_parameter
    get_parameter

    """

    def __init__(self, **kwargs):
        """ Initialize the Process class.
        """
        # Inheritance
        super(Process, self).__init__()

        # Initialize the process identifiers
        self.name = self.__class__.__name__
        self.id = self.__class__.__module__ + "." + self.name

        # Parameter to store which tools will be used dusring the processing
        self.versions = {
            "capsul": get_tool_version("capsul")
        }

        # Initialize the log file name
        self.log_file = None
        self.study_config = None

        default_values = getattr(self, 'default_values', None)
        if default_values:
            self.default_values = default_values.copy()
        else:
            self.default_values = {}
        for k, v in six.iteritems(kwargs):
            self.default_values[k] = v

    def __getstate__(self):
        """ Remove the _weakref attribute eventually set by 
        soma.utils.weak_proxy beacause it prevent Process instance
        from being used with pickle.
        """
        state = super(Process, self).__getstate__()
        state.pop('_weakref', None)
        return state
    
    def add_trait(self, name, trait):
        """Ensure that trait.output and trait.optional are set to a
        boolean value before calling parent class add_trait.
        """
        if trait._metadata is not None:
            trait._metadata['output'] = bool(trait.output)
            trait._metadata['optional'] = bool(trait.optional)
        else:
            trait.output = bool(trait.output)
            trait.optional = bool(trait.optional)
        super(Process, self).add_trait(name, trait)
        
    def __call__(self, **kwargs):
        """ Method to execute the Process.

        Keyword arguments may be passed to set process parameters.
        This in turn will allow calling the process like a standard
        python function.
        In such case keyword arguments are set in the process in
        addition to those already set before the call.

        Raise a TypeError if a keyword argument do not match with a
        process trait name.

        .. note:

            This method must not modify the class attributes in order
            to be able to perform smart caching.

        .. note:

            This method should **not** be overloaded by Process subclasses to
            perform actual processing. Instead, either the
            :meth:`_run_process` method or the :meth:`get_commandline` method
            should be overloaded.

        Parameters
        ----------
        kwargs: dict (optional)
            should correspond to the declared parameter traits.

        Returns
        -------
        results:  ProcessResult object
            contains all execution information.
        """
        # Execute the process
        returncode = self.get_study_config().run(self, **kwargs)
        return returncode


    def run(self, **kwargs):
        '''
        Obsolete: use self.__call__ instead
        '''
        return self.__call__(**kwargs)

    
    ####################################################################
    # Private methods
    ####################################################################

    def _run_process(self):
        """Runs the processings when the instance is called.

        Either this _run_process() or :meth:`get_commandline` must be
        defined in derived classes.

        Note that _run_process() is called as a python function, on a Process
        instance. When using remote processing (cluster for instance), this
        means that the commandline which will run needs to be able to re-
        instantiate the same process: the process thus has to be stored in a
        file or python module which can be accessed from the remote machine,
        and python / capsul correctly installed and available on it.

        :meth:`get_commandline` at the contrary, can implement commandlines
        which are completely inependent from Capsul, and from python.

        .. note::

            If both methods are not defined in the derived class a
            NotImplementedError error is raised.

            On the other side, if both methods are overloaded, the process
            behavior in local sequential computing mode and in Soma-Workflow
            modes may be different.
        """
        # Check if get_commandline() method is specialized
        # If yes, we can make use of it to execute the process
        if self.__class__.get_commandline != Process.get_commandline:
            commandline = self.get_commandline()
            subprocess.check_call(commandline)

        # Otherwise raise an error
        else:
            raise NotImplementedError(
                "Either get_commandline() or _run_process() should be "
                "redefined in process ({0})".format(
                    self.__class__.__name__))
    
    def _before_run_process(self):
        """This method is called by StudyConfig.run() before calling
        _run_process(). By default it does nothing but can be overriden
        in derived classes.
        """
        
    def _after_run_process(self, run_process_result):
        """This method is called by StudyConfig.run() after calling
        _run_process(). It is expected to return the final result of the
        process. By default it does nothing but can be overriden
        in derived classes.
        """
        return run_process_result
        

    def _get_log(self, exec_info):
        """ Method that generate the logging structure from the execution
        information and class attributes.

        Parameters
        ----------
        exec_info: dict (mandatory)
            the execution informations,
            the dictionnary is supposed to contain a runtime attribute.

        Returns
        -------
        log: dict
            the logging information.
        """
        # Set all the execution runtime information in the log
        log = exec_info.runtime

        # Add the process identifiaction class attribute
        log["process"] = self.id

        # Add the process inputs and outputs
        log["inputs"] = exec_info.inputs.copy()
        log["outputs"] = exec_info.outputs.copy()

        # Need to take the representation of undefined input or outputs
        # traits
        for parameter_type in ["inputs", "outputs"]:
            for key, value in six.iteritems(log[parameter_type]):
                if value is Undefined:
                    log[parameter_type][key] = repr(value)

        return log

    def _rst_table(self, data):
        """ Create a rst formated table.

        Parameters
        ----------
        data: list of list of str (mandatory)
            the table line-cell centent.

        Returns
        -------
        rsttable: list of str
            the rst formated table containing the input data.
        """
        # Output rst table
        rsttable = []

        # Get the size of the largest row in order to
        # format properly the rst table (do not forget the '+' and '*')
        row_widths = [len(item)
                      for item in functools.reduce(operator.add, data)]
        width = max(row_widths) + 11

        # Generate the rst table

        # > table synthax
        rsttable.append("+" + "-" * width + "+")
        # > go through the table lines
        for table_row in data:
            # > go through the cell lines
            for index, cell_row in enumerate(table_row):
                # > set the parameter name in bold
                if index == 0 and ":" in cell_row:
                    delimiter_index = cell_row.index(":")
                    cell_row = ("**" + cell_row[:delimiter_index] + "**" +
                                cell_row[delimiter_index:])
                # >  add table rst content
                rsttable.append(
                    "| | {0}".format(cell_row) +
                    " " * (width - len(cell_row) - 3) +
                    "|")
            # > close cell
            rsttable.append("+" + "-" * width + "+")

        return rsttable

    ####################################################################
    # Public methods
    ####################################################################

    def save_log(self, returncode):
        """ Method to save process execution informations in json format.

        If the class attribute `log_file` is not set, a log.json output
        file is generated in the process call current working directory.

        Parameters
        ----------
        returncode: ProcessResult
            the process result return code.
        """
        # Build the logging information
        exec_info = self._get_log(returncode)

        # Generate an output log file name if necessary
        if not self.log_file:
            self.log_file = os.path.join(exec_info["cwd"], "log.json")

        # Dump the log
        json_struct = json.dumps(exec_info, sort_keys=True,
                                 check_circular=True, indent=4)

        # Save the json structure
        with open(self.log_file, "w") as f:
            f.write(unicode(json_struct))

    @classmethod
    def help(cls, returnhelp=False):
        """ Method to print the full help.

        Parameters
        ----------
        cls: process class (mandatory)
            a process class
        returnhelp: bool (optional, default False)
            if True return the help string message,
            otherwise display it on the console.
        """
        cls_instance = cls()
        return cls_instance.get_help(returnhelp)

    ####################################################################
    # Accessors
    ####################################################################

    def get_commandline(self):
        """ Method to generate a comandline representation of the process.

        If not implemented, it will generate a commandline running python,
        instaitiating the current process, and calling its
        :meth:`_run_process` method.

        Returns
        -------
        commandline: list of strings
            Arguments are in separate elements of the list.
        """
        # Get command line arguments (ie., the process user traits)
        # Build the python call expression, keeping apart file names.
        # File names are given separately since they might be modified
        # externally afterwards, typically to handle temporary files, or
        # file transfers with Soma-Workflow.

        class ArgPicker(object):
            """ This small object is only here to have a __repr__() representation which will print sys.argv[n] in a list when writing the commandline code.
            """
            def __init__(self, num):
                self.num = num
            def __repr__(self):
                return 'sys.argv[%d]' % self.num

        reserved_params = ("nodes_activation", "selection_changed")
        # pathslist is for files referenced from lists: a list of files will
        # look like [sys.argv[5], sys.argv[6]...], then the corresponding
        # path args will be in additional arguments, here stored in pathslist
        pathslist = []
        # argsdict is the dict of non-path arguments, and will be printed
        # using repr()
        argsdict = {}
        # pathsdict is the dict of path arguments, and will be printed as a
        # series of arg_name, path_value, all in separate commandline arguments
        pathsdict = {}

        for trait_name, trait in six.iteritems(self.user_traits()):
            value = getattr(self, trait_name)
            if trait_name in reserved_params \
                    or not is_trait_value_defined(value):
                continue
            if is_trait_pathname(trait):
                pathsdict[trait_name] = value
            elif isinstance(trait.trait_type, List) \
                    and is_trait_pathname(trait.inner_traits[0]):
                plist = []
                for pathname in value:
                    if is_trait_value_defined(pathname):
                        plist.append(ArgPicker(len(pathslist) + 1))
                        pathslist.append(pathname)
                    else:
                        plist.append(pathname)
                argsdict[trait_name] = plist
            else:
                argsdict[trait_name] = value

        # Get the module and class names
        if hasattr(self, '_function'):
            # function with xml decorator
            module_name = self._function.__module__
            class_name = self._function.__name__
            call_name = class_name
        else:
            module_name = self.__class__.__module__
            class_name = self.name
            call_name = '%s()' % class_name

        # Construct the command line
        commandline = [
            "python",
            "-c",
            ("import sys; from {0} import {1}; kwargs={2}; "
             "kwargs.update(dict((sys.argv[i * 2 + {3}], "
             "sys.argv[i * 2 + {4}]) "
             "for i in range(int((len(sys.argv) - {3}) / 2)))); "
             "{5}(**kwargs)").format(module_name, class_name,
                                       repr(argsdict), len(pathslist) + 1,
                                       len(pathslist) + 2,
                                       call_name).replace("'", '"')
        ] + pathslist + sum([list(x) for x in pathsdict.items()], [])

        return commandline

    def make_commandline_argument(self, *args):
        """This helper function may be used to build non-trivial commandline
        arguments in get_commandline implementations.
        Basically it concatenates arguments, but it also takes care of keeping
        track of temporary file objects (if any), and converts non-string
        arguments to strings (using repr()).

        Ex:

        >>> process.make_commandline_argument('param=', self.param)

        will return the same as:

        >>> 'param=' + self.param

        if self.param is a string (file name) or a temporary path.
        """
        built_arg = ""
        temp = None
        for arg in args:
            if hasattr(arg, 'pattern'): # tempfile
                built_arg = built_arg + arg
            elif isinstance(arg, basestring):
                built_arg += arg
            else:
                built_arg = built_arg + repr(arg)
        return built_arg

    def get_log(self):
        """ Load the logging file.

        .. note:

            If no log file found, return None

        Returns
        -------
        log: dict
            the content of the log file.
        """
        if os.path.isfile(self.log_file):
            with open(self.log_file) as json_file:
                return json.load(json_file)
        else:
            return None

    def get_input_spec(self):
        """ Method to access the process input specifications.

        Returns
        -------
        outputs: str
            a string representation of all the input trait specifications.
        """
        output = "\nINPUT SPECIFICATIONS\n\n"
        # self.traits(output=False) skips params with no output property
        for trait_name, trait in six.iteritems(self.user_traits()):
            if not trait.output:
                output += "{0}: {1}\n".format(
                    trait_name, trait_ids(self.trait(trait_name)))
        return output

    def get_output_spec(self):
        """ Method to access the process output specifications.

        Returns
        -------
        outputs: str
            a string representation of all the output trait specifications.
        """
        output = "\nOUTPUT SPECIFICATIONS\n\n"
        for trait_name, trait in six.iteritems(self.traits(output=True)):
            output += "{0}: {1}\n".format(
                trait_name, trait_ids(self.trait(trait_name)))
        return output

    def get_inputs(self):
        """ Method to access the process inputs.

        Returns
        -------
        outputs: dict
            a dictionary with all the input trait names and values.
        """
        output = {}
        for trait_name, trait in six.iteritems(self.user_traits()):
            if not trait.output:
                output[trait_name] = getattr(self, trait_name)
        return output

    def get_outputs(self):
        """ Method to access the process outputs.

        Returns
        -------
        outputs: dict
            a dictionary with all the output trait names and values.
        """
        output = {}
        for trait_name, trait in six.iteritems(self.traits(output=True)):
            output[trait_name] = getattr(self, trait_name)
        return output

    def get_help(self, returnhelp=False):
        """ Generate description of a process parameters.

        Parameters
        ----------
        returnhelp: bool (optional, default False)
            if True return the help string message formatted in rst,
            otherwise display the raw help string message on the console.
        """
        # Create the help content variable
        doctring = [""]

        # Update the documentation with a description of the pipeline
        # when the xml to pipeline wrapper has been used
        if returnhelp and hasattr(self, "_pipeline_desc"):
            str_desc = "".join(["    {0}".format(line)
                                for line in self._pipeline_desc])
            doctring += [
                ".. hidden-code-block:: python",
                "    :starthidden: True",
                "",
                str_desc,
                ""
            ]

        # Get the process docstring
        if self.__doc__:
            doctring += self.__doc__.split("\n") + [""]

        # Update the documentation with a reference on the source function
        # when the function to process wrapper has been used
        if hasattr(self, "_func_name") and hasattr(self, "_func_module"):
            doctring += [
                "This process has been wrapped from {0}.{1}.".format(
                    self._func_module, self._func_name),
                ""
            ]
            if returnhelp:
                doctring += [
                    ".. currentmodule:: {0}".format(self._func_module),
                    "",
                    ".. autosummary::",
                    "    :toctree: ./",
                    "",
                    "    {0}".format(self._func_name),
                    ""
                ]

        # Append the input and output traits help
        full_help = (doctring + self.get_input_help(returnhelp) + [""] +
                     self.get_output_help(returnhelp) + [""])
        full_help = "\n".join(full_help)

        # Return the full process help
        if returnhelp:
            return full_help
        # Print the full process help
        else:
            print(full_help)

    def get_input_help(self, rst_formating=False):
        """ Generate description for process input parameters.

        Parameters
        ----------
        rst_formating: bool (optional, default False)
            if True generate a rst table witht the input descriptions.

        Returns
        -------
        helpstr: str
            the class input traits help
        """
        # Generate an input section
        helpstr = ["Inputs", "~" * 6, ""]

        # Markup to separate mandatory inputs
        manhelpstr = ["[Mandatory]", ""]

        # Get all the mandatory input traits
        mandatory_items = dict([x for x in six.iteritems(self.user_traits())
                                if not x[1].output and not x[1].optional])
        mandatory_items.update(self.traits(output=None, optional=False))

        # If we have mandatory inputs, get the corresponding string
        # descriptions
        data = []
        if mandatory_items:
            for trait_name, trait in six.iteritems(mandatory_items):
                trait_desc = get_trait_desc(trait_name, trait)
                data.append(trait_desc)

        # If we want to format the output nicely (rst)
        if data != []:
            if rst_formating:
                manhelpstr += self._rst_table(data)
            # Otherwise
            else:
                manhelpstr += functools.reduce(operator.add, data)

        # Markup to separate optional inputs
        opthelpstr = ["", "[Optional]", ""]

        # Get all optional input traits
        optional_items = self.traits(output=False, optional=True)
        optional_items.update(self.traits(output=None, optional=True))

        # If we have optional inputs, get the corresponding string
        # descriptions
        data = []
        if optional_items:
            for trait_name, trait in six.iteritems(optional_items):
                data.append(
                    get_trait_desc(trait_name, trait))

        # If we want to format the output nicely (rst)
        if data != []:
            if rst_formating:
                opthelpstr += self._rst_table(data)
            # Otherwise
            else:
                opthelpstr += functools.reduce(operator.add, data)

        # Add the mandatry and optional input string description if necessary
        if mandatory_items:
            helpstr += manhelpstr
        if optional_items:
            helpstr += opthelpstr

        return helpstr

    def get_output_help(self, rst_formating=False):
        """ Generate description for process output parameters.

        Parameters
        ----------
        rst_formating: bool (optional, default False)
            if True generate a rst table witht the input descriptions.

        Returns
        -------
        helpstr: str
            the trait output help descriptions
        """
        # Generate an output section
        helpstr = ["Outputs", "~" * 7, ""]

        # Get all the process output traits
        items = self.traits(output=True)

        # If we have no output trait, return no string description
        if not items:
            return [""]

        # If we have some outputs, get the corresponding string
        # descriptions
        data = []
        for trait_name, trait in six.iteritems(items):
            data.append(
                get_trait_desc(trait_name, trait))

        # If we want to format the output nicely (rst)
        if data != []:
            if rst_formating:
                helpstr += self._rst_table(data)
            # Otherwise
            else:
                helpstr += functools.reduce(operator.add, data)

        return helpstr

    def set_parameter(self, name, value):
        """ Method to set a process instance trait value.

        For File and Directory traits the None value is replaced by the
        special _Undefined trait value.

        Parameters
        ----------
        name: str (mandatory)
            the trait name we want to modify
        value: object (mandatory)
            the trait value we want to set
        """
        # The None trait value is _Undefined, do the replacement
        if value is None:
            value = _Undefined()

        # Set the new trait value
        setattr(self, name, value)

    def get_parameter(self, name):
        """ Method to access the value of a process instance.

        Parameters
        ----------
        name: str (mandatory)
            the trait name we want to modify

        Returns
        -------
        value: object
            the trait value we want to access
        """
        return getattr(self, name)

    def get_study_config(self):
        ''' Get (or create) the StudyConfig this process belongs to
        '''
        if self.study_config is None:
            # Import cannot be done on module due to circular dependencies
            from capsul.study_config.study_config import default_study_config
            self.set_study_config(default_study_config())
        return self.study_config

    def set_study_config(self, study_config):
        ''' Set a StudyConfig for the process.
        Note that it can only be done once: once a non-null StudyConfig has
        been assigned to the process, it should not change.
        '''
        if self.study_config is not None \
                and self.study_config is not study_config:
            raise ValueError("A StudyConfig had already been set in the "
                             "process %s. It cannot be changed afterwards."
                             % self.name)
        self.study_config = study_config

    def get_missing_mandatory_parameters(self):
        ''' Returns a list of parameters which are not optional, and which
        value is Undefined or None, or an empty string for a File or
        Directory parameter.
        '''
        def check_trait(trait, value):
            if trait.optional:
                return True
            if hasattr(trait, 'inner_traits') and len(trait.inner_traits) != 0:
                for i, item in enumerate(value):
                    j = min(i, len(trait.inner_traits) - 1)
                    if not check_trait(trait.inner_traits[j], item):
                        return False
                return True
            if isinstance(trait.trait_type, (File, Directory)):
                if trait.output and not trait.input_filename:
                    return True
                return value not in (Undefined, None, '')
            return trait.output or value not in (Undefined, None)

        missing = []
        for name, trait in six.iteritems(self.user_traits()):
            if not trait.optional:
                value = self.get_parameter(name)
                if not check_trait(trait, value):
                    missing.append(name)
        return missing

class InteractiveProcess(Process):
    '''
    Base class for interactive processes. The value of the is_interactive 
    parameter determine if either the process can be run in background
    (eventually remotely) as a standardl process (is_interactive = False)
    or if the process must be executed interactively in the user environment
    (is_interactive = False).
    '''
    is_interactive = Bool(False)

class ProcessResult(object):
    """ Object that contains running information a particular Process.

    Parameters
    ----------
    process : Process class (mandatory)
        A copy of the `Process` class that was called.
    runtime : dict (mandatory)
        Execution attributes.
    returncode: dict (mandatory)
        Execution raw attributes
    inputs :  dict (optional)
        Representation of the process inputs.
    outputs : dict (optional)
        Representation of the process outputs.
    """

    def __init__(self, process, runtime, returncode, inputs=None,
                 outputs=None):
        """ Initialize the ProcessResult class.
        """
        self.process = process
        self.runtime = runtime
        self.returncode = returncode
        self.inputs = inputs
        self.outputs = outputs
