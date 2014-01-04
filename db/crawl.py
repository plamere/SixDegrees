import psycopg2
import sys
import re
import redis
import search
import collections
import string
import simplejson as json
import util

anames = collections.defaultdict(list)

r = redis.StrictRedis(host='localhost', port=6380, db = 1)

artists = {}
albums = {}
tracks = {}

SEP = '<sep>'
PSEP = ' <sep> '

link_tables = {}

anames = {}

def connect():
    conn = psycopg2.connect("dbname=musicbrainz host=dca-dw01 user=musicbrainz password=musicbrainz");
    return conn

#conn = connect()
#cur = conn.cursor()

def add_artist(id):
    if not r.exists('ARTIST:' + str(id)):
        r.sadd('NEW-ARTISTS', id)

def save_artist(p, artist):
    aid = artist['id']
    key = 'ARTIST:' + str(aid)
    for k, v in artist.items():
        p.hset(key, k, v)
    add_to_index(p, artist['name'], aid)

def save_artists(artists):
    p = r.pipeline()
    for artist in artists:
        save_artist(p, artist)
    p.execute()

def process_artists_old():
    total = r.scard('NEW-ARTISTS')
    count = 0
    print 'processing', total, 'new artists'
    while r.scard('NEW-ARTISTS') > 0:
        aid = r.spop('NEW-ARTISTS')
        artist = load_artist_from_mb(aid)
        p = r.pipeline()
        save_artist(p, artist)
        p.execute()
        if count % 100 == 0:
            print count,'of', total
        count += 1
    print 'done'

def process_artists():
    batch_size = 100
    total = r.scard('NEW-ARTISTS')
    count = 0
    print 'processing', total, 'new artists'
    batch = []
    while r.scard('NEW-ARTISTS') > 0:
        aid = r.spop('NEW-ARTISTS')
        batch.append(aid)
        if (len(batch) >= batch_size):
            print count,'of', total
            artists = load_artists_from_mb(batch)
            save_artists(artists)
            batch = []
        count += 1

    if len(batch) > 0:
        artists = load_artists_from_mb(batch)
        save_artists(artists)
    print 'done'

def add_link(p, type, src, dest, extra=''):
    key = 'ARTIST-LINKS:' + str(src)
    link_string = ','.join(map(str,( (type, src, dest, extra) ) ))
    p.sadd(key, link_string)

    add_artist(src)
    add_artist(dest)


def build_link_table():
    query = '''select * from link_type;'''
    cur.execute(query)
    rows = cur.fetchall()


    p = r.pipeline()
    for row in rows:
        id, parent, child, gid, et0, et1, name, description,  link_phrase, reverse_link_phrase, llp, priority, last_updated = row
        id = str(id)
        key = 'LINK:' + id

        p.hset(key, 'id', id)
        p.hset(key, 'type', et0 + '-' + et1)
        p.hset(key, 'name', name)
        p.hset(key, 'description', description)
        p.hset(key, 'link_phrase', link_phrase)
        p.hset(key, 'reverse_link_phrase', reverse_link_phrase)
        p.hset(key, 'long_link_phrase', llp)
        p.hset(key, 'weight', 100)
    p.execute()

    
def load_artist_credit_name_table():
    table = collections.defaultdict(list)
    query = '''select artist_credit, artist from artist_credit_name;'''
    cur.execute(query)
    rows = cur.fetchall()
    for ac, ar in rows:
        table[ac].append(ar)
    print 'ac_table length', len(table)
    return table

def artist_search(text):
    lwords = set()
    text = text.lower()
    text = util.remove_accents(text)
    text = util.remove_punctuation(text)
    words = text.split()
    swords = set(words)
    for word in swords:
        w = 'si-' + word
        lwords.append(w)
    aids = r.sinter(lwords)
    print 'as', lwords, aids
    return list(aids)

def add_to_index(p, name, id):
    text = name.lower()
    text = util.remove_accents(text)
    text = util.remove_punctuation(text)
    words = text.split()
    swords = set(words)
    for word in swords:
        w = 'si-' + word
        p.sadd(w, id)

def index_all_artists():
    p = r.pipeline()
    for key in r.keys('ARTIST:*'):
        prefix, aid = key.split(':')
        name = r.hget(key, 'name')
        add_to_index(p, name, aid)
    p.execute()


def delete_search_index():
    for key in r.keys('si-*'):
        r.delete(key)

