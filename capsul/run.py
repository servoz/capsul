import json
import uuid

from soma.serialization import JSONSerializable

from capsul.api import Process

env_prefix = 'capsul_'

class ExecutionContext(JSONSerializable):
    default_temporary_directory = '/tmp'
    
    def __init__(self, env=None, temporary_directory=None, uuid=None):
        if uuid:
            self.uuid = uuid
        else:
            self.uuid = uuid.uuid4()
        if not temporary_directory:
            self.temporary_directory = self.default_temporary_directory
        else:
            self.temporary_directory = temporary_directory
        self.env = env
        self._json = None
        
    def to_json(self):
        kwargs = {'uuid': self.uuid}
        if self.env:
            kwargs['env'] = self.env
        if self.temporary_directory != default_temporary_directory:
            kwargs['temporary_directory'] = self.temporary_directory
        return ['capsul.engine.processing.ExecutionContext', kwargs]

    def process_command_line(self, process):
        env = {}
        if self._json is None:
            self._json = json.dumps(self._to_json())
        env['%sexecution_context' % env_prefix] = self._json
        if self.env:
            env.update(self.env)
        if process.get_command_line is Process.get_command_line:
            # 
        else:
            if process.run_process is not Process.run_process:
                raise RuntimeError('Cannot run process %s because both '
                                   'get_command_line() and run_process() '
                                   'methods are specialized.' % process.id) 
            command = process.get_command_line()
        return command, env

default_execution_context = ExecutionContext()


def get_environ_parameter(name, default=undefined):
    var_name = env_prefix + name
    try:
        v = os.environ[var_name]
    except KeyError:
        if default is undefined:
            raise ValueError("Missing environment variable '%s'" % var_name)
        return default
    if v:
        return json.loads(v)
    return None

if __name__ == '__main__':
    from soma.serialization import from_json
    from capsul.api import get_process_instance
    
    process_id = get_environ_parameter('process')
    kwargs = get_environ_parameter('process_parameters')
    execution_context = from_json(get_parameter('execution_context'))
    process = get_process_instance(process_id, **kwargs)
    if isinstance(process, Pipeline):
        pass
        # TODO
    else:
        process.run_process()
    execution_context.run(process)
    
