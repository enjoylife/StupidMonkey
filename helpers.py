# -*- coding: utf-8 -*-
import sys
from math import sqrt, floor, modf
import string
from collections import Counter
from Stemmer import Stemmer
import unicodedata

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
 
### STRING READABILITY #############################################################################
# 0.9-1.0 = easily understandable by 11-year old.
# 0.6-0.7 = easily understandable by 13- to 15-year old.
# 0.0-0.3 = best understood by university graduates.

def flesch_reading_ease(string):
    """ Returns the readability of the string as a value between 0.0-1.0:
        0.30-0.50 (difficult) => 0.60-0.70 (standard) => 0.90-1.00 (very easy).
    """
    def count_syllables(word, vowels="aeiouy"):
        n = 0
        p = False # True if the previous character was a vowel.
        for ch in word.endswith("e") and word[:-1] or word:
            v = ch in vowels
            n += int(v and not p)
            p = v
        return n
    if len(string) <  3:
        return 1.0
    string = string.strip()
    string = string.strip("\"'().")
    string = string.lower()
    string = string.replace("!", ".")
    string = string.replace("?", ".")
    string = string.replace(",", " ")
    string = string.replace("\n", " ")
    y = [count_syllables(w) for w in string.split(" ") if w != ""]
    w = len([w for w in string.split(" ") if w != ""])
    s = len([s for s in string.split(".") if len(s) > 2])
    #R = 206.835 - 1.015 * w/s - 84.6 * sum(y)/w
    # Use the Farr, Jenkins & Patterson algorithm,
    # which uses simpler syllable counting (count_syllables() is the weak point here). 
    R = 1.599 * sum(1 for v in y if v == 1) * 100 / w - 1.015*w/s - 31.517
    R = max(0.0, min(R*0.01, 1.0))
    return R

### STATISTICS #####################################################################################

def mean(list):
    """ Returns the arithmetic mean of the given list of values.
        For example: mean([1,2,3,4]) = 10/4 = 2.5.
    """
    return float(sum(list)) / (len(list) or 1)

def median(list):
    """ Returns the value that separates the lower half from the higher half of values in the list.
    """
    s = sorted(list)
    n = len(list)
    if n == 0:
        raise ValueError, "median() arg is an empty sequence"
    if n % 2 == 0:
        return float(s[(n/2)-1] + s[n/2]) / 2
    return s[n/2]

def variance(list, sample=True):
    """ Returns the variance of the given list of values.
        The variance is the average of squared deviations from the mean.
    """
    # Sample variance = E((xi-m)^2) / (n-1)
    # Population variance = E((xi-m)^2) / n
    m = mean(list)
    return sum((x-m)**2 for x in list) / (len(list)-int(sample) or 1)
    
def standard_deviation(list, *args, **kwargs):
    """ Returns the standard deviation of the given list of values.
        Low standard deviation => values are close to the mean.
        High standard deviation => values are spread out over a large range.
    """
    return sqrt(variance(list, *args, **kwargs))
    

def histogram(list, k=10, range=None):
    """ Returns a dictionary with k items: {(start, stop): [values], ...},
        with equal (start, stop) intervals between min(list) => max(list).
    """
    # To loop through the intervals in sorted order, use:
    # for (i,j), values in sorted(histogram(list).items()):
    #     m = i + (j-i)/2 # midpoint
    #     print i, j, m, values
    if range is None:
        range = (min(list), max(list))
    k = max(int(k), 1)
    w = float(range[1] - range[0] + 0.000001) / k # interval (bin width)
    h = [[] for i in xrange(k)]
    for x in list:
        i = int(floor((x-range[0]) / w))
        if 0 <= i < len(h): 
            #print x, i, "(%.2f, %.2f)" % (range[0]+w*i, range[0]+w+w*i)
            h[i].append(x)
    return dict(((range[0]+w*i, range[0]+w+w*i), v) for i, v in enumerate(h))

def moment(list, k=1):
    """ Returns the kth central moment of the given list of values
        (2nd central moment = variance, 3rd and 4th are used to define skewness and kurtosis).
    """
    if k == 1:
        return 0.0
    m = mean(list)
    return sum([(x-m)**k for x in list]) / (len(list) or 1)
    
def skewness(list):
    """ Returns the degree of asymmetry of the given list of values:
        > 0.0 => relatively few values are higher than mean(list),
        < 0.0 => relatively few values are lower than mean(list),
        = 0.0 => evenly distributed on both sides of the mean (= normal distribution).
    """
    # Distributions with skew and kurtosis between -1 and +1 
    # can be considered normal by approximation.
    return moment(list, 3) / (moment(list, 2) ** 1.5 or 1)


def kurtosis(list):
    """ Returns the degree of peakedness of the given list of values:
        > 0.0 => sharper peak around mean(list) = more infrequent, extreme values,
        < 0.0 => wider peak around mean(list),
        = 0.0 => normal distribution,
        =  -3 => flat
    """
    return moment(list, 4) / (moment(list, 2) ** 2.0 or 1) - 3


def quantile(list, p=0.5, sort=True, a=1, b=-1, c=0, d=1):
    """ Returns the value from the sorted list at point p (0.0-1.0).
        If p falls between two items in the list, the return value is interpolated.
        For example, quantile(list, p=0.5) = median(list)
    """
    # Based on: Ernesto P. Adorio, http://adorio-research.org/wordpress/?p=125
    # Parameters a, b, c, d refer to the algorithm by Hyndman and Fan (1996):
    # http://stat.ethz.ch/R-manual/R-patched/library/stats/html/quantile.html
    s = sort is True and sorted(list) or list
    n = len(list)
    f, i = modf(a + (b+n) * p - 1)
    if n == 0:
        raise ValueError, "quantile() arg is an empty sequence"
    if f == 0: 
        return float(s[int(i)])
    if i < 0: 
        return float(s[int(i)])
    if i >= n: 
        return float(s[-1])
    i = int(floor(i))
    return s[i] + (s[i+1] - s[i]) * (c + d * f)


def boxplot(list, **kwargs):
    """ Returns a tuple (min(list), Q1, Q2, Q3, max(list)) for the given list of values.
        Q1, Q2, Q3 are the quantiles at 0.25, 0.5, 0.75 respectively.
    """
    # http://en.wikipedia.org/wiki/Box_plot
    kwargs.pop("p", None)
    kwargs.pop("sort", None)
    s = sorted(list)
    Q1 = quantile(s, p=0.25, sort=False, **kwargs)
    Q2 = quantile(s, p=0.50, sort=False, **kwargs)
    Q3 = quantile(s, p=0.75, sort=False, **kwargs)
    return float(min(s)), Q1, Q2, Q3, float(max(s))
       
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
    test = u""" Alot of python magic and helpers in this list comprehension
     If this is one area where a more precise C implementation would be amazing
     but more work. Matthew's c$$l looking #beast $mode."""
    #print text_processer(test,False)
    #print text_processer(test,)
    print quantile(range(10), p=0.5) == median(range(10))
    a = 1
    b = 1000
    U = [float(i-a)/(b-a) for i in range(a,b)] # uniform distribution
    print abs(-1.2 - kurtosis(U)) < 0.0001

