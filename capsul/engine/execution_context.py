import os
import os.path as osp
import sys

from soma.serialization import JSONSerializable

from capsul.api import get_process_instance

active_execution_context = None

class ExecutionContext:
    '''
    an execution context contains all the information necessary to start a 
    job. For instance, in a previous example we used a process running FSL
    software. In order to use FSL, it is necessary to setup a few
    environment variables whose content depends on the location where FSL 
    is installed. The execution context contains the information about FSL 
    installation necessary to define these environment variable when a job 
    is started. The execution context is shared with each processing nodes 
    and used to build the execution environment of each job.
    '''
    
    def __init__(self, python_path_first=[], python_path_last=[]):
        self.python_path_first = python_path_first
        self.python_path_last = python_path_last
    
    def to_json(self):
        '''
        Returns a dictionary containing JSON compatible representation of
        the execution context.
        '''
        kwargs = {}
        if self.python_path_first:
            kwargs['python_path_first'] = self.python_path_first
        if self.python_path_last:
            kwargs['python_path_last'] = self.python_path_last
        return ['capsul.execution_context_from_json', kwargs]
        
    def __enter__(self):
        self._sys_path_first = [osp.expandvars(osp.expanduser(i)) 
                                for i in self.python_path_first]
        self._sys_path_last = [osp.expandvars(osp.expanduser(i)) 
                                for i in self.python_path_last]
        sys.path = self._sys_path_first + sys.path + self._sys_path_last

    def __exit__(self, exc_type, exc_value, traceback):
        error = False
        if self._sys_path_first:
            if sys.path[0:len(self._sys_path_first)] == self._sys_path_first:
                del sys.path[0:len(self._sys_path_first)]
            else:
                error = True
        if self._sys_path_last:
            if sys.path[-len(self._sys_path_last):] == self._sys_path_last:
                del sys.path[0:len(self._sys_path_last)]
            else:
                error = True
        del self._sys_path_first
        del self._sys_path_last
        if error:
            raise ValueError('sys.path was modified and execution context modifications cannot be undone')


    def get_process_instance(self, process_or_id, **kwargs):
        '''
        The supported way to get a process instance is to use this method.
        For now, it simply calls capsul.api.get_process_instance but it may
        change in the future.
        '''
        instance = get_process_instance(process_or_id, **kwargs)
        return instance


def execution_context_from_json(python_path_first=[], 
                                python_path_last=[]):
    '''
    Creates an ExecutionContext from a set of parameters extracted from a
    JSON format.
    '''
    return ExecutionContext(python_path_first=python_path_first,
                            python_path_last=python_path_last)