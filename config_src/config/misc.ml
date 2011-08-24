(* Copyright 2008  The Regents of the University of California.

   Licensed under the Apache License, Version 2.0 (the "License"); you
   may not use this file except in compliance with the License.  You
   may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
   implied.  See the License for the specific language governing
   permissions and limitations under the License.
*)

(* $Id: misc.ml,v 1.30 2008/05/14 18:26:09 rupak Exp $
 *
 * This file is part of the BLAST Project.
 *)

(**
 * This module provides some miscellaneous useful helper functions.
 *)


open Str
open Printf

(*******************************************************************************
 * failure functions
 ******************************************************************************)

let error s =
  Printf.printf "Fatal Error: %s \n" s; exit 0

let do_catch s f x =
    try f x
    with ex -> begin
        printf "%s hits exn: %s" s (Printexc.to_string ex);
        raise ex
    end

let do_catch_ret s f x y =
    try f x
    with ex -> begin
        printf "%s hits exn: %s" s (Printexc.to_string ex);
        y
    end

let ignoreFailure e = try Lazy.force e with _ -> ()

(*******************************************************************************
 * tuple functions
 ******************************************************************************)

let mk_pair x y = x, y
let mk_triple x y z = x, y, z

let map_fst f (x,y) = f x, y
let map_snd f (x,y) = x, f y
let map_pair f (x,y) = f x, f y
let map_pair2 f g (x,y) = f x, g y
let map_triple3 f g h (x,y,z) = f x, g y, h z

let pair_to_list (x,y) = [x;y]
let triple_to_list (x,y,z) = [x;y;z]

let double x = x, x
let triple x = x, x, x

let swap (x,y) = y, x

let fst3 (x,y,z) = x
let snd3 (x,y,z) = y
let thd3 (x,y,z) = z

(*******************************************************************************
 * function functions
 ******************************************************************************)

let id x = x
let flip f x y = f y x
let const x y = x
let compose f g = fun x -> f (g x)
let (<<) = compose
let (>>) f g = compose g f
let apply f x = f x
let (<|) = apply
let (|>) x f = f x
let compose3 f g h = fun x -> f (g (h x))
let compose4 f g h i = fun x -> f (g (h (i x)))
let rec until p f x = if p x then x else until p f (f x)
let rec repeat f i =  if i > 0 then (f (); repeat f (i-1))
let curry f x y = f (x,y)
let curry3 f x y z = f (x,y,z)
let curry4 f w x y z = f (w,x,y,z)
let uncurry f (x,y) = f x y
let uncurry3 f (x,y,z) = f x y z
let uncurry4 f (w,x,y,z) = f w x y z
let pass f x = ignore (f x); x

(*******************************************************************************
 * Either functions
 ******************************************************************************)

type ('a, 'b) either = Left of 'a | Right of 'b

let either f g = function Left a -> f a | Right b -> g b
let left f = function
  | Left a -> f a
  | _ -> invalid_arg "left: expected left either"
let right g = function
  | Right b -> g b
  | _ -> invalid_arg "right: expected right either"

(*******************************************************************************
 * Option functions
 ******************************************************************************)

let isSome = function Some _ -> true | None -> false
let isNone = function Some _ -> true | None -> false
let maybe b f = function Some a -> f a | None -> b
let maybe' b f = function Some a -> f a | None -> Lazy.force b
let maybe'' b f = function Some a -> f a | None -> b ()
let to_maybe cond a = if cond then Some a else None
let maybe_map f opt = maybe None (fun x -> Some (f x)) opt
let maybe_iter f opt = maybe () f opt
let maybemaybe f opt = maybe None f opt
let rec cat_maybes =
    function [] -> []
    | (Some x) :: ms -> x :: (cat_maybes ms)
    | None :: ms -> cat_maybes ms
let some f =
    function Some a -> f a
    | _ -> invalid_arg "some: expected Some"
let none b =
    function None -> Lazy.force b
    | _ -> invalid_arg "none: expected None"

let option_to_string = maybe "NONE" id
let option_to_list opt = maybe [] (fun x -> x::[]) opt

(*******************************************************************************
 * List functions
 ******************************************************************************)

let list_maybe f = function [] -> [] | x::xs -> f x xs
let empty = function [] -> true | _ -> false
let cons x xs = x::xs
let cons_if hd tl = (if List.mem hd tl then id else cons hd) tl
let consr x r = r := x::(!r)
let snoc xs x = xs@[x]

let list_tl_or_empty = function [] -> [] | _::xs -> xs
let list_is_singleton = function [_] -> true | _ -> false

let list_init xs =
    try List.rev << List.tl <| List.rev xs
    with _ -> invalid_arg "list_init: expected non-empty list"