def strip_punctuation(s):
    return s.translate(string.maketrans("", ""), string.punctuation)

def load_artist_from_mb(aid):
    query = '''select artist.id, n.name as name, artist.gid  from artist 
                    join artist_name n on artist.name = n.id where artist.id=''' + aid + ';'
    cur.execute(query)
    row = cur.fetchone()
    id, name, gid = row
    artist = {
        'id' : aid,
        'name': name,
        'gid': gid,
    }
    return artist

def quote(s):
    return "'" + str(s) + "'"

def load_artists_from_mb(artist_list):
    aids = ",".join(map(quote, artist_list))

    query = '''select artist.id, n.name as name, artist.gid  from artist 
                    join artist_name n on artist.name = n.id where artist.id in (''' + aids + ');'
    # print query
    cur.execute(query)
    rows = cur.fetchall()

    artists = []
    for id, name, gid in rows:
        artist = {
            'id' : id,
            'name': name,
            'gid': gid,
        }
        artists.append(artist)
    # print 'artists', artists
    return artists

def load_artist_to_artist_links():
    print 'loading artist to artist links'
    query = '''select lt.id, lt.name, laa.entity0, laa.entity1 from l_artist_artist laa join link 
        on laa.link = link.id join link_type lt on link.link_type = lt.id
        ;
    '''
    cur.execute(query)
    rows = cur.fetchall()
    p = r.pipeline()
    for lt_id, lt_name, aid0, aid1 in rows:
        add_link(p, lt_id, aid0, aid1)
    results = p.execute()
    print len(results), 'links added'


def save_recording(p, rid, rname, artists):
    key = "RECORDING:" + str(rid)
    if not r.exists(key):
        p.hset(key, 'id', rid)
        p.hset(key, 'name', rname)
        p.hset(key, 'artists', ','.join(map(str, artists)))

def load_recordings_with_multiple_artists():
    query = '''select r.id, tn.name, r.artist_credit from recording r 
        join track_name tn on tn.id = r.name
        join artist_credit ac on r.artist_credit = ac.id
    where ac.artist_count > 1
        ;
    '''
        # limit 100 
    cur.execute(query)
    rows = cur.fetchall()

    data = []
    for rid, wname, ac in rows:
        data.append( (rid, wname, ac) )

    for row, (rid, wname, ac) in enumerate(data):
        key = "RECORDING:" + str(rid)
        if r.exists(key):
            continue
        p = r.pipeline()
        query = 'select acn.artist from artist_credit_name acn where acn.artist_credit = ' + str(ac) + ";"
        cur.execute(query)
        irows = cur.fetchall()
        all_artists = []
        for aid in irows:
            aid = aid[0]
            all_artists.append(str(aid))
        save_recording(p, rid, wname, all_artists)
        print row, len(data), rid, wname, all_artists
        for i in xrange(len(all_artists)):
            for j in xrange(i + 1, len(all_artists)):
                add_link(p, 999, all_artists[i], all_artists[j], rid)
                print '    add link', rid, wname, all_artists[i], all_artists[j]
        p.execute()


def load_artist_to_recording_links():
    ac_table = load_artist_credit_name_table()
    #ac_table = collections.defaultdict(list)
    print 'artist to recording links'
    query = '''select lt.id, laa.entity0, laa.entity1, r.artist_credit, tn.name from l_artist_recording laa 
        join link on laa.link = link.id 
        join link_type lt on link.link_type = lt.id 
        join recording r on laa.entity1 = r.id
        join track_name tn on tn.id = r.name
        where (lt.parent = 122 or lt.parent=156) 
        ;
    '''
        # limit 1000
        # and laa.entity0=938
    cur.execute(query)
    rows = cur.fetchall()

    data = []
    for row in rows:
        data.append( row)

    total_links =0
    for row, (lt_id, aid, rid, ac, rname) in enumerate(data):
        all_artists = ac_table[ac]
        if len(all_artists) == 1 and aid == all_artists[0]:
            continue

        p = r.pipeline()
        save_recording(p, rid, rname, all_artists)
        print row, len(data), total_links, rid, rname, all_artists

        for oaid in all_artists:
            if aid != oaid:
                add_link(p, lt_id, aid, oaid, rid)
                print '    add link', lt_id, aid, n(aid), oaid, n(oaid), '  ', rid, rname
                total_links += 1
        p.execute()
    print 'links added', total_links



# artist to recording parent for performance is 122  156 is performance (want if parent is 122 or 156)
# artist to release_group parent for performance is 34  51 is performance

