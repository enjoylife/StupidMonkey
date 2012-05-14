from math import sqrt, floor, modf
from collections import Counter
import unicodedata

from pattern.web import Wikipedia
from pattern.vector import Corpus, Document

from enwrapper import EvernoteConnector
 
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
 
### Main ###
class EvernoteProfileInferer(EvernoteConnector):
    """ This is the  class that is responsible for extracting all the info
    hidden within the cloud of data from the Evernote service.

    Holds a self.wiki search class to provide searching for related wiki
    articles

    Ideas:
        Boxplot over all users in a certain method, so you would show their
    totals but then also show how that number is relative to others. Maybe this
    should be an ABC?
    http://stackoverflow.com/questions/2775864/python-datetime-to-unix-timestamp

    Caching: 
        perhaps pickling the objects and saving them for a week or something, or
    go all out and store full user state, and continually update the corpus and
    docs? Right now the corpus object is pickled into a basic file, we could
    better yet connect to a mongo GridFS and store it their?

    These are the fields used in the mongo collections 
    mongo.users:
        {_id: user_id} 
        {bool_lsa: False}  =  a boolean for lsa analysis. 

    mongo.notes:
        {_id_user: self.user_id} 
        {str_title: note.title}  
        {_id_notebook: note.notebook} 
        {_id_tags: [note.tags]} 
        {str_tags: [tag_names]}
        {str_content: note.content}

        {tokens_content: [~note.content.split()]} =  the extracted words for this note
        {tokens_lsa: [~tokens.lsa.reduce()]} = the reduced vectors for note
    """ 

    def __init__(self, base_uri, note_url, mongohandle):
        """ Create the wipedia search object 
        """
        EvernoteConnector.__init__(self,base_uri, note_url,mongohandle)
        self.sync_corpus()
        self.wiki = Wikipedia(language='en')

    def load_corpus(self):
        """ Load a corpus, used because we might change corpus saving and
        retrieving and with this we can be sure any changes wont affect other
        methods
        """
        return Corpus.load(cls, '/data/corpus/'+str(self.user_id))

    def save_corpus(self,corpus, update=False):
        """ Save a corpus, used because we might change corpus saving and
        retrieving and with this we can be sure any changes wont affect other
        methods
        """
        corpus.save('/data/corpus/'+str(self.user_id), update)

    def sync_corpus(self):
        """Creates  a new corpus on all notes if we already have synced before
        TODO:
            Store other data in the corpus besides basic text content, ie,
            extracted image, attribute note data, etc...
            catch corpus not found file error?
        """
        docs =[]
        corpus_check =  self.mongo.users.find_one({'_id':self.user_id},
                {'corpus':1}).get('corpus')
        # make sure we already created corpus
        if corpus_check and self.need_sync:
            update_guids = self.resync_db()
            corpus = self.load_corpus()
            # only those that need to be updated from the update_guids
            for x in self.mongo.notes.find(
                    {'_id':{'$in':update_guids}},{'tokens_content':1,'str_title':1}):
                # create the updated doc
                d =  Document(x['tokens_content'],name=x['str_title'],top=50)
                # set the id to what we want
                d._id = x['_id']
                docs.append(d)
                # remove old doc because corpus will still have old content
                corpus.remove(d)
            corpus.extend(docs)
            self.save_corpus(corpus)
        # dont need the sync, do nothing
        elif corpus_check:
            return
        # corpus sync has not been done before
        else: 
            for x in self.mongo.notes.find( # all notes of this user
                        {'_id_user':self.user_id},{'tokens_content':1,'str_title':1}):
                    d =  Document(x['tokens_content'],name=x['str_title'],top=30)
                    d._id = x['_id']
                    docs.append(d)
            corpus = Corpus(docs)
            self.save_corpus(corpus)
            self.mongo.users.update({'_id':self.user_id},{'$set':{'corpus':True}})

    def _lsa_extract(self, update_guids=None):
        """ runs lsa on a user and creates  a new corpus on all notes if we dont
        supply a note guid list, if list, we only updates a corpus.
        TODO:
            Store other data in the corpus besides basic text content, ie,
            extracted image, attribute note data, etc...
        """
        corpus = self.load_corpus()
        # picked arbitrarily
        corpus.reduce(25)
        vectors = corpus.lsa.vectors
        #doc.id and dic of concept vectors
        for doc, conc in vectors.items():
            words=[]
            for index, weight in conc.items():
                if abs(weight) >0.5:
                        words.append(corpus.lsa.terms[index])
            # add only if not already present the minimaized tokens to the note
            self.mongo.notes.update({'_id':doc},{'$addToSet':{'tokens_lsa':{'$each': words}}})
        # boolean to signal lsa has been done
        self.mongo.users.update({'_id':self.user_id},{'$set':{'tokens_lsa':True}})
        ## this might block for a while. TODO: split it into a new thread
        self.save_corpus(corpus,update=True)

    def topic_summary(self, **filterargs):
        """ Returns what are the main features that make up this topic.
        Features, setiment analysis, lsa main features, time deltas,
        could be any  mashup of other statistical technique.
        Ideas:
            Features are not just word counts and tags,
            Could be any number of other methods.
        """
        note_words ={}
        if not self.mongo.users.find_one({'_id':self.user_id, 'bool_lsa':True},{'bool_lsa':1}):
            # we have not done lsa before, do it now
            self._lsa_extract()
        if filterargs.keys():
        
            for x in self.mongo.notes.find({'_id_user':self.user_id},{'tokens_lsa':1}):
                note_words[(x['_id'])] = x['tokens_lsa']
            return note_words
           
        meta_list = [x.guid for x in self.get_notelist_guid_only(**filterargs).notes]
        for x in self.mongo.notes.find({'_id':{'$in':meta_list}}, {'tokens_lsa':1}):
            note_words[(x['_id'])] = x['tokens_lsa']
        return note_words

    def wiki_knowledge(self, note_guid, query, data):
        """ Helper for storing a pattern wiki search query object. 
        Must return the newly creaded data object  """
        document = {}
        document['title'] = data.title
        # links to other perhaps simialr topics
        document['intra_links'] = data.links[:5]
        # outside learning?
        document['extern_links'] = data.external[:5]
        # only want first section not a huge file
        document['data'] = unicodedata.normalize('NFKD',data.sections[0].content).encode('ascii','ignore')
        self.mongo.notes.update(
                {'_id':note_guid, 'knowledge.str_query':query}, 
                {'set':{ 'wikipedia':document}})
        # to set a constistant method call across all knowledge funcs??
        return  {'wikipedia':document}

    def outside_knowledge(self, note_guid, query,  service='wiki'):
        """ Gather resources that are related to this note from other services.
        Prime canidates are wikipedia, duckduckgo, freebase, news feeds, etc..
        Params:
            note_guid
            query = the string that you want searched for
            service = (optional) which service to query, default wikipedia
        mongo.notes{ knowledge scheme layout
        "An doc of  of past query strings that contain result objects with service
        specific data.
        {knowledge: 
            {
            str_query: string that was queried on {
            wikipedia: {
                intra_links: [links], extern_links:[links], data:str
            }
            duckduckgo:{
            }
                ....
            }
        }
        """
        # retrive note that has this query string embedded
        # return only the embedded query doc?
        note = self.mongo.notes.find_one(
                {'_id':note_guid, 'knowledge.str_query':query}, 
                    {'knowledge.str_query':1})
        # query returned sucessful
        if note and service:
            return note[service]
        elif note:
            return note
        # failed, must not have done it before
        else:
            # get the search engine attached to the class
            api = getattr(self, service)
            data = api.search(query,cached=True,timeout=10) 
            if data:
                #call the right method for this service
                f = getattr(self,service+'_knowledge','wiki_knowledge')
                return f(note_guid, query, data)

    def suggest_tags(self, ):
        """ Uses cosine similarity to suggest tags to the note 
        IDEAS:
            more weight for same notebook
            more weight for relative creation time
        """
        corrected_notes = {}

        if not self.mongo.users.find_one({'_id':self.user_id, 'bool_lsa':True},{'bool_lsa':1}):
            # we have not done lsa before, do it now we want a fast KNN
            self._lsa_extract()
        
        corpus = Corpus.load(cls, '/data/corpus/'+str(self.user_id))
        ## only untagged notes
        untaged_notes = self.mongo.notes.find({'_id_tags':None},{})
        for note in untaged_notes:
            suggested_tags =  set()
            # get the doc from the corpus
            for weight, doc in corpus.nearest_neigbors(corpus[(note['_id'])], top=5):
                # get the similar doc
                tags = self.mongo.notes.find_one(
                        {'_id':doc.id},{'str_tags':1}).get('str_tags')
                if tags:
                    suggested_tags.update(tags)
            corrected_notes[(note['_id'])] = suggested_tags
        return corrected_notes

    def word_count(self, **filterargs):
        """ Counts the total number of words in some sort of content of 
        a user's profile. 
        Ideas:
            By time, cluster and not just a single object?
            Note html links in their own counter?
        """
        c = Counter()

        if not filterargs:
            for x in self.mongo.notes.find(
                    {'_id_user':self.user_id},{'tokens_content':1}):
                c.update(x['tokens_content'])
            return c

        meta_list = [x.guid for x in self.get_notelist_guid_only(**filterargs).notes]
        for x in self.mongo.notes.find({'_id':{'$in':meta_list}},
                {'tokens_content':1}):
            c.update(x['tokens_content'])
        return c
    
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

    def readability(self, **filterargs):
        """ Computes a score based upon what an douchebag would mark you
        down for when student critiqing papers.
        Ideas:
            pattern.metrics.flesh_reading_ease
        """
        output={}
        if not filterargs.keys():
            for x in self.mongo.notes.find(
                    {'_id_user':self.user_id},{'str_content':1}):
                output[(x['_id'])] = flesch_reading_ease(x['str_content'])
        return output

        meta_list = [x.guid for x in self.get_notelist_guid_only(**filterargs).notes]
        for x in self.mongo.notes.find(
                {'_id':{'$in':meta_list}}, {'str_content':1}):
            output[(x['_id'])] = flesch_reading_ease(x['str_content'])
        return output

    def update_corpus(self):
        """ Updates the users analityc corpus if their is any changes
        in their note's content.
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

