from traits.api import File, List

from capsul.api import Process, Pipeline

class WordsClassifier(Process):
    id = 'test_project.WordsClassifier'

    documents = List(File)
    language_file = File()
    words_classification = File(output=True)
    
    def run_process(self):
        pass

class WordsFrequencies(Process):
    id = 'test_project.WordsFrequencies'

    document = File()
    language_file = File()
    word_frequencies = File(output=True)
    
    def run_process(self):
        pass



class DocumentClassifier(Process):
    id = 'test_project.DocumentClassifier'
    
    word_frequencies = File(output=False)
    words_classification = File(output=False)
    document_classification = File(output=True)


class DocumentsClassifierPipeline(Pipeline):
    id = 'test_project.DocumentsClassifierPipeline'
    
    def pipeline_definition(self):
        self.add_process('WordsClassifier', 'test_project.WordsClassifier')
        self.add_iterative_process('WordsFrequencies', 'test_project.WordsFrequencies', iterative_plugs=['document'])
        self.add_iterative_process('DocumentClassifier', 'test_project.DocumentClassifier', iterative_plugs=['word_frequencies'])
        
        self.export_parameter('WordsFrequencies', 'document', 'documents_to_classify')
        self.export_parameter('WordsClassifier', 'language_file')
        self.export_parameter('WordsClassifier', 'documents', 'reference_documents')
        self.add_link('WordsClassifier.words_classification->DocumentClassifier.words_classification')
        self.add_link('language_file->WordsFrequencies.language_file')
        self.add_link('WordsFrequencies.word_frequencies->DocumentClassifier.word_frequencies')
        
        self.node_position = {'DocumentClassifier': (342.0, 257.0),
                              'WordsClassifier': (125.0, 306.0),
                              'WordsFrequencies': (132.0, 149.0),
                              'inputs': (-115.0, 219.0),
                              'outputs': (583.0, 308.0)}