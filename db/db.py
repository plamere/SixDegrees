import networkx as nx
import redis
import string
import sys
import time
import random
import collections
import util
import sd

r = redis.StrictRedis(host='localhost', port=6380, db = 1)
G = nx.Graph()
core_ids = None
max_returned_links=5
top_conn_artists = None
bad_artists = set(['1', '97546'])  
quick_mode = False
cache_expiration_time = 60 * 60 * 24 * 7
gstats = collections.defaultdict(int)


'''
link_weights = {
    '148' :20,     #instrument
    '149' :20,     #vocal
    '151' :20,     #conductor
    '150' :20,     #performing orchestra
    '103' :1,     #member of band
    '156' :5,     #performer
    '108' :1,     #is person
    '102' :5,    #collaboration
    '152' :20,     #chorus master
    '110' :5,    #sibling
    '109' :5,    #parent
    '111' :5,    #married
    '305' :20,     #conductor position
    '292' :20,     #voice actor
    '105' :20,     #instrumental supporting musician
    '104' :20,     #supporting musician
    '107' :20,     #vocal supporting musician
    '112' :5,     #involved with
    '101' :20,     #catalogued
    '999' :21,     #artist credit (synthetic link)
}
'''

link_info = {
    '999': {
        'weight': 21,
        'name': 'artist credit',
        'phrase': 'performed with',
        'rphrase': 'performed with',
    },
    '101': {
        'weight': 20,
        'name': 'catalogued',
        'phrase': 'catalogued',
        'rphrase': 'catalogued',
    },
    '112': {
        'weight': 5,
        'name': 'involved with',
        'phrase': 'involved with',
        'rphrase': 'involved with',
    },
    '107': {
        'weight': 20,
        'name': 'vocal supporting musician',
        'phrase': 'performed with',
        'rphrase': 'performed with',
    },
    '104': {
        'weight': 20,
        'name': 'supporting musician',
        'phrase': 'performed wth',
        'rphrase': 'performed with',
    },
    '105': {
        'weight': 20,
        'name': 'instrumental supporting musician',
        'phrase': 'performed wth',
        'rphrase': 'performed with',
    },
    '292': {
        'weight': 0,
        'name': 'voice actor',
        'phrase': 'performed with',
        'rphrase': 'performed with',
    },
    '305': {
        'weight': 20,
        'name': 'conductor',
        'phrase': 'conducted',
        'rphrase': 'was conducted by',
    },
    '111': {
        'weight': 5,
        'name': 'married',
        'phrase': 'was married to',
        'rphrase': 'was married to',
    },
    '109': {
        'weight': 5,
        'name': 'parent',
        'phrase': 'was parent of',
        'rphrase': 'was child of',
    },
    '110': {
        'weight': 5,
        'name': 'sibling',
        'phrase': 'was sibling of',
        'rphrase': 'was sibling of',
    },
    '152': {
        'weight': 20,
        'name': 'chorus master',
        'phrase': 'was chorus master with',
        'rphrase': 'was chorus mastered with',
    },
    '102': {
        'weight': 5,
        'name': 'collaboration',
        'phrase': 'collaborated with',
        'rphrase': 'collaborated with',
    },
    '148': {
        'weight': 20,
        'name': 'instrument',
        'phrase': 'performed with',
        'rphrase': 'performed with',
    },
    '149': {
        'weight': 20,
        'name': 'vocal',
        'phrase': 'performed with',
        'rphrase': 'performed with'
    },

    '150': {
        'weight': 20,
        'name': 'performing orchestra',
        'phrase': 'played with',
        'rphrase': 'played with',
    },

    '156': {
        'weight': 20,
        'name': 'performer',
        'phrase': 'performed with',
        'rphrase': 'performed with',
    },

    '151': {
        'weight': 20,
        'name': 'conductor',
        'phrase': 'conducted with',
        'rphrase': 'conducted by',
    },

    '103': {
        'weight': 1,
        'name': 'member',
        'phrase': 'was a member of',
        'rphrase': 'had member',
    },

    '108': {
        'weight': 1,
        'name': 'is person',
        'phrase': 'is an alias of',
        'rphrase': 'is an alias of',
    },
}

def artist_search(text):
    lwords = []   
    text = filter_name(text)
    words = text.split()
    for word in words:
        w = 'si-' + word
        lwords.append(w)
    if len(lwords) > 0:
        aids = list((r.sinter(lwords)))
        aids = filter_aids_by_graph(aids)
        artists = artist_get(aids)
        exacts, non_exacts = filter_artists(text, artists)
        return exacts + non_exacts
    else:
        print 'no words for', text
        return []

