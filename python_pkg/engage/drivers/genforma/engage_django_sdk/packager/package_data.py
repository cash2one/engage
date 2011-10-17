"""Data and utilities about Django applications and packages (used for validation).
"""

from itertools import ifilter

from engage_django_components import additional_requirements

# These packages are always installed
PREINSTALLED_PACKAGES = ["django", "south"]

# This is a mapping from python packages (as used in requirements.txt)
# to lists of django app names provided by those packages.
KNOWN_PACKAGES_TO_APPS = {
    "django": [
      "django.contrib.admin",
      "django.contrib.admindocs",
      "django.contrib.auth",
      "django.contrib.comments",
      "django.contrib.contenttypes",
      "django.contrib.csrf",
      "django.contrib.databrowse",
      "django.contrib.flatpages",
      "django.contrib.formtools",
      "django.contrib.gis",
      "django.contrib.humanize",
      "django.contrib.localflavor",
      "django.contrib.markup",
      "django.contrib.messages",
      "django.contrib.redirects",
      "django.contrib.staticfiles",
      "django.contrib.sessions",
      "django.contrib.sitemaps",
      "django.contrib.sites",
      "django.contrib.syndication",
      "django.contrib.webdesign"
    ],
    "django-cms": [
      'cms',
      'cms.plugins.text',
      'cms.plugins.picture',
      'cms.plugins.file',
      'cms.plugins.flash',
      'cms.plugins.link',
      'cms.plugins.snippet',
      'cms.plugins.googlemap',
      'cms.plugins.teaser',
      'cms.plugins.video',
      'cms.plugins.twitter',
      'cms.plugins.inherit',
      "menus"
    ],
    "django-mptt": ["mptt"],
    "django-appmedia": ['appmedia'],
    "django-sekizai": ['sekizai'],
    "django-extensions":['django_extensions'],
    "django-disqus": ['disqus'],
    "django-memcache-status": ['memcache_status'],
    "django-tagging": ['tagging'],
    "django-debug-toolbar":['debug_toolbar'],
    "django-activitysync":['activitysync'],
    "south": ['south']
}

def get_apps_for_packages(package_list):
    """Return a list of Django apps corresponding to the package list.
    Packages not in the list are ignored.
    """
    ll = [KNOWN_PACKAGES_TO_APPS[p] for p in ifilter(KNOWN_PACKAGES_TO_APPS.has_key, package_list)]
    return sum(ll, [])


def _get_apps_to_packages(packages_to_apps):
    m = {}
    def add_pkg(app, pkg):
        if m.has_key(app):
            l = m[app]
        else:
            l = []
        if pkg not in l:
            l.append(pkg)
            m[app] = l
    for package in packages_to_apps:
        for app in packages_to_apps[package]:
            add_pkg(app, package)
    return m

PACKAGES_FOR_KNOWN_APPS = _get_apps_to_packages(KNOWN_PACKAGES_TO_APPS)

# packages that aways cause problems.
problem_packages = set(["mysql-python",])


def validate_package_list(package_list, components, results):
    """Validate the package list, checking for packages known to cause
    problems and for those associated with components.
    """
    user_comp_set = set(components)
    # first, we compute the reverse of the additional requirements map
    packages_to_components = {}
    for comp in additional_requirements.keys():
        comp = comp.lower()
        for pkg in additional_requirements[comp]:
            pkg = pkg.lower()
            if packages_to_components.has_key(pkg):
                packages_to_components[pkg].append(comp)
            else:
                packages_to_components[pkg] = [comp,]

    # now, do the validations
    for package in package_list:
        lpackage = package.lower()
        if lpackage in problem_packages:
            results.error("Package %s is known to cause problems with Engage deployments. Please remove it from your requirements.txt file (or comment it out)."
                          % package)
        elif packages_to_components.has_key(lpackage):
            comps_for_pkg = packages_to_components[lpackage]
            if set(comps_for_pkg).isdisjoint(user_comp_set):
                if len(comps_for_pkg)==1:
                    results.warning("Package '%s' is required for Engage component '%s'. Do you want to enable that component?" %
                                    (package, comps_for_pkg[0]))
                else:
                    results.warning("Package '%s' is required for Engage components %s. Do you want to enable one of those components?" %
                                    (package, comps_for_pkg))
