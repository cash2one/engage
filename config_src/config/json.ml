
open Resources

let type_of_json_value (json:json_value) :string =
  match json with
      JsonMap _ -> "map"
    | JsonScalar (Integer i) -> "integer"
    | JsonScalar (String s) -> "string"
    | JsonScalar (Boolean b) -> "boolean"
    | JsonScalar (Null) -> "null"
    | JsonList l -> "list"

let string_of_scalar_val (scalar:scalar_val) :string =
  match scalar with
      Integer i -> string_of_int i
    | String s -> "\"" ^ s ^ "\""
    | Boolean true -> "true"
    | Boolean false -> "false"
    | Null -> "null"


(** Cast errors should be caught internally and converted to an end usr
    error message *)
exception CastError of string * string (* expected type, actual type *)


let cast_to_symbol (v:json_value) :symbol =
  match v with
      JsonScalar (String sym) -> sym
    | _ -> raise (CastError ("string", type_of_json_value v))

let cast_to_string_option (v:json_value) :symbol option =
  match v with
      JsonScalar (String sym) -> Some sym
    | _ -> raise (CastError ("string", type_of_json_value v))


let cast_to_map (v:json_value) :json_map =
  match v with
      JsonMap m -> m
    | _ -> raise (CastError ("map", type_of_json_value v))

let cast_to_list (v:json_value) :json_value list =
  match v with
      JsonList l -> l
    | _ -> raise (CastError ("list", type_of_json_value v))

let cast_to_scalar (v:json_value) :scalar_val =
  match v with
      JsonScalar s -> s
    | _ -> raise (CastError ("string, int, or boolean", type_of_json_value v))


