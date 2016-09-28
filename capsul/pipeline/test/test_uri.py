from __future__ import print_function
import unittest


# Capsul import
from capsul.api import Process, Pipeline
from capsul.pipeline.pipeline_nodes import JoinFilenameNode

# Trait import
from traits.api import Float, File, Int, List, Str, Undefined

class ByteCopy(Process):

    input = File()
    output = File(output=True)
        
    def _run_process(self):
        filename, offset = self.input.split('?')
        offset = int(offset)
        file = open(filename, 'rb')
        file.seek(offset)
        v = file.read(1)
        
        filename, offset = self.output.split('?')
        offset = int(offset)
        file = open(filename, 'rb+')
        file.seek(offset)
        file.write(v)
        
class CreateOffsets(CallbackNode):
    input = File()
    processors = Int()
    offsets = List(Str, output=True)
    
    def callback(self):
        if self.input is not Undefined:
            file = open(self.input,'rb')
            file.seek(0, 2)
            file_size = file.tell()
            self.offsets = ['?%d' % i for i in range(file_size)] # TODO

class FileCreation(Process):
    input = File()
    output = File(output=True)
    
    def _run_process(self):
        file = open(self.input, 'rb')
        file.seek(0, 2)
        size = file.tell()
        file = open(self.output,'wb')
        file.seek(self.size-1)
        file.write('\0')

class BlockIteration(Pipeline):
    def pipeline_definition(self):
        join_node = JoinFilenameNode(ByteCopy, dict('offset': ['input', 'output']))
        self.add_iterative_node( 'iterative_byte_copy', join_node, ['offset'])
        self.declare_inout_parameter('iterative_byte_copy.output')
        
        self.add_process('create_offsets', CreateOffsets)
        self.add_process('create_output', FileCreation)
        
        
        self.add_link('create_offsets.offsets->iterative_byte_copy.offset')
        self.export_parameter('create_offsets', 'input')
        self.add_link('input->iterative_byte_copy.input')
        self.add_link('input->create_output.input')
        self.export_parameter('create_output', 'output')
        self.add_link('create_output.output->iterative_byte_copy.output')
