(** Definitions and functions for representing boolean predicates *)

type predicate =
    | Atom of string
    | Not of predicate
    | And of predicate list
    | Or of predicate list
    | Equiv of predicate * predicate
    | Implies of predicate * predicate
    | True
    | False

(** Predicate using dimacs format for SAT solver. The predicate is in
    cnf form. Each variable is mapped to an integer value, starting at 1.
    Each int array is a clause (disjunction of literals) of the cnf predicate,
    where the value of an array element represents a variable.
    Negative integers are used to represent negation. *)
type dimacs_pred = (int array) list

module Int = struct
  type t = int
  let compare = compare
end

module DimacsIntAtomMap = Map.Make(Int)
module DimacsAtomIntMap = Map.Make(String)

(** structure containing maps between dimacs variable numbers and predicate
    names, along with number of variables *)
type dimacs_mappings = {
    atom_to_int : int DimacsAtomIntMap.t;
    int_to_atom : string DimacsIntAtomMap.t;
    numvars : int;
  }

module PredModel = Map.Make(String)
(** A predicate model is a mapping from predicate variable names to
    true or false *)
type pred_model = bool PredModel.t


(* set to true for internal debug mode *)
let debug = false

(* eager function to print trace messages *)
let trace_msg (msg:string) :unit =
  if debug then print_endline (";; " ^ msg)
  else ()

(* lazy function to print trace messages *)
let trace (msg_thunk:string Lazy.t) :unit =
  if debug then print_endline (";; " ^ (Lazy.force msg_thunk))
  else ()

(* print a debug message containing the specified list, where fn is
   a function to convert a list element to a string *)  
let trace_list fn name lst =
  trace
    (lazy ((List.fold_left
	      (fun str item ->
		str ^ " " ^ (fn item) ^ ";") (name ^ ": [") lst)
	   ^ " ]"))

(** return a Simplify version of the predicate *)
let rec pred2simp (p:predicate) :string =
  match p with
      Atom s -> s
    | Not p' -> "(NOT " ^ (pred2simp p') ^ ")"
    | And pl -> (List.fold_left (fun s p -> s ^ " " ^ (pred2simp p)) 
		    "(AND" pl) ^ ")"
    | Or pl -> (List.fold_left (fun s p -> s ^ " " ^ (pred2simp p))
		   "(OR" pl) ^ ")"
    | Equiv (p1, p2) -> "(IFF " ^ (pred2simp p1) ^ " " ^ (pred2simp p2) ^ ")"
    | Implies (p1, p2) -> "(IMPLIES " ^ (pred2simp p1) ^ " " ^ (pred2simp p2)
	                  ^ ")"
    | False -> "FALSE"
    | True -> "TRUE"

(** return a simple string version of the predicate *)
let rec pred2str (p:predicate) :string =
  let subpred prd =
    match prd with
	Atom s -> s
      | Not (Atom s) -> "^" ^ s
      | _ -> "(" ^ (pred2str prd) ^ ")"
  in let rec fold_with_sep prdlst sep_str =
    match prdlst with
	[] -> "()"
      | fst::[] -> subpred fst
      | fst::rst -> (subpred fst) ^ sep_str ^ (fold_with_sep rst sep_str)
  in match p with
      Atom s -> s
    | Not (Atom s) -> "^" ^ s
    | Not p' -> "^(" ^ (pred2str p') ^ ")"
    | And pl -> fold_with_sep pl "/\\"
    | Or pl -> fold_with_sep pl "\\/"
    | Equiv (p1, p2) -> (subpred p1) ^ " <-> " ^ (subpred p2)
    | Implies (p1, p2) -> (subpred p1) ^ " -> " ^ (subpred p2)
    | False -> "FALSE"
    | True -> "TRUE"

(** return the predicate as a string representing its ocaml data structure.
    Useful for testing. *)
