import socket
import sys
import time
from urlparse import urlparse

SCHEME_PORT_MAP = {'http': 80,
                   'https': 443}

def time_connect(url):
    """Return time in seconds to connect to socket of url,
    or very large number if error in connection"""

    parsed = urlparse(url)
    if parsed.port:
        port = parsed.port
    else:
        try:
            port = SCHEME_PORT_MAP[parsed.scheme]
        except IndexError:
            raise Exception('url must specify port')
    host = parsed.netloc.split(':')[0]

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    time_before = time.time()
    try:
        sock.connect((host, port))
    except:
        return sys.float_info.max
    result = time.time() - time_before
    sock.close()
    return result

def fastest(urls):
    """Return (time, url) tuple of shortest time for all urls"""
    return sorted([(time_connect(u), u) for u in urls])[0]
