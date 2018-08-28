import re
import six

from traits.api import Unicode, Date

from soma.serialization import JSONSerializable
from soma.controller.trait_utils import is_trait_pathname


# TODO put this class in a Capsul module
class MetadataEngine(JSONSerializable):
    def to_json(self):
        raise NotImplementedError()
    
    metaparams_definition = {}
    
    def set_metaparams(self, process):
        '''
        Default implementation parse self.metaparams_definition
        to modify the process.
        '''
        param_to_metaparams = {}
        proc_metaparams_def = self.metaparams_definition.get(process.id)
        if proc_metaparams_def:
            if isinstance(proc_metaparams_def, list):
                metaparams_rules = proc_metaparams_def
            else:
                process.metaparams_options = metaparams_options = proc_metaparams_def.get('options')
                metaparams_rules = proc_metaparams_def.get('rules', [])
            if metaparams_rules:
                metaparams_rules = [[re.compile('^%s$' % i), j] for i, j in metaparams_rules]
                for param_name, param_trait in six.iteritems(process.user_traits()):
                    if is_trait_pathname(param_trait):
                        for select, metaparams in metaparams_rules:
                            if select.match(param_name):
                                for metaparam_name, metaparam_trait in metaparams:
                                    if process.trait(metaparam_name) is None:
                                        process.add_trait(metaparam_name, metaparam_trait)
                                        process.trait(metaparam_name).is_metaparam = True
                                    controlled_by = param_trait.controlled_by_metaparams
                                    if controlled_by is None:
                                        param_trait.controlled_by_metaparams = [metaparam_name]
                                    else:
                                        controlled_by.append(metaparam_name)
                                print('!!!', process, param_name)
                                param_trait.hidden = True
                                break

    def export_metaparams(self, pipeline):
        '''
        Default implementation of export_metaparams
        calls the pipeline's export_metaparams method
        if it exists or does nothing.
        '''
        linker = getattr(pipeline, 'export_metaparams', None)
        if linker is not None:
            linker()


class TestMetadataEngine(MetadataEngine):
    def to_json(self):
        return 'test_project.TestMetadataEngine'
    
    reference_metaparams = [
        ['language', Unicode()],
        ['period_start', Date()],
        ['period_end', Date()],
    ]
    
    document_metaparams = [
        ['language', Unicode()],
        ['author', Unicode()],
        ['document_date', Date()],
    ]
    
    metaparams_definition = {
        'test_project.WordsClassifier': [
            ['.*', reference_metaparams],
        ],
        'test_project.WordsFrequencies': [
            ['.*', document_metaparams],
        ],
        'test_project.DocumentClassifier': [
            ['words_classification', reference_metaparams],
            ['.*', document_metaparams],
        ],
        'test_project.DocumentsClassifierPipeline': {
            'options': {
                'do_not_iterate': ['language'],
            }
        }
    }
