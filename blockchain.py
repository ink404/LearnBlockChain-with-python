"""
Ian Kirkpatrick 9.30.2017
Learn block chain by building one:
https://hackernoon.com/learn-blockchains-by-building-one-117428612f46
"""

import hashlib
import json
from time import time
from textwrap import dedent
from uuid import uuid4
from urllib.parse import urlparse

from flask import Flask, jsonify, request


class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        # creates the genisis block
        self.new_block(previous_hash=1, proof=100)

    def register_node(self, address):
        """
        Add a new node to the list of nodes

        :param address: <str> address of node
        :return: none
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def new_block(self, proof, previous_hash=None):
        """
        Create a new Block in the Blockchain

        :param proof: <int> The proof given by the Proof of Work algorithm
        :param previous_hash: (Optional) <str> Hash of previous block
        :param: <dict> New Block
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # reset the current list of transactions
        self.current_transactions = []

        self.chain.append(block)

        return block

    def new_transaction(self, sender, recipient, amount):
        """
        Create s anew transaction to go into the next mined Block

        :param sender: <str> Address of the sender
        :param recipient: <str> Address of the recipient
        :param amount: <int> Amount
        :return: <int> The index of the Block that will hold this transaction
        """

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    def proof_of_work(self, last_proof):
        """
        Simple Proof of Work algorithm (PoW):
        - find a number p' such that has(pp') contains leading 4 0's where p is the previous p'
        - p is the previous proof, and p' is the new proof

        :param last_proof: <int>
        :return: <int>
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid

        :param chain: <list> blockchain
        :return: <bool> True if valid, False if not
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n------------\n")
            #check hash of blocks is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            #check for valid PoW
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        Consensus Algorithm, resolves conflicts by replacing
         the chain with the longest one in the network

         :return: <bool> True if our chain was replaced, False if not
        """

        neighbors = self.nodes
        new_chain = None

        #looking for chains longer than current
        max_length = len(self.chain)

        #get all chains from network
        for node in neighbors:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                #check for longer/ valid chain
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        #replace current instantiations chain with new chain if a longer one is discovered
        if new_chain:
            self.chain = new_chain
            return True

        return False

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        Creates a SHA-256 hash of a block

        :param block: <dict> Block
        :return: <str>
        """

        # The dictionary must be ordered or there will be inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        validates the proof: does hash(last_proof, proof) checks for containing 4 leading 0's

        :param last_proof: <int> Previous Proof
        :param proof: <int> Current Proof
        :return: <bool> True if correct proof, False if not
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"


# Node instantiation
app = Flask(__name__)

# generate unique node address
node_identifier = str(uuid4()).replace('-', '')

# Blockchain instantiation
blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine():
    #run the PoW algorithm to get next proof
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    #reward for finding proof
    #sender is "0" signifying this node has mined a new coin
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    #add new Block to chain
    block = blockchain.new_block(proof)

    response = {
        'message': "new Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # check for required fields in data
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # creating new transaction
    index = blockchain.new_transaction(
        values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Invalid list of nodes supplied", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Current chain replaced',
            'new_chain': blockchain.chain
        }

    else:
        response = {
            'message': 'Current chain authroitative',
            'chain': blockchain.chain
        }

        return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
