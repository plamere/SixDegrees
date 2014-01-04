import redis

def delete_path_cache():
    r = redis.StrictRedis(host='localhost', port=6380, db = 1)
    keys = r.keys("APC,*")
    print 'found', len(keys)
    p = r.pipeline()
    for key in keys:
        p.delete(key)
    print 'deleted', len(p.execute())

if __name__ == '__main__':
    delete_path_cache()

