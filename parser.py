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


lookup_addr_url= "https://blockchain.info/rawaddr/"
lookup_tx_url = "https://blockchain.info/rawtx/"

satoshi = 100000000
min_request_delay = 15
last_request_time = time.time()
display_len = 8
by_wallet = True
cluster_own = False
cluster_thirdParty = True

unknown = 'Not Tracked'
COINBASE = "NEW COINBASE (Newly Generated Coins)"
FEES = "TransactionFees"

inputs = dict()
outputs = dict()
balances = dict()
transactions = dict()
def get_tx(txid):
    if txid in transactions:
        return transactions[txid]
    else:
        return None

def parse_tx(rawtx):
    txid = rawtx['hash']
    if txid in transactions:
        return transactions[txid]
    
    print("txid:", txid)
    #print(rawtx)
    outs = []
    ins = []
    fee = None
    total = 0
    time = rawtx['time'] / 3600 / 24
    for input in rawtx['inputs']:
        if 'prev_out' not in input:
            break # coinbase transaction
        prev_out = input['prev_out']
        #print(prev_out)
        if 'addr' in prev_out: # segwit
            ins.append( (prev_out['addr'], prev_out['value']/satoshi) )
        else:
            print("segwit input")
        total += prev_out['value']/satoshi
    for output in rawtx['out']:
        #print(output)
        if 'addr' in output: # segwit
            outs.append( (output['addr'], output['value']/satoshi) )
        else:
            print('segwit output')
        total -= output['value']/satoshi
    fee = total
    if len(ins) == 0 and fee < 0:
        # special coinbase generation
        ins.append( (COINBASE, -fee) )
        fee = 0
        print("COINBASE", outs)
    inoutfeetime = (ins, outs, fee, time)
    #print("parse_tx txid=", txid, " got:", inoutfee)
    transactions[txid] = inoutfeetime;
    return transactions[txid]

wallets = dict()
rev_wallet = dict()
def add_to_wallet(wallet, addr):
    if not addr in wallets:
        wallets[wallet] = dict()
    wallets[wallet][addr] = True
    rev_wallet[addr] = wallet
    #print("set ", addr, " to ", wallet)
    
addresses = dict()
def store_addr(addr, addr_json):
    assert( addr not in addresses )
    addresses[addr] = addr_json
    for tx in addr_json['txs']:
        try:
            transaction = parse_tx(tx)
        except:
            print("Could not parse transaction: ", tx)
            raise
        #print(transaction)
    
def load_addr(addr, wallet = None, get_all_tx = True):
    global last_request_time
    if addr in addresses:            
        print("Found ", addr, " in memory")
        return
    
    n_tx = 0
    all_txs = None
    offset = 0
    addr_json = None
    max_n_tx = 10000 # some addresses have 10000s of transactions and we can not download them all
    if not get_all_tx: # do not need to track every transaction that only just touched own wallet
        max_n_tx = 50
    while offset == 0 or n_tx > len(all_txs):
        if offset > max_n_tx:
            break # blockchain won't respond to this excessively used address
        
        #n_txs = test_addr['n_tx']
        #all_txs = test_addr['txs']
        #while n_txs != len(all_txs):
        #    print("Downloading missing transactions", n_txs - len(all_txs), " starting at", n_txs)
        #    old_txs = test_addr['']
        #    more_txs = load_addr(addr, wallet, num_txs)
        #    all_txs.extend(more_txs)
        #    addresses[addr]['txs'] = all_txs

        cache = "data/addresses/%s.json" % (addr)
        if offset > 0:
            cache = "data/addresses/%s-%d.json" % (addr,offset)
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
            # raise("Where did %s come from?" % (addr))
            urllib.request.urlretrieve(url, cache)
            last_request_time = time.time()
        with open(cache) as fh:
            tmp_addr_json = json.load(fh)
            if all_txs is None:
                all_txs = tmp_addr_json['txs']
                addr_json = tmp_addr_json
            else:
                print("Extending existing transactions=",len(addr_json['txs']), "plus", len(tmp_addr_json['txs']))
                all_txs.extend(tmp_addr_json['txs'])
                addr_json['txs'] = all_txs
                
        offset += len(tmp_addr_json['txs'])
        if n_tx == 0:
            n_tx = addr_json['n_tx']
        print("Found", addr, "with", n_tx, "transactions")
    
    if n_tx < max_n_tx:
        assert(n_tx == addr_json['n_tx'])
        assert(n_tx == len(addr_json['txs']))
    store_addr(addr, addr_json)
        
    if by_wallet and wallet is not None:
        add_to_wallet(wallet, addr)
    return addresses[addr]['txs']
    

