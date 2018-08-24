import six

from traits.api import Unicode, Date

from soma.serialization import JSONSerializable
from soma.controller.trait_utils import is_trait_pathname


# TODO put this class in a Capsul module
class MetadataEngine(JSONSerializable):
    def to_json(self):
        raise NotImplementedError()
    

    def set_metaparams(self, process):
        '''
        Default implementation if set_metaparams
        does nothing
        '''

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
    
    def set_metaparams(self, process):
        handlers = self.metaparams_handlers.get(process.id)
        if handlers:
            for handler in handlers:
                handler(process)
        for trait in six.itervalues(process.user_traits()):
            if is_trait_pathname(trait):
                roles = getattr(trait, 'roles')
                if roles is not None:
                    roles.add('sub_meta')
                else:
                    trait.roles = {'sub_meta'}

    
    @staticmethod
    def add_document_metaparams(process):
        if process.trait('language') is None:
            process.add_trait('language', Unicode(roles={'meta'}))
        if process.trait('author') is None:
            process.add_trait('author', Unicode(roles={'meta'}))
        if process.trait('document_date') is None:
            process.add_trait('document_date', Date(roles={'meta'}))
        
    @staticmethod
    def add_reference_metaparams(process):
        if process.trait('language') is None:
            process.add_trait('language', Unicode(roles={'meta'}))
        if process.trait('period_start') is None:
            process.add_trait('period_start', Date(roles={'meta'}))
        if process.trait('period_end') is None:
            process.add_trait('period_end', Date(roles={'meta'}))

TestMetadataEngine.metaparams_handlers = {
    'test_project.WordsClassifier': [TestMetadataEngine.add_reference_metaparams],
    'test_project.WordsFrequencies': [TestMetadataEngine.add_document_metaparams],
    'test_project.DocumentClassifier': [TestMetadataEngine.add_document_metaparams,
                                        TestMetadataEngine.add_reference_metaparams],
}
    