def filter_name(text):
    text = text.lower()
    text = util.remove_accents(text)
    text = util.remove_punctuation(text)
    return text

def filter_artists(text, artists):
    exacts = []
    non_exacts = []

    for artist in artists:
        if filter_name(artist['name']) == text:
            exacts.append(artist)
        else:
            non_exacts.append(artist)

    exacts.sort(key=lambda a: a['link_count'], reverse=True)
    non_exacts.sort(key=lambda a: a['link_count'], reverse=True)
    return exacts, non_exacts
    

def filter_aids_by_graph(aids):
    return [aid for aid in aids if aid in G]
    
def artist_get(aids):
    p = r.pipeline()
    for aid in aids:
        p.hgetall('ARTIST:' + str(aid))
    results =  p.execute()

    for res in results:
        res['link_count'] = int(res['link_count'])

    return results

def is_artist_in_graph(aid):
    return aid in G


def artist_path(start_aid, end_aid, skipset=None, save=True):
    start = time.time()
    try:
        if not start_aid in G:
            print start_aid, 'not in graph'
            return []

        if not end_aid in G:
            print end_aid, 'not in graph'
            return []
            
        length, aids = _get_shortest_path(start_aid, end_aid, skipset)

        # end = time.time()
        #print 'path calculated in  ', end - start

        path = get_path(aids)

        #end = time.time()
        #print 'path retrieved in   ', end - start

        if save:
            save_path_to_db(start_aid, end_aid, len(path['links']), skipset, aids)
        end = time.time()
        print 'path ', end - start, 'secs', 'length:', len(path['links']), 'score:', path['score']
        return path

    except nx.NetworkXNoPath:
        end = time.time()
        print 'no path found in', end - start, 'secs'
        return []

def _get_shortest_path(start, end, skips):
    key = _get_path_cache_key(start, end, skips)
    path_string = r.get(key)
    if not path_string:
        length, aids = sd.bidirectional_dijkstra(G, start, end, weight='weight', skipset=skips)
        path_string  = ','.join(aids)
    else:
        print "cache hit", key, ' ', path_string
        aids = path_string.split(',')
        length = len(aids)
    # always set to reset the cache expiration time
    r.set(key, path_string, ex=cache_expiration_time)
    return length, aids

def _get_path_cache_key(start, end, skips):
    sl = list(skips) if skips else []
    sl.sort()
    mode = 'q' if quick_mode else 'f'
    key = ",".join(['APC', mode, start, end] + sl)
    return key

def top_connected_artists(count=100):
    return top_conn_artists[:count]

def artist_raw_path(start_aid, end_aid, weighted=True, skipset=None):
    start = time.time()
    try:
        if weighted:    
            weight = 'weight'
        else:
            weight = 'None'
        length, aids = sd.bidirectional_dijkstra(G, start_aid, end_aid, weight='weight', skipset=skipset)
        end = time.time()
        score = score_path(aids)
        print 'path calculated in', end - start, 'secs', 'length:', len(aids), 'score:', score
        return score, aids
    except nx.NetworkXNoPath:
        return 0, None


def artist_random_old2():
    return random.choice(G.nodes())


def save_path_to_db(start, end, length, skips, aids):
    if skips:
        slist = list(skips)
        slist.sort()
    else:
        slist = []

    entry_list = [start, end, str(length)] + slist
    sentry = ','.join(entry_list)
    p =  r.pipeline()
    p.zincrby('MOST-FREQUENT-PATHS', sentry, 1)
    p.zadd('LONGEST-PATHS', length, sentry)
    # keep the highest 250 scoring paths
    p.zremrangebyrank("LONGEST-PATHS",  0, -251)
    for aid in aids[1:-1]:
        p.zincrby('MOST-CENTRAL-ARTISTS', aid, 1)
    for aid in slist:
        p.zincrby('MOST-BYPASSED-ARTISTS', aid, 1)
    p.zincrby('STARTING-ARTISTS', start, 1)
    p.zincrby('ENDING-ARTISTS', end, 1)
    p.execute()

def most_central_artists(count):
    results = r.zrevrange('MOST-CENTRAL-ARTISTS', 0, count - 1, withscores=True)

    aids = [ aid for aid, score in results]

    artists = artist_get(aids)

    for artist, (aid, score) in zip(artists, results):
        artist['count'] = score
    return artists

def top_starting_artists(count):
    results = r.zrevrange('STARTING-ARTISTS', 0, count - 1, withscores=True)

    aids = [ aid for aid, score in results]

    artists = artist_get(aids)

    for artist, (aid, score) in zip(artists, results):
        artist['count'] = score
    return artists

