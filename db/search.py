import redis
import sys
import util
import db

r = redis.StrictRedis(host='localhost', port=6380, db = 1)

def artist_search(text):
    lwords = []   
    text = filter_name(text)
    words = text.split()
    for word in words:
        w = 'si-' + word
        lwords.append(w)
    if len(lwords) > 0:
        aids = list((r.sinter(lwords)))
        artists = artist_get(aids)
        return artists
    else:
        print 'no words for', text
        return []

def filter_name(text):
    text = text.lower()
    text = util.remove_accents(text)
    text = util.remove_punctuation(text)
    return text

def artist_get(aids):
    p = r.pipeline()
    for aid in aids:
        p.hgetall('ARTIST:' + str(aid))
    results =  p.execute()
    return results

if __name__ == '__main__':
    query = ' '.join(sys.argv[1:])

    res = artist_search(query)
    for r in res:
        print r
