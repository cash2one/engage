These are some basic tests for the configurator engine. You can run them via
make or just by executing runtests.sh directly. The configurator engine
must have been built already for these tests to work. The tests expect it at
../config/c_wrapper/configurator.

Each test has the following input files:
  testname_resources.json - resource definition file
  testname_instspec.json  - install spec
  testname.exp            - expected value for generated install.script

The resource and install spec files can have different names, if you are
reusing them for multiple tests.

If the test fails, it will leave the following output files:
  testname.log    - output from config engine
  testname.script - generated install.script file, which was compared to
                    testname.exp
  testname.dif    - differences between testname.exp and testname.script

Currently, the comparision of testname.exp and testname.script is done using
the diff utility. If this causes problems, we should look into doing a
JSON-aware diff.
