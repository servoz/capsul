'''
This module defines the main API to interact with Capsul processes.
In order to execute a process, it is mandatory to have an instance of
:py:class:`Platform`. Such an instance can be created with constructor
or by using a JSON representation of the instance (created by 
:py:meth:`Platform.to_json`) with
:py:func:`soma.serialization.from_json`
'''
import json
import os.path as osp

from soma.serialization import JSONSerializable, to_json, from_json

from capsul.engine.database import PopulseDBEngine


class CapsulEngine(JSONSerializable):
    def __init__(self, execution_context, processing_engine, database_engine, metadata_engine):
        self._execution_context = execution_context
        self._processing_engine = processing_engine
        self._database_engine = database_engine
        self._metadata_engine = metadata_engine
        self._json_file = None

    @property
    def execution_context(self):
        return self._execution_context
    
    @property
    def processing_engine(self):
        return self._processing_engine
    
    @property
    def database_engine(self):
        return self._database_engine
    
    @property
    def metadata_engine(self):
        return self._metadata_engine
    

    @property
    def json_file(self):
        return self._json_file
    
    @json_file.setter
    def json_file(self, json_file):
        json_file = osp.normpath(osp.abspath(json_file))
        if json_file != self._json_file:
            self._json_file = json_file
    
    def save(self):
        if self.json_file:
            json_obj = self.to_json()
            json.dump(json_obj, open(self.json_file, 'w'), indent=2)
        else:
            raise RuntimeError('Cannot save a Capsul engine without json_file defined')
    
    def to_json(self):
        '''
        Returns a dictionary containing JSON compatible representation of
        the engine.
        '''
        kwargs = {'execution_context': to_json(self.execution_context),
                  'processing_engine': to_json(self.processing_engine),
                  'database_engine': to_json(self.database_engine),
                  'metadata_engine': to_json(self.metadata_engine)}
        return ['capsul.engine_from_json', kwargs]


def engine(json_file=None):
    '''
    User facrory for capsul engines
    '''
    if json_file is None:
        json_file = osp.expanduser('~/.config/capsul/capsul_engine.json')
    capsul_engine_directory = osp.abspath(osp.dirname(json_file))
    if osp.exists(json_file):
        result = from_json(json.load(open(json_file)))
    else:
        base_directory = osp.dirname(json_file)
        sqlite_file = osp.join(base_directory, 'capsul_database.sqlite')
        database_engine = 'sqlite:///%s' % sqlite_file
        result = CapsulEngine(None, None, PopulseDBEngine(database_engine), None)
    result.json_file = json_file
    result.database_engine.set_named_directory('capsul_engine', capsul_engine_directory)
    return result


def engine_from_json(execution_context, processing_engine, database_engine, metadata_engine):
   return CapsulEngine(from_json(execution_context),
                       from_json(processing_engine),
                       from_json(database_engine),
                       from_json(metadata_engine))
    

