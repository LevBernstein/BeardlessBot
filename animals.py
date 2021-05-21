# Animal images for Beardless Bot

import requests

def animal(animalType, key ):
    if animalType == "cat" or animalType == "dog":
        r = requests.get("https://api.the" + animalType + "api.com/v1/images/search", params={"limit": 1, "size": "full"}, headers={'x-api-key': key})
        if r.status_code == 200:
            return(r.json()[0]['url'])
        else:
            print(r.status_code)
            raise Exception("API Limit Reached!")
    if animalType == "duck":
        r = requests.get("https://random-d.uk/api/quack")
        if r.status_code == 200:
            return(r.json()['url'])
        else:
            print(r.status_code)
            raise Exception("Error " + str(r.status_code) + "!")