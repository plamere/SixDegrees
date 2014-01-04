import pyen
import simplejson as json
import db

en = pyen.Pyen()


start = 0
total = 5000
batch_size = 1000
page_size = 100
max_hotttnesss = 1

names = set()

db.init(quick=False)

while len(names) < total:
    print len(names), 'found, hotttnesss is', max_hotttnesss
    for start in xrange(0, batch_size, page_size):
        response = en.get('artist/search', start=start, sort="hotttnesss-desc", results=page_size, 
            max_hotttnesss = max_hotttnesss, bucket='hotttnesss')
        for a in response['artists']:
            name = a['name']
            results = db.artist_search(name)
            if len(results) > 0:
                names.add(name)
                print len(names), name
            else:
                print "           not found", name
            last_hotttnesss = a['hotttnesss']
    max_hotttnesss = last_hotttnesss


lnames = list(names)
lnames.sort()

out = open('artist_names.js', 'w')
print >>out, json.dumps(lnames)
out.close()
