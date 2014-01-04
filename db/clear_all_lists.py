import redis

r = redis.StrictRedis(host='localhost', port=6380, db = 1)

all_lists = [ 'MOST-FREQUENT-PATHS', 'LONGEST-PATHS', 'MOST-CENTRAL-ARTISTS', 
        'MOST-BYPASSED-ARTISTS', 'STARTING-ARTISTS', 'ENDING-ARTISTS']


def delete_all_lists():
    for key in all_lists:
        r.delete(key)
        print 'deleted', key

if __name__ == '__main__':
    delete_all_lists()

