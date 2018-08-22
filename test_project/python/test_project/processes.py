from traits.api import File, List

from capsul.api import Process, Pipeline

class WordsClassifier(Process):
    documents = List(File, output=False)
    language = File(output=False)
    words_classification = File(output=True)
    
    def run_process(self):
        pass

class WordsFrequencies(Process):
    document = File(output=False)
    language = File(output=False)
    word_frequencies = File(output=True)
    
    def run_process(self):
        pass



class DocumentClassifier(Process):
    word_frequencies = File(output=False)
    words_classification = File(output=False)
    document_classification = File(output=True)


class DocumentsClassifierPipeline(Pipeline):

    def pipeline_definition(self):
        self.add_process('WordsClassifier', 'test_project.WordsClassifier')
        self.add_iterative_process('WordsFrequencies', 'test_project.WordsFrequencies', iterative_plugs=['document'])
        self.add_iterative_process('DocumentClassifier', 'test_project.DocumentClassifier', iterative_plugs=['word_frequencies'])
        
        self.export_parameter('WordsFrequencies', 'document', 'documents_to_classify')
        self.export_parameter('WordsClassifier', 'language')
        self.export_parameter('WordsClassifier', 'documents', 'reference_documents')
        self.add_link('WordsClassifier.words_classification->DocumentClassifier.words_classification')
        self.add_link('language->WordsFrequencies.language')
        self.add_link('WordsFrequencies.word_frequencies->DocumentClassifier.word_frequencies')
        
        self.node_position = {'DocumentClassifier': (342.0, 257.0),
                              'WordsClassifier': (125.0, 306.0),
                              'WordsFrequencies': (132.0, 149.0),
                              'inputs': (-115.0, 219.0),
                              'outputs': (583.0, 308.0)}