and list_last xs =
    try List.hd <| List.rev xs
    with _ -> invalid_arg "list_last: expected non-empty list"

let rec range i j step = if i > j then [] else i::(range (i+step) j step)
let rec list_interval m n = if m <= n then m::(list_interval (m+1) n) else []
let rec list_replicate n x = if n > 0 then x::(list_replicate (n-1) x) else []
let clone xs = flip list_replicate <| xs
let make_list n = list_interval 1 n

let rec take n = function x::xs when n > 0 -> x::(take (n-1) xs) | _ -> []
and takeWhile f = function x::xs when f x -> x::(takeWhile f xs) | _ -> []
and drop n = function x::xs when n > 0 -> drop (n-1) xs | xs -> xs
and dropWhile f = function x::xs when f x -> dropWhile f xs | xs -> xs
and splitAt n xs =
    let rec sp =
        function k, xs, y::ys when k > 0 -> sp (k-1, y::xs, ys)
        | _, xs, ys -> xs, ys in
    map_pair2 List.rev id <| sp (n,[],xs)
and span f xs =
    let rec sp =
        function xs, y::ys when f y -> sp (y::xs, ys)
        | xs, ys -> xs, ys in
    map_pair2 List.rev id <| sp ([],xs)
and break f = span (not << f)
let list_cut i xs =
    let prefix, suffix = splitAt i xs in List.hd suffix, prefix
let list_cut' i xs =
    let prefix, suffix = splitAt i xs in List.tl suffix, List.hd suffix, prefix

let add xs x = if List.mem x xs then xs else x::xs
let list_remove xs y = List.filter (fun x -> not (compare x y = 0)) xs
let rec replace n x =
    function _::ys when n = 0 -> x::ys
    | y::ys when n > 0 -> y::(replace (n-1) x ys)
    | ys -> ys

let list_only =
    function [x] -> x
    | _ -> invalid_arg "list_only: expected singleton list"
