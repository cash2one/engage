from setuptools import setup, find_packages
from engage.version import VERSION

setup(
    name='engage',
    version=VERSION,
    author='genForma Corporation',
    author_email='code@genforma.com',
    url='http://github.com/genforma/engage',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    entry_points = {
        'console_scripts': [
            'svcctl = engage.engine.svcctl:main',
            'install = engage.engine.cmdline_install:call_from_console_script',
            'backup = engage.engine.backup:call_from_console_script',
            'deployer = engage.engine.deploy_spec:call_from_console_script',
            'create-distribution = engage.engine.create_distribution:call_from_console_script',
            'password_manager = engage.engine.password:main',
            ]},
    install_requires=[],
    license='Apache V2.0',
    description='Platform for automated deployment and upgrade of applications',
    long_description="description"
    )
