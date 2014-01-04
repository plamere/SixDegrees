import string
import re
import unicodedata
import gc
import os

def remove_punctuation_old_and_broke(some_string):
    return re.sub('[%s]' % re.escape(string.punctuation), " ", some_string)

def remove_punctuation(some_string):
    return re.sub(r'[\W+]+', ' ', some_string)

def remove_accents(some_string):
    some_string = unicode(some_string)
    return ''.join((c for c in unicodedata.normalize('NFD', some_string) if unicodedata.category(c) != 'Mn'))


_proc_status = '/proc/%d/status' % os.getpid()

_scale = {'kB': 1024.0, 'mB': 1024.0*1024.0,
          'KB': 1024.0, 'MB': 1024.0*1024.0}

def _VmB(VmKey):
    '''Private.
    '''
    global _proc_status, _scale
     # get pseudo file  /proc/<pid>/status
    try:
        t = open(_proc_status)
        v = t.read()
        t.close()
    except:
        return 0.0  # non-Linux?
     # get VmKey line e.g. 'VmRSS:  9999  kB\n ...'
    i = v.index(VmKey)
    v = v[i:].split(None, 3)  # whitespace
    if len(v) < 3:
        return 0.0  # invalid format?
     # convert Vm value to bytes
    return float(v[1]) * _scale[v[2]]


def memory(since=0.0):
    '''Return memory usage in bytes.
    '''
    return _VmB('VmSize:') - since


def resident(since=0.0):
    '''Return resident memory usage in bytes.
    '''
    return _VmB('VmRSS:') - since


def stacksize(since=0.0):
    '''Return stack size in bytes.
    '''
    return _VmB('VmStk:') - since

def summary_memory_usage():
    print 'mem: %d resident: %d  ss: %d' % ( memory() / 1024, resident() / 1024, stacksize()/1024)



def gc_info():
    print 'counts', gc.get_count()
    print 'thresh', gc.get_threshold()
