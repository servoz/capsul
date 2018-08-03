:orphan:

.. _capsul_guide:

##########
User Guide
##########

This section of the documentation is the right places for beginers. It introduce the main concepts of Capsul and explain them with examples of use. The main characteristic of Capsul is its ability to be used in many contexts. Some of this usage context are simple. For instance a single user who wants to run processes on files on its computer does not need a complex context, he can use Capsul directly without configuration. On the other hand, when several users are sharing data with metadata and using a shared cluster to perform computing, it is necessary to have a database to handle metadata and an access to the cluster for running the processes. In these two examples, the user code to use Capsul can be the same in both contexts. The only thing that must be different is the entry point to Capsul. This entry point, that all Capsul user must starts with, is a ``CapsulEngine``. Since a Capsul engine captures all the specificity of a user context, it is possible to create many different Capsul engines but they all share the same `protocol <https://en.wikipedia.org/wiki/Protocol_(object-oriented_programming)>`_ (a protocol is used to specify a behavior that classes must implement, in Java it is called an `interface <https://en.wikipedia.org/wiki/Interface_(Java)>`_). 

For simple usage, a Capsul engine can be created without any parameter:

.. code-block:: python

    import capsul
    
    cengine = capsul.engine()

A Capsul engine follow a protocol allowing to save all its status in a `JSON <https://en.wikipedia.org/wiki/JSON>`_ dictionary. Therefore, if a Capsul engine had been previously saved, one can re-create it from the file name (it is also possible to use a dictionary with the Capsul engine configuration) :

.. code-block:: python

    import os.path
    import capsul
    
    json_file = os.path.expandvars('$HOME/my_study/capsul_engine.json')
    cengine = capsul.engine(json_file)

=======================
Basic process execution
=======================

With a Capsul engine, it is possible to execute processing either synchronously (i.e. waiting for the process to finish before doing anything else) or asynchronously (i.e. starting the process in background). For instance, to run FSL BET synchronously using Nipype interface (Capsul can directly use Nipype interfaces), one can use the following code:

.. code-block:: python

    cengine.run('nipype.interfaces.fsl.BET', in_file='/somewhere/t1_mri.nii')

To start the process in background, simply use ``start()`` instead of ``run()`` :

.. code-block:: python

    bet_proxy = cengine.start('nipype.interfaces.fsl.BET', in_file='/somewhere/t1_mri.nii')
    
The returned object is an ``ExecutionProxy``. It can be used to retrieve information about the process execution or to wait for the execution to finish :

.. code-block:: python

    # Wait for the end of BET execution
    bet_proxy.wait()
    if bet_proxy.has_failed:
        print('Something went wrong')

On of the important feature of Capsul is that client program (i.e. the program that started the process) can quit and another client can be used later to get information about the process. For instance, you can run the following code then quit :

.. code-block:: python

    import capsul
    
    cengine = capsul.engine()
    bet_proxy = cengine.start('nipype.interfaces.fsl.BET', capsul_uiid='I am unique', in_file='/somewhere/t1_mri.nii')

An then run another Python to wait for the termination of the process :

.. code-block:: python

    import capsul
    
    cengine = capsul.engine()
    bet_proxy = cengine.processing_engine.find_execution(capsul_uuid='I am unique')
    bet_proxy.wait()
    
    
=======================
Capsul engine
=======================
A Capsul engine simply brings together four objects that are dedicated to specific tasks :

