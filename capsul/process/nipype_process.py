import sys
import glob
import os
import types
import logging
import traceback
import six
import shutil

from traits.api import Directory, CTrait, Undefined, Int

from soma.controller.trait_utils import trait_ids
from capsul.process.process import Process

# Define the logger
logger = logging.getLogger(__name__)


class FileCopyProcess(Process):
    """ A specific process that copies all the input files.

    Attributes
    ----------
    `copied_inputs` : list of 2-uplet
        the list of copied files (src, dest).

    Methods
    -------
    __call__
    _update_input_traits
    _get_process_arguments
    _copy_input_files
    """
    def __init__(self, activate_copy=True, inputs_to_copy=None,
                 inputs_to_clean=None, destination=None):
        """ Initialize the FileCopyProcess class.

        Parameters
        ----------
        activate_copy: bool (default True)
            if False this class is transparent and behaves as a Process class.
        inputs_to_copy: list of str (optional, default None)
            the list of inputs to copy.
            If None, all the input files are copied.
        inputs_to_clean: list of str (optional, default None)
            some copied inputs that can be deleted at the end of the
            processing.
        destination: str (optional default None)
            where the files are copied.
            If None, files are copied in a '_workspace' folder included in the
            image folder.
        """
        # Inheritance
        super(FileCopyProcess, self).__init__()

        # Class parameters
        self.activate_copy = activate_copy
        self.destination = destination
        if self.activate_copy:
            self.inputs_to_clean = inputs_to_clean or []
            if inputs_to_copy is None:
                self.inputs_to_copy = self.user_traits().keys()
            else:
                self.inputs_to_copy = inputs_to_copy
            self.copied_inputs = None

    def _before_run_process(self):
        """ Method to copy files before executing the process.
        """
        # The copy option is activated
        if self.activate_copy:

            # Copy the desired items
            self._update_input_traits()

            # Set the process inputs
            for name, value in six.iteritems(self.copied_inputs):
                self.set_parameter(name, value)

    def _after_run_process(self, run_process_result):
        """ Method to clean-up temporary workspace after process
        execution.
        """
        # The copy option is activated
        if self.activate_copy:
            # Clean the workspace
            self._clean_workspace()
        return run_process_result

    def _clean_workspace(self):
        """ Removed som copied inputs that can be deleted at the end of the
        processing.
        """
        for to_rm_name in self.inputs_to_clean:
            if to_rm_name in self.copied_inputs:
                self._rm_files(self.copied_inputs[to_rm_name])

    def _rm_files(self, python_object):
        """ Remove a set of copied files from the filesystem.

        Parameters
        ----------
        python_object: object
            a generic python object.
        """
        # Deal with dictionary
        if isinstance(python_object, dict):
            for val in python_object.values():
                self._rm_files(val)

        # Deal with tuple and list
        elif isinstance(python_object, (list, tuple)):
            for val in python_object:
                self._rm_files(val)

        # Otherwise start the deletion if the object is a file
        else:
            if (isinstance(python_object, basestring) and
                    os.path.isfile(python_object)):
                os.remove(python_object)

    def _update_input_traits(self):
        """ Update the process input traits: input files are copied.
        """
        # Get the new trait values
        input_parameters = self._get_process_arguments()
        self.copied_inputs = self._copy_input_files(input_parameters)

    def _copy_input_files(self, python_object):
        """ Recursive method that copy the input process files.

        Parameters
        ----------
        python_object: object
            a generic python object.

        Returns
        -------
        out: object
            the copied-file input object.
        """
        # Deal with dictionary
        # Create an output dict that will contain the copied file locations
        # and the other values
        if isinstance(python_object, dict):
            out = {}
            for key, val in python_object.items():
                if val is not Undefined:
                    out[key] = self._copy_input_files(val)

        # Deal with tuple and list
        # Create an output list or tuple that will contain the copied file
        # locations and the other values
        elif isinstance(python_object, (list, tuple)):
            out = []
            for val in python_object:
                if val is not Undefined:
                    out.append(self._copy_input_files(val))
            if isinstance(python_object, tuple):
                out = tuple(out)

        # Otherwise start the copy (with metadata cp -p) if the object is
        # a file
        else:
            out = python_object
            if (python_object is not Undefined and
                    isinstance(python_object, basestring) and
                    os.path.isfile(python_object)):
                srcdir = os.path.dirname(python_object)
                if self.destination is None:
                    destdir = os.path.join(srcdir, "_workspace")
                else:
                    destdir = self.destination
                if not os.path.exists(destdir):
                    os.makedirs(destdir)
                fname = os.path.basename(python_object)
                out = os.path.join(destdir, fname)
                shutil.copy2(python_object, out)
                
                # Copy associated .mat files
                name = fname.split(".")[0]
                matfnames = glob.glob(os.path.join(
                    os.path.dirname(python_object), name + ".*"))
                for matfname in matfnames:
                    extrafname = os.path.basename(matfname)
                    extraout = os.path.join(destdir, extrafname)
                    shutil.copy2(matfname, extraout)

        return out

    def _get_process_arguments(self):
        """ Get the process arguments.

        The user process traits are accessed through the user_traits()
        method that returns a sorted dictionary.

        Returns
        -------
        input_parameters: dict
            the process input parameters.
        """
        # Store for input parameters
        input_parameters = {}

        # Go through all the user traits
        for name, trait in six.iteritems(self.user_traits()):
            if trait.output:
                continue
            # Check if the target parameter is in the check list
            if name in self.inputs_to_copy:
                # Get the trait value
                value = self.get_parameter(name)
                # Skip undefined trait attributes and outputs
                if value is not Undefined:
                    # Store the input parameter
                    input_parameters[name] = value

        return input_parameters