def top_ending_artists(count):
    results = r.zrevrange('ENDING-ARTISTS', 0, count - 1, withscores=True)

    aids = [ aid for aid, score in results]

    artists = artist_get(aids)

    for artist, (aid, score) in zip(artists, results):
        artist['count'] = score
    return artists

def most_connected_artists(count):
    results = r.zrevrange('CONNECTED-ARTISTS', 0, count - 1, withscores=True)

    aids = [ aid for aid, score in results]

    artists = artist_get(aids)

    for artist, (aid, score) in zip(artists, results):
        artist['count'] = score
    return artists

def most_bypassed_artists(count):
    results = r.zrevrange('MOST-BYPASSED-ARTISTS', 0, count - 1, withscores=True)

    aids = [ aid for aid, score in results]

    artists = artist_get(aids)

    for artist, (aid, score) in zip(artists, results):
        artist['count'] = score
    return artists

def get_most_frequent_paths(start, count):
    results = r.zrevrange('MOST-FREQUENT-PATHS', start, start + count - 1, withscores=True)

    out = []
    for sentry,score in results:
        aids = sentry.split(',')
        artists = artist_get(aids[0:2])
        entry = {
            'src' : artists[0],
            'dest' : artists[1],
            'path_length' : int(aids[2]),
            'skips' : aids[3:],
            'visits' : score,
        }
        out.append(entry)
    return out

def get_longest_paths(start, count):
    results = r.zrevrange('LONGEST-PATHS', start, start + count - 1, withscores=True)

    out = []
    for sentry,score in results:
        aids = sentry.split(',')
        artists = artist_get(aids[0:2])
        entry = {
            'src' : artists[0],
            'dest' : artists[1],
            'path_length' : int(aids[2]),
            'skips' : aids[3:],
            'visits' : score,
        }
        out.append(entry)
    return out


def artist_random():
    global core_ids
    if core_ids == None:
        paths = nx.single_source_dijkstra_path(G, '303')
        core_ids = list(paths.keys())
    return random.choice(core_ids)

def artist_random_old():
    return r.srandmember('ALL-ARTISTS')


def remove_edge(aid1, aid2):
    G.remove_edge(aid1, aid2)


def artist_neighbors_old_and_heavy(aid):
    ''' gets the list of neighbors for an artist '''
    aids = G.neighbors(aid)

    links = []
    path = {
        'links': links,
        'score':0
    }
    for naid in aids:
        total_links, top_links = get_links_between(aid, naid)
        sname, squery = artist_info(aid)
        dname, dquery = artist_info(naid)
        l = {
            'src':aid,
            'src_name':sname,
            'src_query':squery,
            'dest':naid,
            'dest_name':dname,
            'dest_name':dquery,
            'links' : top_links,
            'total_links' : total_links,
            'score': nweight(G[aid][naid]['weight'])
        }
        links.append(l)
    links.sort(key=lambda l:l['total_links'], reverse=True)
    links.sort(key=lambda l: l['score'])
    return path

def artist_neighbors(aid):
    ''' gets the list of neighbors for an artist '''


    if aid not in G:
        return None

    aids = G.neighbors(aid)

    links = []
    path = {
        'links': links,
        'score':0
    }

    anames = artist_names(aids)
    for i, naid in enumerate(aids):
        link = G[aid][naid]
        l = {
            'dest':naid,
            'dest_name': anames[i],
            'main_link' : link_name(link['lt']),
            'total_links' : link['conns'],
            'score': link['weight']
        }
        links.append(l)
    links.sort(key=lambda l:l['total_links'], reverse=True)
    links.sort(key=lambda l: l['score'])
    return path

def artist_raw_neighbors(aid):
    return G.neighbors(str(aid))
    

def artist_path2(start_aid, end_aid):
    start = time.time()
    aids = nx.astar_path(G, start_aid, end_aid)
    end = time.time()
    path = get_path(aids)
    print len(path['links']), 'path, calculated in', end - start, 'secs'
    return path

def get_path(aids):
    links = []
    path = {
        'links': links,
        'score':score_path(aids)
    }

    for i in xrange(len(aids) - 1):
        aid = aids[i]
        next = aids[i + 1]
        total_links, top_links = get_links_between(aid, next)
        sname, squery = artist_info(aid)
        dname, dquery = artist_info(next)
        l = {
            'src':aid,
            'src_name':sname,
            'src_query':squery,
            'dest':next,
            'dest_name':dname,
            'dest_query':dquery,
            'links' : top_links,
            'total_links' : total_links,
            'score': nweight(G[aid][next]['weight'])
        }
        links.append(l)
    return path


