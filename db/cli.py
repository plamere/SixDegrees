import cmd
import os
import db
import time
import sys
import traceback
import collections
from pprint import pprint

class CLI(cmd.Cmd):
    prompt = "6dobs% "
    max_links_to_show = 4

    skipset = set()

    def do_EOF(self, line):
        ''' shuts it all down '''
        print "Goodbye!"
        return True

    def emptyline(self):
        pass


    def print_link(self, i, link):
        if 'song' in link:
            print "%d) %s %s %s %s" % (i, link['src_name'], link['type_name'], link['song'], link['dest_name'])
        else:
            print "%d) %s %s %s" % (i, link['src_name'], link['type_name'], link['dest_name'])


    def print_links(self, links):
        for i,link in enumerate(links):
            self.print_link(i, link)


    def print_step(self, i, step, max_links = 4):
        print "%d) %s(%s) ==> %s(%s)  (%d links) score:%d" % \
            (i, step['src_name'], step['src'], step['dest_name'], step['dest'], len(step['links']), step['score'])
        for link in step['links'][:max_links]:
            if 'song' in link:
                print "    %s %s" % (link['type_name'], link['song'])
            else:
                print "   %s " % (link['type_name'])


    def print_path(self, path, max_links = 4):
        print 'score: %d, length:%d' % (path['score'], len(path['links']))
        for i,step in enumerate(path['links']):
            self.print_step(i, step, max_links)


    def asearch(self, name):
        aids = db.artist_search(name)
        if len(aids) > 0:
            return aids[0]['id']
        else:
            print "no match for", name
            return None
        
    def do_artist(self, line):
        ''' searches for artists '''

        artists = db.artist_search(line)
        for artist in artists:
            print "%s %s" % (artist['id'], artist['name'])

    def do_path(self, line):
        ''' finds path between two artists'''

        start_name, end_name = line.split(',')
        aid_start = self.asearch(start_name)
        aid_end = self.asearch(end_name)

        if aid_start and aid_end:
            path = db.artist_path(aid_start, aid_end, skipset=self.skipset)
            if path:
                self.print_path(path)
            else:
                print "no path between", db.artist_name(aid_start), db.artist_name(aid_end)


    def do_skips(self, line):
        ''' add artists to the skip set, or show the skip set '''

        if len(line) > 0:
            names = line.split(',')
            for name in names:
                aid = self.asearch(name)
                self.skipset.add(aid)
        else:
            for aid in self.skipset:
                print aid, db.artist_name(aid)

    def do_clear_skips(self, line):
        ''' clears the skip set '''
        self.skipset.clear()

    def do_npath(self, line):
        ''' finds no-weighted path between two artists'''

        start_name, end_name = line.split(',')
        aid_start = self.asearch(start_name)
        aid_end = self.asearch(end_name)

        if aid_start and aid_end:
            path = db.artist_path(aid_start, aid_end, weighted=False, skipset=self.skipset)
            if path:
                self.print_path(path)
            else:
                print "no path between", db.artist_name(aid_start), db.artist_name(aid_end)

    def do_neighbors(self, line):
        ''' finds the neighbors of an artist'''

        aid = self.asearch(line)
        if aid:
            path = db.artist_neighbors(aid)
            if path:
                self.print_path(path)
            else:
                print "no neighbors for", db.artist_name(aid)

    def do_remove_path(self, line):
        ''' removes path between two adjacent artists'''

        start_name, end_name = line.split(',')
        aid_start = self.asearch(start_name)
        aid_end = self.asearch(end_name)
        if aid_start and aid_end:
            db.remove_edge(aid_start, aid_end)

    def do_path2(self, line):
        ''' finds path between two artists'''

        start_name, end_name = line.split(',')
        aid_start = self.asearch(start_name)
        aid_end = self.asearch(end_name)

        if aid_start and aid_end:
            path = db.artist_path2(aid_start, aid_end)
            self.print_path(path)

    def do_astats(self, line):
        ''' report connectivity stats for artist '''
        aid = self.asearch(line)
        if aid:
            db.stats(aid)

    def do_links(self, line):
        ''' shows links for an artist '''
        aid = self.asearch(line)
        if aid:
            links = db.artist_links(aid)
            self.print_links(links)



    def do_find_popular_crossroads(self, line):
        ''' creates random paths and find the most common
            crossroads
        '''

        nodes = collections.defaultdict(int)
        count = 100
        if len(line) > 0:
            count = int(line)

        paths = 0
        no_path = 0
        sum_time = 0
        sum_length = 0
        sum_score = 0
        max_length = 0
        max_time = 0
        max_score = 0
        avg_score = 0

        for i in xrange(count):
            aid1 = db.artist_random()
            aid2 = db.artist_random()

            start = time.time()
            score, aids = db.artist_raw_path(aid1, aid2, skipset=self.skipset)
            delta = time.time() - start

            if aids:
                for aid in aids:
                    nodes[aid] += 1
                paths += 1.0
                lpath = len(aids)
                sum_score += score
                if score > max_score:
                    max_score = score
                sum_length += lpath
                sum_time += delta
                if lpath > max_length:
                    max_length = lpath
                if delta > max_time:
                    max_time = delta
            else:
                print "no path between", aid1, db.artist_name(aid1), aid2, db.artist_name(aid2)
                no_path += 1

        nlist = [ (v,k) for k,v in nodes.items()]
        nlist.sort(reverse=True)
        print
        for count, aid in nlist[:40]:
            print count, aid, db.artist_name(aid)

        print
        print 'paths:', paths
        print 'no paths:', no_path
        if paths > 0:
            avg_time =  sum_time / paths
            avg_length =  sum_length / paths
            avg_score =  sum_score / paths
            print 'avg length:', avg_length
            print 'avg time:', avg_time
            print 'avg score:', avg_score
            print 'max length:', max_length
            print 'max time:', max_time
            print 'max score:', max_score

    def do_expand_neighbors(self, line):
        ''' expand the neighborhood of an artist '''

        fields = line.split(',')
        if len(fields) > 0:
            aid = self.asearch(fields[0])
            if aid:
                if len(fields) > 1:
                    radius = int(fields[1])
                else:
                    radius = 3

                queue = []
                queue.append( (0, aid) )
                which = 0
                visited = set()

                while len(queue) > 0:
                    lvl, aid = queue.pop(0)
                    if aid not in visited and lvl < radius:
                        visited.add(aid)
                        which += 1
                        print which, lvl, aid, db.artist_name(aid)
                        aids = db.artist_raw_neighbors(aid)
                        for naid in aids:
                            queue.append( (lvl+1, naid) )

    def do_random_path(self, line):
        ''' picks two artists at random and finds a path between them'''

        count = 1
        if len(line) > 0:
            count = int(line)

        paths = 0
        no_path = 0
        sum_time = 0
        sum_length = 0
        max_length = 0
        max_time = 0

        for i in xrange(count):
            aid1 = db.artist_random()
            aid2 = db.artist_random()
            print "random path between", aid1, db.artist_name(aid1), 'and', aid2, db.artist_name(aid2)
            start = time.time()
            path = db.artist_path(aid1, aid2, skipset=self.skipset)
            delta = time.time() - start
            if path:
                self.print_path(path, 0)
                paths += 1.0
                lpath = len(path['links'])
                sum_length += lpath
                sum_time += delta
                if lpath > max_length:
                    max_length = lpath
                if delta > max_time:
                    max_time = delta
            else:
                print "no path between", aid1, db.artist_name(aid1), aid2, db.artist_name(aid2)
                no_path += 1
            print

        print 'paths:', paths
        print 'no paths:', no_path
        if paths > 0:
            avg_time =  sum_time / paths
            avg_length =  sum_length / paths
            print 'avg length:', avg_length
            print 'avg time:', avg_time
            print 'max length:', max_length
            print 'max time:', max_time


if __name__ == '__main__':
    quick = len(sys.argv) > 1 and sys.argv[1] == '--quick'
    cli = CLI()
    db.init(quick=quick)

    while True:
        try:
            cli.cmdloop()
            break
        except:
            print "Error:", sys.exc_info()[0]
            print "Type:", sys.exc_info()[1]
            print 'Traceback:'
            traceback.print_tb(sys.exc_info()[2])


