#include <cstring>
#include <stdint.h>
#include <errno.h>

#include <signal.h>

#include <Solver.h>

extern "C" {
#include <caml/mlvalues.h>
#include <caml/alloc.h>
#include <caml/memory.h>
#include <caml/custom.h>
#include <caml/fail.h>
}


static struct custom_operations solver_ops = {
  (char*)"edu.ucla.cs.pow.minisat",
  custom_finalize_default,
  custom_compare_default,
  custom_hash_default,
  custom_serialize_default,
  custom_deserialize_default
};

/* Accessing the Solver * part of a Caml custom block */
#define Solver_val(v) (*((void **) Data_custom_val(v)))

extern "C" CAMLprim value create_solver(value unit) {
  CAMLparam1 (unit);
  void *ptr = (void*) (new Solver);
  if (ptr==(void*)0) caml_failwith((char*)"Unable to allocate solver");
  value v = caml_alloc_custom(&solver_ops, sizeof(void *), 0, 1);
  Solver_val(v) = ptr;
  CAMLreturn (v);
}

extern "C" CAMLprim value free_solver(value solver_wrapper) {
  CAMLparam1 (solver_wrapper);
  void *ptr = Solver_val(solver_wrapper);
  if (ptr==NULL) caml_invalid_argument((char*)"solver already deallocated");
  Solver *s = (Solver*)ptr;
  delete s;
  Solver_val(solver_wrapper) = (void*)0; // zero out to prevent reuse after del
  CAMLreturn (Val_unit);
}

extern "C" CAMLprim value add_clause(value solver_wrapper,
				     value int_array_block)
{
  CAMLparam2 (solver_wrapper, int_array_block);
  int i;
  void *ptr = Solver_val(solver_wrapper);
  if (ptr==NULL) caml_invalid_argument((char*)"solver already deallocated");
  unsigned int size = Wosize_val(int_array_block);
  Solver *s = (Solver*)ptr;
  //int *array_p = (int*)Op_val(int_array_block);
  //printf((char*)"Array of size %d\n", size);
  //for(i=0; i < size; i++) printf((char*)"%d ", Int_val(array_p[i]));
  //printf((char*)"\n");
  //for(i=0; i < size; i++) printf((char*)"%d ", Int_val(Field(int_array_block,i)));
  //printf((char*)"\n");
  //fflush(stdout);
  vec<Lit> lits(size);
  for (i = 0; i < size; i++) {
    int val = Int_val(Field(int_array_block,i)); // convert from ocaml int
    int var = abs(val) - 1; // the var number in minisat's 0-based scheme
    int maxVar = s->nVars() - 1;
    if (var>maxVar) { // declare more variables, if necessary
      for (int j = 0; j < (var-maxVar); j++) s->newVar();
    }
    Lit input = val < 0 ? ~Lit(var) : Lit(var);
    //printf((char*)"term %d: value: %d var: %d input to solver: %d\n",
    //	   i, val, var, toInt(input));
    lits.push(input);
  }
  bool ret = s->addClause(lits);
  if (ret) CAMLreturn (Val_true);
  else CAMLreturn (Val_false);
}

extern "C" CAMLprim value solve(value solver_wrapper) {
  CAMLparam1 (solver_wrapper);
  void *ptr = Solver_val(solver_wrapper);
  if (ptr==NULL) caml_invalid_argument((char*)"solver already deallocated");
  Solver *s = (Solver*)ptr;
  bool ret = s->okay();
  if (ret) ret = s->solve();
  if (ret) CAMLreturn (Val_true);
  else CAMLreturn (Val_false);
}

extern "C" CAMLprim value get_model(value solver_wrapper) {
  CAMLparam1 (solver_wrapper);
  void *ptr = Solver_val(solver_wrapper);
  if (ptr==NULL) caml_invalid_argument((char*)"solver already deallocated");
  Solver *s = (Solver*)ptr;
  int nVars = s->nVars();
  value array_block = caml_alloc(nVars, 0);
  int *int_array = (int*)Op_val(array_block);
  for (int i = 0; i < nVars; i++) {
    int intval = toInt(s->model[i]);
    Field(int_array,i) = intval>0 ? Val_true : Val_false;
    printf((char*)"model index: %d, value: %d ocamlval = %d\n",
           i, intval, Field(int_array,i) );
  }
  CAMLreturn (array_block);
}
