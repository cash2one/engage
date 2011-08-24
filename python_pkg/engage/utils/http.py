
# utilities related to the http protocol

import httplib
import urllib2

def ping_webserver(hostname, port, logger=None):
    """Simple check that we can connect to the web server at the given
    hostname and port
    """
    try:
        conn = httplib.HTTPConnection(hostname, port)
        conn.connect()
    except Exception, msg:
        if logger:
            logger.debug("Attempt to connect to http://%s:%d failed: %s." %
                         (hostname, port, msg))
        return False
    conn.close()
    if logger:
        logger.debug("Attempt to connect to http://%s:%d successful." %
                     (hostname, port))
    return True


def check_url(hostname, port, request_path, logger, valid_response_codes=(httplib.OK, httplib.FOUND)):
    """Check that we can connect to the webserver and that it responds
    to a head request for the specified path. We only check for a response code in
    the tuple of valid codes. By default, we look for OK and FOUND (used for login redirects)."""
    try:
        conn = httplib.HTTPConnection(hostname, port)
        conn.connect()
    except Exception, msg:
        logger.debug("Attempt to connect to http://%s:%d failed: %s." %
                     (hostname, port, msg))
        return False
    result = False
    url = "http://%s:%d%s" % (hostname, port, request_path)
    try:
        conn.request("HEAD", request_path)
        response = conn.getresponse()
        if response.status in valid_response_codes:
            result = True
            logger.debug("Attempt to request %s successful." % url)
        else:
            logger.debug("Attempt to request %s failed, response code %d"
                         % (url, response.status))
    except:
        logger.debug("Attempt to request %s failed." % url)
    finally:
        conn.close()
        return result


def make_request_with_basic_authentication(uri, realm, user, password,
                                           auth_uri=None, tries=5):
    if auth_uri==None: auth_uri = uri
    auth_handler = urllib2.HTTPBasicAuthHandler()
    auth_handler.add_password(realm=realm,
                              uri=auth_uri,
                              user=user,
                              passwd=password)
    opener = urllib2.build_opener(auth_handler)
    current_try = 1
    # keep trying the connect. If we connect, break out of the loop.
    # If we get a non-timeout exception or exceeeded the try limit,
    # throw the exception
    while True:
        try:
            conn = opener.open(uri, timeout=10.0)
            break
        except urllib2.URLError, msg:
            if msg == "urlopen error timed out" and current_try < tries:
                logger.debug("make_request_with_basic_authentication: retrying due to timeout [try %d]"
                             % current_try)
                current_try = current_try + 1
            else:
                raise
    result = conn.read()
    conn.close()
    return result

