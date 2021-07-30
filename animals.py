# Animal images for Beardless Bot

import requests
from random import randint

def animal(animalType):
    if animalType == "cat":
        # cat API has been throwing 503 errors regularly, not sure why. Spotty hosting maybe.
        for i in range(10):
            # the loop is to try to make another request if one pulls a 503.
            r = requests.get("https://aws.random.cat/meow")
            if r.status_code == 200:
                return r.json()['file']
            print(str(r.status_code) + " cat")
    
    if animalType.startswith("dog"):
        if len(animalType) == 4 or not (" " in animalType):
            r = requests.get("https://dog.ceo/api/breeds/image/random")
            return r.json()['message']
        breed = animalType.split(" ", 1)[1]
        if breed.startswith("breeds"):
            r = requests.get("https://dog.ceo/api/breeds/list/all")
            return "Dog breeds: " + (", ".join(breed for breed in r.json()["message"])) + "."
        r = requests.get("https://dog.ceo/api/breed/" + breed + "/images/random")
        return r.json()['message'] if not r.json()['message'].startswith("Breed not found") else "Breed not found! Do !dog breeds to see all the breeds."
    
    if animalType == "fish":
        for i in range(10):
            fishID = str(randint(2, 1969))
            print("Fish id: " + fishID)
            r = requests.get("https://fishbase.ropensci.org/species/" + fishID) # valid range of species by id on fishbase.
            # there appear to be gaps in the valid range, so try some more numbers if you random into an invalid fish
            if r.status_code == 200:
                return r.json()["data"][0]["image"]
            print("Invalid fish ID " + fishID)
    
    if animalType == "fox":
        r = requests.get("https://randomfox.ca/floof/")
        if r.status_code == 200:
            return r.json()['image']
    
    if animalType == "bunny" or animalType == "rabbit":
        return "https://bunnies.media/gif/" + str(randint(2, 163)) + ".gif"
    
    if animalType in ["panda", "koala", "bird"]:
        # panda API has had some performance issues lately
        r = requests.get("https://some-random-api.ml/img/" + ("birb" if animalType == "bird" else animalType))
        if r.status_code == 200:
            return r.json()['link']
    
    if animalType in ["lizard", "duck"]:
        r = requests.get("https://nekos.life/api/v2/img/lizard" if animalType == "lizard" else "https://random-d.uk/api/quack")
        if r.status_code == 200:
            return r.json()['url']
    print(str(r.status_code) + " " + animalType)
    
    raise Exception("Error with the " + animalType + "API!")