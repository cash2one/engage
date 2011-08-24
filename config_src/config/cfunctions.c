#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <assert.h>

#include <caml/mlvalues.h>
#include <caml/callback.h>
#include <caml/alloc.h>
#include <caml/memory.h>

#include "cfunctions.h"

// severities
#define SEV_DEBUG 10
#define SEV_ERROR 40

static void log_api_call(int, char *);

int config_init (char *rdeffname, char *rinstfname, char **errorstr) {
  CAMLparam0();
  CAMLlocal2(ret,ex);
  int retval = STATUS_OK;

  static value *caml_init = NULL;
  if (caml_init == NULL) caml_init = caml_named_value("config_init");
  log_api_call(SEV_DEBUG, "entering CAML config_init. Params are:");
  log_api_call(SEV_DEBUG, rdeffname);
  log_api_call(SEV_DEBUG, rinstfname);
  ret = caml_callback2_exn(*caml_init,
                           caml_copy_string(rdeffname),
                           caml_copy_string(rinstfname));
  if (Is_exception_result(ret)) {
    ex = Extract_exception(ret);
    if (Field(ex,0) == *caml_named_value("config_user_error")) {
      printf("User exception raised"); fflush (stdout);
      printf("\n%s\n", (String_val(Field(ex,1))));
      *errorstr = String_val(Field(ex,1));
    } else if (Field(ex,0) == *caml_named_value("config_sys_error")) {
      printf("System exception raised"); fflush (stdout);
      printf("\n%s\n", (String_val(Field(ex,1))));
      *errorstr = String_val(Field(ex,1));
    } else {
      
      printf("Unknown Exception raised in caml_init: %s\n",
             (char*)caml_format_exception(ex));
      *errorstr = (char*)caml_format_exception(ex);
    }
    fflush (stdout);
    retval = STATUS_ERROR;
  }
  log_api_call(SEV_DEBUG, "returning from config_init");
  CAMLreturn(retval);
}

int config_has_next() {
  CAMLparam0();
  CAMLlocal1(ret);

  static value *caml_has_next = NULL;
  if (caml_has_next == NULL) caml_has_next = caml_named_value("config_has_next");

  ret = caml_callback(*caml_has_next, Val_unit);
  CAMLreturn(Bool_val(ret));
}

int config_has_prev() {
  CAMLparam0();
  CAMLlocal1(ret);

  static value *caml_has_prev = NULL;
  if (caml_has_prev == NULL) caml_has_prev = caml_named_value("config_has_prev");

  ret = caml_callback(*caml_has_prev, Val_unit);
  CAMLreturn(Bool_val(ret));
}

int config_next() {
  CAMLparam0();
  CAMLlocal1(ret);

  static value *caml_next = NULL;
  if (caml_next == NULL) caml_next = caml_named_value("config_next");

  ret = caml_callback(*caml_next, Val_unit);
  CAMLreturn(Bool_val(ret));
}

int config_prev() {
  CAMLparam0();
  CAMLlocal1(ret);

  static value *caml_prev = NULL;
  if (caml_prev == NULL) caml_prev = caml_named_value("config_prev");

  ret = caml_callback(*caml_prev, Val_unit);
  CAMLreturn(Bool_val(ret));
}

void config_reinit() {
  CAMLparam0();
  CAMLlocal1(ret);

  static value *caml_reinit = NULL;
  if (caml_reinit == NULL) caml_reinit = caml_named_value("config_reinit");

  caml_callback(*caml_reinit, Val_unit);
  CAMLreturn0;
}