def sanitize_addr(tx):
    # sanitize for unknown
    #print(tx)
    ins, outs, fee, time = tx
    ins2 = []
    outs2 = []
    from_self = False
    to_self = False
    for i in ins:
        addr, val = i
        if not addr in addresses:
            addr = "From " + unknown
        else:
            if addr in rev_wallet:
                addr = rev_wallet[addr]
                if addr[0] != '@':
                    from_self = True
            else:
                addr = addr[0:display_len]
        ins2.append((addr, val))
    for i in outs:
        addr, val = i
        if not addr in addresses:
            addr = "To " + unknown
        else:
            if addr in rev_wallet:
                addr = rev_wallet[addr]
                if addr[0] != '@':
                     to_self = True
            else:
                addr = addr[0:display_len]
        outs2.append((addr, val))
    return (ins2, outs2, fee, time), from_self, to_self

def record_balances(inaddr, outaddr, xferval, ownIn = False, ownOut = False):
    if inaddr == outaddr:
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

    
def append_edge(G, inaddr, outaddr, xferval):
    G.add_edge(inaddr, outaddr)
    edge =  G.get_edge(inaddr, outaddr)
    if not 'count' in edge:
        edge.attr['count'] = 1
        edge.attr['weight'] = xferval
    else:
        edge.attr['count'] += 1
        edge.artr['weight'] += xferval
    


min_val = 0.01
def add_tx_to_graph(G, txid):
    tx = transactions[txid]
    orig_in, orig_outs, fee, time = tx
    tx, from_self, to_self = sanitize_addr(tx)
    print("Adding transaction ", "From Self" if from_self else "", "To Self" if to_self else "", txid, " ", tx, 'original:', orig_in, orig_outs)
    has_unknown = None
    known_in = dict()
    known_out = dict()
    total_xfer = 0
    ins, outs, fee, time = tx
    if from_self:
        balances[FEES] -= fee
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
        #print("in:", (inaddr, inval))
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
            
            #print("out:", (outaddr, outval))
            
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
                
            if xferval >= min_val:
                print("add edge", inaddr, outaddr, xferval)
                append_edge(G, inaddr, outaddr, xferval)
            else:
                print("Skipped tiny edge", inaddr, outaddr, xferval)
            total_xfer += xferval
            
    print("Added a total of ", total_xfer, " for this set of edges from", known_in, "to", known_out)

    if has_unknown is not None:
        print("unknown", has_unknown, ": in=", known_in.keys(), " out=", known_out.keys(), "tx=", orig_in, " => ", orig_outs)

def set_balances(wallet):
    balances[wallet] = 0.0
    inputs[wallet] = 0.0
    outputs[wallet] = 0.0