def get_links_between(aid1, aid2):
    links = []
    for l in get_raw_links(aid1):
        if l['dest'] == aid2:
            links.append(l)
            reverse_link(l, False)
    for l in get_raw_links(aid2):
        if l['dest'] == aid1:
            reverse_link(l, True)
            links.append(l)
    links = populate_links_with_weights(links)
    links.sort(key=lambda l:l['weight'])
    total_links = len(links)
    links = links[:max_returned_links]
    links = populate_links_with_names(links)
    check_links(aid1, aid2, links)
    return total_links, links


def check_links(a1, a2, links):
    for l in links:
        if l['src'] != a1:
            print 'CHECK LINK, mismatch src', a1
            l['error'] = 'mismatch src ' + str(a1)
        if l['dest'] != a2:
            print 'CHECK LINK, mismatch src', a2
            l['error'] = 'mismatch dest ' + str(a2)

def reverse_link(l, reverse):
    # l['reverse']=reverse
    type = l['type']
    if reverse:
        swap = l['src']
        l['src'] = l['dest']
        l['dest'] = swap
        l['phrase'] = link_info[type]['rphrase']
    else:
        l['phrase'] = link_info[type]['phrase']

def score_path(aids):
    score = 0
    for i in xrange(len(aids) - 1):
        aid = aids[i]
        next = aids[i + 1]
        score += nweight(G[aid][next]['weight'])
    return score
    

def get_raw_links(aid):
    key = 'ARTIST-LINKS:' + str(aid)
    link_lines = r.smembers(key)
    links = []
    for line in link_lines:
        type, src, dest, extra = line.split(',')
        weight = link_info[type]['weight']
        if weight == 0:
            continue
        link = {
            'src':src,
            'dest':dest,
            'type':type,
            'extra':extra,
        }
        links.append(link)
    return links


def stats():
    stats = {
        'graph_stats': gstats
    }
    return stats

def report_video(vid, src, dest, q):
    report = ','.join([vid, src, dest, q])
    r.lpush('REPORTED-VIDEOS', report);

def process_video(vid, src, dest, q):
    report = ','.join([vid, src, dest, q])
    r.lrem('REPORTED-VIDEOS', report, count=0);
    r.lpush('PROCESSED-VIDEOS', report);

def get_video_reports(start, count):
    reports = r.lrange('REPORTED-VIDEOS', start, start + count - 1)
    out_list = []
    for rep in reports:
        vid, src, dest,q = rep.split(',')
        asrc, adest = artist_get([src, dest])
        report = {
            'src': asrc,
            'dest': adest,
            'video':vid,
            'query':q
        }
        out_list.append(report)

    total = r.llen('REPORTED-VIDEOS')
    processed = r.llen('PROCESSED-VIDEOS')
    out = {
        'reports': out_list,
        'start' : start,
        'count' : count,
        'total':  total,
        'processed':  processed
    }
    return out

def populate_links_full(links):
    p = r.pipeline()
    for link in links:
        p.hget("ARTIST:" + str(link['src']), 'name')
        p.hget("ARTIST:" + str(link['dest']), 'name')
        if len(link['extra']) > 0:
            p.hget("RECORDING:"+ link['extra'], "name")
    results = p.execute()

    for link in links:
        link['src_name'] = results.pop(0)
        link['dest_name'] = results.pop(0)
        link['type_name'] = link_name(link['type'])
        if len(link['extra']) > 0:
            link['song'] = results.pop(0)
    return links

def populate_links(links):
    p = r.pipeline()
    for link in links:
        if len(link['extra']) > 0:
            p.hget("RECORDING:"+ link['extra'], "name")
    results = p.execute()

    for link in links:
        link['type_name'] = link_name(link['type'])
        if len(link['extra']) > 0:
            link['song'] = results.pop(0)
        link['weight'] = link_info[link['type']]['weight']
    return links

def populate_links_with_weights(links):
    for link in links:
        link['type_name'] = link_name(link['type'])
        link['weight'] = link_info[link['type']]['weight']
    return links

def populate_links_with_names(links):
    p = r.pipeline()
    for link in links:
        if len(link['extra']) > 0:
            p.hget("RECORDING:"+ link['extra'], "name")
    results = p.execute()

    for link in links:
        if len(link['extra']) > 0:
            link['song'] = results.pop(0)
    return links
        

def link_name(type):
    return link_info[type]['name']

