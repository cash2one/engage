/*
 * Test driver for configurator c api.
 * Command line args: <resource definition file> <install spec file>
 */
#include "../cfunctions.h"

#include <caml/mlvalues.h>
#include <caml/callback.h>
#include <caml/alloc.h>
#include <caml/memory.h>

#include <stdio.h>

int main(int argc, char **argv) {
  int r;
  char * cfgports;
  char *errorstr;
  char *rdf, *isf;
  int debug = 0;
  caml_main(argv);
  if (argc==3) {
    rdf = argv[1];
    isf = argv[2];
    debug = 0;
  }
  else if (argc==4 && strcmp(argv[1], "--debug")==0) {
    rdf = argv[2];
    isf = argv[3];
    debug = 1;
  }
  else {
    printf("command line args: {--debug} <resource definition file> <install spec file>\n");
    exit(1);
  }
  if (debug) {printf("\n\n\n\n\nIn C Interface\n\n");}
  r = config_init(rdf, isf, &errorstr);

  if (r == STATUS_OK) {
    if (debug) {printf("NOW ITERATING FIRST TIME THROUGH PORTS\n");}
    while (config_has_next ()) {
      if (debug) {printf("[1]NEXT MODULE>>>\n");}
      config_next();
      cfgports = config_get_config_port_types_as_string(&errorstr);
      if (cfgports == (char*)0) {
        if (debug) {printf("config_get_config_ports_as_string() returns error: %s\n", errorstr);}
        exit(1);
      }
      if (debug) {printf("[1]GOT THE FOLLOWING config ports:: \n%s\n", cfgports);}
    }
    config_reinit ();
    if (debug) {printf("NOW ITERATING SECOND TIME THROUGH PORTS\n");}
    while (config_has_next ()) {
      if (debug) {printf("[2]NEXT MODULE>>>\n");}
      config_next();
      cfgports = config_get_config_ports_as_string(&errorstr);
      if (cfgports == (char*)0) {
        printf("[2]config_get_config_ports_as_string() returns error: %s\n", errorstr);
        exit(1);
      }
      if (debug) {printf("[2]GOT THE FOLLOWING config ports:: \n%s\n", cfgports);}
      config_set_config_ports_from_string(cfgports);
      if (debug) {printf("[2]SETTING PORTS OF CURRENT MODULE\n");}
      config_set_ports_of_current();
    }
    if (debug) {printf("NOW WRITING INSTALL FILE \n");}
    r = config_write_install_file("install.script", &errorstr);
    if (r == STATUS_ERROR) {
      printf("write_install_file returns error: %s\n", errorstr);
    }
  } else if (r == STATUS_ERROR) {
    printf("config returns error: %s\n", errorstr);
  }
  if (debug) {printf("r = %d\n", r);}
  return 0;
}
