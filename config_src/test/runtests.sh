#!/bin/bash
# Run tests of the configurator. These tests run the configurator on
# specified input files and generate a .log file from the configurator's
# standard output. This .log file is then compared to a .exp file. If the
# two match, the test is successful. Otherwise, the number of failed tests
# is incremented and a .dif file generated containing the differences between
# the .exp and .log files.
#

# counts of successful and failed tests.
success=0
failed=0

# runTest is the main function to run a test. It
# takes as an argument the name of the test. Any remaining arguments are
# passed to the configurator.
runTest() {
  basetestname=$1
  testname=$1
  shift
  rm -f ${testname}.log ${testname}.dif ${testname}.script
  echo "--- [${testname}] $* ---"
  if $CONFIG_EXE $@ >${testname}.log 2>&1; then
    mv install.script ${testname}.script
    if diff -b ${basetestname}.exp ${testname}.script >${testname}.dif; then
      echo "  Test" ${testname} "successful."
      rm ${testname}.dif ${testname}.log ${testname}.script
      success=$[$success + 1 ]
    else
      echo "  Test" ${testname} "failed!"
      failed=$[$failed + 1 ]
    fi
  else # call to configurator failed
    echo "  Test" ${testname} "failed: configurator exited with error"
    failed=$[$failed + 1 ]
  fi
}

# runNegTest tests the configurator when we expect it to exit with an error.
runNegTest() {
  if [[ "$MODE" == "opt" ]]; then
    basetestname=$1
    testname=${basetestname}_opt
  else
    basetestname=$1
    testname=$1
  fi
  shift
  rm -f ${testname}.log ${testname}.dif ${testname}.script
  echo "--- [${testname}] (neg) $* ---"
  if $CONFIG_EXE $@ >${testname}.log 2>&1; then
    echo "  Test" ${testname} "failed: configurator expected to fail, but did not."
    failed=$[$failed + 1 ]
  else # call to configurator failed, as expected
    if diff -b ${basetestname}.exp ${testname}.log >${testname}.dif; then
      echo "  Test" ${testname} "successful."
      rm ${testname}.dif ${testname}.log
      success=$[$success + 1 ]
    else
      echo "  Test" ${testname} "failed!"
      failed=$[$failed + 1 ]
    fi
  fi
}

CONFIG_DIR=`cd ../config/c_wrapper; pwd`
CONFIG_EXE=$CONFIG_DIR/configurator
echo "==== Running configurator tests ===="


# check that the configurator actually exists and is executable
if ! [[ -a $CONFIG_EXE ]]; then
  echo "Configurator command '$CONFIG_EXE' does not exist."
  exit 1
fi
if ! [[ -x $CONFIG_EXE ]]; then
  echo "Configurator command '$CONFIG_EXE' not executable."
  exit 1
fi


# run the actual tests
#runTest parser1 test_parser.rdef test_inst_parser.json
runTest simple simple_resources.json simple_inst_spec.json
runTest openmrs openmrs_resources.json openmrs_inst_spec.json
runTest default_val_test default_val_test_res.json default_val_test_instspec.json
runTest django1 django_resources.json django1_instspec.json
runTest gfwebsite gfwebsite_resources.json gfwebsite_instspec.json


echo "Configurator tests complete: $success tests passed, $failed tests failed."
if [ $failed -gt 0 ]; then
    exit 1
else
    exit 0
fi