let list_only2 =
    function [x;x'] -> x, x'
    | _ -> invalid_arg "list_only2: expected two-element list"
let last_two l =
   match List.rev l with h1::h2::_ -> h2, h1
   | _ -> invalid_arg "last_two: expected two-or-more-element list"

(* this runs in O(min(m,n)),
 * vs. O(m+n) for length xs = length ys *)
let rec list_eq_len xs ys =
    match xs, ys with
    | [], [] -> true
    | x::xs, y::ys -> list_eq_len xs ys
    | _ -> false

(* this offers nothing over List.{iter,map} *)
(* depricated in psrc2 *)
let ignore_list_iter f l = ignore (List.map f l)

let fold_left3 f a bs cs ds =
    if list_eq_len bs cs && list_eq_len cs ds then
        List.fold_left2 (fun a b (c,d) -> f a b c d) a bs
        <| List.combine cs ds
    else failwith "fold_left3: expected equal length lists"

let fold_left_and_map f a bs =
    let rec flam f a bs cs =
        match bs with
        | b::bs -> let a, c = f a b in flam f a bs (c::cs)
        | []   -> a, List.rev cs
    in flam f a bs []

let list_exists_cross2 f l1 l2 =
    List.exists (fun e -> (List.exists (fun e' -> f e e') l2)) l1

let rec map_exn ex f =
    function [] -> []
    | x::xs -> try (f x)::(map_exn ex f xs) with ex -> map_exn ex f xs

let mapi f = snd << fold_left_and_map (fun i x -> i+1, f i x) 0
let list_iteri f = ignore << List.fold_left (fun i x -> f i x; i+1) 0
let list_fold_lefti f a =
    fst << List.fold_left (fun (a,i) b -> f a i b, i+1) (a,0)
let list_filteri f =
    List.rev << list_fold_lefti (fun ys i x -> if f i x then x::ys else ys) []
let list_mask f = list_filteri (fun i _ -> f i)


(* depricated in psrc2 *)
(* also, mje doesn't like this function because it is less transparent than
 * flatten << map f, and no faster *)
let flap f xs = List.flatten (List.map f xs)

let list_first_index f xs =
    let rec find i =
        function [] -> raise Not_found
        | x::xs -> if f x then i else find (i+1) xs in
    find 0 xs


(* depricated in psrc2 *)
let list_filter_unique f l =
  match List.filter f l with
  [a] -> a
  | [] -> failwith "filter_unique: empty!"
  | _ -> failwith "filter_unique: multiple!"


let list_count x =
    (* List.length << List.filter ((=) x) *)
    List.fold_left (fun c y -> if x = y then c+1 else c) 0

let rec map_partial f =
    function [] -> []
    | h::t -> begin
        match f h with
        | Some x -> x::(map_partial f t)
        | None -> map_partial f t
    end

let list_map_maybe = map_partial
let filter_cut f l = List.partition f l

(* returns the truncated list containing the first n
 * elements Raise Failure "nth" if list is too short *)
let truncateList xs n =
    if List.length xs < n then
        invalid_arg "truncateList: list too short"
    else take n xs

let rec list_gather_option opt_l =
  List.map (some id) << List.filter isSome <| opt_l

let sum = List.fold_left (+) 0

let list_min =
    function x::xs -> List.fold_left min x xs
    | _ -> invalid_arg "list_min: expected non-empty list"
let list_max =
    function x::xs -> List.fold_left max x xs
    | [] -> invalid_arg "list_max: expected non-empty list"
let list_min_with x = function [] -> x | xs -> list_min xs
let list_max_with x = function [] -> x | xs -> list_max xs
let list_argmin f =
    function x::xs -> List.fold_left
        (fun (x,v) y -> let w = f y in if w < v then y, w else x, v)
        (x, f x) xs
    | _ -> failwith "list_argmin: expected non-empty list"

let rec make_all_pairs =
    function [] -> []
    | x::xs -> (List.map (fun y -> (x,y)) xs)@(make_all_pairs xs)

let cross_product xs ys =
    List.flatten <| List.map (fun x -> List.map (fun y -> x,y) ys) xs

(** compact l -> l' where l' is the list l without redundancies *)
let compact l =
  let t = Hashtbl.create (List.length l) in
  List.iter (fun x -> Hashtbl.replace t x ()) l;
  Hashtbl.fold (fun k _ ks -> k::ks) t []

let bi_sort (x,y) =
  if compare x y = 1 then y, x else x, y

let rec sorted_uniqify =
    function x::y::ys ->
        if x <> y then x::(sorted_uniqify (y::ys))
        else sorted_uniqify (y::ys)
    | xs -> xs

let uniqify xs =
    List.rev
    <| List.fold_left (fun ys x -> if List.mem x ys then ys else x::ys) [] xs

let uniqify' xs = sorted_uniqify << List.sort compare <| xs

let sort_and_compact xs = sorted_uniqify <| List.sort compare xs

(** takes a dom_rel should be a p.o. I guess, and returns the maximal elts of list_l *)
(* as you can see, a most frivolous algorithm, but hey! *)
let maximal dom_rel xs =
    List.filter (fun x -> not <| List.exists (fun y -> dom_rel y x) xs) xs

let rec partial_combine xs ys =
    match xs, ys with
    | x::xs, y::ys -> (x,y)::(partial_combine xs ys)
    | _ -> []
let list_min_combine = partial_combine

let rec get_first f =
    function [] -> None
    | x::xs -> begin
        match f x with
        | Some y -> Some y
        | None -> get_first f xs
    end

let rec list_first_cont_suffix f xs =
    if List.exists (not << f) xs then
        list_first_cont_suffix f
        << dropWhile (not << f)
        << dropWhile f
        <| xs
    else xs


(* depricated in psrc2 *)
let boolean_list_leq xs ys =
    list_eq_len xs ys
    && List.for_all2 (fun b b' -> not b || b') xs ys

(* depricated in psrc2 *)
let rec make_list_pairs l =
  match l with
      [] -> []
    | [h] -> []
    | a::b::t -> (a,b)::(make_list_pairs (b::t))

let rec group_pairwise xs =
    match xs with
    | [] -> []
    | a::b::xs -> (a,b)::(group_pairwise xs)
    | _ -> invalid_arg "group_pairwise: expected even-length list"

(* depricated in psrc2 *)
let rec hd_ll l  =
  match l with
      [] -> None
    | l1::t -> if l1 <> [] then Some(List.hd l1) else hd_ll t

let strList l = String.concat ", " l
let string_list_cat sep = String.concat sep
let list_toString toString = strList << List.map toString
let string_of_int_list = list_toString string_of_int

(* depricated in psrc2 *)
(* also, this offers nothing over fold_left *)
let accumulate f binop seed arglist =
  List.fold_left (fun sum arg -> binop sum (f arg)) seed arglist

let rec list_tabulate f start stop =
    if start < stop then
        (f start)::(list_tabulate f (start+1) stop)
    else []

(** assoc_list (  *)
let delete_assoc_list l1 l2 =
  let rec sf l1 l2 res =
    match (l1,l2) with
      ([],_) | (_,[]) -> (List.rev res)@l1
    | (((_,i1) as h1)::t1,h2::t2) ->
        if i1 < h2 then sf t1 l2 (h1::res)
        else if i1 > h2 then sf l1 t2 res
        else sf t1 t2 res in
  sf (List.sort (fun (_,x) (_,y) -> compare x y) l1) (List.sort compare l2) []

(*******************************************************************************
 *
 ******************************************************************************)

let queue_to_list q =
    List.rev << Queue.fold (flip cons) [] <| q

(* depricated in psrc2 *)
let boolean_list_leq xs ys =
    list_eq_len xs ys
    && List.for_all2 (fun b b' -> not b || b') xs ys

(*******************************************************************************
 * List set operations
 ******************************************************************************)

let union l1 l2 = List.fold_left add l2 l1
let difference l1 l2 = List.filter (function elem -> not(List.mem elem l2)) l1
let proj_difference_l l1 l2 = List.filter (function (x,y) -> not (List.mem x l2)) l1
let proj_difference_r l1 l2 = let l2' = List.map fst l2 in difference l1 l2'

let nontrivial_intersect f cmp l1' l2' =
   let rec _check l1 l2 =
    match (l1,l2) with
	(h1::t1,h2::t2) ->
	  let s = cmp h1 h2 in
	    if s = 0 then
	      if f h1 then true
	      else (_check t1 t2)
	    else
	      if s < 0 then _check t1 l2
	      else _check l1 t2
      | _ -> false
  in
    _check (List.sort cmp l1') (List.sort cmp l2')

let nonempty_intersect cmp l1 l2 =
  nontrivial_intersect (fun _ -> true) cmp l1 l2

let sort_and_intersect l1 l2 =
  let i_list_ref = ref [] in
  let rec _ints  _l1 _l2 =
    match (_l1,_l2) with
    (h1::t1,h2::t2) ->
      let s = compare h1 h2 in
      if s = 0 then (i_list_ref := h1::!i_list_ref; _ints t1 t2)
      else if s < 0 then _ints t1 _l2 else _ints _l1 t2
    | _ -> ()
  in
  _ints (List.sort compare l1) (List.sort compare l2);
  !i_list_ref

let intersection l1 l2 = difference l1 (difference l1 l2)

(* set containment using lists *)
let rec subsetOf xs ys =
    List.for_all (fun x -> List.exists (fun y -> y = x) ys) xs

let rec sorted_subsetOf xs ys =
    match xs, ys with
    | [], _ -> true
    | _::_, [] -> false
    | x::xs, y::ys when x = y -> sorted_subsetOf xs (y::ys)
    | x::xs, y::ys when x > y -> sorted_subsetOf (x::xs) ys
    | x::xs, y::ys -> false

(* Cartesian product *)
let cartesianProduct ll =
  List.fold_right
      (fun xs ys -> List.fold_right
          (fun x pairs -> List.fold_right
              (fun y l -> (x::y)::l)
              ys pairs)
          xs [])
      ll [[]]

(*******************************************************************************
 *
 ******************************************************************************)

(* returns the to_string function corresponding to the given
   pretty-printer *)
let to_string_from_printer printer =
  function data ->
    printer Format.str_formatter data ;
    Format.flush_str_formatter ()

(* given a printer for a type t, returns a printer for lists of elements of
   type t *)
let list_printer_from_printer printer fmt list =
  Format.fprintf fmt "@[[@[" ;
  begin
    match list with
        [] ->
          ()
      | head::tail ->
          printer fmt head ;
          List.iter (function e -> Format.fprintf fmt ";@ " ;
                                   printer fmt e)
                    tail
  end ;
  Format.fprintf fmt "@]]@]"

(* returns true if the character is a digit [0-9] *)
let is_digit c =
    match c with
    | '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9' -> true
    | _ -> false

(*******************************************************************************
 * Hashtbl functions
 ******************************************************************************)

let hashtbl_find_maybe table key =
    try Some (Hashtbl.find table key) with Not_found -> None

let hashtbl_find_with table default key =
    try Hashtbl.find table key with Not_found -> default

let hashtbl_map_partial f t =
  let res = ref [] in
  let _iter a b =
    match f a b with
	None -> ()
      | Some(r) -> res := r::!res
  in
    Hashtbl.iter _iter t;
    !res

(** hashtbl_map tbl f returns the list f a b where the bindings in the table are a -> b *)
let hashtbl_map tbl f =
    Hashtbl.fold (fun key value ls -> (f key value)::ls) tbl []

(** hashtbl_filter f tbl returns the list a, s.t. f a b = true, where a -> b in tbl *)
let hashtbl_filter f tbl =
    Hashtbl.fold (fun key value ls -> if f key value then key::ls else ls) tbl []

let hashtbl_filter_tbl f tbl =
    Hashtbl.iter
        (fun key value -> if not (f key value) then Hashtbl.remove tbl key)
        tbl;

    (* XXX: can you modify the table during iteration?? if not, use this
     * slower code
     *
     *  List.iter (Hashtbl.remove tbl) (hashtbl_filter f tbl)
     *)

exception Hashtbl_exists

let hashtbl_exists f t =
    try Hashtbl.iter (fun k v -> if f k v then raise Hashtbl_exists) t;
        false
    with Hashtbl_exists -> true

let hashtbl_exists_key f t = hashtbl_exists (const f) t
let hashtbl_forall f tbl = not <| hashtbl_exists (fun k v -> not <| f k v) tbl

(** hashtbl_keys tbl returns the list of keys that have bindings in the table --
 * assumes that every key has a unique binding *)
let hashtbl_keys t = Hashtbl.fold (fun x _ l -> x::l) t []
let hashtbl_data t = Hashtbl.fold (fun _ y l -> y::l) t []
let hashtbl_to_list t = Hashtbl.fold (fun x y l -> (x,y)::l) t []

let hashtbl_of_list size ls =
   let t = Hashtbl.create size in
   List.iter (fun x -> Hashtbl.replace t x ()) ls;
   t

(** the hasthbl is key -> elem_list *)
let hashtbl_elem_cons table key element =
    Hashtbl.replace table key (element ::
        (try Hashtbl.find table key with Not_found -> []))

let hashtbl_check_elem_cons table key element =
    let ls = try Hashtbl.find table key with Not_found -> [] in
    if not (List.mem element ls) then begin
        Hashtbl.replace table key (element::ls);
        true end
    else false

let hashtbl_delete table key element =
    Hashtbl.replace table key (list_remove
        (try Hashtbl.find table key with Not_found -> [])
        element)

(* like hashtbl_check_update -- only instead of ensuring that elt not in table.key
   we check that forall elt' in table.key not (f elt elt')
   i.e. not (exists elt'. f elt elt') *)

let hashtbl_fun_check_elem_cons f table key element =
  let ls = try Hashtbl.find table key with Not_found -> [] in
  if not (List.exists (f element) ls) then begin
      Hashtbl.replace table key (element::ls);
      true end
  else false


(* Hashtable union: hash_union t1 t2 adds all the data of t2 to t1 *)

let run_on_table f tab =
  let reslist_ref = ref [] in
    Hashtbl.iter (fun x y -> reslist_ref := (f x y)::(!reslist_ref)) tab;
    !reslist_ref


let hashtbl_addtable t1 t2 = Hashtbl.iter (Hashtbl.add t1) t2

let append_counter_table = Hashtbl.create 31

let update_act fname =
    let c = try Hashtbl.find append_counter_table fname with Not_found -> 0 in
    Hashtbl.replace append_counter_table fname (c+1);
    c


(*******************************************************************************
 * String functions
 ******************************************************************************)

(* chop s chopper returns ([x;y;z...]) if s = x.chopper.y.chopper ...*)
let chop s chopper = Str.split (Str.regexp chopper) s

(* like chop only the chop is by chop+ *)
let chop_star chopper s =
    Str.split (Str.regexp (Printf.sprintf "[%s+]" chopper)) s

let bounded_chop s chopper i = Str.bounded_split (Str.regexp chopper) s i
let is_prefix p s = Str.string_match (Str.regexp p) s 0

let is_suffix suffix s =
  let k = String.length suffix
  and n = String.length s in
  (n-k >= 0) && Str.string_match (Str.regexp suffix) s (n-k)

let is_substring s subs =
    try ignore (Str.search_forward (Str.regexp subs) s 0);
        true
    with Not_found -> false

let substitute_substrings s_s'_list one_string =
    List.fold_right
        (fun (s,s') -> Str.global_replace (Str.regexp s) s')
        s_s'_list
        one_string

let suffix k s = String.sub s k <| (String.length s) - k

(*  chop_after_prefix p s = if s = p.s' then s' *)
let chop_after_prefix prefix s =
    List.hd <| Str.bounded_split (Str.regexp prefix) s 1

let chop_before_suffix suffix s =
    try String.sub s 0
        <| Str.search_backward (Str.regexp suffix) s (String.length s -1)
    with Not_found -> s

let insert_before c s ins =
    match bounded_chop s c 2 with
    | [_] -> s
    | [s; t] -> Printf.sprintf "%s%s%s%s" s ins c t
    | _ -> failwith "This cannot happen!"

let replace_string old_s new_s s = Str.global_replace (Str.regexp old_s) new_s s

(*******************************************************************************
 *
 ******************************************************************************)

let write_to_file fname _string =
  let oc = open_out fname in
  output_string oc _string;
  close_out oc

let write_list_to_file fname string_list =
  let oc = open_out fname in
    List.iter (output_string oc) string_list;
    close_out oc

(*******************************************************************************
 *
 ******************************************************************************)


let append_to_file fname s =
  ignore (update_act fname);
  let oc = Unix.openfile fname  [Unix.O_WRONLY; Unix.O_APPEND; Unix.O_CREAT] 420  in
  ignore (Unix.write oc s 0 ((String.length s)-1) );
  Unix.close oc

(* ambitious -- take a text file and return a list of lines that is the file *)
let string_list_of_file fname =
  let ic  = open_in fname in
  let doneflag = ref false in
  let listoflines = ref [] in
    while not (!doneflag) do
      try
	listoflines := (input_line ic)::(!listoflines)
      with
	  End_of_file -> doneflag := true
    done;
    close_in ic;
  List.rev !listoflines

let words_of_string string =
    List.filter (fun x -> not ((x = "") || (x = " ")))
    << Str.split (Str.regexp " +") <| string

(* source file is some random text file and grepfile is a list of interesting
words *)


(* depricated in psrc2 *)
let grep_file sourcefile grepfile =
  let wordtable = Hashtbl.create 101 in
  let interesting_words = List.flatten (List.map words_of_string (string_list_of_file grepfile)) in
  let _ = List.iter (fun x -> Hashtbl.add wordtable x true) interesting_words in
  let lines_of_file = List.map words_of_string (string_list_of_file sourcefile) in
    List.filter (fun x -> List.exists (Hashtbl.mem wordtable) x) lines_of_file


(*******************************************************************************
* powerSet, power
******************************************************************************)

  (* compute the power set of a given set of elements represented as a
     list.  the presence of an element e in a subset is represented as
     (true, e), and the absence is represented as (false, e).
  *)
  let powerSet l =
(*
    let rec powAux currSet elems =
      match elems with
          [] -> [currSet]
        | head::tail ->
            (powAux ((true,head)::currSet) tail)@
            (powAux ((false,head)::currSet) tail) in
      powAux [] l
*)
  (* Generate all the (exponentially many) minterms to check.
   * We are given l, a list of absPredExpressions. For example, l might
   * be [a;b;c]. We are supposed to generate:
   * 	a, ~a, b, ~b, c, ~c
   * 	ab, a~b, ~a~b, ~ab, ac, a~c, ~ac, ~a~c, bc, b~c ...
   * 	abc, ab~c, a~bc, ...
   *
   * Through amazingly convoluted coding, this procedure uses an amount of
   * stack space that is LINEAR in MaxCubeLen (which is <= l).
   * Heap space is exponential, but so is the answer. *)
  match l with [] -> [[]]
  | _ ->
  (* what is the maximum cube length for one of our answers? *)
    let maxCubeLen = List.length l
    in
  (* we'll store our answers here *)
    let answer_list = ref [] in

  (* we need random access to the input list of predicates, so we convert
     * it to an array *)
    let l_array = Array.of_list l in
    let l_len = maxCubeLen - 1 in

(*[rupak]    for cubeLen = maxCubeLen downto 1 do *) let cubeLen = maxCubeLen in (*[rupak]*)
    (* now we want to spit out all minterm-lists of length cubeLen *)
    (* so we will consider all subsets of l of length cubeLen *)
    (* inThisSubset is an array of indices into l_array *)
      let inThisSubset = Array.make cubeLen (-1) in
    (* exampe: if inThisSubset.(0) = 3 and inThisSubset.(1) = 5 then
       * this subset consists of elements 3 and 5 *)

    (* we also want to know if we are including the input term or its
       * negation *)
      let polarity = Array.make cubeLen 0 in

    (* Here comes the black magic. Normally to enumerate all subsets of
       * length three you would use three nested for-loops. To enumerate
       * all subsets of length cubeLen we need cubeLen nested for loops.
       * We will build our loop nest up dynamically using function pointers.
       *
       * To avoid considering both 3,5 and 5,3 as subsets of length 2 we will
       * only consider subsets that have their l-indices in ascending order.
       *)

    (* "iter" is one such for loop.
       * "index" tells us which element of inThisSubset and polarity we are
       * setting. "last_value" helps us stay in ascending order.
       * "continuation" is what to call when we are done. We call it with
       * our current value as its only argument.
       *)
      let iter (index : int) (last_value : int) (continuation : int -> unit) =
	for i = last_value+1 to l_len do (* consider every element in l *)
	  inThisSubset.(index) <- i; (* it just became element 'index' of our subset *)
	  for pol = 0 to 1 do 	   (* include it once positively *)
	    polarity.(index) <- pol ; (* and once negatively *)
	  (continuation) i
	  done
	done
      in
      (* "construct" is the inner-most loop. Given that previous iterations
       * have set up the inThisSubset and polarity arrays for us, construct
       * the associated cube. *)
      let construct _ =
	let this_cube = ref [] in (* we'll build the cube here *)
	for gather = 0 to cubeLen-1 do (* pick out all elts in this subset *)
	  let elt = l_array.(inThisSubset.(gather)) in
	  let elt' = if polarity.(gather) = 0 then
	    (false,elt) else (true,elt) in
	  this_cube := elt' :: !this_cube ;
	done ; (* now that we have it, append it to the answer list *)
	answer_list := !this_cube :: !answer_list
      in
      (* Now it's time to built up our loop nest. Recall that we'll have
       * cubeLen for loops. We'll store them in this array. The default
       * array element is "construct", which handles the innermost loop. *)
      let funPtrArray = Array.make cubeLen construct in
      (* NOTE: ocaml will not do what you want if you try to define these
       * guys like: "myfun := iter x y (!myfun)". So we need the array. *)

      (* Actually constuct the loop nest. Each iteration calls another
       * iteration. *)
    for i = 1 to cubeLen-1 do
      funPtrArray.(i) <- (fun last_val -> iter i last_val funPtrArray.(i-1))
    done ;
    (* Here's the outermost loop: This one is an actual function call. *)
      iter 0 (-1) (funPtrArray.(cubeLen-1)) ;
    (*[rupak]done;[rupak]*)
    !answer_list


let power a b =
    if b = 0 then 1
    else if b > 0 then begin
        let p = ref a in
        let e = ref b in
        while !e > 1 do
            p := !p * !p ; e := !e / 2;
        done;
        if b mod 2 = 0 then !p else !p * a
    end
    else invalid_arg "power: expected non-negative power"

(*******************************************************************************
 * Binary search
 ******************************************************************************)

(** binary_search f lo hi returns k where:
  * lo <= k <= hi,
  * forall lo <= j < k: (f j = false)
  * k <> hi => (f k = true) *)

let binary_search f lo hi =
    fst
    << until (uncurry (=)) (fun (lo,hi) ->
        assert (lo<=hi);
        let p = (lo+hi)/2 in
        if f p then lo, p else p+1, hi)
    <| (lo, hi)

(*******************************************************************************
 * Parentheses matching
 ******************************************************************************)

(* input: 'a array, f: 'a -> paren. Output: l,r : int -> int *)

let paren_match f arr =
  let n = Array.length arr in
  let left_array = Array.create n (-1) in
  let right_array = Array.create n (-1) in
  let pot = ref [] in
    for i = 0 to n-1 do
      match (f (arr.(i))) with
	| "(" -> (pot := i::!pot;Array.set left_array i i)
	| ")" ->
	      (match !pot with
		| (tos::tl) ->
		    Array.set right_array tos i;
		    Array.set left_array i tos;
		    pot := tl
		| _ -> failwith "unhandled match case :: paren_match @ misc.ml")
	| _ ->  let tos = try List.hd !pot with _ -> -1 in
                Array.set left_array i tos
    done;
  let l i = if i < 0 || i >= Array.length left_array then -1 else left_array.(i) in
  let r i = if (l i = -1) then -1 else right_array.(l i) in
    (l,r)

let gen_paren_match f arr =
  let pot = Hashtbl.create 37 in
  let _get k = try Hashtbl.find pot k with Not_found -> [] in
  let _set k l = Hashtbl.replace pot k l in
  let push k i = let l = _get k in _set k (i::l) in
  let pop k = match _get k with i::l -> (_set k l; i) | _ -> failwith "bad match" in
  try
    let n = Array.length arr in
    let left_array = Array.create n (-1) in
    let right_array = Array.create n (-1) in
      for i = 0 to n-1 do
        match f (arr.(i)) with
        | ("(",k) -> push k i
        | (")",k) ->
            let i' = pop k in (Array.set right_array i' i;Array.set left_array i i')
        | _ -> ()
      done;
    let l i = if i < 0 || i >= Array.length left_array then (-1) else left_array.(i) in
    let r i = if i < 0 || i >= Array.length left_array then (-1) else right_array.(i) in
     Some (l,r)
  with _ -> None

(*******************************************************************************
 *
 ******************************************************************************)

let rec _kcombine =
  (* each list in l must have the same length *)
    function [] -> []
    | xs ->
	try
	  let ys = List.filter (not << empty) xs in
	  List.map List.hd ys @ _kcombine (List.map List.tl ys)
	with _ -> failwith "Failure in kcombine"

(* depricated in psrc2 *)
let kcombine l =
    print_string
    << sprintf "Kcombine called with : %s : \n"
    << list_toString string_of_int
    << List.map List.length <| l;
    _kcombine l


(*******************************************************************************
 * Array functions
 ******************************************************************************)

let array_fold_lefti f x arr =
    fst <| Array.fold_left (fun (a,idx) b -> (f a idx b,idx+1)) (x,0) arr

(* depricated in psrc2 *)
let array_of_list2 xs =
  Array.of_list <| List.map Array.of_list xs

(* depricated in psrc2 *)
let array_filter f arr =
  let iptr = ref [] in
  let collect i a =
    if f a then
      iptr := i::!iptr;
  in
    Array.iteri collect arr;
    List.rev !iptr

(* depricated in psrc2 *)
let array_select2 arr l =
  try
    List.map (List.map (fun i -> arr.(i))) l
  with _ -> failwith "array_select2 fails!"

let array_counti f arr =
    array_fold_lefti (fun n i a -> if f i a then n+1 else n) 0 arr

let array_reset arr resetval =
  Array.fill arr 0 (Array.length arr) resetval

(*******************************************************************************
 *
 ******************************************************************************)

(* HACK to get around the lvals_type -- see AliasAnalyzer.get_lval_aliases_iter *)
(* XXX: relocate this! *)
let allLvals_t_c = 0
let scopeLvals_t_c = 1
let traceLvals_t_c = 2

(*******************************************************************************
 *
 ******************************************************************************)
let compute_fixpoint_bounded depth next_fn seed =
  let fp_table = Hashtbl.create 17 in
  let rec bfs d s =
    let get_next e =
        if Hashtbl.mem fp_table e  then []
        else (Hashtbl.replace fp_table e (depth-d);next_fn e)
    in
    if (d = 0 || s = []) then ()
    else
        let succs = List.flatten (List.map get_next s) in
        bfs (d-1) succs
  in
  bfs depth seed;
  hashtbl_to_list fp_table

let compute_fixpoint next_fn seed = compute_fixpoint_bounded (-1) next_fn seed

(*******************************************************************************
 *
 ******************************************************************************)

(* depricated in psrc2 *)
let get_binary i n =
  let rec n_zeros n = if n<=0 then [] else 0::(n_zeros (n-1)) in
  let j = ref i in
  let bits = ref [] in
  while (!j >= 1) do
    let thisbit = !j land 1 in
    bits := thisbit :: !bits ;
    j := !j lsr 1;
  done ;
  if (List.length !bits < n) then (n_zeros (n - List.length !bits)) @ !bits
  else !bits

(*******************************************************************************
 *
 ******************************************************************************)

(* result list is in increasing order of significance *)
let base_convert b n =
    snd
    << until ((=) 0 << fst) (fun (n,rs) -> n/b, (n mod b)::rs)
    <| (n, [])

let ascii_of_int i =
    let ascii_string = "abcdefghijklmnopqrstuvwxyz" in
    if i < 0 || i > 25 then
        invalid_arg "ascii_of_int: expected ..."
    else String.make 1 ascii_string.[i]

let ascii_string_of_int =
  String.concat "" << List.map ascii_of_int << base_convert 26

(*******************************************************************************
 * Memo
 ******************************************************************************)

let memoize table key f arg =
    try Hashtbl.find table key
    with Not_found ->
        let elem = f arg in
        Hashtbl.replace table key elem;
        elem

(*******************************************************************************
 * Timeouts
 ******************************************************************************)

exception TimeOutException
 (* The trouble with raising TimeOutException here is
  * that if TimeOutException is caught at some random place (and absorbed),
  * we have lost the alarm. Moreover this exception can be
  * raised at an awkward moment, leaving the internal state inconsistent.
  * So we set a global bit that the model checker will check at the beginning
  * of each loop. The model_check routine raises TimeOutException if this bit is set.
  * This bit is reset by the catchers of TimeOutException *)

let sig_caught_bit = ref false

let set_time_out_signal t =
    if t >= 0 then begin
        printf "Setting signal for %d seconds \n" t;
        sig_caught_bit := false;
        ignore << Sys.signal Sys.sigalrm <| Sys.Signal_handle (fun i ->
            output_string stdout "Caught exception sigalrm in handler!";
            print_string "Caught exception sigalrm in handler!";
            sig_caught_bit := true;
            exit 1);
        ignore <| Unix.alarm t;
    end

let reset_time_out_signal () =
    Sys.set_signal Sys.sigalrm (Sys.Signal_ignore);
    sig_caught_bit := false

let check_time_out () =
    if !sig_caught_bit then begin (* Time out has occurred *)
        reset_time_out_signal (); (* reset the timeout for next iteration *)
        printf "Time out!\n\n";
        exit 1;
    end
