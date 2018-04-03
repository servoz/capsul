from __future__ import print_function

import six  
import os
import os.path as osp
import json
import tempfile
import sqlite3


from soma.controller import Controller
from soma.serialization import JSONSerializable
from soma.undefined import undefined
from soma.topological_sort import Graph

from capsul.pipeline.pipeline import Pipeline, Switch
from capsul.engine import ProcessingEngine

class JobStatus(object):
    ready = 0
    waiting = 1
    started = 2
    success = 3
    failure = 4
    undetermined = 5

class ExecutionPipeline(Pipeline):
    def __init__(self, pipeline, remove_disabled_steps=True):
        self.pipeline = pipeline
        self.remove_disabled_steps = remove_disabled_steps
        self.nodes_dependency = set()
        super(ExecutionPipeline, self).__init__()
        
    def pipeline_definition(self):
        if self.remove_disabled_steps:
            steps = getattr(self.pipeline, 'pipeline_steps', Controller())
            disabled_nodes = set()
            for step, trait in six.iteritems(steps.user_traits()):
                if not getattr(steps, step):
                    disabled_nodes.update(
                        [self.pipeline.nodes[node] for node in trait.nodes])
        
        # First step: create a process node for each activated process execution
        # node in the pipeline and its sub-pipelines
        
        # Create a stack containing all nodes to consider. It is
        # initialized with all the top level pipeline nodes.
        stack = []
        for node_name, node in six.iteritems(self.pipeline.nodes):
            # Do not consider the pipeline node
            if node_name == "":
                continue
            stack.append((node_name, node))
        
        created_nodes = {}
        while stack:
            node_name, node = stack.pop(0)
            # Select only active Process nodes
            if node.activated \
                    and not isinstance(node, Switch) \
                    and (not self.remove_disabled_steps
                            or node not in disabled_nodes):
                if isinstance(node.process, Pipeline):
                    # If a Pipeline is found, add its nodes to the stack
                    if self.remove_disabled_steps:
                        steps = getattr(node.process, 'pipeline_steps', Controller())
                        disabled_sub_nodes = set()
                        for step, trait in six.iteritems(steps.user_traits()):
                            if not getattr(steps, step):
                                disabled_sub_nodes.update(
                                    [node.process.nodes[i] for i in trait.nodes])
                    for nn, n in six.iteritems(node.process.nodes):
                        # Do not consider the pipeline node
                        if nn == "" or (self.remove_disabled_steps and 
                                        node in disabled_nodes):
                            continue
                        stack.append((node_name + '_' + nn, n))
                else:
                    # If a Process node is found: simply create a process for it
                    self.add_process(node_name, node.process)
                    created_nodes[node] = node_name
        
        # Second step: create a link for all parameters that are connected to
        # the main pipeline node. Starts from the pipeline node and follow all
        # plugs (going throuhg sub-pipeline nodes and switch).
        for pipeline_plug_name, pipeline_plug in six.iteritems(self.pipeline.nodes[''].plugs):
            if pipeline_plug.output:
                # The source plug is an output plug. Therefore, we follow
                # iteratively the links_form until we reach a process node.
                stack = [pipeline_plug]
                while stack:
                    plug = stack.pop(0)
                    for (node_name, plug_name, node, plug,
                            weak_link) in plug.links_from:
                        if node.activated:
                            if isinstance(node, Switch):
                                stack.extend(p for n, p in node.plugs.iteritems()
                                             if p.activated and not p.output and 
                                                n.endswith('_switch_' + plug_name))
                            elif isinstance(node.process, Pipeline):
                                stack.append(plug)
                            else:
                                source_node_name = created_nodes.get(node)
                                if source_node_name:
                                    self.add_link('%s.%s->%s' % (source_node_name, 
                                                                 plug_name, 
                                                                 pipeline_plug_name))
            else:
                # The source plug is an input plug. Therefore, we follow
                # iteratively the links_to until we reach a process node.
                stack = [pipeline_plug]
                while stack:
                    plug = stack.pop(0)
                    for (node_name, plug_name, node, plug,
                            weak_link) in plug.links_to:
                        if node.activated:
                            if isinstance(node, Switch):
                                stack.extend(p for n, p in node.plugs.iteritems() 
                                             if p.activated and p.output and 
                                                plug_name.endswith('_switch_' + n))
                            elif isinstance(node.process, Pipeline):
                                stack.append(plug)
                            else:
                                dest_node_name = created_nodes.get(node)
                                if dest_node_name:
                                    self.add_link('%s->%s.%s' % (pipeline_plug_name, 
                                                                 dest_node_name, 
                                                                 plug_name))
                                    
        
        # Third step: create the parameters links between the created
        # process nodes. For this, we follow all plugs starting from a created
        # process node (going through pipeline nodes and switch nodes) to check
        # if it connects to another process node.
        for source_node, source_node_name in six.iteritems(created_nodes):
            stack = list((plug_name, plug) 
                         for plug_name, plug in
                            six.iteritems(source_node.plugs) 
                         if plug.activated and plug.output)
            while stack:
                source_plug_name, source_plug = stack.pop(0)
                for (dest_node_name, dest_plug_name, dest_node, dest_plug,
                        weak_link) in source_plug.links_to:
                    if dest_node.activated:
                        if isinstance(dest_node, Switch):
                            stack.extend((source_plug_name, p)
                                         for n, p in dest_node.plugs.iteritems()
                                         if p.activated and p.output and 
                                            dest_plug_name.endswith('_switch_' + n))
                        elif isinstance(dest_node.process, Pipeline):
                            stack.append((source_plug_name, dest_plug))
                        else:
                            dest_node_name = created_nodes.get(dest_node)
                            if dest_node_name:
                                self.add_link('%s.%s->%s.%s' % (source_node_name,
                                                                source_plug_name, 
                                                                dest_node_name, 
                                                                dest_plug_name))
                                self.nodes_dependency.add((source_node_name, dest_node_name))
    
    def add_link(self, link, weak_link=False):
        '''
        This specialization of add_link allow to create links to or from a
        pipeline node even if the plug does not exists. In that case,
        self.export_parameter is used to create the link.
        '''
        if weak_link:
            raise ValueError('ExecutionPipeline does not support weak links')
        source, dest = link.split('->')
        if '.' not in source and source not in self.nodes[''].plugs:
            dest_node, dest_plug = dest.rsplit('.', 1)
            self.export_parameter(dest_node, dest_plug, source)
        elif '.' not in dest and dest not in self.nodes[''].plugs:
            source_node, source_plug = source.rsplit('.', 1)
            self.export_parameter(source_node, source_plug, dest)
        else:
            super(ExecutionPipeline, self).add_link(link, weak_link)



