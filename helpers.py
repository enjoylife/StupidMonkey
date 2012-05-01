# -*- coding: utf-8 -*-
import sys
from time import time
from collections import Counter
from Stemmer import Stemmer
import simplejson as json
import unicodedata


def gen_stops():
    english_ignore = []
    with open('stoplist.txt',  'r') as stops:
        for word in stops:
            english_ignore.append(word.strip())
    return frozenset(english_ignore)

def ngrams(tokens, MIN_N, MAX_N):
    n_tokens = len(tokens)
    for i in xrange(n_tokens):
        for j in xrange(i+MIN_N, min(n_tokens, i+MAX_N)+1):
            yield " ".join(tokens[i:j])

def text_processer(document):
    """ Alot of python magic and helpers in this list comprehension
     If this is one area where a more precise C implementation would be amazing
     but more work."""
    raw_strings = document.lower().split()
    print type(raw_strings)
    container = Counter(raw_strings)
    container.update([x for x in ngrams(raw_strings,2,4)])
    return container

STOPLIST =  gen_stops()

class BasicXmlExtract(object):

    def __init__(self):
        self.globs = []

    def data(self, data):
        self.globs.append(data)
    def close(self):
        data = self.globs
        self.globs = []
        return " ".join(data)
        

class TokenXmlExtract(object):

    def __init__(self):
        self.container = Counter()
        self.globs = []

    def data(self, data):
        data = unicodedata.normalize('NFKD',data).encode('ascii','ignore')
        self.globs.append(data)
        data = data.lower().split()
        if data:
            ## single word tokens 
            self.container.update([d for d in data if d not in STOPLIST])
            ## ngrams
            self.container.update([x for x in ngrams(tuple(data),2,2)])

    def close(self):
        return  self.container


if __name__ == '__main__':
    c =text_processer('This is a test sencence with strings')
    print json.dumps(c)