#class Platform(JSONSerializable):
    #'''
    #`Platform` is the main class for using processes in Capsul.
    
    #.. py:attribute:: metadata_engine
    
        #:py:class:`MetadataEngine` instance used by this platform

    #.. py:attribute:: processing_engine
    
        #:py:class:`ProcessingEngine` instance used by this platform
    
    #.. py:attribute:: database_engine

        #:py:class:`DatabaseEngine` instance used by this platform
    #'''
    #def __init__(self, workflow_engine, metadata_engine,
                 #processing_engine, database_engine):
        #self.workflow_engine = workflow_engine
        #self.metadata_engine = metadata_engine
        #self.processing_engine = processing_engine
        #self.database_engine = database_engine
    
    
    #def get_process_in_platform(self, process_source):
        #'''
        #Returns a ProcessInPlatform instance for the given process
        #'''
        #process = self.workflow_engine.execution_context.get_process_instance(process_source)
        #return ProcessInPlatform(process)
        
    
    #def submit(self, process_in_platform, **kwargs):
        #'''
        #Receive a processing query to be executed as soon as possible. 
        #It creates a new ExecutionState instance and returns its uuid.
        #'''
        ## Split kwargs arguments between process parameters and metadata
        ## parameters
           
        #process_metadata = self.metadata_engine.metadata_parameters(process)
        #metadata_traits = process_metadata.user_traits()
        #process_traits = process.user_traits()
        #has_metadata_parameters = False
        #for k, v in six.iteritems(kwargs):
            #if k in process_traits:
                #setattr(process, k, v)
            #elif metadata_traits is not None and k in metadata_traits:
                #setattr(process_metadata, k, v)
                #has_metadata_parameters = True
            #else:
                #raise ValuError("Process %s got an unexpected argument '%s'" % (process.id, k))
        
        ## Perform path completion if at least one metadata parameter was used
        #if has_metadata_parameters:
            #self.metadata_engine.generate_paths(process, process_metadata)
        
        ## Declare the submission to the database
        #process_history_id = self.database_engine.new_process_history(self, process, process_metadata)
        
        ## submit the process to the processing engine
        #job_id = self.processing_engine.submit(process)
        #self.database_engine.change_process_history(process_history_id, job_id=job_id)
        #self.update_process_history(process_history_id)
        
        #return process_history_id
    
    #def status(self, process_history_id):
        #'''
        #Returns None if the uuid does not correspond to an Execution instance
        #known by the server. Otherwise, returns the status of the processing 
        #corresponding to the query. See ProcessingEngine.status().
        #'''
        #db_status = self.database_engine.status(process_history_id)
        #if db_status is not None:
            #job_id = self.database_engine.job_id(process_history_id)
            #if job_id is not None:
                #job_status = self.processing_engine.status(job_status)
                #if job_status != db_status:
                    #self.update_process_history(process_history_id)
                    #db_status = self.database_engine.status(process_history_id)
        #return db_status
    
    #def update_process_history(process_history_id):
        #job_id = self.database_engine.job_id(process_history_id)
        #if job_id is not None:
            #job_state = self.processing_engine.state(job_id)
            #if job_state is not None:
                #self.database_engine.change_process_history(
                    #process_history_id,
                    #status=job_state['status'],
                    #job_state=job_state)

    #def process_history(process_history_id):
        #return self.database_engine.get_process_history(process_history_id)
    
    #def to_json(self):
        #'''
        #Returns a dictionary containing JSON compatible representation of
        #the engine.
        #'''
        #kwargs = {'metadata_engine': self.metadata_engine.to_json(),
                 #'processing_engine': self.processing_engine.to_json()}
        #if self.database_engine is not None:
            #kwargs['database_engine'] = self.database_engine.to_json()
        #return ['capsul.engine.platform', kwargs]

#def platform(workflow_engine, metadata_engine, processing_engine,
             #database_engine):
    #'''
    #Factory to create a `Platform`instance from its JSON serialization.
    #'''
    #return Platform(from_json(workflow_engine),
                    #from_json(metadata_engine),
                    #from_json(processing_engine),
                    #from_json(database_engine))



class WorkflowEngine(JSONSerializable):
    '''
    A WorkflowEngine is used to convert a process or pipeline into a Workflow.
    Basically, a workflow is a series of command lines with dependencies (i.e.
    links saying that a command must be run before another). But, a workflow
    can contain more advanced features for dealing with :
      - File transfers
      - Temporary files management
      - Dynamic output management
      - Dynamic exectution of commands (i.e. running commands that are
        produced by other commands).
    '''
    def __init__(self, execution_context):
        '''
        Creation of a WorkflowEngine. A workflow engine is always connected
        to an execution context.
        '''
        self._execution_context = execution_context
    
    @property
    def execution_context(self):
        '''
        ExecutionContext instance attached to this WorkflowEngine.
        '''
        return self._execution_context

    def workflow(self, process):
        '''
        Creates a workflow for a process or pipeline.
        '''
        raise NotImplementedError()

