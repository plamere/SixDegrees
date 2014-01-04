import time
import igraph as ig
import random

# some graph tests

# make a big graph

# G = ig.Graph.GRG(250000,.005)
G = ig.Graph.GRG(250000,.003)

eweights = [random.randint(1,21) for x in xrange(G.ecount())]


skip_set = set([20,30,40,50, 100])

for e in G.es:
    e['weight'] = random.randint(1,21)


def gen_random_path():
    start_node = random.randint(0, G.vcount()-1)
    end_node = random.randint(0, G.vcount()-1)

    ts = time.time()
    G.get_shortest_paths(start_node, end_node)
    delta_time = time.time() - ts
    return delta_time

def gen_random_weighted_path():
    start_node = random.randint(0, G.vcount()-1)
    end_node = random.randint(0, G.vcount()-1)

    ts = time.time()
    G.get_shortest_paths(start_node, end_node, eweights)
    delta_time = time.time() - ts
    return delta_time

def gen_random_weighted_path2():
    start_node = random.randint(0, G.vcount()-1)
    end_node = random.randint(0, G.vcount()-1)

    ts = time.time()
    G.get_shortest_paths(start_node, end_node, 'weight')
    delta_time = time.time() - ts
    return delta_time

def gen_random_weighted_path3():
    start_node = random.randint(0, G.vcount()-1)
    end_node = random.randint(0, G.vcount()-1)

    ts = time.time()
    seq = G.vs.select(lambda vertex : vertex.index not in skip_set)
    seq.get_shortest_paths(start_node, end_node, 'w')
    delta_time = time.time() - ts
    return delta_time


def filter_out(vs, weights):
    pairs = []
    for v in vs:
        ns = G.neighbors(v)
        for n in ns:
            pairs.append( (v,n) )
    eids = G.get_eids(pairs)
    for eid in eids:
        weights[eid] = 1000000
    #print 'pairs', pairs
    #print 'eids', eids

def get_random_skips():
    num_skips = random.randint(0, 100)
    skips = set()
    for n in xrange(num_skips):
        node = random.randint(0, G.vcount()-1)
        skips.add(node)
    return skips

def gen_random_weighted_path4():

    start_node = random.randint(0, G.vcount()-1)
    end_node = random.randint(0, G.vcount()-1)
    skips = get_random_skips()

    ts = time.time()
    if len(skips) > 0:
        cweights = list(eweights)
        filter_out(skip_set, cweights);
        G.get_shortest_paths(start_node, end_node, cweights)
    else:
        G.get_shortest_paths(start_node, end_node)
    delta_time = time.time() - ts
    return delta_time, len(skips)


def gen_random_paths(count):
    sum = 0

    for i in xrange(count):
        t = gen_random_path()
        sum += t
        print i, t

    print
    print 'avg', sum/count, 'seconds'

def gen_random_weighed_paths(count):
    sum = 0

    for i in xrange(count):
        t, skips = gen_random_weighted_path4()
        sum += t
        print i, t, skips

    print
    print 'avg', sum/count, 'seconds'


#gen_random_paths(1000)
ig.summary(G)
gen_random_weighed_paths(200)
ig.summary(G)
print 'is weigted', G.is_weighted()