class Workflow(object):
    def __init__(self, process, execution_context):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('''
            PRAGMA foreing_keys = NO;
            CREATE TABLE jobs(id TEXT, 
                              status INTEGER,
                              command TEXT,
                              env TEXT,
                              message TEXT,
                              CONSTRAINT pkey PRIMARY KEY id);
            CREATE TABLE links(source TEXT NOT NULL,
                               dest TEXT NOT NULL,
                               FOREIGN KEY (source) REFERENCES jobs(id); 
                               FOREIGN KEY (dest) REFERENCES jobs(id); 
                               CONSTRAINT pkey PRIMARY KEY (source, dest) ON CONFLICT IGNORE);
            ''')
        self.execution_context = execution_context
        
        if isinstance(process, ExecutionPipeline):
            self._init_from_execution_pipeline(process)
        elif isinstance(process, Pipeline):
            epipeline = ExecutionPipeline(process)
            self._init_from_execution_pipeline(epipeline)
        elif isinstance(process, Process):
            cmd, env = self.execution_context.process_command_line(process)
            self.add_job(cmd, env)
        else:
            raise ValueError('Wrong process type for workflow creation. '
                             'Expect an instance of Process, Pipeline or '
                             'ExecutionPipeline but got %s' % \
                                 str(type(process)))

    def _init_from_execution_pipeline(self, epipeline):
        for node_name, node in six.iteritem(epipeline.nodes):
            if node_name:
                cmd, env = self.execution_context.process_command_line(node.process)
                self.add_job(cmd, env, node_name)
        for source, dest in epipeline.nodes_dependency:
            self.add_link(source, dest)
    
    def add_job(self, command, env=None, id=None):
        if id is None:
            id = str(uuid4())
        self.db.execute('INSERT INTO jobs (id, status, command, env) '
                        'VALUES (?, ?, ?, ?);',
                        [id, JobStatus.ready, command, json.dumps(env)])
    
    def add_link(self, source, dest):
        self.db.execute('''INSERT INTO links VALUES (?,?);
            UPDATE jobs SET status = ? WHERE id = ?;''',
            [source, dest, JobStatus.waiting, dest])

    @property
    def links(self):
        for row in self.db.execute('SELECT source, dest FROM links;'):
            yield row
        
    def jobs_with_and_without_dependency(self):
        jobs_with_dependency = set(i[0] for i in 
                                   self.db.execute('SELECT DISTINCT dest FROM links;'))
        return (jobs_with_dependency, set(self.jobs) - jobs_with_dependency)
    
    def jobs_linked_to(self, dest):
        for row in self.db.execute('SELECT DISTINCT source FROM links WHERE dest=?;',
                                   [dest]):
            yield row[0]
    
    def jobs_linked_from(self, source):
        for row in self.db.execute('SELECT DISTINCT dest FROM links WHERE source=?;',
                                   [source]):
            yield row[0]

    def start_job(self):
        cur = self.db.execute('SELECT id FROM jobs WHERE status = ?;',
                              [JobStatus.ready])
        row = cur.fetchone()
        if row:
            job_id = row[0]
            self.db.execute('UPDATE jobs SET status = ? WHERE id = ?;',
                            [JobStatus.started, job_id])
            return job_id
        return None
    
    def job_successful(self, job_id, message):
        # Change the status of the job to "success"
        self.db.execute('UPDATE jobs SET status = ?, message = ? WHERE id = ?;',
                        [JobStatus.success, message, job_id])
        # Look for all jobs directly connected to job_id
        for row in self.db.execute('SELECT dest FROM links WHERE source = ?;',
                                   [job_id]):
            waiting_job = row[0]
            # Count all jobs that are linked to waiting_job and have a status
            # "ready", "started" or "waiting". If there is none, the job
            # is ready to be started.
            cur = self.db.execute('SELECT COUNT(*) '
                                  'FROM jobs LEFT JOIN links '
                                  'ON jobs.id = links.source '
                                  'WHERE jobs.status IN (?, ?, ?) AND '
                                        'links.dest = ?',
                                  [JobStatus.ready,
                                   JobStatus.waiting,
                                   JobStatus.started,
                                   waiting_job])
            if cur.fetchone()[0] == 0:
                self.db.execute('UPDATE jobs SET status = ? WHERE id = ?;',
                                [JobStatus.ready, waiting_job])
        
    def job_failed(self, job_id, message):
        # Change the job status to "failure"
        self.db.execute('UPDATE jobs SET status = ?, message = ? WHERE id = ?;',
                        [JobStatus.failure, message, job_id])
        
        waiting_jobs = [i[0] for in in 
                        self.db.execute('SELECT dest FROM links WHERE source = ?;',
                                        [job_id])]
        other_message = 'Will never start because previous job %s failed.' % job_id
        while waiting_jobs:
            waiting_job = waiting_jobs.pop()
            # Change the dependent job status to "failure"
            self.db.execute('UPDATE jobs SET status = ?, message = ? WHERE id = ?;',
                            [JobStatus.failure, other_message, waiting_job])
            # Adds all jobs that are linked to waiting_jon and in "waiting" state
            waiting_jobs.extend(i[0] for in in 
                self.db.execute('SELECT links.dest '
                    'FROM links LEFT JOIN jobs '
                    'ON dest.dest = jobs.id '
                    'WHERE links.source = ? AND '
                    'jobs.status = ?;',
                    [waiting_job, JobStatus.waiting])]

        
        
