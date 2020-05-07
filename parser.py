#!/usr/bin/env python3

import networkx as nx
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
unknown = 'N/A'
COINBASE = "NEW COINBASE (Newly Generated Coins)"

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
    
    print(txid)
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
    
def load_addr(addr, wallet = None):
    global last_request_time
    if addr in addresses:            
        print("Found ", addr, " in memory")
        return
    
    n_tx = 0
    all_txs = None
    offset = 0
    addr_json = None
    while offset == 0 or n_tx > len(all_txs):
        
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
                print("Waiting to make next URL API request: ", wait_time)
                time.sleep(min_request_delay - wait_time)
            print("Downloading everything about ", addr, " from ", url)
            
            # raise an error if we need to re-download some data to avoid getting blocked by blockchain.com while debugging
            raise("Where did %s come from?" % (addr))
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
    for i in ins:
        addr, val = i
        if not addr in addresses:
            addr2 = unknown
        else:
            if addr in rev_wallet:
                addr2 = rev_wallet[addr]
            else:
                addr2 = addr[0:display_len]
        ins2.append((addr2, val))
    for i in outs:
        addr, val = i
        if not addr in addresses:
            addr2 = unknown
        else:
            if addr in rev_wallet:
                addr2 = rev_wallet[addr]
            else:
                addr2 = addr[0:display_len]
        outs2.append((addr2, val))
    return (ins2, outs2, fee, time)

def record_balances(inaddr2, outaddr2, xferval):
    if not unknown in inaddr2:
        balances[inaddr2] -= xferval
        outputs[inaddr2] += xferval
    if not unknown in outaddr2:
        balances[outaddr2] += xferval
        inputs[outaddr2] += xferval

    
def append_edge(G, inaddr2, outaddr2, xferval):
    G.add_edge(inaddr2, outaddr2)
    edge =  G.get_edge(inaddr2, outaddr2)
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
    tx = sanitize_addr(tx)
    print("Adding transaction ", txid, " ", tx, 'original:', orig_in, orig_outs)
    has_unknown = None
    known_in = dict()
    known_out = dict()
    total_xfer = 0
    ins, outs, fee, time = tx
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
            
            record_balances(inaddr, outaddr, xferval)
            
            # we may modify the address labels if one side is unknown
            inaddr2 = inaddr
            outaddr2 = outaddr


            
            if inaddr2 == outaddr2:
                # noop transaction do not add an edge
                continue
                
            if inaddr == unknown and outaddr == unknown:
                # neither address is tracked
                # do not add an edge
                continue
                
            if inaddr == unknown:
                if outaddr[0] == '@':
                    # unknown -> thirdparty destination
                    # do not add an edge
                    continue 
                # otherwise log it
                has_unknown = "FROM"
                inaddr2 = "From " + unknown
            else:
                inaddr2 = inaddr
                if inaddr2 not in known_in:
                    known_in[inaddr2] = 0
                known_in[inaddr2] -= xferval
                
            if outaddr == unknown:
                if inaddr[0] == '@':
                    # thirdpaty -> unknown destination
                    # do not add an edge
                    continue
                # otherwise log it
                has_unknown = "TO"
                outaddr2 = "To " + unknown
            else:
                outaddr2 = outaddr
                if outaddr2 not in known_out:
                    known_out[outaddr2] = 0
                known_out[outaddr2] += xferval
                
            if xferval >= min_val:
                print("add edge", inaddr2, outaddr2, xferval)
                append_edge(G, inaddr2, outaddr2, xferval)
            else:
                print("Skipped tiny edge", inaddr2, outaddr2, xferval)
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

    #G = nx.DiGraph()
    #Gown = nx.DiGraph()
    #G.add_node(Gown)
    G = pgv.AGraph(directed=True)
    G.add_subgraph(name="cluster_ThirdParty", label="ThirdParty")
    thirdParty = G.get_subgraph("cluster_ThirdParty")
    
    if by_wallet:
        G.add_node(newcoin_wallet)
    else:
        G.add_node(COINBASE, wallet=newcoin_wallet)
    #G.add_node(unknown, wallet="Untracked")
    own_nodes = []
    not_own_nodes = []
    
    for f in args:
        print("Inspecting file: ", f);
        wallet = os.path.basename(f)
        wallet, ignored = os.path.splitext(wallet)
    
        is_own = wallet[0] != '@'
        if by_wallet:
            G.add_node(wallet)
            if not is_own:
                thirdParty.add_node(wallet)
            set_balances(wallet)
            if is_own:
                own_nodes.append(wallet)
            else:
                not_own_nodes.append(wallet)
        
        print("Opening f=", f, " wallet=", wallet)
        with open(f) as fh:
            for addr in fh.readlines():
                addr = addr.strip();            
                txs = load_addr(addr, wallet)
                if not by_wallet:
                    G.add_node(addr, wallet=wallet)
                    if not is_own:
                        thirdParty.add_node(addr)
                    set_balances(addr)
                    if is_own:
                        own_nodes.append(addr)
                    else:
                        not_own_nodes.append(addr)
                #G.add_node(addr[0:display_len], wallet=wallet)
                #print(json.dumps(addresses[addr], sort_keys=True, indent=2))
    for txid in transactions.keys():
        add_tx_to_graph(G, txid)
      
    G.add_subgraph(name="cluster_OWN", label="OWN")
    own_subgraph = G.get_subgraph("cluster_OWN")
    
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
        else:
            own_subgraph.add_node(node)
            
    for name in subclusters.keys():
        scname = "cluster_%s"%(name)
        own_subgraph.add_subgraph(subclusters[name], name=scname, label=name)
        sc = own_subgraph.get_subgraph(scname)
        for node in subclusters[name]:
            sc.add_node(node)
        


 
    # add balance labels to fully tracked nodes
    for n in G.nodes():
        if unknown in n:
            continue
        if n in balances:
            if balances[n] < min_val:
                balances[n] = 0
            print(n, balances[n])
            if str(n)[0] != '@':
                node = G.get_node(n)
                node.attr['net'] = balances[n]
                node.attr['input'] = inputs[n]
                node.attr['output'] = outputs[n]
                node.attr['label'] = "%s\n%0.3f" % (n, balances[n])
    
    print("Graph:", G)
    print("\tnodes:", G.nodes)
    print("\tnodes.data:", G.nodes())
    print("\tedges:", G.edges)
    print("\tedges.data:", G.edges())
    
    #from networkx.drawing.nx_pydot import write_dot
    #pos = nx.nx_agraph.graphviz_layout(G)
    #nx.draw(G, pos=pos)
    #write_dot(G, 'file.dot')
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

    #pos = nx.nx_agraph.graphviz_layout(ownG)
    #nx.draw(ownG, pos=pos)
    #write_dot(ownG, 'file-own.dot')

    #import matplotlib.pyplot as plt
    #plt.subplot()
    #nx.draw(G, with_labels=True, font_weight='bold')
    #plt.savefig("path.png")
    print('Finished')
  