class ProcessingEngine(JSONSerializable):
    '''
    This class is a kind of JSON serializable version of a WorkflowController
    API. It is used to define the minimum API required for Platform but
    could be replaced by a real Soma Workflow class.
    '''

    def submit(self, workflow):
        '''
        Start execution of a workflow as soon as possible. Returns a workflow
        identifier.
        '''
        raise NotImplementedError()


    def status(self, workflow_id):
        '''
        Returns a simple status of the workflow execution (or None if workflow_id
        is not known) :
            'not_submitted':
                The job was not submitted yet to soma-workflow.
            'pending':
                Due to a limitation of the number of job in the queue (see
                Configuration items optional on the server side:), the job is
                waiting to be submitted to the DRMS.
            'queued':
                The job was submitted to the DRMS and is currently waiting in
                the queue.
            'running':
                The job is running on the computing resource.
            'done':
                The job finished normally. However it does not mean that it
                ended with success (see job exit status).
            'failed':
                The job exited abnormally before finishing.
            'undetermined':
                Transitive status. The job status is changing and will be
                updated soon.
        '''
        raise NotImplementedError()


    def state(self, workflow_id):
        '''
        Returns the full state of the workflow execution (or None if workflow_id
        is not known).
        '''
        raise NotImplementedError()

    def wait(self, workflow_id, timeout=None):
        '''
        Wait for a workflow execution to be finished.
        Returns the status of the workflow (or None if workflow_id
        is not known).
        '''
        raise NotImplementedError()


class DatabaseEngine(JSONSerializable):
    def new_processing_history(self, processing_query):
        raise NotImplementedError()

    def get_processing_history(self, processing_history_id):
        raise NotImplementedError()

    def change_processing_history(self, processing_history_id,
                               status=None,
                               job_id=None,
                               job_state=None):
        raise NotImplementedError()

    def status(self, processing_history_id):
        raise NotImplementedError()

    def job_id(self, processing_history_id):
        raise NotImplementedError()

    def to_json(self):
        raise NotImplementedError()


class MetadataEngine(JSONSerializable):
    def meta_parameters(self, process):
        '''
        Returns a Controller whose traits defines an alternative parameter 
        set for the given process. This alternative parameter set is called
        meta parameters of the process. The returned controller must have a
        `meta_links` attribute containing a dictionary that associate each
        meta parameter to the process parameter(s) that can be modified if
        the meta parameter value is changed.
        '''
        raise NotImplementedError()
    
    def set_process_parameters(self, meta_parameters, process):
        '''
        Set the process parameters according to the value of its
        meta parameters.
        '''
        raise NotImplementedError()
    
    def process_attributes(self, processing_query):
        '''
        Returns attributes metadata associated to a process.
        These metadata can be generated before the execution of the process,
        therefore they must only rely on input parameters. 
        '''
        raise NotImplementedError()
    
    def process_result_attributes(self, process):
        '''
        Returns a dictionary that associate output parameters of the process
        with their metadata attributes. This method must be called once the
        process execution is finished. 
        '''
        raise NotImplementedError()


class ProcessingQuery(object):
    '''
    '''
    def __init__(self, platform, process):
        self.platform = platform
        self.process = process
        self.meta_parameters = self.platform.metadata_engine.meta_parameters(self.process)
        self._parameters = {}
        self._has_meta_parameters = False
        
    def set_parameters(**kwargs):        
        process_traits = process.user_traits()
        meta_parameters_traits = self.meta_parameters.user_traits()
        for k, v in six.iteritems(kwargs):
            if k in process_traits:
                setattr(self.process, k, v)
                self._parameters[k] = v
            elif meta_parameters_traits is not None and k in meta_parameters_traits:
                setattr(self.meta_parameters, k, v)
                self._parameters[k] = v
                has_metadata_parameters = True
            else:
                raise ValuError("Process %s got an unexpected argument '%s'" % (process.id, k))
        
        # Perform path completion if at least one metadata parameter was used
        if self.has_metadata_parameters:
            self.platform.metadata_engine.set_process_parameters(self.meta_parameters, self.process)

    def to_json(self):
        '''
        Returns a dictionary containing JSON compatible representation of
        thi processing query.
        '''
        kwargs = {'platform': self.platform.to_json(),
                  'process': self.process.id,
                  'parameters': self._parameters}
        return ['capsul.engine.processing_query', kwargs]

def processing_query(platform, process, parameters):
    '''
    Factory to create a `ProcessingQuery` instance from its JSON serialization.
    '''
    platform = from_json(platform)
    process = platform.workflow_engine.execution_context.get_process_instance(process)
    result = ProcessingQuery(platform, process)
    result.set_parameters(**parameters)
    