class LocalhostProcessingEngine(ProcessingEngine):    
    def get_commandline(self, process):
        #TODO
        return None
    
    
    @staticmethod
    def _check_trait_missing_value(trait, value):
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
    
    def check_process_parameters(self, process):
        '''
        Check that process parameters are all valid to call the process.
        Raises a ValueError if a mandatory paramameter is missing.
        '''
        missing = []
        for name, trait in six.iteritems(self.user_traits()):
            if not trait.optional:
                value = self.get_parameter(name)
                if not self._check_trait_missing_value(trait, value):
                    missing.append(name)

        if len(missing) != 0:
            if isinstance(process_or_pipeline, Pipeline):
                ptype = 'pipeline'
            else:
                ptype = 'process'
            raise ValueError('In %s %s: missing mandatory parameters: %s'
                             % (ptype, process_or_pipeline.name,
                                ', '.join(missing)))

        
    def submit(self, process, 
                check_parameters=True,
                create_output_directories=True):
        """Start the execution of a process or a pipline
        
        Returns a job identifier that can be used to get the execution status

        Parameters
        ----------
        process: Process or Pipeline instance (mandatory)
            the process or pipeline we want to execute
        create_output_directories: If `True` (the default), check existance of
            parent directories of all output `File` or `Directory` and create it
            if it does not exist.
        check_parameters: If `True` (the default), check process parameters
            validity before calling the process.
        """
        if check_parameters:
            self.check_process_paramaters(process)
        
        if create_output_directories:
            for name, trait in process.user_traits().items():
                if trait.output and isinstance(trait.handler, (File, Directory)):
                    value = getattr(process, name)
                    if value is not Undefined and value:
                        base = osp.dirname(value)
                        if base and not osp.exists(base):
                            os.makedirs(base)
        
        cmd = self. get_command_line(process)
        execution_file = tempfile.NamedTemporaryFile(dir=self.temporary_directory, prefix='capsul_execution_')
        job_id = osp.basename(execution_file.name)[len('capsul_execution_'):]
        stdout = execution_file.name + '_stdout'
        stderr = execution_file.name + '_stderr'
        popen = subprocess.Popen(cmd,
                                 env=self.env,
                                 stdout=open(stdout, 'w'),
                                 stderr=open(stderr, 'w'))
        
        job_state = {
            'process': process.id,
            'command_line': cmd,
            'context': self.to_json(),
            'pid': popen.pid,
            'stdout': stdout,
            'stderr': stderr,
            'status': Status.running,
        }
        json.dump(job_state, execution_file)
        return job_id

    def status(self, job_id):
        '''
        Return the status of the job previously started by submit()
        '''
        job_state = self.state(job_id)
        if job_state is not None:
            return job_state.get('status', Status.undefined)
        return Status.undefined
    
    def state(self, job_id):
        '''
        Return the full state of the job previously started by submit()
        '''
        execution_file = ops.join(self.temporary_directory, 'capsul_execution_%s' % job_id)
        if osp.exists(execution_file):
            job_state = json.load(open(execution_file))
            return job_state
        return None

    #def _check_temporary_files_for_node(self, node, temp_files):
        #""" Check temporary outputs and allocate files for them.

        #Temporary files or directories will be appended to the temp_files list,
        #and the node parameters will be set to temp file names.

        #This internal function is called by the sequential execution,
        #_run_process() (also used through __call__()).
        #The pipeline state will be restored at the end of execution using
        #_free_temporary_files().

        #Parameters
        #----------
        #node: Node
            #node to check temporary outputs on
        #temp_files: list
            #list of temporary files for the pipeline execution. The list will
            #be modified (completed).
        #"""
        #process = getattr(node, 'process', None)
        #if process is not None and isinstance(process, NipypeProcess):
            ##nipype processes do not use temporaries, they produce output
            ## file names
            #return

        #for plug_name, plug in six.iteritems(node.plugs):
            #value = node.get_plug_value(plug_name)
            #if not plug.activated or not plug.enabled:
                #continue
            #trait = node.get_trait(plug_name)
            #if not trait.output:
                #continue
            #if hasattr(trait, 'inner_traits') \
                    #and len(trait.inner_traits) != 0 \
                    #and isinstance(trait.inner_traits[0].trait_type,
                                   #(traits.File, traits.Directory)):
                #if len([x for x in value if x in ('', traits.Undefined)]) == 0:
                    #continue
            #elif value not in (traits.Undefined, '') \
                    #or ((not isinstance(trait.trait_type, traits.File)
                          #and not isinstance(trait.trait_type, traits.Directory))
                         #or len(plug.links_to) == 0):
                #continue
            ## check that it is really temporary: not exported
            ## to the main pipeline
            #if self.pipeline_node in [link[2]
                                      #for link in plug.links_to]:
                ## it is visible out of the pipeline: not temporary
                #continue
            ## if we get here, we are a temporary.
            #if isinstance(value, list):
                #if trait.inner_traits[0].trait_type is traits.Directory:
                    #new_value = []
                    #tmpdirs = []
                    #for i in range(len(value)):
                        #if value[i] in ('', traits.Undefined):
                            #tmpdir = tempfile.mkdtemp(suffix='capsul_run')
                            #new_value.append(tmpdir)
                            #tmpdirs.append(tmpdir)
                        #else:
                            #new_value.append(value[i])
                    #temp_files.append((node, plug_name, tmpdirs, value))
                    #node.set_plug_value(plug_name, new_value)
                #else:
                    #new_value = []
                    #tmpfiles = []
                    #if trait.inner_traits[0].allowed_extensions:
                        #suffix = 'capsul' + trait.allowed_extensions[0]
                    #else:
                        #suffix = 'capsul'
                    #for i in range(len(value)):
                        #if value[i] in ('', traits.Undefined):
                            #tmpfile = tempfile.mkstemp(suffix=suffix)
                            #tmpfiles.append(tmpfile[1])
                            #os.close(tmpfile[0])
                            #new_value.append(tmpfile[1])
                        #else:
                            #new_value.append(value[i])
                    #node.set_plug_value(plug_name, new_value)
                    #temp_files.append((node, plug_name, tmpfiles, value))
            #else:
                #if trait.trait_type is traits.Directory:
                    #tmpdir = tempfile.mkdtemp(suffix='capsul_run')
                    #temp_files.append((node, plug_name, tmpdir, value))
                    #node.set_plug_value(plug_name, tmpdir)
                #else:
                    #if trait.allowed_extensions:
                        #suffix = 'capsul' + trait.allowed_extensions[0]
                    #else:
                        #suffix = 'capsul'
                    #tmpfile = tempfile.mkstemp(suffix=suffix)
                    #node.set_plug_value(plug_name, tmpfile[1])
                    #os.close(tmpfile[0])
                    #temp_files.append((node, plug_name, tmpfile[1], value))

    #def _free_temporary_files(self, temp_files):
        #""" Delete and reset temp files after the pipeline execution.

        #This internal function is called at the end of _run_process()
        #(sequential execution)
        #"""
        ##
        #for node, plug_name, tmpfiles, value in temp_files:
            #node.set_plug_value(plug_name, value)
            #if not isinstance(tmpfiles, list):
                #tmpfiles = [tmpfiles]
            #for tmpfile in tmpfiles:
                #if osp.isdir(tmpfile):
                    #try:
                        #shutil.rmtree(tmpfile)
                    #except:
                        #pass
                #else:
                    #try:
                        #os.unlink(tmpfile)
                    #except:
                        #pass
                ## handle additional files (.hdr, .minf...)
                ## TODO
                #if osp.exists(tmpfile + '.minf'):
                    #try:
                        #os.unlink(tmpfile + '.minf')
                    #except:
                        #pass


    #def _run(self, process_instance, output_directory, verbose, **kwargs):
        #""" Method to execute a process in a study configuration environment.

        #Parameters
        #----------
        #process_instance: Process instance (mandatory)
            #the process we want to execute
        #output_directory: Directory name (optional)
            #the output directory to use for process execution. This replaces
            #self.output_directory but left it unchanged.
        #verbose: int
            #if different from zero, print console messages.
        #"""
        ## Message
        #logger.info("Study Config: executing process '{0}'...".format(
            #process_instance.id))

        ## Run
        #if self.get_trait_value("use_smart_caching") in [None, False]:
            #cachedir = None
        #else:
            #cachedir = output_directory

        ## Update the output directory folder if necessary
        #if output_directory is not None and output_directory is not Undefined and output_directory:
            #if self.process_output_directory:
                #output_directory = osp.join(output_directory, '%s-%s' % (self.process_counter, process_instance.name))
            ## Guarantee that the output directory exists
            #if not osp.isdir(output_directory):
                #os.makedirs(output_directory)
            #if self.process_output_directory:
                #if 'output_directory' in process_instance.user_traits():
                    #if (process_instance.output_directory is Undefined or
                            #not(process_instance.output_directory)):
                        #process_instance.output_directory = output_directory
        
        #returncode, log_file = run_process(
            #output_directory,
            #process_instance,
            #cachedir=cachedir,
            #generate_logging=self.generate_logging,
            #verbose=verbose,
            #**kwargs)

        ## Increment the number of executed process count
        #self.process_counter += 1
        #return returncode

        
