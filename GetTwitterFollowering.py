# Import libraries to check if the other required libraries are installed
import subprocess
import importlib

# List of required libraries for script to run
required_libraries = ["requests", "json", "pandas",
                      "time", "geopy", "os", "math", "getpass"]

# Loop through the libraries
for library in required_libraries:
    # Test if the library is available
    try:
        importlib.import_module(library)
    # If the library is not available install the library with pip3
    except ImportError:
        subprocess.run(["pip3", "install", library])

# Import libraries for the script
import os
import geopy.distance
from geopy.geocoders import Nominatim
import time
import pandas as pd
import json
import requests
import math
import getpass

# Set the Twitter Bearer Token
bearer_token = None

# Set the username
twitter_username = None

# Get home directory for user running script
home_dir = os.path.expanduser("~")

# Detect the directory separator to allow to run on Mac and Windows systems
if str(home_dir)[0] == '/':
    dir_separator = '/'
else:
    dir_separator = '\\'

# Set up directory name to save files to
twitter_dir = home_dir + dir_separator + 'Twitter Followering' + dir_separator


# Test if the Twitter directory exists, if it does not it makes it
def create_twitter_dir(twitter_dir_in):
    if not os.path.exists(twitter_dir_in):
        os.mkdir(twitter_dir_in)


# Tests if there is a saved Twitter Bearer Token, if not it provides instructions to create one, and gives the user the option to save it in the future.
def get_bearer_token():
    global bearer_token
    print("###############################################################################################################")
    print("#                                                                                                             #")
    print("#   Input your Twitter Bearer Token                                                                           #")
    print("#                                                                                                             #")
    print("#   If you do not have a Twitter Bearer Token, follow the below steps:                                        #")
    print("#       • Go to https://developer.twitter.com/en/portal/                                                      #")
    print("#       • Login with your Twitter account                                                                     #")
    print("#       • Create a Project                                                                                    #")
    print("#           • Create an App in that Project                                                                   #")
    print("#       • In that App generate a Bearer Token in the \"Keys and tokens\" section                                #")
    print("#       • Copy your Twitter Bearer Token and store it a safe place YOU can retrieve it                        #")
    print("#           • This app gives you the option to save the Token                                                 #")
    print("#           • If you save the Token, you should not get this message again, unless the files are deleted      #")
    print("#           • Keep a copy of your your Twitter Bearer Token, you cannot retrieve it again                     #")
    print("#           • You can generate a new Twitter Bearer Token, but your current one will lose access              #")
    print("#                                                                                                             #")
    print("#   DO NOT give ANYONE a copy of your your Twitter Bearer Token, as it can give them access to your account   #")
    print("#                                                                                                             #")
    print("###############################################################################################################")
    # Ask user to provide the Twitter Bearer Token
    bearer_token = getpass.getpass(prompt='\nPaste in Twitter Bearer Token and press Enter (no text will appear): ')


# Create the user URL that will be used to look up their user ID
# The user ID will be used for all further lookups
def create_user_url(username):
    return "https://api.twitter.com/2/users/by/username/{}/?user.fields=public_metrics".format(username)


# Create URL to look up followers
def create_follower_url(user_id):
    return "https://api.twitter.com/2/users/{}/followers".format(user_id)


# Create URL to look up following
def create_following_url(user_id):
    return "https://api.twitter.com/2/users/{}/following".format(user_id)


# Configure parameters for looks ups
def get_params(pagination_token):
    # If the previous response provided a pagination token it passes it on to get the next page of data
    if pagination_token is not None:
        params = {"user.fields": "created_at,location,public_metrics", "max_results": 1000,
                  "pagination_token": pagination_token}
    # If not it was the first request
    else:
        params = {"user.fields": "created_at,location,public_metrics",
                  "max_results": 1000}
    return params


# Configure Twitter Bearer Token to be used in GET requests
def bearer_oauth(r):
    global bearer_token # = get_bearer_token()
    r.headers["Authorization"] = "Bearer {}".format(bearer_token)
    r.headers["User-Agent"] = "TwitterLookupPython"
    return r


# Get json data from Twitter API
def connect_to_endpoint(url, params):
    response = requests.request("GET", url, auth=bearer_oauth, params=params)
    if response.status_code != 200 and response.status_code != 429:
        raise Exception(
            "Request returned an error: {} {}".format(
                response.status_code, response.text
            )
        )
    return response.json()


# Twitter's free API has a limit of 15 Following/Followers queries per 15 minutes
# This will pause the script so this time can pass
def countdown(t):
    while t:
        mins, secs = divmod(t, 60)
        timer = '{:02d}:{:02d}'.format(mins, secs)
        print("Twitter's API has a limit of 15 queries per 15 minutes, pausing for 15 minutes:", timer,'\r', end='\r')
        time.sleep(1)
        t -= 1
    print("\033[K", end="")


