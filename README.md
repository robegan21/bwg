# BWG - Bitcoin Wallet Graph

An easy way to visualize transactions from the blockchain, given a set of bitcoin
public addresses within any number of different wallets.

Data is downloaded from blockchain.com's API and may take a long time for a large
data set because queries to that service are limited to 1 for every 15 seconds.
After the initial download, the data is cached and does not need to be retrieved again.

## License

```
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
```

## Usage

```
parser.py my_wallet1.txt [my_wallet2.txt] [ @other_wallet.txt ]
```

Presently options are not supported but will be soon.

Outputs:
```
mywallet.dot
mywallet-own.dot
mywaller-simplified.dot
```

One can easily convert the text based dot format to pdf using any number of programs,
I use the program from GraphViz, dot:

```
for f in *.dot
do
 dot -Tpdf -Gdpi=600 -o${f%.dot}.pdf 
done
```

For example if one woudld like to model the first blocks and transactions on the
bitcoin blockchain:
```
parser.py example/SatoshiThemselves/*.txt
```

## File Formats

parser.py accepts text files for a "wallet" with a list of bitcoin addresses

The name of the file is important for the display of the graph.  The extension 
after the period ('.') is discarded

Every wallet without a an at sign ('@') as the first character is owned and will be
drawn together in a shaded box.

If the file is prefixed with an at sign ('@') then the "wallet" is assumed to be
not owned and so all inputs and outputs are not going to be fully tracked.

If there is a dash ('-') then anything following will be associated in a subgraph
named after the label, and attempted to be drawn together in a box


For example:

A-Wallet.txt
B-Wallet.txt
alpha-ColdWallet.txt
beta-ColdWallet.txt

@C-Exchange.txt
@D-Exchange.txt
@E-Friend.txt

A, B, alpha and beta are all owned so fully tracked with all inputs and output and
transaction fees in the accounting

A, B are further within the 'Wallet' subgraph
alpha, bata are within the 'ColdWallet' subgraph
And both Wallet and ColdWallet are within the OWN subgraph

C and D are in the Exchange subgraph
and E is alone in the Friend subgraph