###############################
# Backup from Process class
################################
    #def get_commandline(self):
        #""" Method to generate a comandline representation of the process.

        #Either this :meth:`get_commandline` or :meth:`run_process` must be
        #defined in derived classes. But not both. If the execution code of a
        #process is in Python, it must be defined in :meth:`get_commandline`.
        #On the other hand, if the process encapsulate a command line that does
        #not need Python, one should use :meth:`get_commandline` to define it.

        #Returns
        #-------
        #commandline: list of strings
            #Arguments are in separate elements of the list.
        #"""
        #raise NotImplementedError(
                #"Either get_commandline() or _run_process() should be "
                #"redefined in process ({0})".format(self.id))
        
        
        
        ## Get command line arguments (ie., the process user traits)
        ## Build the python call expression, keeping apart file names.
        ## File names are given separately since they might be modified
        ## externally afterwards, typically to handle temporary files, or
        ## file transfers with Soma-Workflow.

        #class ArgPicker(object):
            #""" This small object is only here to have a __repr__() representation which will print sys.argv[n] in a list when writing the commandline code.
            #"""
            #def __init__(self, num):
                #self.num = num
            #def __repr__(self):
                #return 'sys.argv[%d]' % self.num

        #reserved_params = ("nodes_activation", "selection_changed")
        ## pathslist is for files referenced from lists: a list of files will
        ## look like [sys.argv[5], sys.argv[6]...], then the corresponding
        ## path args will be in additional arguments, here stored in pathslist
        #pathslist = []
        ## argsdict is the dict of non-path arguments, and will be printed
        ## using repr()
        #argsdict = {}
        ## pathsdict is the dict of path arguments, and will be printed as a
        ## series of arg_name, path_value, all in separate commandline arguments
        #pathsdict = {}

        #for trait_name, trait in six.iteritems(self.user_traits()):
            #value = getattr(self, trait_name)
            #if trait_name in reserved_params \
                    #or not is_trait_value_defined(value):
                #continue
            #if is_trait_pathname(trait):
                #pathsdict[trait_name] = value
            #elif isinstance(trait.trait_type, List) \
                    #and is_trait_pathname(trait.inner_traits[0]):
                #plist = []
                #for pathname in value:
                    #if is_trait_value_defined(pathname):
                        #plist.append(ArgPicker(len(pathslist) + 1))
                        #pathslist.append(pathname)
                    #else:
                        #plist.append(pathname)
                #argsdict[trait_name] = plist
            #else:
                #argsdict[trait_name] = value

        ## Get the module and class names
        #if hasattr(self, '_function'):
            ## function with xml decorator
            #module_name = self._function.__module__
            #class_name = self._function.__name__
            #call_name = class_name
        #else:
            #module_name = self.__class__.__module__
            #class_name = self.name
            #call_name = '%s()' % class_name

        ## Construct the command line
        #commandline = [
            #"python",
            #"-c",
            #("import sys; from {0} import {1}; kwargs={2}; "
             #"kwargs.update(dict((sys.argv[i * 2 + {3}], "
             #"sys.argv[i * 2 + {4}]) "
             #"for i in range(int((len(sys.argv) - {3}) / 2)))); "
             #"{5}(**kwargs)").format(module_name, class_name,
                                       #repr(argsdict), len(pathslist) + 1,
                                       #len(pathslist) + 2,
                                       #call_name).replace("'", '"')
        #] + pathslist + sum([list(x) for x in pathsdict.items()], [])

        #return commandline

    #@staticmethod
    #def make_commandline_argument(*args):
        #"""This helper function may be used to build non-trivial commandline
        #arguments in get_commandline implementations.
        #Basically it concatenates arguments, but it also takes care of keeping
        #track of temporary file objects (if any), and converts non-string
        #arguments to strings (using repr()).

        #Ex:

        #>>> process.make_commandline_argument('param=', self.param)

        #will return the same as:

        #>>> 'param=' + self.param

        #if self.param is a string (file name) or a temporary path.
        #"""
        #built_arg = ""
        #temp = None
        #for arg in args:
            #if hasattr(arg, 'pattern'): # tempfile
                #built_arg = built_arg + arg
            #elif isinstance(arg, basestring):
                #built_arg += arg
            #else:
                #built_arg = built_arg + repr(arg)
        #return built_arg        


