#!/usr/bin/env python3
"""
Copyright (c) 2020, Rob Egan
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of the <organization> nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.
    * Dorothy Haraminac, and any of her affliates not limited to GreenVets, LLC,
      or any entity that has employed Dorothy Haraminac or any entity employed by
      her or performing any work in her interests are prohibited from any use,
      redistribution or modification of this code

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import pygraphviz as pgv
import json
import sys
import os
import urllib.request
import time
import math

# wait 15 seconds per query to blockchain to not get banned
min_request_delay = 15 
last_request_time = time.time() - 14
lookup_addr_url= "https://blockchain.info/rawaddr/"
lookup_tx_url = "https://blockchain.info/rawtx/"
cache_dir = "data/addresses"

# constants and options
satoshi = 100000000   # 100 M satoshi per BTC
min_draw_val = 0.0001  # minimum sum of transactions to add an edge to the graph (all transactions are always counted, just not drawn)
display_len = 8
by_wallet = True      # if true all addresses in a wallet are a single node
cluster_own = False   # do not constrain drawing of own wallets
cluster_thirdParty = True  # group drawing of 3rd party wallets
save_addresses_in_dot = True
verbose = False
debug_mode = False

# whether to add suggestions for other addresses to be included in existing wallets
suggest_irrelevant = False
suggest_change = True
suggest_thirdparty = True
suggest_mergable = False

# what labels to include
label_3rdto3rd = True
label_income = True
label_expense = True

# the maxumum day since epoch to include, or all if None
max_date = None # 1587742790 / 3600.0 / 24.0 

unknown = 'Not Tracked'
COINBASE = "NEW COINBASE (Newly Generated Coins)"
FEES = "TransactionFees"
OWN = "Own"

# global variables
mergable_wallets = dict()
suggest_additional_own_address = dict()
inputs = dict()
outputs = dict()
balances = dict()
transactions = dict()
wallets = dict()
rev_wallet = dict()
addresses = dict()
def reset_global_state():
    mergable_wallets.clear()
    inputs.clear()
    outputs.clear()
    balances.clear()
    transactions.clear()
    wallets.clear()
    rev_wallet.clear()
    addresses.clear()

def get_tx(txid):
    if txid in transactions:
        return transactions[txid]
    else:
        return None

def parse_tx(rawtx):
    """
    Takes a single raw json transaction and returns a tuple 
    (ins=[], outs=[], fee=float, date=float)
    """
    txid = rawtx['hash']
    if txid in transactions:
        return transactions[txid]
    
    if verbose:
        print("txid:", txid)
    outs = []
    ins = []
    fee = None
    total = 0
    time = rawtx['time'] / 3600.0 / 24.0
    for input in rawtx['inputs']:
        if 'prev_out' not in input:
            break # coinbase transaction
        prev_out = input['prev_out']
        if 'addr' in prev_out: # segwit
            ins.append( (prev_out['addr'], prev_out['value']/satoshi) )
        else:
            if verbose:
                print("segwit input")
        total += prev_out['value']/satoshi
    for output in rawtx['out']:
        if 'addr' in output: # segwit
            outs.append( (output['addr'], output['value']/satoshi) )
        else:
            if verbose:
                print('segwit output')
        total -= output['value']/satoshi
    fee = total
    if len(ins) == 0 and fee < 0:
        # special coinbase generation
        ins.append( (COINBASE, -fee) )
        fee = 0
        if verbose:
            print("COINBASE", outs)
    inoutfeetime = (ins, outs, fee, time)
    if max_date is None or time < max_date:
        transactions[txid] = inoutfeetime
    else:
        print("Skipping transaction after max_date(", max_date, "), :", inoutfeetime)
    return inoutfeetime

def add_to_wallet(wallet, addr):
    if not addr in wallets:
        wallets[wallet] = dict()
    wallets[wallet][addr] = True
    rev_wallet[addr] = wallet
    
def store_addr(addr, addr_json, wallet = None):
    assert( addr not in addresses )
    addresses[addr] = addr_json
    if 'txs' in addr_json:
        for tx in addr_json['txs']:
            try:
                transaction = parse_tx(tx)
            except:
                print("Could not parse transaction: ", tx)
                raise
    if by_wallet and wallet is not None:
        add_to_wallet(wallet, addr)
    
def load_addr(addr, wallet = None, get_all_tx = True, get_any_tx = True):
    """
    looks up in local file cache or blockchain.com the transactions for address
    stores in cache if blockchain.com returned data
    """
    
    global last_request_time
    if addr in addresses:            
        if verbose:
            print("Found ", addr, " in memory")
        return
    if not get_any_tx:
        store_addr(addr, dict(), wallet)
        return []
    
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    
    n_tx = 0
    all_txs = None
    offset = 0
    addr_json = None
    max_n_tx = 10000 # some addresses have 10000s of transactions and we can not download them all
    if not get_all_tx: # do not need to track every transaction that only just touched own wallet
        max_n_tx = 50
    while offset == 0 or n_tx > len(all_txs):
        if offset > max_n_tx:
            break # blockchain won't respond to this excessively used addresses

        print(addr, "offset=", offset)
        cache = cache_dir + "/%s.json" % (addr)
        if offset > 0:
            cache = cache_dir + "/%s-%d.json" % (addr,offset)
        if verbose:
            print ("Checking for cached addr:", addr , "at offset", offset, "in", cache)
    
        if not os.path.exists(cache):
            url = lookup_addr_url + addr
            if offset > 0:
                url += "?&limit=50&offset=%d" % (offset)
            wait_time = time.time() - last_request_time
            if wait_time < min_request_delay:
                wait_time = min_request_delay - wait_time
                print("Waiting to make next URL API request: ", wait_time)
                time.sleep(wait_time)
            print("Downloading everything about ", addr, " from ", url)
            
            # raise an error if we need to re-download some data to avoid getting blocked by blockchain.com while debugging
            if debug_mode:
                raise "Where did addr=%s come from?" % (addr)
            
            urllib.request.urlretrieve(url, cache)
            last_request_time = time.time()
        with open(cache) as fh:
            tmp_addr_json = json.load(fh)
            if all_txs is None:
                all_txs = tmp_addr_json['txs']
                addr_json = tmp_addr_json
            else:
                if verbose:
                    print("Extending existing transactions=",len(addr_json['txs']), "plus", len(tmp_addr_json['txs']))
                all_txs.extend(tmp_addr_json['txs'])
                addr_json['txs'] = all_txs
                
        assert(addr_json is not None)
        offset += len(tmp_addr_json['txs'])
        if n_tx == 0:
            n_tx = addr_json['n_tx']
        if verbose:
            print("Found", addr, "with", n_tx, "transactions")
        if n_tx == 0:
            break

    if n_tx < max_n_tx:
        assert(n_tx == addr_json['n_tx'])
        assert(n_tx == 0 or n_tx == len(addr_json['txs']))
    store_addr(addr, addr_json, wallet)

    return addresses[addr]['txs']
    

def sanitize_addr(tx):
    """
    replaces address with a known wallet label or To/From unknown
    """
    ins, outs, fee, time = tx
    ins2 = []
    outs2 = []
    from_self = False
    to_self = False
    known_in = None
    known_out = None
    unknown_in = []
    unknown_out = []
    
    for i in ins:
        addr, val = i
        orig_addr = addr
        if not addr in addresses:
            addr = "From " + unknown
            unknown_in.append(orig_addr)
        else:
            if addr in rev_wallet:
                orig_addr = addr
                addr = rev_wallet[addr]
                if addr[0] != '@':
                    from_self = True
                if known_in is None:
                    known_in = addr
                if known_in != addr:
                    if not from_self:
                        print("WARNING: MIXED account: addr", orig_addr, "is from wallet", addr, "but other inputs are from wallet", known_in, ". tx:", tx)
                    if from_self:
                        if addr < known_in:
                            mergable_wallets[addr + " and " + known_in] = True
                        else:
                            mergable_wallets[known_in + " and " + addr] = True
                        if suggest_mergable:
                            print("INFO: Suggest MERGE two", OWN, "wallets share a transaction, this is okay but can be confusing:", orig_addr, addr, known_in, tx)
            else:
                unknown_in.append(orig_addr)
                addr = addr[0:display_len]
        ins2.append((addr, val))
    if known_in is not None:
        for i in ins:
            addr, val = i
            if not addr in rev_wallet:
                suggest_additional_own_address[addr] = known_in
    for i in outs:
        addr, val = i
        orig_addr = addr
        if not addr in addresses:
            addr = "To " + unknown
            unknown_out.append(orig_addr)
        else:
            if addr in rev_wallet:
                addr = rev_wallet[addr]
                if addr[0] != '@':
                     to_self = True
                known_out = addr
            else:
                addr = addr[0:display_len]
                unknown_out.append(orig_addr)
        outs2.append((addr, val))
    if known_in is not None and (known_in[0] != '@' or suggest_thirdparty):
        if len(unknown_in) > 0 and (suggest_irrelevant or known_out is not None):
            print("Suggestion: append associated addresses to", known_in, ":", unknown_in)
        if len(outs) > 1 and len(unknown_out) == 1 and suggest_change and (suggest_irrelevant or known_out is not None):
            print("Suggestion: perhaps this is a change address for", known_in, ":", unknown_out)
    return (ins2, outs2, fee, time), from_self, to_self

def record_balances(inaddr, outaddr, xferval, ownIn = False, ownOut = False):
    """
    tracks balance, inputs and outputs
    only own addresses can have accurate numbers, as 3rd party wallets are largely unknown
    """
    
    if inaddr == outaddr or xferval == 0.0:
        return
    if not unknown in inaddr:
        balances[inaddr] -= xferval
        if ownIn:
            outputs[inaddr] += xferval
            if not unknown in outaddr and not ownOut:
                # also track input from other
                inputs[outaddr] += xferval
            
    if not unknown in outaddr:
        balances[outaddr] += xferval
        if ownOut:
            inputs[outaddr] += xferval
            if not unknown in inaddr and not ownIn:
                # also track output from other
                outputs[inaddr] += xferval

    
def append_edge(G, inaddr, outaddr, xferval, count = 1):
    """
    Add an edge to the graph accumulate counet and weight attributes
    """
    
    G.add_edge(inaddr, outaddr)
    edge =  G.get_edge(inaddr, outaddr)
    # attributes are strings
    if edge.attr['count'] is None or edge.attr['count'] == '':
        #print("Initializing edge", edge)
        edge.attr['count'] = "0"
        edge.attr['weight'] = "0.0"
    edge.attr['count'] = str(int(edge.attr['count']) + count)
    edge.attr['weight'] = str(float(edge.attr['weight']) + xferval)
    


def add_tx_to_graph(G, txid):
    """
    Add all the micro transactions between the input(s) and output(s) to the graph
    take care not to double count and report if important unknown addresses are included"
    """
    
    tx = transactions[txid]
    orig_in, orig_outs, fee, time = tx
    tx, from_self, to_self = sanitize_addr(tx)
    if verbose:
        print("Adding transaction ", "From Self" if from_self else "", "To Self" if to_self else "", txid, " ", tx, 'original:', orig_in, orig_outs)
    has_unknown = None
    known_in = dict()
    known_out = dict()
    total_xfer = 0
    ins, outs, fee, time = tx
    if from_self:
        balances[FEES] -= fee
        if verbose:
            print("Applying transaction fee", fee, " total ", balances[FEES])
    invalues=dict()
    outvalues=dict()
    
    # copy the input and output values
    for i in ins:
        inaddr, inval = i
        if inaddr not in invalues:
            invalues[inaddr] = 0
        invalues[inaddr] += inval
    for o in outs:
        outaddr, outval = o
        if outaddr not in outvalues:
            outvalues[outaddr] = 0
        outvalues[outaddr] += outval
    
    for i in ins:
        inaddr, orig_inval = i
        if invalues[inaddr] <= 0:
            # no remaining amount in inaddr to send
            continue
        inval = invalues[inaddr]
        for o in outs:
            assert(inval >= 0.0)
            if inval == 0.0:
                break
            
            outaddr, orig_outval = o
            if outvalues[outaddr] <= 0:
                # no remaining amount to receive
                continue
            outval = outvalues[outaddr]
            
            # calculate the micro transaction between a single input and a single output address
            xferval = outval
            if inval <= outval:
                xferval = inval
            
            outval -= xferval
            inval -= xferval     
            
            invalues[inaddr] = inval
            outvalues[outaddr] = outval
            
            if inaddr == outaddr:
                # noop transaction do not add an edge, change ins or outs or balances
                continue

            if inaddr == unknown and outaddr == unknown:
                # neither address is tracked
                # do not add an edge or track balances
                continue

            # At least some parts of this transaction are being tracked
            record_balances(inaddr, outaddr, xferval, from_self, to_self)
     
                
            if unknown in inaddr:
                if unknown in outaddr or outaddr[0] == '@':
                    # unknown -> thirdparty destination
                    # do not add an edge
                    continue 
                # otherwise log it
                has_unknown = "FROM"
            else:
                if inaddr not in known_in:
                    known_in[inaddr] = 0
                known_in[inaddr] -= xferval
                
            if unknown in outaddr:
                if unknown in inaddr or inaddr[0] == '@':
                    # unkown or thirdparty -> unknown destination
                    # do not add an edge
                    continue
                # otherwise log it
                has_unknown = "TO"
            else:
                if outaddr not in known_out:
                    known_out[outaddr] = 0
                known_out[outaddr] += xferval
                
            if xferval > 0 and xferval >= min_draw_val:
                if verbose:
                    print("add edge", inaddr, outaddr, xferval)
                append_edge(G, inaddr, outaddr, xferval)
            else:
                if verbose:
                    print("Skipped tiny edge", inaddr, outaddr, xferval)
            total_xfer += xferval
            
    print("Added a total of ", total_xfer, " for this set of edges from", known_in, "to", known_out)

    if has_unknown is not None and total_xfer > 0 and total_xfer > min_draw_val:
        print("unknown", has_unknown, ": in=", known_in.keys(), " out=", known_out.keys(), "tx=", orig_in, " => ", orig_outs)

def set_balances(wallet):
    balances[wallet] = 0.0
    inputs[wallet] = 0.0
    outputs[wallet] = 0.0

def set_node_labels(G, n):
    """
    Apply pretty labels to a node
    """
    
    node = G.get_node(n)
    is_own = str(n)[0] != '@'
    if True:
        node.attr['input'] = inputs[n]
        node.attr['output'] = outputs[n]
        node.attr['label'] = '%s' % (n)
        if inputs[n] > 0.0:
            node.attr['label'] += "\nin=%0.3f" % (inputs[n])
        if outputs[n] > 0.0:
            node.attr['label'] += "\nout=%0.3f" % (outputs[n])
        if is_own and unknown not in n:
            node.attr['label'] += "\nbal=%0.3f" % (balances[n])

        if is_own and unknown not in n:
            # only color own wallets
            if balances[n] > 0 and balances[n] >= min_draw_val:
                node.attr['color'] = 'green'
            elif round(balances[n],3) < 0.0:
                node.attr['color'] = 'red'
            else:
                node.attr['color'] = 'yellow'
    else:
        node.attr['color'] = 'blue'

def set_edge_labels(G, e, own_nodes, not_own_nodes):
    """
    apply pretty lables to an edge
    """
    
    f,t = e
    from_own = True if f in own_nodes else False
    from_third = True if f in not_own_nodes else False
    to_own = True if t in own_nodes else False
    to_third = True if t in not_own_nodes else False
        
    if from_third and to_third :
        # display this ThirdParty to Thirdparty edge as the value is not otherwise tracked
        if label_3rdto3rd:
            e.attr['label'] = "%0.3f" % (float(e.attr['weight']))
            e.attr['fontcolor'] = 'purple'
        e.attr['color'] = 'purple'
        e.attr['style'] = 'dashed'
    elif from_own and to_own :
        # Own to Own
        e.attr['style'] = "dotted"
    elif to_own:
        # to Own
        if label_income:
            e.attr['label'] = "%0.3f" % (float(e.attr['weight']))
            e.attr['fontcolor'] = 'green'
        e.attr['color'] = 'green'
    elif from_own:
        # from Own
        if label_expense:
            e.attr['label'] = "%0.3f" % (float(e.attr['weight']))
            e.attr['fontcolor'] = 'red'
        e.attr['color'] = 'red'
    
""" TODO
import argparser
def parse_args():
    argparser = argparse.ArgumentParser(add_help=False)
    
    argparser.add_argument("wallets", metavar='N', type=str, nargs='+', help="List of wallet files (see below for naming scheme and how it affects display)")
    argparser.add_argument("--min-draw", dest=min_draw_val, default=min_draw_val, type=int, help="Minimum sum of transactions to draw a link")
    argparser.add_argument("--by-address", dest=by_wallet, default=True, const=False, type=bool, help="Nodes are by address, not grouped by wallet" )
    argparser.add_argument("--verbose", dest=verbose, default=False, const=True, type=bool, help="Extra verbosity to print out transaction data while parsing")
    argparser.add_argument("--debug", dest=debug_mode, default=False, const=True, type=bool, help="Additional debug information")
    argparser.add_argument("--no-label-income", dest=label_income, default=True, const=False, type=bool, help="Do not label incoming transactions to own wallet")
    argparser.add_argument("--no-label-outgoing", dest=label_expanse, default=True, const=False, type=bool, help="Do not label outgoing transactions from own wallet")
    

    options, unknown_options = argparser.parse_known_args()
    if unknown_options is not None:
        raise
    return options
