from __future__ import print_function

import datetime
import json
import sys
import os
import os.path as osp
from pprint import pprint
import random
import string
import time
from uuid import uuid4

import capsul

vowels = list('aeiou')

def generate_word(min, max):
    syllables = min + int(random.random() * (max - min))
    word = ''.join(generate_syllable() for i in range(syllables))
    return word


def generate_syllable():
    ran = random.random()
    if ran < 0.333:
        return word_part('v') + word_part('c')
    if ran < 0.666:
        return word_part('c') + word_part('v')
    return word_part('c') + word_part('v') + word_part('c')


def word_part(type):
    if type is 'c':
        return random.sample([ch for ch in string.ascii_lowercase if ch not in vowels], 1)[0]
    if type is 'v':
        return random.sample(vowels, 1)[0]


def generate_language(max_words, min_syllabes, max_syllabes):
    return {generate_word(min_syllabes, max_syllabes) for i in range(max_words)}


def generate_document(languages, authors, words_count):
    uuid = str(uuid4())
    language = random.choice(list(languages.keys()))
    language_words = list(languages[language])
    author = random.choice(list(authors))
    date = datetime.date.fromtimestamp(time.time() * random.random())
    words = [random.choice(language_words) for i in range(words_count)]
    return dict(uuid=uuid,
                language=language,
                author=author,
                date=date,
                words=words)

def generate_documents(cengine,
                       max_languages = 3,
                       max_authors = 4,
                       max_documents = 50):
    base_directory = cengine.database_engine.named_directory('capsul_engine')
    
    languages = dict((generate_word(5,5), generate_language(50, 2,4)) for i in range(max_languages))
    for language, language_words in languages.iteritems():
        path = 'source/{0}.language'.format(language)
        fpath = osp.join(base_directory, path)
        dir = osp.dirname(fpath)
        if not osp.exists(dir):
            os.makedirs(dir)
        print('Generating', fpath)
        json.dump(sorted(language_words), open(fpath,'w'))
        metadata = dict(
            language=language,
            uuid=str(uuid4()),
            date=datetime.datetime.now().date(),
        )
        cengine.database_engine.set_path_metadata(path, metadata)
        
    authors = set('%s %s' % (generate_word(2,4), generate_word(2,4)) for i in range(max_authors))

    for i in range(max_documents):
        document = generate_document(languages, authors, 200)
        path = 'source/{language}/{author}/{uuid}.document'.format(**document)
        fpath = osp.join(base_directory, path)
        dir = osp.dirname(fpath)
        if not osp.exists(dir):
            os.makedirs(dir)
        print('Generating', fpath)
        json.dump(document['words'], open(fpath,'w'))
        metadata = dict(
            language=document['language'],
            author=document['author'],
            uuid=document['uuid'],
            date=document['date'],
        )
        cengine.database_engine.set_path_metadata(path, metadata)



if len(sys.argv) != 2:
    print('Invalid arguments: usage:', sys.argv[0], '<directory>', file=sys.stderr)
    sys.exit(1)
           
base_directory = sys.argv[1]
capsul_engine_json = osp.join(base_directory, 'capsul_engine.json')
cengine = capsul.engine(capsul_engine_json)
if not osp.exists(osp.join(base_directory, 'source')):
    generate_documents(cengine)
if not osp.exists(capsul_engine_json):
    cengine.execution_context.python_path_last.append(osp.abspath(osp.dirname(__file__)))
    cengine.save()

with cengine.execution_context:
    import capsul_sample



for root, dirs, files in os.walk(osp.join(base_directory, 'source')):
    for f in files:
        path = osp.join(root,f)
        metadata = cengine.database_engine.path_metadata(path)
        print(path)
        pprint(dict(metadata))
        print()
        