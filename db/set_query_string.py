import sys
import redis

r = redis.StrictRedis(host='localhost', port=6380, db = 1)

if __name__ == '__main__':
    aid = sys.argv[1]
    key = 'ARTIST:' + aid

    if len(sys.argv) > 2:
        query = sys.argv[2]
        print r.hset(key, 'query', query)
    print r.hgetall(key)

