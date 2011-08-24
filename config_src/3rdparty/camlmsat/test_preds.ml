(** Tests for the higher level predicate interface.
    The output of this program can be piped to the Simplify theorem prover.
    All the predicates should be valid. *)


open Predicates;;


let verbose = false (* set to true to get debugging output *)

let debug msg = 
  if verbose then print_endline (";; " ^ msg)

let message msg =
  print_endline (";; " ^ msg)

exception Test_failure of string

let test_counter = ref 1

let run_pred2cnf_test (predname:string) (p:predicate) =
  message ("Running pred2cnf test " ^ (string_of_int !test_counter) ^
	      ", input pred " ^ predname ^ " = " ^ (pred2str p));
  test_counter := !test_counter + 1;
  let p_cnf = pred2cnf p
  in
    debug (" output pred = " ^ (pred2str p_cnf));
    if not (is_in_cnf p_cnf) then raise (Test_failure "Result not in cnf!")

let (preds:predicate array) = [|
  Or [Atom "a"; Not (Atom "b")];

  And [Atom "a"; Not (Atom "b")];

  (And [Not (Atom "a"); Not (And [Atom "b"; Atom "c"]);]);

  Or [Atom "a"; (And [Atom "b"; Atom "c"]);];

  And [Atom "a"; (Or [Atom "b"; Atom "c"]);];

  Not (And [Atom "a"; (Or [Atom "b"; Atom "c"]);]);

  (* ^(^a/\^b) *)
  Not (And [Not (Atom "a"); Not (Atom "b")]);

  (* (^(^a/\^b))/\(^(^a/\^c)) *)
  And [(Not (And [Not (Atom "a"); Not (Atom "b")]));
       (Not (And [Not (Atom "a"); Not (Atom "c")]))];

  Not (Or [(And [Not (Atom "a"); Not (Atom "b")]);
                       And [Not (Atom "a"); Not (Atom "c")]]);

  And [Not (And [Not (Atom "a"); Not (Atom "b")]);
                  Not (And [Not (Atom "a"); Not (Atom "c")]);];

  Not (Or [Not (Atom "b"); Not (Atom "a")]);

  And [Not (Not (Atom "b")); Not (Not (Atom "a"));];

  And [Atom "a"; Not (Atom "a")]; (* unsatisfiable *)

  (* (^a/\b) /\ (^b \/ a) : unsatisfiable *)
  And [And [Not (Atom "a"); Atom "b";]; Or [Not (Atom "b"); Atom "a"];];


  (* test of Equiv *)
  Not (And [Equiv (Atom "l_1_oknr", And [Atom "BookFlight";
                               Not (Atom "CancelFlight")]);
       Equiv (Atom "l_2_oknr", And [Atom "RentCar"; Not (Atom "CancelCar")])]);

  Or [(And [Atom "a"; Atom "b"]); (And [Not (Atom "a"); Not (Atom "b")])];
  (* nasty test case from process verifier *)
  Implies (And [Equiv (Atom "l_1_oknr", And [Atom "BookFlight"; Not (Atom "CancelFlight")]); Equiv (Atom "l_2_oknr", And [Atom "RentCar"; Not (Atom "CancelCar")]); Equiv (Atom "l_3_oknr", And [Atom "l_1_oknr"; Atom "l_2_oknr"]); Equiv (Atom "l_1_flok", And [Not (Atom "BookFlight"); Not (Atom "CancelFlight")]); Equiv (Atom "l_2_nrnr", And [Not (Atom "RentCar"); Not (Atom "CancelCar")]); Equiv (Atom "l_1_okok", And [Atom "BookFlight"; Atom "CancelFlight"]); Equiv (Atom "l_2_flok", And [Not (Atom "RentCar"); Not (Atom "CancelCar")]); Equiv (Atom "l_3_flok", Or [And [Atom "l_2_nrnr"; Atom "l_1_flok"]; And [Atom "l_2_flok"; Atom "l_1_okok"]]); Or [Atom "l_3_flok"; Atom "l_3_oknr"]], Or [And [Atom "RentCar"; Not (Atom "CancelCar"); Or [And [Not (Atom "BookFlight"); Not (Atom "CancelFlight")]; And [Atom "BookFlight"; Atom "CancelFlight"]]]; And [Atom "RentCar"; Not (Atom "CancelCar"); Atom "BookFlight"; Not (Atom "CancelFlight")]]) ;

  And [Atom "7"; Atom "5"; Atom "8"; Atom "6"; Atom "4"; Atom "0"; Atom "2"; Atom "1"; Atom "3"; Implies (Atom "6", Or [Atom "1"]); Implies (Atom "8", Or [Atom "4"]); Implies (Atom "8", Or [Atom "3"]); Implies (Atom "7", Or [Atom "2"]); Implies (Atom "7", Or [Atom "4"]); Implies (Atom "7", Or [Atom "8"]); Implies (Atom "5", Or [Atom "6"]); Implies (Atom "5", Or [Atom "1"]); Implies (Atom "4", Or [Atom "3"]); Implies (Atom "2", Or [Atom "3"]); Implies (Atom "0", Or [Atom "1"])] ;

  And [Atom "1"; Atom "2"; Or [ Not(Atom "1");  Atom "2"] ];
  And [Atom "1"; Or [ Not(Atom "1");  Atom "2"] ];

  And [Atom "1"; Atom "2"; Or [ Atom "2"] ];
  And [Atom "1"; Atom "2"; Implies (Atom "1", Atom "2") ];

  And [Atom "1"; Not (Atom "2")];
  And [Atom "1"; Not (Atom "1")];
|]

let run_cnf_tests () =
  Array.iteri
    (fun idx pred ->
      let pname = "p" ^ (string_of_int (idx+1)) in
	  run_pred2cnf_test pname pred)
    preds

let run_pred2dimacs_tests () =
  Array.iteri
    (fun idx pred ->
      let predno = (string_of_int (idx+1)) in
	message ("Running pred2dimacs test " ^ predno ^
		    ", input pred = " ^ (pred2str pred));
	let (dp, mappings) = pred2dimacs pred	  
	in debug (" output pred = " ^ (dimacs2str dp));
	  let pred' = dimacs2pred dp mappings
	  in debug (" back to pred = " ^ (pred2str pred'));
	    message " Test successful.")
    preds

let run_solver_tests () =
  Array.iteri
    (fun idx pred ->
      let predno = (string_of_int (idx+1)) in
	message ("Running solver test " ^ predno ^
		    ", input pred = " ^ (pred2str pred));
	let res = solve_pred pred
	in (match res with
	    None ->
	      message (" Unsatisifiable.");
	      let test_p = Not pred in
		print_endline (pred2simp test_p);
		print_endline ""
	  | Some model ->
	      let modelpred = model2pred model in
		message (" Solution: " ^ (pred2str modelpred));
		let test_p = Implies (modelpred, pred) in
		  print_endline (pred2simp test_p);
		  print_endline "");
	  message " Test successful.")
    preds
  
let main () =
  message "Starting Test_preds";
  run_cnf_tests ();
  run_pred2dimacs_tests ();
  run_solver_tests ();
  message "Test_preds: all tests successful."
;;

main ();;
