
open Camlmsat

let verbose = true (* set to true to get debugging output *)

let debug msg = if verbose then print_endline msg else ()

let model_to_str (model:bool array) :string =
  let (str, idx) =
    Array.fold_left
      (fun (str,idx) element ->
	if str="" then ("[| v" ^ (string_of_int idx) ^ "=" ^
			   (string_of_bool element), idx+1)
	else (str ^ ", v" ^ (string_of_int idx)^ "=" ^
		 (string_of_bool element), idx+1))
      ("",0) model
  in str ^ " |]"

let clause_to_str (clause:int array) :string =
  let vartostr vno =
    if vno < 0 then "^v" ^ (string_of_int (-vno))
    else "v" ^ (string_of_int vno)
  in
    Array.fold_left
      (fun str element ->
	if str="" then (vartostr element)
	else str ^ " \\/ " ^ (vartostr element))
      "" clause

exception Test_failure of string

let run_testcase (name:string) (clauses:(int array) list) (satisfiable:bool) =
  print_endline ("Running test " ^ name);
  let solver = create_solver () in
   begin
     debug " got solver";
     List.iter
       (fun clause ->
	 debug (" Adding clause " ^ (clause_to_str clause));
	 let res = add_clause solver clause in ())
       clauses;
     debug " solving...";
     let res = solve solver in
       match (satisfiable, res) with
	   (true, true) ->
	     print_endline " Satisfiable";
	   let model = get_model solver in
	     print_endline (" Model: " ^ (model_to_str model))
	 | (false, false) ->
	     print_endline " Unsatsifiable"
	 | (true, false) ->
	     free_solver solver; debug " released solver";
	     raise (Test_failure
		       (name ^ ": expecting satisfiable, got unsatisfiable"))
	 | (false, true) ->
	     free_solver solver; debug " released solver";
	     raise (Test_failure
		       (name ^ ": expecting unsatisfiable, got satisfiable"))
       free_solver solver;
       debug " released solver"
   end

let test_deallocated_solver () =
  print_endline "Running test Deallocated_solver";
  let solver = create_solver () in
    debug " got solver";
    free_solver solver;
    debug " freed solver";
    let got_error =
      try ignore (add_clause solver [| 1; -1 |]); false
      with Invalid_argument s
	    -> debug ("Got expected except: " ^ s); true
    in
      if got_error = false then
	raise (Test_failure
		  "Dellocated_solver: did not get Invalid_argument error")
      else ()

let main () =
  print_endline "Starting Test_stubs";
  run_testcase "Simple_sat" [ [| 1; -1;|]; [| 2; |]; ] true;
  run_testcase "Simple_unsat" [ [| 1 |]; [| -1; |]; ] false;
  test_deallocated_solver ();
  print_endline "Test_stubs: all tests successful."
;;

main ();;
