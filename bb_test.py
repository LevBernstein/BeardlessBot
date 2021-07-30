# Beardless Bot Unit Tests

from random import choice

import requests

from animals import *
from dice import *
from eggTweet import *
from fact import *

IMAGETYPES = ["image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"]
IMAGESIGS = ["b'\\xff\\xd8\\xff\\xe0\\x00\\x10", "b'\\x89\\x50\\x4e\\x47\\x0d\\x0a\\x1a\\x0a", "'b\'\\xff\\xd8\\xff\\xe2\\x024"]

def test_cat():
    r = requests.head(animal("cat"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_dog():
    r = requests.head(animal("dog"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_dog_breeds():
    assert animal("dog breeds").startswith("Dog breeds:")
    assert len(animal("dog breeds")[12:-1].split(", ")) == 95

def test_dog_breed(): 
    for breed in animal("dog breeds")[12:-1].split(", "):
        r = requests.head(animal("dog " + breed))
        assert r.ok and r.headers["content-type"] in IMAGETYPES
    assert animal("dog invalid breed") == "Breed not found! Do !dog breeds to see all the breeds."

def test_fish():
    r = requests.head(animal("fish"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_fox():
    r = requests.head(animal("fox"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_rabbit():
    r = requests.head(animal("rabbit"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_panda():
    r = requests.head(animal("panda"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_koala(): # Koala API headers lack a content-type field, so check if the URL points to a jpg or png instead
    r = requests.get(animal("koala"))
    assert r.ok and any(str(r.content).startswith(signature) for signature in IMAGESIGS)

def test_bird():# Bird API headers lack a content-type field, so check if the URL points to a jpg or png instead
    r = requests.get(animal("bird"))
    assert r.ok and any(str(r.content).startswith(signature) for signature in IMAGESIGS)

def test_lizard():
    r = requests.head(animal("lizard"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_duck():
    r = requests.head(animal("duck"))
    assert r.ok and r.headers["content-type"] in IMAGETYPES

def test_fact():
    with open("resources/facts.txt", "r") as f:
        assert fact() in f.read().splitlines()

def test_egg_formatted_tweet():
    eggTweet = tweet()
    assert formattedTweet(eggTweet) in eggTweet

def test_dice():
    for sideNum in [4, 6, 8, 100, 10, 12, 20]:
        sideRoll = roll("!d" + str(sideNum))
        assert 1 <= sideRoll and sideRoll <= sideNum
    assert not roll("!d9")