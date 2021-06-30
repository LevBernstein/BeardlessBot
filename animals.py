# Animal images for Beardless Bot

import requests

def animal(animalType, key ):
    if animalType == "cat":
        r = requests.get("https://api.the" + animalType + "api.com/v1/images/search", params={"limit": 1, "size": "full"}, headers={'x-api-key': key})
        if r.status_code == 200:
            return(r.json()[0]['url'])
        else:
            print(r.status_code)
            raise Exception("API Limit Reached!")
    if animalType.startswith("dog"):
        if not (" " in animalType):
            r = requests.get("https://dog.ceo/api/breeds/image/random")
            return(r.json()['message'])
        else:
            breed = animalType.split(" ", 1)[1]
            if breed.startswith("breeds"):
                r = requests.get("https://dog.ceo/api/breeds/list/all")
                report = "Dog breeds: " + (", ".join(breed for breed in r.json()["message"])) + "."
                return(report)
            else:
                r = requests.get("https://dog.ceo/api/breed/" + breed + "/images/random")
                return(r.json()['message'] if not r.json()['message'].startswith("Breed not found") else "Breed not found! Do !dog breeds to see all the breeds.")
        
    if animalType == "duck":
        r = requests.get("https://random-d.uk/api/quack")
        if r.status_code == 200:
            return(r.json()['url'])
        else:
            print(r.status_code)
            raise Exception("Error " + str(r.status_code) + "!")