from random import choice
from random import random
from random import randint

#The following markov chain code was provided by CSTUY SHIP.

KEY_SIZE = 2
FILE = 'eggtweets_clean.txt'

def read_file( fname ):
    f = open( fname, 'r' )
    text = f.read()
    f.close()
    return text

def get_csv_list( fname ):
    text = read_file( fname )
    lines = text.split('\n')
    line_list = []
    for line in lines:
        line_list.append( line.split(',') )
    return line_list

def get_csv_dict( fname ):
    text = read_file( fname )
    lines = text.split('\n')
    line_dict = {}
    for line in lines:
        line_list = line.split(',')
        key = line_list[0]
        value = line_list[1:]
        line_dict[ key ] = value
    return line_dict

def generate_chains( fname, key_size ):
    chains = {}
    text = read_file( fname )
    words = text.split()
    i = 0
    while i < len(words) - key_size:
        key = ' '.join( words[i : i+key_size] ) 
        value = words[i + key_size]
        if key in chains:
            chains[ key ].append( value )
        else:
            new_list = []
            new_list.append( value )
            chains[ key ] = new_list
        i+= 1
    return chains

def generate_text( chains, num_words, key_size ):
    key = choice( list(chains.keys()) )
    s = key
    i = 0
    while i < num_words:
        word = choice( chains[ key ] )
        s+= ' ' + word
        key = ' '.join(key.split()[1 : key_size + 1])
        if key_size > 1:
            key+= ' '
        key+= word
        i+= 1
    sourceTextCapital = s
    firstLetter = sourceTextCapital[0]
    sourceTextCapital = sourceTextCapital[1:]
    firstLetter = firstLetter.title()
    s = firstLetter + sourceTextCapital
    return s

def final():
    chains = generate_chains( FILE, KEY_SIZE )
    text = generate_text( chains, randint(10,35), KEY_SIZE )
    print(text)
    return text
