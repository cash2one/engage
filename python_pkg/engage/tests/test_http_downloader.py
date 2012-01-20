import os.path
import subprocess
import sys
import time
import unittest
import urllib

from engage.engine.library import randstr, HTTPDownloader, get_logger, get_test_logger

HTTP = {'host': 'localhost',
        'port': '5555',
        'deadport': '5556'}

THIS_FILE = os.path.basename(__file__)

class TestHTTPDownloader(unittest.TestCase):
    def setUp(self):
        """Replace regular get_logger() with temporary logger"""
        global tmp_logger, get_logger
        tmp_logger = get_logger
        get_logger = get_test_logger
        python = sys.executable
        os.chdir(os.path.dirname(__file__))
        self.httpserver = subprocess.Popen([python, '-m', 'SimpleHTTPServer', HTTP['port']])
        time.sleep(1)

    def tearDown(self):
        """Restore regular get_logger()"""
        global tmp_logger, get_logger
        get_logger = tmp_logger
        self.httpserver.terminate()
        self.httpserver.wait()

    def test_httpserver(self):
        f = urllib.urlopen('http://{host}:{port}/{path}'.format(path=THIS_FILE, **HTTP))
        assert f.info().getheader('content-length') > 0

    def test_not_available(self):
        bogus_filename = randstr()
        dl = HTTPDownloader(
            'http://{host}:{port}/%s'.format(**HTTP) % bogus_filename,
            bogus_filename)
        assert not dl.is_available()

    def test_download(self):
        target = 'httpdownloader-test-' + randstr()
        dl = HTTPDownloader('http://{host}:{port}/{path}'.format(path=THIS_FILE, **HTTP), target)
        assert dl.is_available()
        dl.download_to_cache()
        assert os.path.exists(target)
        os.remove(target)

    def test_mirrors(self):
        goodurl = 'http://{host}:{port}/{path}'.format(path=THIS_FILE, **HTTP)
        badurl = 'http://{host}:{deadport}/{path}'.format(path=randstr(), **HTTP)
        target = 'httpdownloader-test-' + randstr()
        dl = HTTPDownloader([badurl, goodurl], target)
        assert dl.location == goodurl
        assert dl.is_available()
        dl.download_to_cache()
        assert os.path.exists(target)
        os.remove(target)
