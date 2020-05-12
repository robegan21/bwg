
## File Formats

parser.py accepts text files of a "wallet" with a list of bitcoin addresses

The name of the file is important to the display of the graph.  The extension 
after the period ('.') is discarded

If there is a dash ('-') then anything following will be associated in a subgraph
named after the label.

If the file is prefixed with an at sign ('@') then the "wallet" is assumed to be
not owned and so all inputs and outputs are not going to be fully tracked.

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