# Loops through the Following/Follower data to pull them 1,000 at a time
def get_twitter_data(url, loops, ering):
    df = pd.DataFrame()
    notEnd = True
    next_token = None
    loop_count = loops

    while notEnd:
        print("Getting", ering, "data:", loop_count, '\r', end='\r')
        params = get_params(next_token)
        json_response = connect_to_endpoint(url, params)
        # A status code 429 means that the 15 queries per 15 min cap has been reached
        # This will pause the script for 15 mins to allow the time to pass and try again
        while '\"status\": 429' in json.dumps(json_response):
            countdown(int(905))
            print('\r', end='\r')
            json_response = connect_to_endpoint(url, params)
        in_data = pd.json_normalize(json_response['data'])

        if df.empty:
            df = in_data
        else:
            df = pd.concat([df, in_data], ignore_index=True)
        # Get next pagination token if there is one
        if 'next_token' in json_response['meta']:
            next_token = json_response['meta']['next_token']
        else:
            next_token = None
            notEnd = False
        loop_count -= 1
    print('\r\r', end='\r')
    return df


# Get the location to compare against the follower/following location data
def get_location():
    geolocator = Nominatim(user_agent="FollowerDistance")
    # Ask user if they want to use their location, if yes it uses their IP location to compare.
    use_current = input(
        '\nDo you want to use your current location to compare against your followers/following? [Y/N] ')
    longitude_latitude = None
    # If the user selects no they will be prompted for a location to compare against
    if use_current.lower() == "n" or use_current.lower() == "no":
        location_found = None
        while location_found is None:
            look_up_location = input(
                'What location do want to look up (city, state/country)? ')
            location_found = geolocator.geocode(look_up_location)
            if location_found is None:
                print("   ", look_up_location, "was not found, check your spelling or try a different location")
        print('Location used for comparison: ' + str(location_found))
        longitude_latitude = (location_found.latitude,
                              location_found.longitude)
        city = str(location_found).split(',')[0]
    # If yes it will get location data from their IP
    else:
        look_up_location = requests.get('http://ipinfo.io').json()
        city = look_up_location['city']
        region = look_up_location['region']
        country = look_up_location['country']
        print('Location used for comparison: ' +
              city + ', ' + region + ', ' + country)
        longitude_latitude = look_up_location['loc']
    return longitude_latitude, city


# Get distance from the the compare location selected
def get_follower_distance(df_in, current_location, city):
    geolocator = Nominatim(user_agent="FollowerDistance")
    
    distance = []
    found_location = []

    location_df = pd.DataFrame(
        columns=['twit_location', 'distance', 'found_location'])
    # Get a list of locations to look up by deduplicating all the locations from the Following/Follower list
    dedup_df_loc = df_in['location'].drop_duplicates()
    lookup_location = ''

    # Get number of look ups that need to be done
    j = len(dedup_df_loc.index)
    total_lookups = j

    #Loop through list of locations
    for follower_loc in dedup_df_loc:
        follower_loc = str(follower_loc)
        location_in = None
        # Replace location with a searchable one
        # Airport codes do not seem to work
        if follower_loc.lower() == 'atl':
            lookup_location = 'Atlanta, GA'
        # 'Veitshöchheim, Germany' is the exact center of the EU
        elif follower_loc.lower() == 'european union' or follower_loc.lower() == 'eu':
            lookup_location = 'Veitshöchheim, Germany'
        # This was a weird one, 'san jose' for some reason causes the geolocator library to crash
        elif 'san jose' in follower_loc.lower() and 'ca' in follower_loc.lower():
            lookup_location = 'Santa Clara County, California'
        else:
            lookup_location = follower_loc
        # Try to look up user location
        try:
            print(total_lookups, 'locations to look up:', j, "-", follower_loc, "                        \r", end="\r")
            j = j - 1
            location_in = geolocator.geocode(lookup_location)
        # If a location was not found it is set to 'Not Found'
        except:
            temp_df = pd.DataFrame(
                {'twit_location': [follower_loc], 'distance': 'Not Found', 'found_location': 'Not Found'})
            location_df = pd.concat(
                [location_df, temp_df], ignore_index=True)
        else:
            # If location was found compare user input location to the location found and get distance apart
            if location_in is not None:
                lookup_location = (location_in.latitude,
                                    location_in.longitude)
                # Get distance apart in miles
                calculated_distance = geopy.distance.geodesic(
                    current_location, lookup_location).miles
                temp_df = pd.DataFrame(
                    {'twit_location': [follower_loc], 'distance': [calculated_distance], 'found_location': [str(location_in)]}) 
                location_df = pd.concat(
                    [location_df, temp_df], ignore_index=True)
            # If the location was None, set data to 'Not Found'
            else:
                temp_df = pd.DataFrame(
                    {'twit_location': [follower_loc], 'distance': 'Not Found', 'found_location': 'Not Found'})
                location_df = pd.concat(
                    [location_df, temp_df], ignore_index=True)
    print("\033[K", end="")

    # Loop through all user locations and set to the found locations 
    for follower_loc in df_in['location']:
        if not pd.isnull(follower_loc):
            temp_df = location_df.loc[location_df['twit_location']
                                      == follower_loc]
            distance.append(temp_df['distance'].item())
            found_location.append(temp_df['found_location'].item())
        else:
            distance.append(follower_loc)
            found_location.append(follower_loc)
    df_in['distance'] = distance
    df_in['found_location'] = found_location
    return df_in, city


