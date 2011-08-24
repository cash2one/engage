(** Definitions and functions for representing boolean predicates *)

(** The high-level predicates type *)
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

module Int :
sig
  type t = int
  val compare : t -> t -> int
end

module DimacsIntAtomMap :
  sig
    type key = Int.t
    type 'a t = 'a Map.Make(Int).t
    val empty : 'a t
    val is_empty : 'a t -> bool
    val add : key -> 'a -> 'a t -> 'a t
    val find : key -> 'a t -> 'a
    val remove : key -> 'a t -> 'a t
    val mem : key -> 'a t -> bool
    val iter : (key -> 'a -> unit) -> 'a t -> unit
    val map : ('a -> 'b) -> 'a t -> 'b t
    val mapi : (key -> 'a -> 'b) -> 'a t -> 'b t
    val fold : (key -> 'a -> 'b -> 'b) -> 'a t -> 'b -> 'b
    val compare : ('a -> 'a -> int) -> 'a t -> 'a t -> int
    val equal : ('a -> 'a -> bool) -> 'a t -> 'a t -> bool
  end

module DimacsAtomIntMap :
  sig
    type key = String.t
    type 'a t = 'a Map.Make(String).t
    val empty : 'a t
    val is_empty : 'a t -> bool
    val add : key -> 'a -> 'a t -> 'a t
    val find : key -> 'a t -> 'a
    val remove : key -> 'a t -> 'a t
    val mem : key -> 'a t -> bool
    val iter : (key -> 'a -> unit) -> 'a t -> unit
    val map : ('a -> 'b) -> 'a t -> 'b t
    val mapi : (key -> 'a -> 'b) -> 'a t -> 'b t
    val fold : (key -> 'a -> 'b -> 'b) -> 'a t -> 'b -> 'b
    val compare : ('a -> 'a -> int) -> 'a t -> 'a t -> int
    val equal : ('a -> 'a -> bool) -> 'a t -> 'a t -> bool
  end

(** structure containing maps between dimacs variable numbers and predicate
    names, along with number of variables *)
type dimacs_mappings = {
    atom_to_int : int DimacsAtomIntMap.t;
    int_to_atom : string DimacsIntAtomMap.t;
    numvars : int;
  }

module PredModel :
  sig
    type key = String.t
    type 'a t = 'a Map.Make(String).t
    val empty : 'a t
    val is_empty : 'a t -> bool
    val add : key -> 'a -> 'a t -> 'a t
    val find : key -> 'a t -> 'a
    val remove : key -> 'a t -> 'a t
    val mem : key -> 'a t -> bool
    val iter : (key -> 'a -> unit) -> 'a t -> unit
    val map : ('a -> 'b) -> 'a t -> 'b t
    val mapi : (key -> 'a -> 'b) -> 'a t -> 'b t
    val fold : (key -> 'a -> 'b -> 'b) -> 'a t -> 'b -> 'b
    val compare : ('a -> 'a -> int) -> 'a t -> 'a t -> int
    val equal : ('a -> 'a -> bool) -> 'a t -> 'a t -> bool
  end
(** A predicate model is a mapping from predicate variable names to
    true or false *)
type pred_model = bool PredModel.t


(** return a Simplify version of the predicate *)
val pred2simp : predicate -> string

(** return a simple string version of the predicate *)
val pred2str : predicate -> string

(** return the predicate as a string representing its ocaml data structure.
    Useful for testing. *)
val pred2camlstr : predicate -> string

(** Perform a shallow simplification on a predicate - only looks at the
    outermost level. This is designed to be called as you build up a
    predicate. *)
val simp : predicate -> predicate

(** Return the size of the given predicate *)
val predicate_size : predicate -> int

(** convert an arbitrary predicate to conjunctive normal form *)
val pred2cnf : predicate -> predicate

(** true if predicate is in conjunctive normal form *)
val is_in_cnf : predicate -> bool

(** convert a dimacs predicate to a high-level predicate *)
val dimacs2pred : dimacs_pred -> dimacs_mappings -> predicate

(** Convert a predicate to dimacs form. Returns the predicate and a
    mapping from dimacs variable numbers to the original variable names *)
val pred2dimacs : predicate -> dimacs_pred * dimacs_mappings

(** Return a string representation of dimacs predicate *)
val dimacs2str : dimacs_pred -> string

(** convert a dimacs model to a predicate model *)
val model2map : bool array -> dimacs_mappings -> pred_model

(** convert a predicate model to a conjunction *)
val model2pred : pred_model -> predicate

(** Call the solver to search for a satisifiable solution to the input
    predicate. If found, return a model describing the solution. Otherwise,
    return None. *)
val solve_pred : predicate ->pred_model option
