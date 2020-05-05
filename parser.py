#!/usr/bin/env python3

import networkx as nx
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
display_len = 6

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
                time.sleep(min_request_delay)
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
        
    if wallet is not None:
        add_to_wallet(wallet, addr)
    return addresses[addr]['txs']
    
unknown = 'N/A'
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

def append_edge(G, inaddr2, outaddr2, xferval):
    G.add_edge(inaddr2, outaddr2)
    edge =  G[inaddr2][outaddr2]
    if not 'count' in edge:
        edge['count'] = 1
        edge['weight'] = xferval
    else:
        edge['count'] += 1
        edge['weight'] += xferval
    #edge['arrowsize'] = math.log10(edge['weight'])

min_val = 0.001
def add_tx_to_graph(G, txid):
    tx = transactions[txid]
    orig_in, orig_outs, fee, time = tx
    tx = sanitize_addr(tx)
    print("Adding ", txid, " ", tx)
    ins, outs, fee, time = tx
    for i in ins:
        inaddr, inval = i
        #print("in:", (inaddr, inval))
        if inval <= 0:
            continue
        for o in outs:
            outaddr, outval = o
            if outval <= 0:
                continue
            if inaddr == unknown and outaddr == unknown:
                continue
            #print("out:", (outaddr, outval))
            if inaddr == unknown:
                for x in orig_in:
                    print("unknown from: ", x)
                inaddr2 = "From " + unknown
            else:
                inaddr2 = inaddr
                
            if outaddr == unknown:
                continue
                outaddr2 = "To " + unknown
            else:
                outaddr2 = outaddr
                
            if inval <= outval:
                xferval = inval
                if xferval > min_val:
                    print("add", inaddr2, outaddr2, xferval)
                    append_edge(G, inaddr2, outaddr2, xferval)
                    #G.add_edge(inaddr2, outaddr2, weight=xferval, time=time)
                inval = 0
                outval -= xferval
                break # no more input get next one
            else:
                xferval = outval
                if xferval > min_val:
                    print("add", inaddr2, outaddr2, xferval)
                    append_edge(G, inaddr2, outaddr2, xferval)
                    #G.add_edge(inaddr2, outaddr2, weight=xferval, time=time)
                inval -= xferval
                outval = 0

if __name__ == "__main__":
    # remove the .py from this script as the hipmer wrapper needs to be excecuted for proper environment variable detection
    args = sys.argv[1:]
    G = nx.DiGraph()
    #G.add_node(unknown, wallet="Untracked")
    G.add_node("Untracked")
    for f in args:
        print("Inspecting file: ", f);
        wallet = os.path.basename(f).split('.')[0]
        G.add_node(wallet)
        print("Opening f=", f, " wallet=", wallet)
        with open(f) as fh:
            for addr in fh.readlines():
                addr = addr.strip();            
                txs = load_addr(addr, wallet)
                #G.add_node(addr[0:display_len], wallet=wallet)
                #print(json.dumps(addresses[addr], sort_keys=True, indent=2))
    for txid in transactions.keys():
        add_tx_to_graph(G, txid)

    print("Graph:", G)
    print("\tnodes:", G.nodes)
    print("\tnodes.data:", G.nodes.data())
    print("\tedges:", G.edges)
    print("\tedges.data:", G.edges.data())
    
    from networkx.drawing.nx_pydot import write_dot
    pos = nx.nx_agraph.graphviz_layout(G)
    nx.draw(G, pos=pos)
    write_dot(G, 'file.dot')
    
    #import matplotlib.pyplot as plt
    #plt.subplot()
    #nx.draw(G, with_labels=True, font_weight='bold')
    #plt.savefig("path.png")
    print('Finished')
  