def main():
    # GET shot URL to track the number of runs
    # If you want to see the number of times this script has been run go to the below link:
    # https://www.shorturl.at/url-total-clicks.php?u=shorturl.at%2FauvzF
    requests.request("GET", "https://shorturl.at/auvzF")
    
    # Get the Twitter Bearer Token, if saved it will pull from memory
    # If the Twitter Bearer Token is not saved the user will be prompted
    get_bearer_token()

    # Bring in the global twitter_username variable from outside the def
    global twitter_username
    
    # If the twitter_username was not declared, prompt user for it
    if twitter_username is None:
        twitter_username = input('\nWhat Twitter user are you searching? ')
    user_url = create_user_url(twitter_username)

    # Get basic Twitter data on the user to look up
    twitter_user_id = connect_to_endpoint(user_url, None)
    # Test if the username was found, if not prompt user for it again
    while 'Could not find user with username' in json.dumps(twitter_user_id):
        print('Can not find user ' + twitter_username + ', try again.')
        twitter_username = input('What Twitter user are you searching? ')
        user_url = create_user_url(twitter_username)
        twitter_user_id = connect_to_endpoint(user_url, None)

    # Get the users location
    # It will either be their current IP location or a location they decide
    user_location, user_city = get_location()

    # Start timer to report the total time the script took to run
    start_time = time.time()

    # Get the number of followers and following of inputted Twitter user
    follower_num = int(twitter_user_id['data']['public_metrics']['followers_count'])
    following_num = int(twitter_user_id['data']['public_metrics']['following_count'])

    # Set twitter_user_id variable to the Twitter ID from the 
    twitter_user_id = twitter_user_id['data']['id']
    # Create the follower and following URLs 
    follower_url = create_follower_url(twitter_user_id)
    following_url = create_following_url(twitter_user_id)
    
    # Calculate the number of loops that the script will have to pull follower data
    follower_loops = math.ceil(follower_num/1000)
    # Get the follower data
    follower_df = get_twitter_data(follower_url, follower_loops, "follower")
    follower_df['source'] = 'Follower'

    # Calculate the number of loops that the script will have to pull following data
    following_loops = math.ceil(following_num/1000)
    # Get the following data
    following_df = get_twitter_data(following_url, following_loops, "following")
    following_df['source'] = 'Following'

    # Combine the follower and following data
    df_all = pd.concat([follower_df, following_df], ignore_index=True)
    # Drop duplicate usernames, keeping the followers first
    df_all = df_all.drop_duplicates(subset='username', keep="first")

    # Get distance from followers/following users
    df_all, city = get_follower_distance(df_all, user_location, user_city)

    # Create directory to save output file to, it it is not already there
    create_twitter_dir(twitter_dir)
    # Create User_Info directory if it does not alrady exist
    if not os.path.isdir(twitter_dir + 'User_Info' + dir_separator):
        os.mkdir(twitter_dir + 'User_Info' + dir_separator)
    # Save follower/following data to CSV file
    df_all.to_csv(twitter_dir + 'User_Info' + dir_separator +
                  '{}-{}.csv'.format(twitter_username, city), index=False)
    print("\nSaved Twitter followering data to: " + twitter_dir + 'User_Info' +
          dir_separator + '{}-{}.csv'.format(twitter_username, city))

    # Report total time to run the script
    end_time = time.time()
    total_time = end_time - start_time
    mins, secs = divmod(total_time, 60)
    timer = '{:02d}:{:02d}'.format(int(mins), int(secs))
    print("\nTotal time to run: " + timer,
          "                                                                         ")


if __name__ == "__main__":
    main()