* ``execution_context``: an execution context contains all the information necessary to start a job. For instance, in a previous example we used a process running FSL software. In order to use FSL, it is necessary to setup a few environment variables whose content depends on the location where FSL is installed. The execution context contains the information about FSL installation necessary to define these environment variable when a job is started. The execution context is shared with each processing nodes and used to build the execution environment of each job.
* ``processing_engine``: a processing engine contains the configuration of a computing ressource. It is able to start jobs on this ressource (typically using Soma-workflow). Its API allows to start the execution of simple processes and complex pipelines, to monitor their execution and to interact with the underlying jobs. For instance, it is used to check the execution status of all jobs of a pipeline ad to retrieve the standard error output of jobs that failed.
* ``database_engine``: a database engine is used to store, retrieve and query information structured information. It is used to store metadata (information that describe the data such as subject, modality, format, etc.) and processing related information (such as history of processings).
* ``metadata_engine``: the metadata engine is responsible of data organization and of the production of metadata. For instance, it allows to retrieve metadata for a file given its path, it can generate a path for an output file given metadata, etc. 
.. 
.. =======================
.. Tutorial
.. =======================
.. 
.. Tutorial is available as a `Jupyter notebook <https://jupyter.org/>`_ (Jupyter is the new name for `IPython notebook <http://ipython.org/notebook.html>`_).
.. 
..   .. ifconfig:: 'nbsphinx' in extensions
.. 
..       * `See the notebook contents <../_static/tutorial/capsul_tutorial.html>`_
..       * `Download notebook <../_static/tutorial/capsul_tutorial.ipynb>`_ (for use with Jupyter)
.. 
.. 
.. To run it, the following must be done:
.. 
.. * :ref:`install_guid`.
.. * have IPython installed.
.. * run the tutorial ipython notebook server, with Qt GUI support:
.. 
..     .. code-block:: bash
.. 
..         jupyter notebook --gui=qt my_tutorial.ipynb
.. 
.. 
.. .. Building processes
.. .. ##################
.. .. 
.. .. 
.. .. Building pipelines
.. .. ##################
.. .. 
.. .. Python API
.. .. ==========
.. .. .. 
.. .. Graphical display and edition
.. .. =============================
.. .. 
.. .. 
.. .. Configuration
.. .. #############
.. .. 
.. .. StudyConfig object, options, modules
.. .. ====================================
.. .. 
.. .. Data paths
.. .. 
.. .. Execution options: Soma-Workflow
.. 
.. 
.. =======================
.. Running Capsul
.. =======================
.. 
.. Running as commandline
.. ----------------------
.. 
.. CAPSUL has a commandline program to run any process, pipeline, or process iteration. It can be used from a shell, or a script. It allows to run locally, either sequentially or in parallel, or on a remote processing server using Soma-Workflow.
.. 
.. The program is a python module/script:
.. 
.. .. code-block:: bash
.. 
..     python -m capsul <parameters>
.. 
.. or, especially if run with Python 2.6 which does not accept the former (it does the same otherwise):
.. 
.. .. code-block:: bash
.. 
..     python -m capsul.run <parameters>
.. 
.. It can accept a variety of options to control configuration settings, processing modes, iterations, and process parameters either through file names or via attributes and paramters completion system.
.. 
.. To get help, you may run it with the ``-h`` or ``--help`` option:
.. 
.. .. code-block:: bash
.. 
..     python -m capsul -h
.. 
.. **Ex:**
.. 
.. .. code-block:: bash
.. 
..     python -m capsul --swf -i /home/data/study_data --studyconfig /home/data/study_data/study_config.json -a subject=subjet01 -a center=subjects morphologist.capsul.morphologist.Morphologist
.. 
.. will run the Morphologist pipeline on data located in the directory ``/home/data/study_data`` using Soma-Workflow on the local computer, for subject ``subject01``
.. 
.. **Ex with iteration:**
.. 
.. .. code-block:: bash
.. 
..     python -m capsul --swf -i /home/data/study_data --studyconfig /home/data/study_data/study_config.json -a subject='["subjet01", "subject02", "subject03"]' -a center=subjects -I t1mri morphologist.capsul.morphologist.Morphologist
.. 
.. will iterate the same process 3 times, for 3 different subjects.
.. 
.. To work correctly, StudyConfig settings have to be correctly defined in ``study_config.json`` including FOM completion parameters, external software, formats, etc.
.. 
.. Alternatively, or in addition to attributes, it is possible to pass process parameters as additional options after the process name. They can be passed either as positional arguments (given in the order the process expects), or as "keyword" arguments:
.. 
.. .. code-block:: bash
.. 
..   python -m capsul --swf -i /home/data/study_data --studyconfig /home/data/study_data/study_config.json -a subject=subjet01 -a center=subjects morphologist.capsul.morphologist.Morphologist /home/data/raw_data/subject01.nii.gz pipeline_steps='{"importation": True, "orientation": True}'
.. 
.. To get help about a process, its parameters, and available attributes to control its completion:
.. 
.. .. code-block:: bash
.. 
..   python -m capsul --process-help morphologist.capsul.morphologist.Morphologist
.. 
.. 
.. .. Simple, sequential execution
.. .. ============================
.. .. 
.. .. Distributed execution
.. .. =====================
.. .. 
.. .. Running on-the-fly using StudyConfig
.. .. ------------------------------------
.. .. 
.. .. Generating and saving workflows
.. .. -------------------------------
.. =======================
.. XML Specifications
.. =======================
.. 
.. Processes may be functions with XML specifications for their parameters.
.. 
.. Pipelines can be saved and loaded as XML files.
.. 
.. :doc:`The specs of XML definitions can be found on this page. <xml_spec>`
.. 
.. =======================
.. Advanced usage
.. =======================
.. 
.. :doc:`More advanced features can be found on this page. <advanced_usage>`
