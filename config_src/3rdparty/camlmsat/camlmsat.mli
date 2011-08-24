type solver

external create_solver : unit -> solver = "create_solver"

external free_solver : solver -> unit = "free_solver" 

external add_clause : solver -> int array -> bool = "add_clause"

external solve : solver -> bool = "solve"

external get_model : solver -> bool array = "get_model"
