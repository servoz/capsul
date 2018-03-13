import os
import operator
from copy import deepcopy
import json
try:
    import subprocess32 as subprocess
except ImportError:
    import subprocess
import six
import sys
import functools

from traits.trait_base import _Undefined
from traits.api import Directory, Undefined, Int, List, Bool, File
from traits.trait_handlers import BaseTraitHandler

from soma.controller import Controller
from soma.controller import trait_ids
from soma.controller.trait_utils import is_trait_value_defined
from soma.controller.trait_utils import is_trait_pathname
from soma.controller.trait_utils import get_trait_desc

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


def _rst_table(data):
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

class Process(six.with_metaclass(ProcessMeta, Controller)):
    """ A process is an atomic component that contains a processing.

    A process is typically an object with typed parameters, and an execution
    function. Parameters are described using Enthought
    `traits <http://docs.enthought.com/traits/>`_ through Soma-Base
    :somabase:`Controller <api.html#soma.controller.controller.Controller>`
    base class.

    In addition to describing its parameters, a Process must implement its
    execution function, either through a python method, by overloading
    :meth:`run_process`, or through a commandline execution, by overloading
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

            def run_process(self):
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
    run_process
    add_trait
    help
    get_input_help
    get_output_help
    get_commandline
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

            This method should **not** be overloaded by Process subclasses to
            perform actual processing. Instead, either the
            :meth:`_run_process` method or the :meth:`get_commandline` method
            should be overloaded.

        Parameters
        ----------
        kwargs: dict (optional)
            should correspond to the declared parameter traits.

        """
        from capsul.engine.processing import default_execution_context
        for k, v in six.iteritems(kwargs):
            self.set_parameter(k, v)
        default_execution_context.run(self)
    
    def run_process(self):
        """This method contains the code to run when the process is executed.

        Either this :meth:`run_process` or :meth:`get_commandline` must be
        defined in derived classes. But not both. If the execution code of a
        process is in Python, it must be defined in :meth:`get_commandline`.
        On the other hand, if the process encapsulate a command line that does
        not need Python, one should use :meth:`get_commandline` to define it.
        """
        raise NotImplementedError(
                "Either get_commandline() or run_process() should be "
                "redefined in process ({0})".format(self.id))
    
    def get_commandline(self):
        """ Method to generate a comandline representation of the process.

        Either this :meth:`get_commandline` or :meth:`run_process` must be
        defined in derived classes. But not both. If the execution code of a
        process is in Python, it must be defined in :meth:`get_commandline`.
        On the other hand, if the process encapsulate a command line that does
        not need Python, one should use :meth:`get_commandline` to define it.

        Returns
        -------
        commandline: list of strings
            Arguments are in separate elements of the list.
        """
        raise NotImplementedError(
                "Either get_commandline() or _run_process() should be "
                "redefined in process ({0})".format(self.id))


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
                manhelpstr += _rst_table(data)
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
                opthelpstr += _rst_table(data)
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
                helpstr += _rst_table(data)
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
