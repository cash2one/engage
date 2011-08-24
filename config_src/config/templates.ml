(** Parsing of string templates *)

type parsed_string =
    String of string
  | Reference of string
  | Template of string * (string list)

(** pattern used to match variable references in strings *)
let variable_pat = "\\${\\([0-9]\\|[a-z]\\|[A-Z]\\|_\\|\\.\\)+}"


let source_only_re = Str.regexp ("^" ^ variable_pat ^ "$")

(** Return true if the entire string is a variable (used for source references) *)
let is_source s = Str.string_match source_only_re s 0

(** Pattern for an escaped dollar sign *)
let dollar_escape_pat = "\\$\\$"


(** Regular expression for matching both variable references or dollar escapes ($$) *)
let search_re = Str.regexp ("\\(" ^ variable_pat ^ "\\)\\|\\(" ^
                              dollar_escape_pat ^ "\\)")

(** Extract the variable name from a variable reference of the form ${var} *)
let extract_var_name str =
  String.sub str 2 ((String.length str)-3)

(** Figure out whether the string is a plain old string, a variable
    reference, or a template. *)
let parse_string (str:string) :parsed_string =
  if is_source str then Reference (extract_var_name str)
  else 
    let variables = ref []
       and result = ref ""
       and idx = ref 0
       and len = String.length str in
      begin
        (try
           while !idx < len do
             let match_start = Str.search_forward search_re str !idx in
             let match_end = Str.match_end () in
               result := !result ^
                         (String.sub str !idx (match_start - (!idx)));
               (match String.sub str match_start (match_end-match_start) with
                    "$$" -> result := !result ^ "$"
                  | var_ref -> begin
                      result := !result ^ var_ref;
                      variables := (extract_var_name var_ref)::(!variables)
                    end);
               idx := match_end
           done
         with Not_found ->
           result :=  !result ^ (String.sub str !idx (len- (!idx))));
        match !variables with
            [] ->
              (* Return the escaped string *)
              String (!result)
          | lst ->
              (* Note that, for templates, we discard the escaped string
                 and return the original string. We are going to need
                 the escapes when we do substition later. *)
              Template (str, lst)
      end

(** Perform template substitutions on the string using the specified lookup
    function to get the values for template variables. *)
let substitute_template (str:string) (lookup_fn:string->string)
    :string =
  let result = ref ""
  and idx = ref 0
  and len = String.length str in
    (try
       while !idx < len do
         let match_start = Str.search_forward search_re str !idx in
         let match_end = Str.match_end () in
           result := !result ^
             (String.sub str !idx (match_start - (!idx)));
           (match String.sub str match_start (match_end-match_start) with
                "$$" -> result := !result ^ "$"
              | var_ref ->
                  let value = lookup_fn (extract_var_name var_ref) in
                    result := !result ^ value);
           idx := match_end
       done
     with Not_found ->
       result :=  !result ^ (String.sub str !idx (len- (!idx))));
    !result
