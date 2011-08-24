import os.path
import unittest

from parse_requirements import *

_django_blog_requirements = """
Django>=1.2.5
South==0.7.3
django-activitysync==0.2.2
django-debug-toolbar==0.8.4
django-disqus==0.3.4
django-memcache-status==1.0.1
django-tagging==0.3.1
django-xmlrpc==0.1.2
feedparser==4.1
httplib2==0.6.0
oauth2==1.2.0
python-memcached==1.47
python-twitter>=0.8.1
simplejson==2.1.2
wsgiref==0.1.2
yolk==0.4.1
docutils==0.6
Pygments==1.3.1
foo>1.0
bar>0.1
"""

_parsed_django_blog_requirements = [
    ('Django', '>=', '1.2.5'), ('South', '==', '0.7.3'), ('django-activitysync', '==', '0.2.2'),
    ('django-debug-toolbar', '==', '0.8.4'), ('django-disqus', '==', '0.3.4'), ('django-memcache-status', '==', '1.0.1'),
    ('django-tagging', '==', '0.3.1'), ('django-xmlrpc', '==', '0.1.2'), ('feedparser', '==', '4.1'), ('httplib2', '==', '0.6.0'),
    ('oauth2', '==', '1.2.0'), ('python-memcached', '==', '1.47'), ('python-twitter', '>=', '0.8.1'),
    ('simplejson', '==', '2.1.2'), ('wsgiref', '==', '0.1.2'), ('yolk', '==', '0.4.1'), ('docutils', '==', '0.6'),
    ('Pygments', '==', '1.3.1'),
    ('foo', '>', '1.0'),
    ('bar', '>', '0.1')
]

_package_cache_files = [
    'Pygments-1.3.1.tar.gz',
    'Pygments-1.3.tar.gz',
    'Django-1.2.5.tar.gz',
    'Django-1.2.6.zip',
    'python-twitter-0.8.0.tar.gz',
    'foo-1.0.tar.gz',
    'bar-0.2.tar.gz'
]

class TestParseRequirements(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        self.req_filename = os.path.join(self.temp_dir, "requirements.txt")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def _write_requirements_file(self, data):
        with open(self.req_filename, "w") as f:
            f.write(data)

    def _get_packages(self, parse_version_constraints=False):
        return parse(self.req_filename, parse_version_constraints=parse_version_constraints)

    def test_unconstrained_packages(self):
        self._write_requirements_file("Django\nSouth\n")
        pkgs = self._get_packages(parse_version_constraints=True)
        self.assertEqual(['Django', 'South'], pkgs)

    def test_basic_equality_constraints(self):
        self._write_requirements_file("Django==1.2\nSouth==0.78\n")
        pkgs = self._get_packages(parse_version_constraints=True)
        self.assertEqual([('Django', '==', '1.2'), ('South', '==', '0.78')], pkgs)

    def test_compare_versions(self):
        self.assertEqual(compare_versions("1.2", "1.2"), 0)
        self.assertEqual(compare_versions("1.2.5", "1.2"), 1)
        self.assertEqual(compare_versions("1.2", "1.2.5"), -1)
        self.assertEqual(compare_versions("1.1", "1.21"), -1)
        
    def test_django_blog_requirements_file(self):
        self._write_requirements_file(_django_blog_requirements)
        pkgs = self._get_packages(parse_version_constraints=True)
        self.assertEqual(_parsed_django_blog_requirements, pkgs)

    def test_find_matching_files(self):
        self._write_requirements_file(_django_blog_requirements)
        matches = get_local_files_matching_requirements(self.req_filename,
                                                        _package_cache_files)
        self.assertEqual(['Pygments-1.3.1.tar.gz', 'bar-0.2.tar.gz', 'Django-1.2.6.zip'],
                         matches)

if __name__ == '__main__':
    unittest.main()