if __name__ == "__main__":
    # remove the .py from this script as the hipmer wrapper needs to be excecuted for proper environment variable detection
    args = sys.argv[1:]
    if not by_wallet:
        display_len = 50
    
    # special case of coinbase "address"
    newcoin_wallet = "@NewCoins"
    addresses[COINBASE] = None
    add_to_wallet(newcoin_wallet, COINBASE)
    set_balances(newcoin_wallet)
    set_balances(COINBASE)

    own_nodes = []
    not_own_nodes = []
    G = pgv.AGraph(directed=True, landscape=False)
    
    own_name = "cluster_OWN"
    G.add_subgraph(name=own_name, label="OWN", style="filled", fillcolor="lightgrey")
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
        
    # untracked are in neither OWN nor ThirdParty
    G.add_node("From " + unknown, wallet="Untracked")
    set_balances("From " + unknown)
    G.add_node("To " + unknown, wallet="Untracked")
    set_balances("To " + unknown)
    
    
    for f in args:
        print("Inspecting file: ", f);
        wallet = os.path.basename(f)
        wallet, ignored = os.path.splitext(wallet)
    
        is_own = wallet[0] != '@'
        topsubgraph = own_subgraph if is_own else thirdParty_subgraph
        
        # further subgraph is the wallet contains a dash
        x = wallet.split('-')
        if len(x) > 1:
            name_id, name = wallet.split('-')
            if is_own and cluster_own:
                # impose drawing restrictions
                subgraph_name = "cluster_" + name
            elif cluster_thirdParty and not is_own:
                subgraph_name = "cluster_" + name
            else:
                subgraph_name = name
            subgraph = G.get_subgraph(subgraph_name)
            if subgraph is None:
                subgraph = topsubgraph.add_subgraph(subgraph_name, name=subgraph_name, label=name)
                print("Created subgraph", name, "within", "OWN" if is_own else "ThirdParty")
            print("wallet", wallet, "is of subgraph", name)
        else:
            subgraph = topsubgraph
            print("wallet", wallet, "is", "OWN" if is_own else "ThirdParty")
            
        if by_wallet:
            subgraph.add_node(wallet)
            set_balances(wallet)
            
            if is_own:
                own_nodes.append(wallet)
            else:
                not_own_nodes.append(wallet)
        
        print("Opening f=", f, " wallet=", wallet)
        with open(f) as fh:
            for addr in fh.readlines():
                addr = addr.strip();            
                get_all_tx = True
                if addr[0] == '#':
                    # do not exhastively lookup all transactions
                    addr = addr[1:]
                    get_all_tx = False
                if not is_own:
                    # not own, do not exhastively lookup all transactions
                    get_all_tx = False
                
                txs = load_addr(addr, wallet, get_all_tx)
                if not by_wallet:
                    subgraph.add_node(addr, wallet=wallet)
                    set_balances(addr)

                    if is_own:
                        own_nodes.append(addr)
                    else:
                        not_own_nodes.append(addr)
                    
                #G.add_node(addr[0:display_len], wallet=wallet)
                #print(json.dumps(addresses[addr], sort_keys=True, indent=2))
    
    for txid in transactions.keys():
        add_tx_to_graph(G, txid)
    
    """
    subclusters = dict()
    own_cluster = []
    for node in own_nodes:
        x = node.split('-')
        if len(x) > 1:
            print("Adding subcluster", x[0], x[1])
            y = x[1]
            if y not in subclusters:
                subclusters[y] = []
            subclusters[y].append(node)
            
    for name in subclusters.keys():
        if cluster_own:
            # impose drawing constraints by name prefix cluster_
            # Note: drawing constraints on own *clusters* make splines collide too much
            scname = "cluster_%s" %(name)
        else:
            scname = name
        own_subgraph.add_subgraph(subclusters[name], name=scname, label=name)
        sc = own_subgraph.get_subgraph(scname)
        for node in subclusters[name]:
            sc.add_node(node)
            print("Added", node, " to OWN subcluster", name)
    
    # do same for not-own clusters / subgraphs
    subclusters = dict()
    notown_cluster = []
    for node in not_own_nodes:
        x = node.split('-')
        if len(x) > 1:
            print("Adding subcluster", x[0], x[1])
            y = x[1]
            if y not in subclusters:
                subclusters[y] = []
            subclusters[y].append(node)
        
    for name in subclusters.keys():
        if cluster_thirdParty:
            # impose drawing constraints on thirdParty groups by naming prefix cluster_
            scname = "cluster_%s"%(name)
        else:
            scname = name
        G.add_subgraph(subclusters[name], name=scname, label=name)
        sc = G.get_subgraph(scname)
        for node in subclusters[name]:
            sc.add_node(node)
            print("Added", node, " to not-own subcluster", name)
"""

 
    # add balance labels to fully tracked nodes
    for n in G.nodes():
        if unknown in n:
            continue
        if n in balances:
            print(n, round(balances[n],3))
            node = G.get_node(n)
            is_own = str(n)[0] != '@'
            if True:
                node.attr['net'] = balances[n]
                node.attr['input'] = inputs[n]
                node.attr['output'] = outputs[n]
                node.attr['label'] = '%s' % (n)
                if inputs[n] > 0.0:
                    node.attr['label'] += "\nin=%0.3f" % (inputs[n])
                if outputs[n] > 0.0:
                    node.attr['label'] += "\nout=%0.3f" % (outputs[n])
                if is_own:
                    node.attr['label'] += "\nbal=%0.3f" % (balances[n])

                if is_own:
                    # only color own wallets
                    if balances[n] >= min_val:
                        node.attr['color'] = 'green'
                    elif round(balances[n],3) < 0.0:
                        node.attr['color'] = 'red'
                    else:
                        node.attr['color'] = 'yellow'
            else:
                node.attr['color'] = 'blue'
    
    for e in G.edges():
        f,t = e
        from_own = True if f in own_nodes else False
        from_third = True if f in not_own_nodes else False
        to_own = True if t in own_nodes else False
        to_third = True if t in not_own_nodes else False
        
        if from_third and to_third :
            # display this ThirdParty to Thirdparty edge as the value is not otherwise tracked
            e.attr['label'] = e.attr['weight']
            e.attr['color'] = 'purple'
        elif from_own and to_own :
            # Own to Own
            e.attr['style'] = "dotted"
        elif to_own:
            # to Own
            e.attr['color'] = 'green'
        elif from_own:
            # from Own
            e.attr['color'] = 'red'
        
        
    print("Graph:", G)
    print("\tnodes:", G.nodes)
    print("\tnodes.data:", G.nodes())
    print("\tedges:", G.edges)
    print("\tedges.data:", G.edges())
    
    G.write('file.dot')
    tmp = G.copy()
    for node in not_own_nodes:
        tmp.delete_node(node)
    tmp.write('file-own.dot')
    
    #pgvG = pgv.AGraph('file.dot')
    #for own in own_nodes:
    #    node = pgvG.get_node(own)
    #    node.attr['name'] = "cluster_OWN"
    #pgvG.write('file2.dot')

    print('Finished')
  

