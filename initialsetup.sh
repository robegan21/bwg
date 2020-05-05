
for file in *.txt ; do for addr in $(cat $file) ; do f=addresses/$addr.json ; [ -f $f ] || (echo looking for $addr from $file && curl https://blockchain.info/rawaddr/$addr > $f.tmp && mv $f.tmp $f && sleep 15 ) done ; done 


curl https://blockchain.info/rawtx/$txid > $txid.json




pip3 install networkx


