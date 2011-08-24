
type constraint_t = INSIDE | ENVIRONMENT | PEER
type key     = (Resources.symbol * Resources.scalar_val) list
type instance = key * Resources.symbol
type resource_graph_node_data_t = instance * instance
type resource_graph_edge_data_t = constraint_t * int * int
type resource_graph_node_t = (resource_graph_node_data_t, resource_graph_edge_data_t) BidirectionalLabeledGraph.node

val parse_json_file : string -> Resources.json_value
val read_rdefs_from_file : string -> Resources.resource_def list
val read_install_spec_from_file : string -> Resources.resource_inst list

val generate : Resources.resource_def list -> Resources.resource_inst list ->
  ((* model *) Predicates.pred_model *
   (* id to node table *)  (int, instance * instance) Hashtbl.t *
   (* node to id table *)  (instance * instance, int) Hashtbl.t *
   (* node list in topo order *)
     (instance * instance, 
      constraint_t * int * int)
     BidirectionalLabeledGraph.node list)


(** given a resource instance to be installed, return its configuration ports
    together with values specified for these ports
*)
val get_config_ports : bool -> Resources.resource_def -> Resources.resource_inst -> Resources.json_value

class type ['a] inst_iterator =
  object
    val mutable leftlist : 'a list
    val mutable rightlist : 'a list
    method has_next : unit -> bool
    method has_prev : unit -> bool
    method next : unit -> 'a
    method prev : unit -> 'a
end

class type config_engine =
  object

    val mutable current_node :
        ((instance * instance, constraint_t * int * int)
        BidirectionalLabeledGraph.node) option

    val id_node_tbl :
        (int,  instance * instance) Hashtbl.t

    val node_id_tbl :
        (instance * instance, int) Hashtbl.t

    val mutable node_iterator :
        (instance * instance, constraint_t * int * int)
        BidirectionalLabeledGraph.node inst_iterator

    val pmodel : Predicates.pred_model

    val topo_list :
        (instance * instance, constraint_t * int * int)
        BidirectionalLabeledGraph.node list

  method private get_current_inst : unit -> Resources.resource_inst

  method has_next : unit -> bool
  method has_prev : unit -> bool
  method next : unit -> bool
  method prev : unit -> bool

  method reinit : unit -> unit

  method get_config_port_types_as_string : unit -> string
  method get_config_ports_as_string : unit -> string
  method set_config_ports_from_string : string -> unit
  method set_ports : string -> string -> unit
  method set_ports_of_current : unit -> unit

  method get_resource : string -> string -> string
  method get_current_resource : unit -> string
  method write_install_file : string -> unit
end


class config_engine_factory :
      Predicates.pred_model ->
	(instance * instance, int) Hashtbl.t ->
	(int, instance * instance) Hashtbl.t ->
  (instance * instance,
   constraint_t * int * int)
    BidirectionalLabeledGraph.node list ->
  config_engine
