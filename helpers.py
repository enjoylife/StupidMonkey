# -*- coding: utf-8 -*-
import sys
import string
from collections import Counter
from Stemmer import Stemmer
import unicodedata

from pymongo import Connection 
from pymongo.errors import ConnectionFailure, OperationFailure

def mongo_connect(name,extra=False):
    """ 
    Connect to a MongoDB database, and write to stdio if failure. 
    Returns: the database handle
    Params: 
        name: the database name to connect to EX: test

    """
    try:
        #global connection
        connection = Connection()
        #database connection 
        db = connection[name]
        if extra:
            sys.stdout.write(" ** MongoDB connected to %s **\n" % name)

        # Good time to ensure that we have fast indexs, or should I wait?? 
        #db.users.ensureIndex({'username':1}, {unique: True})
        return db
    except ConnectionFailure, e:
        sys.stderr.write("Could Not connect to MongoDB: %s\n" %e)
        sys.exit(1)

def mongo_connect_gridfs(db, name):
    return gridfs.GridFS(db)

def redis_connect():
    """ 
    Connect to a Redis instance, and write to stdio if failure. 
    """
    try:
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        r.ping()
        sys.stdout.write(" ** Redis connected **\n")
    except ConnectionError, e:
        sys.stderr.write("Could note connect to Redis: %s\n" %e)
        sys.exit(1)

def gen_stops():
    english_ignore = []
    with open('bigstoplist.txt',  'r') as stops:
        for word in stops:
            english_ignore.append(word.strip())
    return frozenset(english_ignore)

def ngrams(tokens, MIN_N, MAX_N):
    """ iterable of tokens, smallest nrgram you want (use 1), and the largest.
    If both Min_N and MAX_N are 1, it just yields the same iterable."""

    n_tokens = len(tokens)
    for i in xrange(n_tokens):
        for j in xrange(i+MIN_N, min(n_tokens, i+MAX_N)+1):
            yield " ".join(tokens[i:j])

TABLE = string.maketrans("","")
STOPLIST =  gen_stops()
STEMMER = Stemmer('english')

def text_processer(doc,punc=True):
    """ Alot of python magic and helpers in this list comprehension
     If this is one area where a more precise C implementation would be
     alot faster but more work."""
    # get ride of weird unicode that pops up 
    doc = unicodedata.normalize('NFKD',doc).encode('ascii','ignore')
    if  not punc:
        # don't want puncuation, delete it 
        doc = doc.translate(TABLE, string.punctuation)
    return Counter([STEMMER.stemWord(x) for x in ngrams((doc.lower().split()),1,2) if x not in STOPLIST])

class BasicXmlExtract(object):

    def __init__(self):
        self.glob = []

    def data(self, data):
        self.glob.append(data)

    def close(self):
        data = self.glob
        self.glob = []
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
