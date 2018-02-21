'''
This module defines the main API to interact with Capsul processes.
In order to execute a process, it is mandatory to have an instance of
:py:class:`CapsulEngine`. Such an instance can be created with constructor
or by using a JSON representation of the instance (created by 
:py:meth:`CapsulEngine.to_json`) with
:py:func:`soma.serialization.from_json`
'''

from soma.serialization import JSONSerializable, from_json

class CapsulEngine(JSONSerializable):
    '''
    `CapsulEngine` is the main class for using processes in Capsul.
    
    .. py:attribute:: metadata_engine
    
        :py:class:`MetadataEngine` instance used by this platform

    .. py:attribute:: processing_engine
    
        :py:class:`ProcessingEngine` instance used by this platform
    
    .. py:attribute:: database_engine

        :py:class:`DatabaseEngine` instance used by this platform
    '''
    def __init__(self, metadata_engine,
                 processing_engine, database_engine):
        self.metadata_engine = metadata_engine
        self.processing_engine = processing_engine
        self.database_engine = database_engine
        
    
    def submit(self, process, **kwargs):
        '''
        Receive a processing query to be executed as soon as possible. 
        It creates a new ExecutionState instance and returns its uuid.
        '''
        # Split kwargs arguments between process parameters and metadata
        # parameters
        process_metadata = self.metadata_engine.metadata_parameters(process)
        metadata_traits = process_metadata.user_traits()
        process_traits = process.user_traits()
        has_metadata_parameters = False
        for k, v in six.iteritems(kwargs):
            if k in process_traits:
                setattr(process, k, v)
            elif metadata_traits is not None and k in metadata_traits:
                setattr(process_metadata, k, v)
                has_metadata_parameters = True
            else:
                raise ValuError("Process %s got an unexpected argument '%s'" % (process.id, k))
        
        # Perform path completion if at least one metadata parameter was used
        if has_metadata_parameters:
            self.metadata_engine.generate_paths(process, process_metadata)
        
        # Declare the submission to the database
        process_history_id = self.database_engine.new_process_history(self, process, process_metadata)
        
        # submit the process to the processing engine
        job_id = self.processing_engine.submit(process)
        self.database_engine.change_process_history(process_history_id, job_id=job_id)
        self.update_process_history(process_history_id)
        
        return process_history_id
    
    def status(self, process_history_id):
        '''
        Returns None if the uuid does not correspond to an Execution instance
        known by the server. Otherwise, returns the status of the processing 
        corresponding to the query. See ProcessingEngine.status().
        '''
        db_status = self.database_engine.status(process_history_id)
        if db_status is not None:
            job_id = self.database_engine.job_id(process_history_id)
            if job_id is not None:
                job_status = self.processing_engine.status(job_status)
                if job_status != db_status:
                    self.update_process_history(process_history_id)
                    db_status = self.database_engine.status(process_history_id)
        return db_status
    
    def update_process_history(process_history_id):
        job_id = self.database_engine.job_id(process_history_id)
        if job_id is not None:
            job_state = self.processing_engine.state(job_id)
            if job_state is not None:
                self.database_engine.change_process_history(
                    process_history_id,
                    status=job_state['status'],
                    job_state=job_state)

    def process_history(process_history_id):
        return self.database_engine.get_process_history(process_history_id)
    
    def to_json(self):
        '''
        Returns a dictionary containing JSON compatible representation of
        the engine.
        '''
        kwargs = {'metadata_engine': self.metadata_engine.to_json(),
                 'processing_engine': self.processing_engine.to_json()}
        if self.database_engine is not None:
            kwargs['database_engine'] = self.database_engine.to_json()
        return ['capsul.engine.capsul_engine', kwargs]

def capsul_engine(self, metadata_engine, processing_engine, database_engine):
    '''
    Factory to create a `CapsulEngine`instance from its JSON serialization.
    '''
    return CapsulEngine(from_json(metadata_engine),
                        from_json(processing_engine),
                        from_json(database_engine))



class ProcessingEngine(JSONSerializable):
    '''
    This class is a kind of JSON serializable version of a WorkflowController
    API. It is used to define the minimum API required for Platform but
    could be replaced by a real Soma Workflow class.
    '''
    
    def submit(self, process):
        '''
        Start execution of a process as soon as possible. Returns a job
        identifier.
        '''
        raise NotImplementedError()


    def status(self, job_id):
        '''
        Returns a simple status of the process execution (or None if processing_id
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


    def state(self, job_id):
        '''
        Returns the full state of the process execution (or None if processing_id
        is not known).
        '''
        raise NotImplementedError()

class DatabaseEngine(JSONSerializable):
    def new_process_history(self, capsul_engine, process, process_metadata):
        raise NotImplementedError()

    def get_process_history(self, process_history_id):
        raise NotImplementedError()

    def change_process_history(self, process_history_id,
                               status=None,
                               job_id=None,
                               job_state=None):
        raise NotImplementedError()

    def status(self, process_history_id):
        raise NotImplementedError()

    def job_id(self, process_history_id):
        raise NotImplementedError()

    def to_json(self):
        raise NotImplementedError()


class MetadataEngine(JSONSerializable):
    def metadata_parameters(self, process):
        '''
        Returns a Controller whose traits defines a set of non file parameters
        that are used to generate file names for all process parameters.
        See generate_paths() method.
        '''
        raise NotImplementedError()
    
    def generate_paths(self, process, context_parameters):
        '''
        Set a value for parameters of the process that requires a path.
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