"""

def add_legend(G):
    G.add_subgraph(name="cluster_LEGEND", label="Legend", rank="sink")
    sg = G.get_subgraph("cluster_LEGEND")
    sg.add_node("FromOwn", shape="plaintext", rankdir="LR")
    sg.add_node("ToOwn  ", shape="plaintext", rankdir="LR")
    sg.add_edge("FromOwn", "ToOwn  ", style="dotted", rankdir="LR")
    
    sg.add_node("FromOwn    ", shape="plaintext", rankdir="LR")
    sg.add_node("To3rdParty ", shape="plaintext", rankdir="LR")   
    sg.add_edge("FromOwn    ", "To3rdParty ", color="red", rankdir="LR")
    
    sg.add_node("From3rdParty ", shape="plaintext", rankdir="LR")
    sg.add_node("ToOwn        ", shape="plaintext", rankdir="LR")
    sg.add_edge("From3rdParty ","ToOwn        ",  color="green", rankdir="LR")
    
    
    sg.add_node("From3rdParty", shape="plaintext", rankdir="LR")
    sg.add_node("To3rdParty  ", shape="plaintext", rankdir="LR")
    sg.add_edge("From3rdParty", "To3rdParty  ",  color="purple", style="dashed", rankdir="LR")

  
def process_wallets(output_file_name, wallet_files, collapse_own = False, only_own = False):
    
    reset_global_state()
    print("Preparing graph for:", output_file_name, "collapse_own:", collapse_own, "only_own:", only_own, "wallet_files:", wallet_files)
    
    # special case of coinbase "address"
    newcoin_wallet = "@NewCoins"
    addresses[COINBASE] = None
    add_to_wallet(newcoin_wallet, COINBASE)
    set_balances(newcoin_wallet)
    set_balances(COINBASE)

    own_nodes = []
    not_own_nodes = []

    G = pgv.AGraph(directed=True, landscape=False)
    
    add_legend(G)
    
    own_name = "cluster_" + OWN
    G.add_subgraph(name=own_name, label=OWN, style="filled", fillcolor="lightgrey")
    own_subgraph = G.get_subgraph(own_name)

    thirdParty_name = "ThirdParty"
    G.add_subgraph(name=thirdParty_name, label="ThirdParty")
    thirdParty_subgraph = G.get_subgraph(thirdParty_name)

    own_subgraph.add_node(FEES)
    set_balances(FEES)
    own_nodes.append(FEES)

    
    # Origin / Coinbase are in neither OWN nor ThirdParty
    if by_wallet:
        G.add_node(newcoin_wallet)
    else:
        G.add_node(COINBASE, wallet=newcoin_wallet)
        
    # untracked are in neither OWN nor ThirdParty; they are unknown
    G.add_node("From " + unknown, wallet="Untracked")
    set_balances("From " + unknown)
    from_unknown_node = G.get_node("From " + unknown)
    G.add_node("To " + unknown, wallet="Untracked")
    set_balances("To " + unknown)
    to_unknown_node = G.get_node("To " + unknown)
    
    if collapse_own:
        own_subgraph.add_node(OWN)
        set_balances(OWN)
        own_nodes.append(OWN)
        
    # load all the wallets and addresses contained in the wallet files
    for f in wallet_files:
        print("Inspecting file: ", f);
        wallet = os.path.basename(f)
        wallet, ignored = os.path.splitext(wallet)
    
        is_own = wallet[0] != '@'
        if only_own and not is_own:
            print("Skipping ThirdParty file", f)
            continue
        
        topsubgraph = own_subgraph if is_own else thirdParty_subgraph
        subgraph = topsubgraph
        
        # further subgraph if the wallet contains a dash
        x = wallet.split('-')
        if len(x) > 1 and not collapse_own:
            name_id, name = wallet.split('-')
            if cluster_own and is_own:
                # impose drawing restrictions
                subgraph_name = "cluster_" + name
            elif cluster_thirdParty and not is_own:
                subgraph_name = "cluster_" + name
            else:
                subgraph_name = name
            subgraph = G.get_subgraph(subgraph_name)
            if subgraph is None:
                topsubgraph.add_subgraph(subgraph_name, name=subgraph_name, label=name)
                subgraph = topsubgraph.get_subgraph(subgraph_name)
                print("Created subgraph", name, "within", OWN if is_own else "ThirdParty")
            print("wallet", wallet, "is of subgraph", name)

            
        if is_own and collapse_own:
            print("Collapsing wallet", wallet, "to", OWN)
            wallet = OWN
        elif by_wallet:
            print("Adding wallet:", wallet)
            subgraph.add_node(wallet)
            set_balances(wallet)
            
        if by_wallet:
            if is_own:
                if wallet not in own_nodes:
                    own_nodes.append(wallet)
            else:
                if wallet not in not_own_nodes:
                    not_own_nodes.append(wallet)
        
        wallet_addresses = []
        print("Opening f=", f, " wallet=", wallet)
        with open(f) as fh:
            for addr in fh.readlines():
                addr = addr.strip();            
                print(addr)
                get_all_tx = True
                get_any_tx = True
                if addr[0] == '#':
                    # do not lookup any transactions
                    addr = addr[1:]
                    get_all_tx = False
                    get_any_tx = False
                if not is_own:
                    # not own, do not exhastively lookup all transactions
                    get_all_tx = False
                
                txs = load_addr(addr, wallet, get_all_tx, get_any_tx)
                if not by_wallet:
                    subgraph.add_node(addr, wallet=wallet)
                    set_balances(addr)

                    if is_own:
                        own_nodes.append(addr)
                    else:
                        not_own_nodes.append(addr)
                else:
                    wallet_addresses.append(addr)
        
        # save the addresses in the .dot file
        if save_addresses_in_dot and by_wallet and len(wallet_addresses) > 0:
            n = G.get_node(wallet)
            if n.attr['addresses'] is not None:
                n.attr['addresses'] += ","
            else:
                n.attr['addresses'] = ""
            n.attr['addresses'] += ",".join(wallet_addresses)
    
    # apply all the recorded transactions to the graph
    for txid in transactions.keys():
        add_tx_to_graph(G, txid)
 
    # add balance labels to fully tracked nodes
    for n in G.nodes():
        if unknown in n:
            continue
        if n in balances:
            print("Balance for", n, round(balances[n],3))
            set_node_labels(G, n)
    
    # add edge labels
    for e in G.edges():
        set_edge_labels(G, e, own_nodes, not_own_nodes)
        
    if verbose:
        print("Graph:", G)
        print("\tnodes.data:", G.nodes())
        print("\tedges.data:", G.edges())
    
    for mergable in mergable_wallets.keys():
        print("INFO: Suggest MERGE these OWN wallets:", mergable)
    
    set_node_labels(G,to_unknown_node)
    set_node_labels(G,from_unknown_node)
    
    print("Writing full graph:", output_file_name)
    G.write(output_file_name)
    G.clear()

    
  

if __name__ == "__main__":
    args = sys.argv[1:]
    if not by_wallet:
        display_len = 50
    
    process_wallets("mywallet.dot", args)
    for i in suggest_additional_own_address:
        print("INFO: Suggest ADD ", i, " to wallet ", suggest_additional_own_address[i])
    process_wallets("mywallet-own.dot", args, only_own = True)
    process_wallets("mywallet-simplified.dot", args, collapse_own = True)
    print('Finished')