class NipypeProcess(FileCopyProcess):
    """ Base class used to wrap nipype interfaces.
    """
    def __init__(self, nipype_instance, *args, **kwargs):
        """ Initialize the NipypeProcess class.

        NipypeProcess instance get automatically an additional user trait
        'output_directory'.

        This class also fix also some lake of the nipye version '0.10.0'.

        Parameters
        ----------
        nipype_instance: nipype interface (mandatory)
            the nipype interface we want to wrap in capsul.

        Attributes
        ----------
        _nipype_interface : Interface
            private attribute to store the nipye interface
        _nipype_module : str
            private attribute to store the nipye module name
        _nipype_class : str
            private attribute to store the nipye class name
        _nipype_interface_name : str
            private attribute to store the nipye interface name
        """
        # Set some class attributes that characterize the nipype interface
        self._nipype_interface = nipype_instance
        self._nipype_module = nipype_instance.__class__.__module__
        self._nipype_class = nipype_instance.__class__.__name__
        msplit = self._nipype_module.split(".")
        if len(msplit) > 2:
            self._nipype_interface_name = msplit[2]
        else:
            self._nipype_interface_name = 'custom'

        # Inheritance: activate input files copy for spm interfaces.
        if self._nipype_interface_name == "spm":
            # Copy only 'copyfile' nipype traits
            inputs_to_copy = self._nipype_interface.inputs.traits(
                copyfile=True).keys()
            super(NipypeProcess, self).__init__(
                activate_copy=True, inputs_to_copy=inputs_to_copy,
                *args, **kwargs)
        else:
            super(NipypeProcess, self).__init__(
                  activate_copy=False, *args, **kwargs)

        # Replace the process name and identification attributes
        self.id = ".".join([self._nipype_module, self._nipype_class])
        self.name = self._nipype_interface.__class__.__name__

        # Add a new trait to store the processing output directory
        super(Process, self).add_trait(
            "output_directory", Directory(Undefined, exists=True,
                                          optional=True))

        # Add a 'synchronize' nipype input trait that will be used to trigger
        # manually the output nipype/capsul traits sync.
        super(Process, self).add_trait("synchronize", Int(0, optional=True))


    def set_output_directory(self, out_dir):
        """ Set the process output directory.

        Parameters
        ----------
        out_dir: str (mandatory)
            the output directory
        """
        self.output_directory = out_dir

    def set_usedefault(self, parameter, value):
        """ Set the value of the usedefault attribute on a given parameter.

        Parameters
        ----------
        parameter: str (mandatory)
            name of the parameter to modify.
        value: bool (mandatory)
            value set to the usedefault attribute
        """
        setattr(self._nipype_interface.inputs, parameter, value)

    def _before_run_process(self):
        if self._nipype_interface_name == "spm":
            # Set the spm working
            self.destination = self.output_directory
        super(NipypeProcess, self)._before_run_process()
    
    def _run_process(self):
        """ Method that do the processings when the instance is called.

        Returns
        -------
        runtime: InterfaceResult
            object containing the running results
        """
        self._before_run_process()
        try:
            cwd = os.getcwd()
        except OSError:
            cwd = None
        if self.output_directory is None or self.output_directory is Undefined:
            raise ValueError('output_directory is not set but is mandatory '
                             'to run a NipypeProcess')
        os.chdir(self.output_directory)
        self.synchronize += 1

        # Force nipype update
        for trait_name in self._nipype_interface.inputs.traits().keys():
            if trait_name in self.user_traits():
                old = getattr(self._nipype_interface.inputs, trait_name)
                new = getattr(self, trait_name)
                if old is Undefined and old != new:
                    setattr(self._nipype_interface.inputs, trait_name, new)

        results = self._nipype_interface.run()
        self.synchronize += 1
        
        # For spm, need to move the batch
        # (create in cwd: cf nipype.interfaces.matlab.matlab l.181)
        if self._nipype_interface_name == "spm":
            mfile = os.path.join(
                os.getcwd(),
                self._nipype_interface.mlab.inputs.script_file)
            destmfile = os.path.join(
                self.output_directory,
                self._nipype_interface.mlab.inputs.script_file)
            if os.path.isfile(mfile):
                shutil.move(mfile, destmfile)
        
        # Restore cwd
        if cwd is not None:
            os.chdir(cwd)

        results = self._after_run_process(results)
        
        return results

    @classmethod
    def help(cls, nipype_interface, returnhelp=False):
        """ Method to print the full wraped nipype interface help.

        Parameters
        ----------
        cls: process class (mandatory)
            a nipype process class
        nipype_instance: nipype interface (mandatory)
            a nipype interface object that will be documented.
        returnhelp: bool (optional, default False)
            if True return the help string message,
            otherwise display it on the console.
        """
        from .nipype_process import nipype_factory
        cls_instance = nipype_factory(nipype_interface)
        return cls_instance.get_help(returnhelp)