def load_artist_alias():
    query = '''select aa.artist, n.name as name from artist_alias aa join artist_name n on aa.name = n.id;'''
    cur.execute(query)
    rows = cur.fetchall()
    for id, name in rows:
        if id in artists:
            artists[id]['aliases'].append(name)
            print 'alias', name, ' === ', artists[id]['name']
        else:
            print "can't find artist", id, "for alias", name

def proc_all():
    load_artists()
    load_artist_alias()


def dump_artist_to_artist_links():
    query = '''select lt.id, lt.name, laa.entity0, laa.entity1 from l_artist_artist laa join link 
        on laa.link = link.id join link_type lt on link.link_type = lt.id;
    '''
    cur.execute(query)
    rows = cur.fetchall()
    for lt_id, lt_name, aid0, aid1 in rows:
        print  "|".join( map(str, (lt_id, lt_name, aid0, anames[aid0], aid1, anames[aid1])) )

def dump_artist_to_track_links():
    query = '''select lt.id, lt.name, lar.entity0, lar.entity1 from l_artist_recording lar join link 
        on lar.link = link.id join link_type lt on link.link_type = lt.id
        ;
    '''
        #limit 1000 ;
    cur.execute(query)
    rows = cur.fetchall()

    tracks = collections.defaultdict(list)
    lt_names = {}

    for lt, name, entity0, entity1 in rows:
        lt_names[lt] = name
        tracks[entity1].append( (lt, entity0, name) )

    for k, v in tracks.items():
        if len(v) > 0:
            for i, (lt, a1, name) in enumerate(v):
                for (scratch,  a2, scratch) in v[i+1:]:
                    print  "|".join( map(str, (lt, a1, anames[a1], a2, anames[a2], k, name) ))


def dump_recordings_with_multiple_artists():
    query = '''select r.id, rn.name, r.artist_credit from recording r join release_name rn on r.name = rn.id join artist_credit ac on r.artist_credit = ac.id
    where ac.artist_count > 1;
    '''
        #limit 1000 ;
    cur.execute(query)
    rows = cur.fetchall()
    for i, row in enumerate(rows):
        print i, row

    for id, rname, ac  in rows:
        query = 'select acn.artist, n.name  from artist_credit_name acn join artist_name n on acn.name = n.id where acn.artist_credit = ' + str(ac) + ";"
        cur.execute(query)
        irows = cur.fetchall()
        for aid, name in irows:
            print id, rname, aid, name

def dump_releases_with_multiple_artists():
    query = '''select r.id, rn.name, r.artist_credit from release r join release_name rn on r.name = rn.id join artist_credit ac on r.artist_credit = ac.id
    where ac.artist_count > 1;
    '''
        #limit 1000 ;
    cur.execute(query)
    rows = cur.fetchall()
    for i, row in enumerate(rows):
        print i, row

    for id, rname, ac  in rows:
        query = 'select acn.artist, n.name  from artist_credit_name acn join artist_name n on acn.name = n.id where acn.artist_credit = ' + str(ac) + ";"
        cur.execute(query)
        irows = cur.fetchall()
        for aid, name in irows:
            print id, rname, aid, name

def dump_artists(aids):
    for aid in aids:
        print r.hget('ARTIST:' + str(aid), 'name')

def n(aid):
    return r.hget('ARTIST:' + str(aid), 'name')

def walk_artist(aid, visited=None):
    aid = str(aid)
    if visited == None:
        visited = set()

    visited.add(aid)
    key = 'ARTIST-LINKS:' + str(aid)
    links = r.smembers(key)

    next = []

    print "===", artist_name(aid), "==="
    for link in links:
        type, src, dest, extra = link.split(',')
        print "   ", link_name(type), artist_name(dest)
        if not dest in visited:
            next.append(dest)

    for naid in next:
        walk_artist(naid, visited)

def dump_links(aids):
    for aid in aids:
        key = 'ARTIST-LINKS:' + str(aid)
        links = r.smembers(key)
        print "===", artist_name(aid), "==="
        for link in links:
            type, src, dest, extra = link.split(',')
            print "   ", link_name(type), artist_name(dest),
            if len(extra) > 0:
                name = r.hget("RECORDING:"+extra, "name")
                if name:
                    print "    ", name,
            print