char * config_get_config_port_types_as_string (char **errorstr) {
  CAMLparam0();
  CAMLlocal2(ret, ex);

  char *sv;
  static value *caml_get_config_port_types = NULL;
  if (caml_get_config_port_types == NULL) caml_get_config_port_types  = caml_named_value("config_get_config_port_types");
  log_api_call(SEV_DEBUG, "calling OCAML get_config_port_types_as_string");
  ret = caml_callback_exn(*caml_get_config_port_types, Val_unit);
  if (Is_exception_result(ret)) {
    ex = Extract_exception(ret);
    if (Field(ex,0) == *caml_named_value("config_user_error")) {
      log_api_call(SEV_ERROR, "User exception raised in get_config_port_types_as_string:");
      log_api_call(SEV_ERROR, (String_val(Field(ex,1))));
      *errorstr = String_val(Field(ex,1));
    } else if (Field(ex,0) == *caml_named_value("config_sys_error")) {
      log_api_call(SEV_ERROR, "System exception raised in get_config_port_types_as_string:");
      log_api_call(SEV_ERROR, (char*)(String_val(Field(ex,1))));
        *errorstr = String_val(Field(ex,1));
    } else {
      log_api_call(SEV_ERROR,
                   "Unknown Exception raised in get_config_port_types_as_string");
      log_api_call(SEV_ERROR, (char*)caml_format_exception(ex));
      *errorstr = (char*)caml_format_exception(ex);
    }
    sv = (char *)0;
  }
  else {
    sv = (char *)String_val(ret);
    log_api_call(SEV_DEBUG, "get_config_port_types_as_string returns");
  }
  CAMLreturn(sv);
}

char * config_get_config_ports_as_string (char **errorstr) {
  CAMLparam0();
  CAMLlocal2(ret, ex);

  char *sv;
  static value *caml_get_config_ports = NULL;
  if (caml_get_config_ports == NULL) caml_get_config_ports  = caml_named_value("config_get_config_ports");
  log_api_call(SEV_DEBUG, "calling OCAML get_config_ports_as_string");
  ret = caml_callback_exn(*caml_get_config_ports, Val_unit);
  if (Is_exception_result(ret)) {
    ex = Extract_exception(ret);
    if (Field(ex,0) == *caml_named_value("config_user_error")) {
      log_api_call(SEV_ERROR, "User exception raised in get_config_ports_as_string:");
      log_api_call(SEV_ERROR, (String_val(Field(ex,1))));
      *errorstr = String_val(Field(ex,1));
    } else if (Field(ex,0) == *caml_named_value("config_sys_error")) {
      log_api_call(SEV_ERROR, "System exception raised in get_config_ports_as_string:");
      log_api_call(SEV_ERROR, (char*)(String_val(Field(ex,1))));
        *errorstr = String_val(Field(ex,1));
    } else {
      log_api_call(SEV_ERROR,
                   "Unknown Exception raised in get_config_ports_as_string");
      log_api_call(SEV_ERROR, (char*)caml_format_exception(ex));
      *errorstr = (char*)caml_format_exception(ex);
    }
    sv = (char *)0;
  }
  else {
    sv = (char *)String_val(ret);
    log_api_call(SEV_DEBUG, "get_config_ports_as_string returns");
  }
  CAMLreturn(sv);
}

void config_set_config_ports_from_string (char *cp) {
  CAMLparam0();

  static value *caml_set_config_ports = NULL;
  if (caml_set_config_ports == NULL) caml_set_config_ports  = caml_named_value("config_set_config_ports");
  log_api_call(SEV_DEBUG, "calling OCAML set_config_ports_from_string");
  caml_callback(*caml_set_config_ports, caml_copy_string(cp));
  log_api_call(SEV_DEBUG, "returned from set_config_ports_from_string");
  CAMLreturn0;
}

void config_set_ports(char *key, char *id) {
  CAMLparam0();
  static value *caml_set_ports = NULL;
  if (caml_set_ports == NULL) caml_set_ports = caml_named_value("config_set_ports");

  caml_callback2(*caml_set_ports, caml_copy_string(key), caml_copy_string(id));
  CAMLreturn0;
}
void config_set_ports_of_current() {
  CAMLparam0();
  static value *caml_set_ports = NULL;
  if (caml_set_ports == NULL) caml_set_ports = caml_named_value("config_set_ports_of_current");

  log_api_call(SEV_DEBUG, "calling OCAML set_ports");
  caml_callback(*caml_set_ports, Val_unit);
  log_api_call(SEV_DEBUG, "returned from set_ports");
  CAMLreturn0;
}

