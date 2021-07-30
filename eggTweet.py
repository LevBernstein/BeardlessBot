#The following Markov chain code was provided by CSTUY SHIP.
import re
from random import choice, randint

def generate_chains(fileName, keySize):
    with open(fileName, 'r') as f:
        words = f.read().split()
    chains = {}
    for i in range(len(words) - keySize):
        key = ' '.join(words[i : i + keySize]) 
        value = words[i + keySize]
        if key in chains:
            chains[key].append(value)
        else:
            chains[key] = [value]
    return chains

def generate_text(chains, num_words, keySize):
    key = choice(list(chains.keys()))
    s = key
    for i in range(num_words):
        word = choice(chains[key])
        s += ' ' + word
        key = ' '.join(key.split()[1 : keySize + 1]) + ' ' + word if keySize > 1 else word
    return s[0].title() + s[1:]

def tweet():
    keySize = randint(1, 2)
    return generate_text(generate_chains('resources/eggtweets_clean.txt', keySize), randint(10, 35), keySize)

def formattedTweet(tweet):
    for i in range(len(tweet)):
        if tweet[len(tweet) - i - 1] in [".", "!", "?"]:
            return (tweet[:(len(tweet) - i - 1)])
    return tweet

if __name__ == "__main__":
    result = tweet()
    print(result)
    print(formattedTweet(result))