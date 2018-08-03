from __future__ import print_function

import random
import string
import time

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
    language = random.choice(list(languages.keys()))
    language_words = list(languages[language])
    author = random.choice(list(authors))
    date = time.localtime(time.time() * random.random())
    words = [random.choice(language_words) for i in range(words_count)]
    return dict(language=language,
                author=author,
                date=date,
                words=words)

max_languages = 3
max_authors = 4
max_documents = 50

languages = dict((generate_word(5,5), generate_language(50, 2,4)) for i in range(max_languages))
authors = set('%s %s' % (generate_word(2,4), generate_word(2,4)) for i in range(max_authors))
documents = [generate_document(languages, authors, 200) for i in range(max_documents)]
              