###############################
# End of backup from Process
################################

if __name__ == '__main__':
    import sys
    from pprint import pprint

    from soma.qt_gui.qt_backend import QtGui
    from soma.qt_gui.controller_widget import ControllerWidget

    from traits.api import File

    from capsul.api import get_process_instance, Process, Pipeline
    from capsul.qt_gui.widgets import PipelineDevelopperView

    app = QtGui.QApplication(sys.argv)

    
    pipeline = get_process_instance('capsul.pipeline.test.test_complex_pipeline_activations.ComplexPipeline')
    #pipeline = get_process_instance('capsul.process.test.test_pipeline')
    
    def show_execution_graph():
        global flat_view
        
        #xp = ExecutionGraph(pipeline)
        #pprint(xp._nodes)
        #pprint(xp._links)
        #pprint(xp._parameter_links)
        flat_pipeline = ExecutionPipeline(pipeline)
        flat_view = PipelineDevelopperView(flat_pipeline, 
                                           allow_open_controller=True,
                                           show_sub_pipelines=True)
        flat_view.auto_dot_node_positions()
        flat_view.show()
    
    show_execution_graph()
    pipeline.on_trait_change(show_execution_graph)
            
    view = PipelineDevelopperView(pipeline, allow_open_controller=True, show_sub_pipelines=True)
    view.show()


    app.exec_()
