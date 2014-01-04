import sys
import collections
import requests
import simplejson as json
import random

stats = collections.defaultdict(float)

host = "http://localhost:9922/6dobs/";
host = "http://ec2-54-227-6-186.compute-1.amazonaws.com/6dobs/"

def read_artists():
    f = open('artist_names.js')
    js = f.read()
    f.close()
    return json.loads(js)


def generate_path(which, src, dest, skips):
    #print which, src, '  ', dest
    if len(skips) > 0:
        skipstring = ','.join(skips)
        r = requests.get(host + 'path', params={'src':src, 'dest':dest, 'skips':skipstring, 'save':False });
    else:
        r = requests.get(host + 'path', params={'src':src, 'dest':dest, 'save':False});
    js = r.json()
    if 'path' in js and len(js['path']) > 0:
        stats['time'] += js['time']
        stats['count'] += 1
        print which, len(skips), int(stats['time'] / stats['count']), int(js['time']), js['path']['score'], len(js['path']['links']), src, ' -> ', dest
    else:
        print which, int(js['time']), 'empty path', src, ' -> ', dest
        stats['empty'] += 1

def most_central(which):
    #print which, src, '  ', dest
    r = requests.get(host + 'most_central_artists?count=10&_=1388585501508');
    js = r.json()
    print which, js['time']

    

def random_skips():
    if random.randint(0,9) < 5:
        return ['303', '938']
    else:
        return []

def generate_random_paths(artists, count):
    for i in xrange(count):
        src = random.choice(artists)
        dest = random.choice(artists)
        skips = random_skips()
        generate_path(i, src, dest, skips)

def generate_same_paths(artists, count):
    src = random.choice(artists)
    dest = random.choice(artists)
    for i in xrange(count):
        generate_path(i, src, dest)

def generate_most_central(count):
    for i in xrange(count):
        most_central(i)


if __name__ == '__main__':
    count = 100
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
    artists = read_artists()
    generate_random_paths(artists, count)
    #generate_same_paths(artists, count)
    #generate_most_central(count)


    

