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

class ProfileInferer(object):
    """ This is the type of  class that is responsible for extracting all the info
    hidden within the cloud of data from a particular service.

    Ideas:
        Boxplot over all users in a certain method, so you would show their
    totals but then also show how that number is relative to others. Maybe this
    should be an ABC?

    Storage: 
        perhaps pickling the objects and saving them for a week or something, or
    go all out and store full user state.
    """ 

    def __init__(self):
        pass

    def topic_summary(self, docs):
        """ Returns what are the main features that make up this topic.
        Features, setiment analysis, lsa main features, time deltas,
        could be any  mashup of other statistical technique.
        Ideas:
            Features are not just word counts and tags,
            Could be any number of other methods.
        """
        pass

    def word_count(self, word_container):
        """ Counts the total number of words in some sort of content of 
        a user's profile. 
        Ideas:
            By time, cluster and not just a single object?
        """
        pass
    
    def readability(self, doc):
        """ Computes a score based upon what an douchebag would mark you
        down for when student critiqing papers.
        Ideas:
            pattern.metrics.flesh_reading_ease
        """
        pass
    
    def word_importance(self, word):
        """ How important is this word/phrases, or more techniquely what is the
        ratio of this word affect on topic, and other statistics.
        Ideas:
            relative to parts of speach
            relative to time, "recent topic of intrest for you has been ..."
            basic word, or more complex, detrmined by wiki topic complexity search.
        """
        pass
    
    def wiki_complexity_search(self, topic):
        """ Determines the complexity of a topic in wikipedia by starting at the
        topic and then using  monte carlo techniques visit a few links of "see
        also" and the "intro". Use dimision reduction techniques on the vectors
        and then apply anaylsis. 
            That analysis is clustering links and detriming the more basic
        topic, or the more abstract(based on wordnet sysnset stuff), or more
        important(page rank?). Or a simple lookup in a premade model of
        intro topics for a large range, and then monte carlo your way from
        their. 
        """
        pass

    def outside_knowledge(self, doc):
        """ Gather resources that are related to this doc from other services.
        Prime canidates are wikipedia, duckduckgo, freebase, the times, etc..
        """
        pass

    def average_location_of(self,obj):
        """ Using lat, long coordinetes detrmine the places where the most data
        is coming from. 
        """
        pass
            
    def learning_process(self):
        """ Compute the tree or path that the data has taken over time based
        upon wiki_complexity_search. 
        """
        pass

    def time_between(self, obj1, obej2):
        """ What is the time deltas of interaction of between these two things.
        """
        pass

    def fix_data(self, training_data, testing_data):
        """ Uses classification to suggest labels to the data according to the
        learned classifications.
        """
        pass

if __name__ == '__main__':
    pass

