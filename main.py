import time
from functools import lru_cache
from io import StringIO
from time import sleep

import pandas as pd
import requests
from bs4 import BeautifulSoup
from geopy.distance import geodesic
from geopy.exc import GeocoderUnavailable
from geopy.geocoders import Nominatim
from tqdm import tqdm


@lru_cache(maxsize=2000)
def get_coordinates(city_name):
    geolocator = Nominatim(user_agent="your_app_name")
    # This API limits how many requests you can make per second, so we need to wait a bit between requests
    sleep_time = 0
    while True:
        try:
            location = geolocator.geocode(city_name)
            break
        except (TimeoutError, GeocoderUnavailable):
            print("Timeout, trying again...")
            sleep(sleep_time)
            sleep_time += 1
    if location:
        return location.latitude, location.longitude
    else:
        return None


@lru_cache(maxsize=2000)
def calculate_distance(city1, city2):
    coords1 = get_coordinates(city1)
    coords2 = get_coordinates(city2)

    if coords1 and coords2:
        distance = geodesic(coords1, coords2).kilometers
        return distance
    else:
        return None


def main():
    url = "https://en.wikipedia.org/wiki/List_of_U.S._places_named_after_non-U.S._places"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    original_country = None
    rows = []
    elements = list(soup.find_all(["h2", "table"]))
    for i, element in enumerate(elements):
        if element.name == "h2":
            original_country = element.find("span", {"class": "mw-headline"})
            if original_country:
                original_country = original_country.text
        else:
            if original_country is None:
                continue

            # parse the html table into a pandas dataframe
            df = pd.read_html(StringIO(str(element)))[0]

            try:
                for i, row in df.iterrows():
                    original_city = row["City or town"]
                    if isinstance(original_country, float):
                        continue
                    original = f'{original_city}, {original_country}'.strip("\n")
                    namesake = row["Namesake"]
                    if isinstance(namesake, float):
                        continue

                    # strip the reference numbers from the namesake
                    namesake = namesake.split("[")[0]
                    namesake_coords = get_coordinates(namesake)
                    original_coords = get_coordinates(original)

                    coord_row = [namesake, original, namesake_coords, original_coords]
                    print(f"{i}/{len(elements)}", namesake, "-->", original)

                    rows.append(coord_row)
            except KeyError:
                continue

    df = pd.DataFrame(rows, columns=["Namesake", "Original", "Namesake Coordinates", "Original Coordinates"])
    df.to_csv("namesake_cities.csv", index=False)

    # For every pair of namesake cities, compute the distance between them, and the distance between their original cities
    min_r = 1e9
    min_namesake_distance = None
    min_original_distance = None
    min_namesake_1 = None
    min_namesake_2 = None
    min_original_1 = None
    min_original_2 = None
    for i, row_i in df.iterrows():
        for j, row_j in df.iterrows():
            if i == j:
                continue
            else:
                namesake_distance = geodesic(row_i['Namesake Coordinates'], row_j['Namesake Coordinates']).kilometers
                original_distance = geodesic(row_i['Original Coordinates'], row_j['Original Coordinates']).kilometers
                if namesake_distance is None:
                    continue
                if original_distance is None:
                    continue
                if original_distance == 0:
                    continue  # this is a duplicate original city
                if namesake_distance == 0:
                    continue # must be a flaw in the data

                r = namesake_distance / original_distance
                if r < min_r:
                    min_r = r
                    min_namesake_distance = namesake_distance
                    min_original_distance = original_distance
                    min_namesake_1 = row_i['Namesake']
                    min_namesake_2 = row_j['Namesake']
                    min_original_1 = row_i['Original']
                    min_original_2 = row_j['Original']

                    print(f"Ratio: {1/min_r:.5f}")
                    print(f"{row_i['Namesake']} and {row_j['Namesake']} are {namesake_distance:.0f}km apart, whereas")
                    print(f"{row_i['Original']} and {row_j['Original']} are {original_distance:.0f}km apart")

    print(f"{min_namesake_1} and {min_namesake_2} are {min_namesake_distance:.0f}km apart, whereas")
    print(f"{min_original_1} and {min_original_2} are {min_original_distance:.0f}km apart")
    print(f"Ratio: {1/min_r:.5f}")


if __name__ == '__main__':
    main()
