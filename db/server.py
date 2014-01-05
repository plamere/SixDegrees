import cherrypy
from cherrypy import tools
#import db2 as db
import db
import webtools
import time
import sys
import util
import gc
from pprint import pprint
import simplejson as json


class SixDegrees(object):
    paths = 0
    
    @cherrypy.expose
    def index(self):
        raise cherrypy.HTTPRedirect("index.html")

    @cherrypy.expose
    @tools.json_out()
    def path(self, src=None, dest=None, src_id=None, dest_id=None, skips=None, save='True', _=None):
        log_api_call('path')

        results = get_results()

        if src_id:
            a1 = aget(src_id)
            src = ''
        else:
            a1 = asearch(src)

        save = save.lower() == 'true'

        if not a1:
            return seal_results(results, 'ERROR', "can't find " + src)

        if dest_id:
            a2 = aget(dest_id)
            dest = ''
        else:
            a2 = asearch(dest)

        if not a2:
            return seal_results(results, 'ERROR', "can't find " + dest)

        skipset = None
        if skips:
            try:
                skipset = set([sid for sid in skips.split(',')])
                results['skips'] = db.artist_get(list(skipset))
            except ValueError:
                return seal_results(results, 'ERROR', "bad skiplist " + skips)
        else:
            results['skips'] = []

        results['src'] = a1
        results['dest'] = a2
        path = db.artist_path(a1['id'], a2['id'], skipset=skipset, save=save)
        results['path'] = path
        gc.collect(0)
        self.paths += 1

        if self.paths % 100 == 0:
            gc.collect()
            util.summary_memory_usage()
            util.gc_info()
            print
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def neighbors(self, src=None, src_id=None, _=None):
        log_api_call('neighbors')

        results = get_results()

        if src_id:
            a1 = aget(src_id)
        else:
            a1 = asearch(src)
        if not a1:
            return seal_results(results, 'ERROR', "can't find source artist")

        results['src'] = a1
        path = db.artist_neighbors(a1['id'])
        results['neighbors'] = path
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def search(self, query=None, _=None):
        log_api_call('search')
        results = get_results()
        artists = db.artist_search(query)
        results['artists'] = artists
        results['query'] = query
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def popular_paths(self, start='0', count='20', _=None):
        log_api_call('popular_paths')

        results = get_results()

        try:
            start = int(start)
            count = int(count)
            frequent_paths = db.get_most_frequent_paths(start, count)
            results['paths'] = frequent_paths
        except ValueError:
            return seal_results(results, 'ERROR', "bad value for start or count")
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def longest_paths(self, start='0', count='20', _=None):
        log_api_call('longest_paths')

        results = get_results()

        try:
            start = int(start)
            count = int(count)
            frequent_paths = db.get_longest_paths(start, count)
            results['paths'] = frequent_paths
        except ValueError:
            return seal_results(results, 'ERROR', "bad value for start or count")
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def top_connected_artists(self, count='200', _=None):
        log_api_call('top_connected_artists')
        results = get_results()

        try:
            count = int(count)
            artists = db.most_connected_artists(count)
            results['top_connected_artists'] = artists
        except ValueError:
            return seal_results(results, 'ERROR', "bad value for count")
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def most_central_artists(self, count='200', _=None):
        log_api_call('most_central_artists')
        results = get_results()

        try:
            count = int(count)
            artists = db.most_central_artists(count)
            results['most_central_artists'] = artists
        except ValueError:
            return seal_results(results, 'ERROR', "bad value for count")
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def top_starting_artists(self, count='200', _=None):
        log_api_call('top_starting_artists')
        results = get_results()

        try:
            count = int(count)
            artists = db.top_starting_artists(count)
            results['top_starting_artists'] = artists
        except ValueError:
            return seal_results(results, 'ERROR', "bad value for count")
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def top_ending_artists(self, count='200', _=None):
        log_api_call('top_ending_artists')
        results = get_results()

        try:
            count = int(count)
            artists = db.top_ending_artists(count)
            results['top_ending_artists'] = artists
        except ValueError:
            return seal_results(results, 'ERROR', "bad value for count")
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def most_bypassed_artists(self, count='200', _=None):
        log_api_call('most_bypassed_artists')
        results = get_results()

        try:
            count = int(count)
            artists = db.most_bypassed_artists(count)
            results['most_bypassed_artists'] = artists
        except ValueError:
            return seal_results(results, 'ERROR', "bad value for count")
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def stats(self, _=None):
        log_api_call('stats')
        results = get_results()
        stats = {
            'db_stats' : db.stats(),
            'api_stats' : get_api_call_stats()
        }
        results['stats'] = stats
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def report_video(self, video_id='', src='', dest='', q='', _=None):
        log_api_call('report_video')
        db.report_video(video_id, src, dest, q)
        results = get_results()
        return seal_results(results)

    @cherrypy.expose
    @tools.json_out()
    def reported_videos(self, start='0', count='10',  _=None):
        log_api_call('report_video')
        results = get_results()
        try:
            start = int(start)
            count = int(count)
            results['reported_videos'] = db.get_video_reports(start, count)
        except ValueError:
            return seal_results(results, 'ERROR', "bad value for start or count")
        return seal_results(results)


def asearch(q):
    if len(q) > 0:
        aids = db.artist_search(q)
        if len(aids) > 0:
            return aids[0]
    return None

def aget(said):
    try:
        aid = int(said)
        results = db.artist_get([aid])
        return results[0]
    except ValueError:
        return None

def get_results():
    results = {'status' : 'OK', 'time' : time.time()}
    return results

def seal_results(results, status='OK', message = 'OK'):
    results['status'] = status
    results['time'] = 1000.0 * (time.time() - results['time'])
    results['message'] = message
    return results
    
def CORS():
    cherrypy.response.headers["Access-Control-Allow-Origin"] = "*" 

def error_page_404(status, message, traceback, version):
    cherrypy.response.headers['Content-Type']= 'application/json'
    cherrypy.response.headers["Access-Control-Allow-Origin"] = "*" 

    results = get_results()
    seal_results(results, 404, message)
    return json.dumps(results)


def log_api_call(method):
    p = db.r.pipeline()
    p.hincrby('api_stats', method, 1)
    p.hincrby('api_stats', 'total_calls', 1)
    p.execute()


def get_api_call_stats():
    return db.r.hgetall('api_stats')

if __name__ == '__main__':
    cherrypy.tools.CORS = cherrypy.Tool('before_handler', CORS)
    root = SixDegrees()

    config = {
        'global' : {
            'server.socket_host' : '0.0.0.0',
            'server.socket_port' : 9922,
            'server.thread_pool' : 10,
            # 'environment' : 'production',
        },
        '/' : {
            'tools.CORS.on' : True,
            'error_page.404': error_page_404,
        }
    }

    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        db.init(quick=True)
    else:
        #config['global']['environment'] = 'production'
        db.init(quick=False)

    #gc.set_debug(gc.DEBUG_STATS | gc.DEBUG_COLLECTABLE)
    gc.collect()
    gc.disable()
    gc.set_threshold(10000)
    util.summary_memory_usage()

    static_doc_config = webtools.get_export_map_for_directory("static")
    config.update(static_doc_config)
    cherrypy.quickstart(root, '/6dobs', config=config)