char *config_get_current_resource() {
  CAMLparam0();
  CAMLlocal1(ret);
  char *res_str;
  static value *caml_get_current_resource = NULL;
  if (caml_get_current_resource == NULL) caml_get_current_resource = caml_named_value("config_get_current_resource");

  ret = caml_callback(*caml_get_current_resource, Val_unit);
  res_str = strdup(String_val(ret));
  CAMLreturn(res_str);

}
char *config_get_resource(char *key, char *id) {
  CAMLparam0();
  CAMLlocal1(ret);
  char *res_str;
  static value *caml_get_resource = NULL;
  if (caml_get_resource == NULL) caml_get_resource = caml_named_value("config_get_resource");

  ret = caml_callback2(*caml_get_resource, caml_copy_string(key), caml_copy_string(id));
  res_str = strdup(String_val(ret));
  CAMLreturn(res_str);
}

int config_write_install_file(char *fname, char **errorstr) {
  CAMLparam0();
  CAMLlocal2(ret,ex);
  int retval = STATUS_OK;

  static value *caml_write_install_file = NULL;
  if (caml_write_install_file == NULL) {
    caml_write_install_file = caml_named_value("config_write_install_file");
    assert(caml_write_install_file != NULL);
  }
  log_api_call(SEV_DEBUG, "calling OCAML write_install_file");
  ret = caml_callback_exn(*caml_write_install_file, caml_copy_string(fname));
  if (Is_exception_result(ret)) {
    ex = Extract_exception(ret);
    if (Field(ex,0) == *caml_named_value("config_sys_error")) {
      *errorstr = String_val(Field(ex,1));
    } else {
      printf("Unknown Exception raised in caml_init: %s\n",
             (char*)caml_format_exception(ex));
      *errorstr = (char*)caml_format_exception(ex);
    }
    retval = STATUS_ERROR;
  }
  log_api_call(SEV_DEBUG, "Returning from write_install_file");
  CAMLreturn(retval);
}

static void (*logger_fn)(char *, char *, int, char *) = NULL;

void register_logger(void (*logger)(char *, char *, int, char *)) {
  logger_fn = logger;
}

/* Call the logging callback directly, without ocaml wrappers. This is only for
 * logging the functions in this file.
 */
static void log_api_call(int severity, char *msg) {
  if (NULL != logger_fn) {
    (logger_fn)("Config", "CAPI", severity, msg);
  }
  else {
    printf("[Config][CAPI][%d] %s\n", severity, msg);
    fflush(stdout);
  }
}

/* Ocaml wrapper around logging callback
 */
void c_system_logger(value _area, value _subarea, value _severity, value _msg) {
  CAMLparam3(_area,_subarea,_msg);
  char *area = String_val(_area);
  char *subarea = String_val(_subarea); 
  int severity = Int_val(_severity);
  char *msg = String_val(_msg);

  // Call Jeff's UI Error logger
  if (NULL != logger_fn) {
    (logger_fn)(area, subarea, severity, msg);
  }
  else {
    printf("[%s][%s][%d] %s\n", area, subarea, severity, msg);
  }
  CAMLreturn0;
}

void c_system_print_string(value _msg) {
  CAMLparam1(_msg);
  char *msg = String_val(_msg);
  printf("%s", msg);
  CAMLreturn0;
}
void c_system_print_endline(value _msg) {
  CAMLparam1(_msg);
  char *msg = String_val(_msg);
  printf("%s\n", msg);
  CAMLreturn0;
}
void c_system_print_newline() {
  CAMLparam0();
  printf("\n");
  CAMLreturn0;
}
