#The following Markov chain code was provided by CSTUY SHIP.
from random import choice, randint

KEY_SIZE = 2
FILE = 'resources/eggtweets_clean.txt'

def generate_chains(fname, key_size):
    with open(fname, 'r') as f:
        text = f.read()
    chains = {}
    words = text.split()
    for i in range(len(words) - key_size):
        key = ' '.join(words[i : i + key_size]) 
        value = words[i + key_size]
        if key in chains:
            chains[key].append(value)
        else:
            new_list = []
            new_list.append(value)
            chains[key] = new_list
    return chains

def generate_text(chains, num_words, key_size):
    key = choice(list(chains.keys()))
    s = key
    for i in range(num_words):
        word = choice(chains[key])
        s += ' ' + word
        key = (' '.join(key.split()[1 : key_size + 1])) + (' ' + word) if key_size > 1 else word
    sourceTextCapital = s
    firstLetter = sourceTextCapital[0]
    sourceTextCapital = sourceTextCapital[1:]
    firstLetter = firstLetter.title()
    s = firstLetter + sourceTextCapital
    return s

def final():
    complexity = randint(1, 2)
    text = generate_text(generate_chains(FILE, complexity), randint(10, 35), complexity)
    print(text)
    return text

if __name__ == "__main__":
    final()