def artist_name(aid):
    return r.hget("ARTIST:" + str(aid), 'name')

def artist_info(aid):
    p = r.pipeline()
    p.hget("ARTIST:" + str(aid), 'name')
    p.hget("ARTIST:" + str(aid), 'query')
    results = p.execute()
    if results[1] == None:
        results[1] = results[0]
    return results

def artist_names(aids):
    p = r.pipeline()
    for aid in aids:
        p.hget("ARTIST:" + str(aid), 'name')
    return p.execute()


def artist_links(aid):
    links = get_raw_links(aid)
    populate_links(links)
    return links

def init(quick=False):
    global quick_mode
    quick_mode = quick
    if quick:
        _build_quick_graph()
    else:
        _build_graph()
        #_build_beatle_graph()

def set_query_string(aid, query):
    key = 'ARTIST:' + aid
    if query == '(delete)':
        r.hdel(key, 'query')
    elif len(query) > 0:
        r.hset(key, 'query', query)
    return r.hgetall(key)

def calc_top_connected_artists():
    top = collections.defaultdict(int)

    for aid in G.nodes():
        conns = 0
        naids = G.neighbors(aid)
        for naid in naids:
            conns += G[aid][naid]['conns']
        top[aid] = conns

    toplist = [ (v,k) for k,v in top.items()]
    toplist.sort(reverse=True)
    toplist = toplist[:250]

    aids = []
    for count, aid in toplist:
        aids.append(aid)

    artists = artist_get(aids)

    for (count, aid), artist in zip(toplist, artists):
        artist['connections'] = count

    global top_conn_artists
    top_conn_artists = artists


def prep_graph():
    calc_top_connected_artists()
    print 'artists:', gstats['nodes']
    print 'edges:', gstats['edges']
    print 'connections:', gstats['connections']
        


def _add_weighted_links(i, key):
    all = r.smembers(key)

    print i, key
    lsrc = key.split(':')[1]
    weights = collections.defaultdict(list)
    best_type = {}

    gstats['nodes'] += 1
    for l in all:
        lt, src, dest, extra = l.split(',')

        if src != lsrc:
            print 'woah, inconsistent linkage for', key, src, lsrc

        if src in bad_artists:
            break
        if dest in bad_artists:
            continue
        weight = link_info[lt]['weight']
        if weight == 0:
            continue

        weights[dest].append(weight)

        if dest not in best_type:
            best_type[dest] = lt
        else:
            btype = best_type[dest]
            if link_info[btype]['weight'] < weight:
                best_type[dest] = lt

    for dest, weights in weights.items():
        if G.has_edge(lsrc, dest):
            prev_conns = G[lsrc][dest]['conns']
        else:
            prev_conns = 0

        nconns = len(weights) + prev_conns
        weight = min(weights)

        if weight > 2 and nconns > 20:
            weight = 2
        elif weight > 3 and nconns > 10:
            weight = 3
        elif weight > 10 and nconns > 2:
            weight = 10

        gstats['edges'] += 1
        gstats['connections'] += len(weights)

        if G.has_edge(lsrc, dest):
            prev_weight = G[lsrc][dest]['weight']
            if weight < prev_weight:
                G[lsrc][dest]['weight'] = weight
                G[lsrc][dest]['conns'] = nconns
                G[lsrc][dest]['lt'] = best_type[dest]
        else:
            G.add_edge(lsrc, dest, weight=weight, conns=nconns, lt=best_type[dest])
        
def nweight(weight):
    return weight

def build_beatles_cluster():
    nodes = nx.node_connected_component(G, "303")
    print 'beatles nodes', len(nodes)
    p = r.pipeline()
    for node in nodes:
        p.sadd('BEATLES-SET', node)
    p.execute()


def _build_graph():
    for i, key in enumerate(r.keys("ARTIST-LINKS:*")):
        _add_weighted_links(i, key)
    prep_graph()

def _build_quick_graph():
    for i, key in enumerate(r.smembers("ARTIST-QUICK-SET")):
        _add_weighted_links(i, 'ARTIST-LINKS:' + key)
    prep_graph()

def _build_beatle_graph():
    for i, key in enumerate(r.smembers("BEATLES-SET")):
        _add_weighted_links(i, 'ARTIST-LINKS:' + key)
    prep_graph()

def _strip_punctuation(s):
    print 'strip', s
    exclude = set(string.punctuation)
    s = ''.join(ch for ch in s if ch not in exclude)
    return s

    #return s.translate(string.maketrans("", ""), string.punctuation)

if __name__ == '__main__':
    init(quick=True)
    #build_beatles_cluster()