def nipype_factory(nipype_instance):
    """ From a nipype class instance generate dynamically a process
    instance that encapsulate the nipype instance.

    This function clone the nipye traits (also convert special traits) and
    conect the process and nipype instances traits.

    A new 'output_directory' nipype input trait is created.

    Since nipype inputs and outputs are separated and thus can have
    the same names, the nipype process outputs are prefixed with '_'.

    It also monkey patch some nipype functions in order to execute the
    process in a specific directory:
    the monkey patching has been written for Nipype version '0.10.0'.

    Parameters
    ----------
    nipype_instance : instance (mandatory)
        a nipype interface instance.

    Returns
    -------
    process_instance : instance
        a process instance.

    See Also
    --------
    _run_interface
    _list_outputs
    _gen_filename
    _parse_inputs
    relax_exists_constrain
    sync_nypipe_traits
    sync_process_output_traits
    clone_nipype_trait
    """

    ####################################################################
    # Monkey patching for Nipype version '0.9.2'.
    ####################################################################

    # Change first level masking explicit in postscript
    def _make_matlab_command(self, content):
        from nipype.interfaces.spm import Level1Design
        return super(Level1Design, self)._make_matlab_command(
            content, postscript=None)
    if (nipype_instance.__class__.__module__.startswith('nipype.interfaces.spm.')
        and nipype_instance.__class__.__name__ == "Level1Design"):
        nipype_instance._make_matlab_command = types.MethodType(
            _make_matlab_command, nipype_instance)

    # Create new instance derived from Process
    process_instance = NipypeProcess(nipype_instance)

    ####################################################################
    # Define functions to synchronized the process and interface traits
    ####################################################################

    def relax_exists_constrain(trait):
        """ Relax the exist constrain of a trait

        Parameters
        ----------
        trait: trait
            a trait that will be relaxed from the exist constrain
        """
        # If we have a single trait, just modify the 'exists' contrain
        # if specified
        if hasattr(trait.handler, "exists"):
            trait.handler.exists = False

        # If we have a selector, call the 'relax_exists_constrain' on each
        # selector inner components.
        main_id = trait.handler.__class__.__name__
        if main_id == "TraitCompound":
            for sub_trait in trait.handler.handlers:
                sub_c_trait = CTrait(0)
                sub_c_trait.handler = sub_trait
                relax_exists_constrain(sub_c_trait)
        elif len(trait.inner_traits) > 0:
            for sub_c_trait in trait.inner_traits:
                relax_exists_constrain(sub_c_trait)

    def sync_nypipe_traits(process_instance, name, old, value):
        """ Event handler function to update the nipype interface traits

        Parameters
        ----------
        process_instance: process instance (mandatory)
            the process instance that contain the nipype interface we want
            to update.
        name: str (mandatory)
            the name of the trait we want to update.
        old: type (manndatory)
            the old trait value
        new: type (manndatory)
            the new trait value
        """
        # Set the new nypipe interface value
        setattr(process_instance._nipype_interface.inputs, name,
                value)

    def sync_process_output_traits(process_instance, name, value):
        """ Event handler function to update the process instance outputs

        This callback is only called when an input process instance trait is
        modified.

        Parameters
        ----------
        process_instance: process instance (mandatory)
            the process instance that contain the nipype interface we want
            to update.
        name: str (mandatory)
            the name of the trait we want to update.
        value: type (manndatory)
            the old trait value
        """
        # Get all the input traits
        input_traits = process_instance.traits(output=False)

        # Try to update all the output process instance traits values when
        # a process instance input trait is modified or when the dedicated
        # 'synchronize' trait value is modified
        if name in input_traits or name == "synchronize":

            # Try to set all the process instance output traits values from
            # the nipype autocompleted traits values
            try:
                nipype_outputs = (process_instance.
                                  _nipype_interface._list_outputs())

                # Synchronize traits: check file existance
                for out_name, out_value in six.iteritems(nipype_outputs):

                    # Get trait type
                    trait_type = trait_ids(
                        process_instance._nipype_interface.output_spec().
                        trait(out_name))

                    # Set the output process trait value
                    process_instance.set_parameter(
                        "_" + out_name, out_value)

            # If we can't update the output process instance traits values,
            # print a logging debug message.
            except Exception:
                ex_type, ex, tb = sys.exc_info()
                logger.debug(
                    "Something wrong in the nipype output trait "
                    "synchronization:\n\n\tError: {0} - {1}\n"
                    "\tTraceback:\n{2}".format(
                        ex_type, ex, "".join(traceback.format_tb(tb))))

    ####################################################################
    # Clone nipype traits
    ####################################################################

    # The following function is not shared since it is too specific
    def clone_nipype_trait(process_instance, nipype_trait):
        """ Create a new trait (cloned and converrted if necessary)
        from a nipype trait.

        Parameters
        ----------
        nipype_trait: trait
            the nipype trait we want to clone and convert if necessary.

        Returns
        -------
        process_trait: trait
            the cloned/converted trait that will be used in the process
            instance.
        """
        # Clone the nipype trait
        process_trait = process_instance._clone_trait(nipype_trait)

        # Copy some information from the nipype trait
        process_trait.desc = nipype_trait.desc
        process_trait.optional = not nipype_trait.mandatory
        process_trait._metadata = {}
        
        return process_trait

    # Add nipype traits to the process instance
    # > input traits
    for trait_name, trait in nipype_instance.input_spec().items():

        # Check if trait name already used in calss attributes:
        # For instance nipype.interfaces.fsl.FLIRT has a save_log bool input
        # trait.
        if hasattr(process_instance, trait_name):
            trait_name = "nipype_" + trait_name

        # Relax nipye exists trait contrain
        relax_exists_constrain(trait)

        # Clone the nipype trait
        process_trait = clone_nipype_trait(process_instance, trait)

        # Add the cloned trait to the process instance
        process_instance.add_trait(trait_name, process_trait)

        # Need to copy all the nipype trait information
        process_instance.trait(trait_name).optional = not trait.mandatory
        process_instance.trait(trait_name).desc = trait.desc
        process_instance.trait(trait_name).output = False

        # initialize value with nipype interface initial value
        setattr(process_instance, trait_name,
                getattr(nipype_instance.inputs, trait_name))

        # Add the callback to update nipype traits when a process input
        # trait is modified
        process_instance.on_trait_change(sync_nypipe_traits, name=trait_name)

    # Add callback to synchronize output process instance traits with nipype
    # autocompleted output traits
    process_instance.on_trait_change(sync_process_output_traits)

    # > output traits
    for trait_name, trait in nipype_instance.output_spec().items():

        # Clone the nipype trait
        process_trait = clone_nipype_trait(process_instance,trait)

        # Create the output process trait name: nipype trait name prefixed
        # by '_'
        private_name = "_" + trait_name

        # Add the cloned trait to the process instance
        process_instance.add_trait(private_name, process_trait)

        # Need to copy all the nipype trait information
        process_instance.trait(private_name).optional = not trait.mandatory
        process_instance.trait(private_name).desc = trait.desc
        process_instance.trait(private_name).output = True
        process_instance.trait(private_name).enabled = False

    return process_instance
