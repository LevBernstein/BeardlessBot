# Animal images for Beardless Bot

import requests
from random import randint

def animal(animalType, key = "no key"):
    if animalType == "cat":
        r = requests.get("https://api.thecatapi.com/v1/images/search", params={"limit": 1, "size": "full"}, headers={'x-api-key': key})
        if r.status_code == 200:
            return(r.json()[0]['url'])
        print(r.status_code)
        raise Exception("API Limit Reached!")
    
    if animalType.startswith("dog"):
        if not (" " in animalType):
            r = requests.get("https://dog.ceo/api/breeds/image/random")
            return(r.json()['message'])
        breed = animalType.split(" ", 1)[1]
        if breed.startswith("breeds"):
            r = requests.get("https://dog.ceo/api/breeds/list/all")
            report = "Dog breeds: " + (", ".join(breed for breed in r.json()["message"])) + "."
            return(report)
        r = requests.get("https://dog.ceo/api/breed/" + breed + "/images/random")
        return(r.json()['message'] if not r.json()['message'].startswith("Breed not found") else "Breed not found! Do !dog breeds to see all the breeds.")
    
    if animalType == "fish":
        count = 0
        while count < 10:
            fishID = str(randint(2, 1969))
            print("Fish id: " + fishID)
            r = requests.get("https://fishbase.ropensci.org/species/" + fishID) # valid range of species by id on fishbase.
            # there appear to be gaps in the valid range, so try some more numbers if you random into an invalid fish
            if r.status_code == 200:
                return(r.json()["data"][0]["image"])
            count += 1
            print("Invalid fish ID " + fishID)
        print(r.status_code)
        raise Exception("Error " + str(r.status_code) + "!")
    
    if animalType == "fox":
        r = requests.get("https://randomfox.ca/floof/")
        if r.status_code == 200:
            return(r.json()['image'])
        print(r.status_code)
        raise Exception("Error " + str(r.status_code) + "!")
    
    if animalType == "bunny" or animalType == "rabbit":
        return("https://bunnies.media/gif/" + str(randint(2, 163)) + ".gif")
    
    if animalType in ["panda", "koala", "bird"]:
        r = requests.get("https://some-random-api.ml/img/" + ("birb" if animalType == "bird" else animalType))
        if r.status_code == 200:
            return(r.json()['link'])
        print(r.status_code)
        raise Exception("Error " + str(r.status_code) + "!")
    
    if animalType in ["lizard", "duck"]:
        r = requests.get("https://nekos.life/api/v2/img/lizard" if animalType == "lizard" else "https://random-d.uk/api/quack")
        if r.status_code == 200:
            return(r.json()['url'])
        print(r.status_code)
        raise Exception("Error " + str(r.status_code) + "!")