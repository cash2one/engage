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

(* $Id: biDirectionalLabeledGraph.ml,v 1.5 2008/05/14 18:26:09 rupak Exp $
 *
 * This file is part of the BLAST Project.
 *)


(**
 * This module gives an implementation of labeled bi-directional Graph.
 * [Jhala]
 *)


(* the node type *)
type ('a, 'b) node = {
  (* the label of this node *)
  mutable node_label  : 'a ;
  (* the edge from the parent of this node to this node *)
  mutable parents : (('a, 'b) edge) list;
  (* this node's children *)
  mutable children : (('a, 'b) edge) list;
}
(* the edge type *)
and ('a, 'b) edge = {
  (* the label of this edge *)
  mutable edge_label : 'b ;
  (* the source of this edge *)
  source     : ('a, 'b) node ;
  target     : ('a, 'b) node ;
}

(**
 * Accessor functions.
 *)
let get_source e = e.source

let get_target e = e.target

let get_node_label n = n.node_label

let get_parents n = List.map get_source n.parents

let get_children n = List.map get_target n.children

let get_edge_label e = e.edge_label

let get_out_edges n = n.children

let get_in_edges n = n.parents

let deconstruct_edge e = (e.source,e.edge_label,e.target)

(**
  * Label mutator functions.
  *)

let set_node_label n nl = n.node_label <- nl

let set_edge_label e el = e.edge_label <- el

 (**
  * Useful predicates on nodes.
  *)
let has_parent n = n.parents != []

let has_child n = n.children != []


(**
 * Node constructors.
 *)

(* root node creation *)
let create_root nl =
  {    node_label  = nl ;
       parents = [] ;
       children = [] }

let make_link src trg el =
  { edge_label = el;
    source = src;
    target = trg;
  }

let exists_edge n1 n2 label =
  let e = { source = n1 ; target = n2; edge_label = label; } in
  List.mem e n1.children

let add_child_edge n e =
  assert ( compare n e.source = 0);
  if (not (List.mem e n.children)) then n.children <- e::n.children

let add_parent_edge n e =
  assert ( compare n e.target = 0);
  if (not (List.mem e n.parents)) then n.parents <- e::n.parents

let hookup_parent_child pn cn el =
  let e = make_link pn cn el in
    add_child_edge pn e;
    add_parent_edge cn e

let delete_parent_child pn cn =
  (* we require that pn, cn be connected *)
  assert (List.mem pn (get_parents cn) && List.mem cn (get_children pn));
  let e = List.find (fun x -> compare x.target  cn = 0) pn.children in
    pn.children <- Misc.list_remove pn.children e;
    cn.parents <- Misc.list_remove cn.parents e

(* child node creation *)
let create_child nl el parent =
  let child = { node_label  = nl ;
                parents = [];
                children = [] }
  in
    hookup_parent_child parent child el

let delete_children parent =
  parent.children <- []; ()

(* must be supplied a non-root node else it barfs *)
let delete_child child =
  List.iter
    (fun parent -> delete_parent_child parent child)
    (get_parents child);
  child.parents <- []

let delete_parent parent =
  List.iter
    (fun child -> delete_parent_child parent child)
    (get_children parent);
  parent.children <- []

let delete_node node =
  delete_child node;
  delete_parent node

let delete_edge edge =
  let pn = edge.source in
  let cn = edge.target in
    pn.children <- Misc.list_remove pn.children edge;
    cn.parents <- Misc.list_remove cn.parents edge


let copy_edge_source node edge =
  hookup_parent_child node edge.target edge.edge_label

let copy_edge_target node edge =
  hookup_parent_child edge.source node edge.edge_label

(* i suppose i should test this function -- RJ *)

let collect_component neighbor_fn n_list =
  let visited_table = Hashtbl.create 31 in
  let visited_list = ref [] in
  let rec _cc (n : ('a, 'b) node) =
    match (Hashtbl.mem visited_table n) with
	true -> ()
      | false ->
	  begin
	    Hashtbl.add visited_table n true;
	    visited_list := n::!visited_list;
	    List.iter _cc (neighbor_fn n)
	  end
  in
    List.iter _cc n_list;
    !visited_list
(* JHALA COMMENT
    (Misc.hashtbl_keys visited_table)
*)

let connected_component n_list =
  collect_component
    (fun x -> ((get_parents x)@(get_children x))) n_list

let descendants n_list = collect_component (fun x -> get_children x) n_list

let ancestors n_list = collect_component (fun x -> get_parents x) n_list

let graph_filter f n =
  List.filter f (connected_component [n])

(** deletes all those nodes that satisfy the predicate f *)
let prune f node_list =
  let to_be_deleted = List.flatten (List.map (graph_filter f) node_list) in
  List.iter (delete_node) to_be_deleted

let sources n = graph_filter (fun x -> not (has_parent x))
let sinks n = graph_filter (fun x -> not (has_child x))

let graph_map f root =
  List.map (fun x-> f x.node_label) (descendants [root])



let ac_output_graph_dot nl_to_string el_to_string cfa_file ns_l_list =
  begin
    let ch = if cfa_file <> "" then open_out cfa_file else stdout in
    let output_edge e =
      let n1s = nl_to_string e.source.node_label in
      let n2s = nl_to_string e.target.node_label in
      let  n1s = List.hd (Misc.bounded_chop n1s "[$][$]" 2) in
      let  n2s = List.hd (Misc.bounded_chop n2s "[$][$]" 2) in

      let es = el_to_string e.edge_label in
      Printf.fprintf ch "  %s -> %s [label=\"%s\"]\n" n1s n2s es
    in
    let visited_table = Hashtbl.create 31 in
    let rec output_node n  =
      let ns = nl_to_string (get_node_label n) in
(* let _ = Message.msg_string Message.Debug ("chopping2: "^ns) in *)
      let ns1, ns2 = Misc.list_only2 (Misc.bounded_chop ns "[$][$]" 2) in
      let ns = Printf.sprintf "%s  [label = \"%s\"]" ns1 ns2 in
      match Hashtbl.mem visited_table ns with
	true -> ()
      | _ ->
	  begin
	    Hashtbl.add visited_table ns true;
	    Printf.fprintf ch "  %s;\n" ns;
	    List.iter
	      (fun e -> output_edge e; output_node e.target)
	      n.children
	  end
    in
    List.iter
    (fun (n_list,name) -> Printf.fprintf ch "digraph %s {\n" name;
        List.iter output_node n_list; Printf.fprintf ch "}\n\n")
    ns_l_list;
    if cfa_file <> "" then close_out ch;
    ()
  end

 let output_graph_dot nls els file n_list =
       ac_output_graph_dot nls els file [(n_list,"main")]

 let output_multi_graph_dot nls els file nl_list =
   ac_output_graph_dot nls els file nl_list


(* using only f successors, find a path from s to t *)
(* requires that different nodes have different node labels *)

let local_connect f source target =
  let _ = print_string "In local_connect" in
  let visited_table = Hashtbl.create 37 in
  let target_node_label = get_node_label target in
  let rec _connect e =
    let _ = print_string "." in
    let s' = get_target e in
    let s'_node_label = get_node_label s' in
      if (s'_node_label = target_node_label) then Some [e]
      else
	if Hashtbl.mem visited_table s'_node_label then None
	else
	  begin
	    Hashtbl.replace visited_table s'_node_label true;
	    match Misc.get_first _connect (f s') with
		None -> None
	      | Some edge_list -> Some (e::edge_list)
	  end
  in
    if (get_node_label source) = target_node_label then Some []
    else
      Misc.get_first _connect (f source)


let get_all_edges_like e =
  let (n1,_,n2) = deconstruct_edge e in
  let n1_out = get_out_edges n1 in
    List.filter (fun e -> get_target e = n2) n1_out

let find_edges n1 n2 =
  if List.mem n2 (get_children n1) then
    List.filter (fun e -> (get_target e = n2)) (get_out_edges n1)
  else []

let hookup_wo_duplicate pn cn elabel =
  let el = find_edges pn cn in
    if List.exists (fun e -> get_edge_label e = elabel) el then ()
    else hookup_parent_child pn cn elabel

(* strongly connected components. ugh. *)
(* given a root, where the graph is the vertices reachable from root,
   computes a node list list where each list is a connected component *)


let scc root =
  (* first we have to copy the graph *)
  let nodes = descendants [root] in
  let size = List.length nodes in
  let visited_table = Hashtbl.create size in
    (* used for dfs *)
  let deleted_table = Hashtbl.create size in
    (* used to "delete" nodes
       -- if a node is in this table,
       then it is considered deleted *)
  let post_number_list = ref [] in
    (* to store the POST number computed by dfs *)
  let post_counter = ref 0 in
  let rec dfs_with_post n =
    if Hashtbl.mem visited_table n then ()
    else
      begin
	Hashtbl.replace visited_table n true; (* mark this node as visited *)
	List.iter dfs_with_post (get_parents n);
	  post_number_list := (n,!post_counter)::!post_number_list;
	  post_counter := !post_counter + 1;
	  ()
      end
  in
  let _ = List.iter dfs_with_post nodes in
     (* now at this point we have all the post numbers *)
  let post_number_list =
    List.sort
      (fun (_,y1) (_,y2) -> y2 - y1)
      !post_number_list
  in
    (* we have the nodes in decreasing order of post number wrt back edges *)
  let succ_fun n =
    List.filter (fun n' -> not (Hashtbl.mem deleted_table n')) (get_children n)
  in
  let gather_scc scc_list (n,_) =
    if Hashtbl.mem deleted_table n then scc_list
    else
      begin
	let this_scc = collect_component succ_fun [n] in
	  List.iter (fun n' -> Hashtbl.replace deleted_table n' true) this_scc;
	  this_scc::scc_list
      end
  in
    List.fold_left gather_scc [] post_number_list


exception Path_found of int

let bfs efilter n_s n_t_opt =
  let hash n = get_node_label n in
  let nth = match n_t_opt with None -> None | Some n_t -> Some (hash n_t) in
  let bfs_table = Hashtbl.create 31 in
  let rec _bfs d wkl =
    let proc n =
      let pk e =
        let e_label = get_edge_label e in
        if not (efilter n e_label ) then None
        else
          let n' = get_target e in
          if Hashtbl.mem bfs_table (hash n') then None
          else (Hashtbl.add bfs_table (hash n') (n',d+1,n,Some e_label);Some n')
      in
      if (compare (Some (hash n))  nth = 0) then raise (Path_found d)
      else Misc.map_partial pk (get_out_edges n)
    in
    if wkl = [] then ()
    else let wkl' = List.flatten (List.map proc wkl) in _bfs (d+1) wkl'
  in
  let rec get_rev_path (d,n) =
    (* Printf.printf "grp: %d" d;*)
    if d = 0 then [] else
      try
        (* assert no match failure *)
        let (_,d',n',el'_o) = Hashtbl.find bfs_table (hash n) in
        (n',Misc.some Misc.id el'_o)::(get_rev_path (d'-1,n'))
      with Not_found -> failwith "bfs: no parent in bfs_table!"
  in
  try
    Hashtbl.add bfs_table (hash n_s) (n_s,0,n_s,None);
    ignore(_bfs 0 [n_s] );
    (List.map (fun (_,(n,d,_,_))-> (n,d)) (Misc.hashtbl_to_list bfs_table),[])
  with (Path_found d) ->
    (match n_t_opt with Some n_t ->  ([], List.rev (get_rev_path (d,n_t)))
    | None -> failwith "bfs impossible")

let shortest_path efilter n_s n_t = snd (bfs efilter n_s (Some n_t))

let shortest_path_lengths n = fst (bfs (fun x y -> true) n None)