def cleanup_links(i, key):
    all = r.smembers(key)
    found = {}
    dups = 0

    dels = []
    for l in all:
        lt, src, dest, extra = l.split(',')
        tag = dest + ',' + extra
        if tag in found:
            olt, ol = found[tag]
            iolt = int(olt)
            ilt = int(lt)
            if ilt < iolt:
                found[tag] = (lt, l)
                dels.append(ol)
            else:
                dels.append(l)
            dups += 1
        else:
            found[tag] = (lt, l)

    if len(dels) > 0:
        p = r.pipeline()
        for d in dels:
            print '    dups', d
            p.srem(key, d)
        results = p.execute()
        print i, 'would delete', len(dels), 'did delete', len(results)

def cleanup_all_links():
    for i, key in enumerate(r.keys("ARTIST-LINKS:*")):
        cleanup_links(i, key)
    

def link_name(type):
    if type == '999':
        return 'collab on song'
    else:
        return r.hget("LINK:" + str(type), 'name')

def artist_name(aid):
    return r.hget("ARTIST:" + str(aid), 'name')


def create_quick_artist_list():
    full_set = set()
    ids = set(['303'])
    max_ids = 10000
    max_passes = 3

    for p in xrange(max_passes):
        full_set = set()
        for i, key in enumerate(r.keys("ARTIST-LINKS:*")):
            all = r.smembers(key)

            for l in all:
                lt, src, dest, extra = l.split(',')
                if (src in ids) or (dest in ids):
                    full_set.add(src)
                    full_set.add(dest)
                    print 'full set', len(full_set)
            if len(full_set) >= max_ids:
                break
        if len(full_set) >= max_ids:
            break
        ids = full_set

    print 'full set', len(full_set)

    p = r.pipeline()

    for aid in full_set:
        p.sadd('ARTIST-QUICK-SET', aid)
    p.execute()

def create_all_artist_list():
    p = r.pipeline()
    for i, key in enumerate(r.keys("ARTIST:*")):
        aid = key.split(':')[1]
        p.sadd('ALL-ARTISTS', aid)
    p.execute()

def add_connection_count_to_artists():

    skips = set(['292'])
    counts = collections.defaultdict(int)

    for i, key in enumerate(r.keys("ARTIST-LINKS:*")):
        all = r.smembers(key)
        print i, key
        lsrc = key.split(':')[1]
        weights = collections.defaultdict(list)
        for l in all:
            lt, src, dest, extra = l.split(',')
            if lt in skips:
                continue
            counts[src] += 1
            counts[dest] += 1

    p = r.pipeline()
    for k,v in counts.items():
        key = 'ARTIST:' + str(k)
        p.hset(key, 'link_count', v)
        p.zadd('CONNECTED-ARTISTS', v, int(k))
        print k,v
    p.execute()

def delete_path_cache():
    keys = r.keys("APC,*")
    print 'found', len(keys)
    p = r.pipeline()
    for key in keys:
        p.delete(key)
    print 'deleted', len(p.execute())


def go():
    if len(sys.argv) < 2:
        print '''
        usage python crawl.py
            --artist-to-artist-links
            --artist-to-recording-links
            --recording-with-multiple-artists
            --create-quick-artist-list
            --link-table
            --artists
            --index-artists
            --delete-search-index
        '''
    else:
        for arg in sys.argv[1:]:

            if arg == '--artist-to-artist-links':
                load_artist_to_artist_links()

            if arg == '--recordings-with-multiple-artists':
                load_recordings_with_multiple_artists()

            if arg == '--artist-to-recording-links':
                load_artist_to_recording_links()

            if arg == '--link-table':
                build_link_table()

            if arg == '--artists':
                process_artists()

            if arg == '--index-artists':
                index_all_artists()

            if arg == '--delete-search-index':
                delete_search_index()

            if arg == '--cleanup-links':
                cleanup_all_links()

            if arg == '--search':
                query = raw_input('artist name:')
                aids = artist_search(query)
                dump_artists(aids)

            if arg == '--links':
                query = raw_input('artist name:')
                aids = artist_search(query)
                dump_links(aids)

            if arg == '--create-quick-artist-list':
                create_quick_artist_list()

            if arg == '--create-all-artist-list':
                create_all_artist_list()

            if arg == '--add-connection-counts':
                add_connection_count_to_artists()
            if arg == '--delete-path-cache':
                delete_path_cache()
            if arg == '--walk':
                query = raw_input('artist name:')
                aids = artist_search(query)
                for aid in aids:
                    walk_artist(aid)

if __name__ == '__main__':
    go()
