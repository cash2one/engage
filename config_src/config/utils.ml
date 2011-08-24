(** Miscellaneous utilities *)

open Resources (* needed for symbol, SymbolMap, etc. *)

(** combine a list of strings into a single string using the separator 'sep' *)
let join (lst:string list) (sep:string) :string =
  List.fold_left
    (fun str item ->
       if str="" then item
       else str ^ sep ^ item) "" lst


(** utility function to split a string 'str' at occurences of character
    'char' *)
let split (str:string) (char:char) :string list =
  let rec split_rec (str:string) (lst:string list) =
    try
      let idx = String.index str char in
      let new_start = idx + 1 in
      let new_len = (String.length str) - new_start in
        split_rec (String.sub str new_start new_len)
          ((String.sub str 0 idx)::lst)
    with Not_found -> str::lst
  in List.rev (split_rec str [])

(** create a SymbolMap map from a list of pairs *)
let make_map (list:(symbol*'v) list) :'v SymbolMap.t =
  List.fold_left
    (fun map ((key:symbol), value) ->
       SymbolMap.add key value map) SymbolMap.empty list