let rec pred2camlstr (p:predicate) :string =
  let rec fold_with_sep prdlst sep_str =
    match prdlst with
	[] -> "()"
      | fst::[] -> pred2camlstr fst
      | fst::rst -> (pred2camlstr fst) ^ sep_str ^ (fold_with_sep rst sep_str)
  in match p with
      Atom s -> "Atom \"" ^ s ^ "\""
    | Not p' -> "Not (" ^ (pred2camlstr p') ^ ")"
    | And pl -> "And [" ^ (fold_with_sep pl "; ") ^ "]"
    | Or pl -> "Or [" ^ (fold_with_sep pl "; ") ^ "]"
    | Equiv (p1, p2) ->
	"Equiv (" ^ (pred2camlstr p1) ^ ", " ^ (pred2camlstr p2) ^ ")"
    | Implies (p1, p2) ->
	"Implies (" ^ (pred2camlstr p1) ^ ", " ^ (pred2camlstr p2) ^ ")"
    | False -> "False"
    | True -> "true"



(** Perform a shallow simplification on a predicate - only looks at the
    outermost level. This is designed to be called as you build up a
    predicate. *)
let rec simp (p:predicate) :predicate =
  match p with
      Atom s -> p
    | Not p' ->
      (match p' with True -> False | False -> True | Not p'' -> p'' | _ -> p)
    | And pl ->
	(* use Not_found exception to finish iteration and return false *)
	(try
	  let pl' =
	    List.fold_left
	      (fun pl' pred ->
	         match pred with
		   True -> pl'
		   | False -> raise Not_found
		   | And pl'' -> List.rev_append pl' pl''
		   | _ -> pred::pl')
	      [] pl
	  in match pl' with
	      [] -> True
	    | fst::[] -> simp fst
	    | fst::rst -> And pl'
	with Not_found -> False)
    | Or pl ->
	(* use Not_found exception to finish iteration and return true *)
	(try
	  let pl' =
	    List.fold_left
	      (fun pl' pred ->
	         match pred with
		   True -> raise Not_found
		   | False -> pl'
		   | Or pl'' -> List.rev_append pl' pl''
		   | _ -> pred::pl')
	      [] pl
	  in match pl' with
	      [] -> False
	    | fst::[] -> simp fst
	    | fst::rst -> Or pl'
	with Not_found -> True)
    | Equiv (p1, p2) -> p
    | Implies (p1, p2) -> p
    | False -> False
    | True -> True


(** Return the size of the given predicate *)
let rec predicate_size (pred:predicate) :int =
  match pred with
    | Atom n -> 1
    | Not p -> (predicate_size p) + 1
    | And pl
    | Or pl ->
	List.fold_left (fun sz p -> sz + (predicate_size p))
	  ((List.length pl)-1) pl
    | Equiv (p1, p2) -> (predicate_size p1) + (predicate_size p2) + 1
    | Implies (p1, p2) ->  (predicate_size p1) + (predicate_size p2) + 1
    | True -> 1
    | False -> 1


(* helper functions *)
let negate_terms (pl:predicate list) :predicate list =
  List.rev_map (fun term -> Not term) pl

let is_literal (p:predicate) :bool =
  match p with Atom _ | False | True | Not (Atom _) -> true | _ -> false

(* true if predicate is a literal or a conjuction of literals *)
let is_lit_conjunction (p:predicate) :bool =
  match p with
      Atom _ | False | True | Not (Atom _) -> true
    | And pl -> List.for_all is_literal pl
    | _ -> false
    

let cross_product (cp_fn:'a -> 'b -> 'c) (a_list:'a list) (b_list:'b list)
                  :'c list =
    List.fold_left
      (fun c_list a ->
	List.fold_left (fun c_list b -> (cp_fn a b)::c_list)
	  c_list b_list) [] a_list

(** Run the mapping function on each list item and join the lists *)
let map_and_merge (fn:'a->'b list) (lst:'a list) :'b list =
  List.fold_left (fun res_list item -> List.rev_append res_list  (fn item)) [] lst

exception Always_false
exception Always_true

(* stuff for dummy variables *)
(* We have to start with a letter to make simplify (used for testing)
   happy *)
let prefix = "z__"
let is_dummy_var str =
  (String.length str)>=3 && str.[0]='z' && str.[1]='_' && str.[2]='_'
let _next_pname = ref 1
(* get a name for a dummy variable *)
let get_dummy_predname () =
  let name = prefix ^ (string_of_int !_next_pname)
  in _next_pname := !_next_pname + 1; name
      
(** convert an arbitrary predicate to conjunctive normal form *)
let rec pred2cnf (pred:predicate) :predicate =
  let pred' = preprocess pred
  in trace (lazy ("preprocessed pred: " ^ (pred2str pred')));
    let pred'' =
      match pred' with
	  True | False | Atom _ | Not (Atom _) -> pred'
	| And pl ->
	    let (pl, ands) = apply_replace_to_list pl
	    in And (List.rev_append pl ands)
	| Or pl ->
	    let (pl, ands) = apply_replace_to_list pl
	    in And ((Or pl)::ands)
	| _ -> failwith ("Unexpected pred after preprocessing: " ^
			    (pred2str pred'))
    in trace (lazy (";;Renamed pred: " ^ (pred2str pred'')));
      let distributed_pred = distribute_ands pred''
    in let result =
      match distributed_pred with
	| fst::[] -> fst
	| fst::rest -> And distributed_pred
	| [] -> failwith "Empty list from distribute_ands"
    in trace (lazy ("pred2cnf result: " ^ (pred2str result))); result
and preprocess (pred:predicate) :predicate =
 (* preprocess a predicate, removing Implies and Equals, and push all the
    Not's down to Atoms. Also, call simp to flatten redundant ands/ors and
    eliminate constants. *)
  let pred =
    match pred with
	True | False -> pred
      | Atom n | Not (Atom n) -> pred
      | Equiv (p1, p2) ->
	  preprocess (Or [(And [Not p1; Not p2]); (And [p1; p2])])
      | Implies (p1, p2) ->  preprocess (Or [Not p1; p2])
      | And pl -> And (List.rev_map preprocess pl)
      | Or pl -> Or (List.rev_map preprocess pl)
      | Not pred' -> begin
	  match pred' with
	      True -> False
	    | False -> True
	    | Atom n ->
		failwith "preprocess: case should be handled in outer match"
	    | Not pred'' -> preprocess pred'' (* get rid of double negatives *)
	    | Equiv (p1, p2) -> (* convert using demorgan's to the negation *)
		preprocess
		  (Or [(And [p1; Not p2]); (And [Not p1; p2])])
		  (* convert using demorgan's to the negation *)
	    | Implies (p1, p2) -> preprocess (And [p1; Not p2;])
	    | And pl ->
		Or (List.rev_map (fun p -> preprocess (Not p)) pl)
	    | Or pl ->
		And (List.rev_map (fun p -> preprocess (Not p)) pl)
	end
  in simp pred
and distribute_ands (pred:predicate) :predicate list =
  (* Take a predicate from a list of conjoined predicates. Return a list
     of conjoined predicates where the ands have been distributed. (for cnf) *)
  let get_and_terms pl =
    (* helper that results a list of terms from the first and predicate that is
       found in the list and the rest of the list *)
    List.fold_left
      (fun (and_terms, rest) p ->
	match (and_terms,p) with
	    ([], And pl') -> (pl', rest)
	  | _ -> (and_terms, p::rest)) ([], []) pl
  in let rec flatten_ors pl =
    List.fold_left
      (fun or_list term ->
	match term with
	    Or pl' -> List.rev_append or_list (flatten_ors pl')
	  | _ -> term::or_list) [] pl
  in 
    match pred with
	True | False -> [pred]
      | Atom n | Not (Atom n) -> [pred]
      | And pl -> map_and_merge distribute_ands pl
      | Or pl -> begin
	  match get_and_terms pl with
	      ([], _) -> [Or pl]
	    | (and_terms, rest) -> begin
		(*trace (lazy ("distribute_ors and-terms=" ^
				(pred2str (And and_terms)) ^
				"  rest=" ^ (pred2str (Or rest))));*)
		(* We have an And inside the Or. We remove the and by
		   creating a new conjuction where each conjunct is
		   the disjunction of one
		   term from the and_terms and all the terms from rest.
		   We then distribute each conjunct in a recursive call. *)
		map_and_merge
		  (fun and_term ->
		    distribute_ands (Or (flatten_ors (and_term::rest)))) and_terms
	      end
      end
    | Equiv _ | Implies _ | Not _ ->
	failwith "Should not have non-literal Not, Equiv or Implies in distribute_ands"
and apply_replace_to_list term_list =
  List.fold_left
    (fun (term_list, ands) term ->
      let (term, newands) = replace_term term
      in (term::term_list, List.rev_append newands ands)) ([],[]) term_list
and replace_term term :predicate*predicate list=
  (* replace_term replaces any non-terminals with dummy variables. It returns
     the new term (possibly the same as the original) and a list of terms
     to be conjoined with the top level predicate *)
  let negate_lit lit =
    match lit with
	True -> False
      | False -> True
      | Atom n -> Not (Atom n)
      | Not (Atom n) -> Atom n
      | Not (Not p') -> p'
      | _ -> failwith ("negate_lit got nonlit: " ^ (pred2str lit))
  in
    match term with
	True | False -> (term, [])
      | Atom n | Not (Atom n) -> (term, [])
      | And pl -> 
	  let newpred = Atom (get_dummy_predname ()) in
	  let (pl, ands) = apply_replace_to_list pl
	  in let defn1 = Or (newpred::(List.rev_map negate_lit pl))
	  and defn2 = Or [Not newpred; And pl]
	  in (newpred, defn1::defn2::ands)
      | Or pl ->
	  let newpred = Atom (get_dummy_predname ()) in
	  let (pl, ands) = apply_replace_to_list pl
	  in let defn1 = Or [newpred; And (List.rev_map negate_lit pl)]
	  and defn2 = Or ((Not newpred)::pl)
	  in (newpred, defn1::defn2::ands)
      | _ -> failwith ("replace_term: unexpected predicate " ^ (pred2str term))
	
(** true if predicate is in conjunctive normal form *)
let rec is_in_cnf (p:predicate) :bool =
  match p with
      True | False ->true
    | Atom n | Not (Atom n) -> true
    | Not p' -> false
    | And pl ->
	List.for_all
	  (fun term ->
	    match term with
		True | False -> true
	      | Atom n | Not (Atom n) -> true
	      | Not p' -> false
	      | Or pl -> List.for_all is_literal pl
	      | And pl -> false
	      | Equiv (p1, p2) | Implies (p1, p2) -> false) pl
    | Or pl -> List.for_all is_literal pl
    | Equiv (p1, p2) | Implies (p1, p2) -> false

(** convert a dimacs predicate to a high-level predicate, using the
    provided mappings.  *)
let dimacs2pred (dpred:dimacs_pred) (state:dimacs_mappings) :predicate =
  let int2pred (term:int) =
    if term < 0 then
      let var = DimacsIntAtomMap.find (-term) state.int_to_atom
      in Not (Atom var)
    else
      let var = DimacsIntAtomMap.find term state.int_to_atom
      in Atom var
  in let clause2pred clause =
    if (Array.length clause) = 1 then int2pred clause.(0)
    else Or (Array.fold_right (fun term pl -> (int2pred term)::pl) clause [])
  in match dpred with
      [] -> failwith "Empty dimacs list"
    | fst::[] -> clause2pred fst
    | _ -> And (List.rev_map clause2pred dpred)


let empty_dimacs_state = {int_to_atom = DimacsIntAtomMap.empty;
			  atom_to_int = DimacsAtomIntMap.empty; numvars=0;}

(** Convert a predicate to dimacs form. Returns the predicate and
    mappings between dimacs variable numbers and the original variable names.
    Not valid if the predicate is just the constant True or False *)
let  pred2dimacs (pred:predicate) :dimacs_pred * dimacs_mappings =
  let lit2term (var:string) (state:dimacs_mappings) =
    if DimacsAtomIntMap.mem var state.atom_to_int then
	let varno = DimacsAtomIntMap.find var state.atom_to_int in
	  (varno, state)
    else
	let varno = state.numvars + 1 in
	    (varno,
	    {atom_to_int=DimacsAtomIntMap.add var varno state.atom_to_int;
	     int_to_atom=DimacsIntAtomMap.add varno var state.int_to_atom;
	     numvars = varno;})
  in let or2clause (pl:predicate list) (state:dimacs_mappings)
                   :(int array * dimacs_mappings) =
    let (lst, state) =
      List.fold_left 
	(fun (lst, state) pred ->
	  let (term, state) =
	    match pred with
		Atom n -> lit2term n state
	      | Not (Atom n) ->
		  let (absterm, state) = lit2term n state
		  in (-absterm, state)
	      | _ -> failwith "expecting a literal"
	  in (term::lst, state)) ([], state) pl;
    in (Array.of_list lst, state)
  in let orlit2clause (reslist, state) pred =
    match pred with
      Atom n ->
	let (term, state) = lit2term n state
	in ((Array.make 1 term)::reslist, state)
    | Not (Atom n) ->
	let (term, state) = lit2term n state
	in ((Array.make 1 (-term))::reslist, state)
    | Or pl ->
	let (array, state) = or2clause pl state
	in (array::reslist, state)
    | _ -> failwith "unexpected pred type"
  in let state = empty_dimacs_state
  in  let cnf2dimacs pred =
    match pred with
	Atom n ->
	  let (term, state) = lit2term n state
	  in ([Array.make 1 term;], state)
      | Not (Atom n) ->
	  let (term, state) = lit2term n state
	  in ([Array.make 1 (-term);], state)
      | Or pl ->
	  let (array, state) = or2clause pl state
	  in ([array], state)
      | And pl ->
	  List.fold_left orlit2clause ([], state) pl
      | _ -> failwith "unexpected pred type"
  in
    trace (lazy ("pred2dimacs: " ^ (pred2str pred)));
    let cnfpred = pred2cnf pred in
    trace (lazy ("pred2dimacs: " ^ (pred2str pred)));
    cnf2dimacs cnfpred

(* internal helper function *)
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

(** Return a string representation of dimacs predicate *)
let dimacs2str (dp:dimacs_pred) :string =
  match dp with
      clause::[] -> clause_to_str clause
    | fst::rest ->
	List.fold_left
	  (fun str clause ->
	    str ^ " /\\ (" ^ (clause_to_str clause) ^ ")")
	  ("(" ^ (clause_to_str fst) ^ ")") rest
    | [] -> "[empty dimacs predicate]"

(** Convert a dimacs model to a predicate model. We drop any variables
    starting with the dummy prefix, these are internally generated variables. *)
let model2map (model:bool array) (state:dimacs_mappings) : pred_model =
  let map = ref PredModel.empty in
    Array.iteri
      (fun varno value ->
        print_string "varno = " ; print_int varno ; print_string " value = "; print_string (if value then "true\n" else "false\n");
	let var = DimacsIntAtomMap.find (varno+1) state.int_to_atom
	in if not (is_dummy_var var)
	   then map := PredModel.add var value !map)
      model;
    !map
     

(** convert a predicate model to a conjunction *)
let model2pred (model:pred_model) :predicate =
  And
    (PredModel.fold
	(fun pname value pl ->
	  if value then (Atom pname)::pl
	  else (Not (Atom pname))::pl) model [])

exception Not_satisfiable

(** Call the solver to search for a satisifiable solution to the input
    predicate. If found, return a model describing the solution. Otherwise,
    return None. *)
let solve_pred (pred:predicate) :pred_model option =
  trace (lazy ("solve_pred: " ^ (pred2str pred)));
  let solver = Camlmsat.create_solver ()
  in let (dp,mappings) = pred2dimacs pred
  in
       trace (lazy (" solve_pred: dimacs = " ^ (dimacs2str dp)));
       try
	 List.iter
	   (fun clause ->
	     trace (lazy (" solve_pred: adding clause " ^ (clause_to_str clause)));
	     if (Camlmsat.add_clause solver clause)=false
	     then (trace_msg "clause not satisifiable"; raise Not_satisfiable)) dp;
	 if not (Camlmsat.solve solver) then raise Not_satisfiable;
	 let model = model2map (Camlmsat.get_model solver) mappings
	 in Camlmsat.free_solver solver; Some model
       with Not_satisfiable -> Camlmsat.free_solver solver; None
