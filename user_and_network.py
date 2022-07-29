""" 
    - For getting basic info about user: profile statistics, ratings
    - For getting other users' names within a user's network. 
"""

## Imports
from math import ceil
import re
from types import SimpleNamespace
import requests

## Local Imports
from session import SESSION
from util import make_soup


def get_psuedo_username(username, soup=None):
    """ Letterboxd username is the name that corresponds to the URL of the user's profile page
    Their psueodo_username is how their name is displayed on their profile page
    A discrepency between the two occurs if a free user changes their display_name 
        (they cannot change their actual username, like pro users)

    This function retrives the psuedo_username by visiting the user's profile page
    """
    if not soup:
        response = SESSION.request('GET', suburl=f'{username}/')
        soup = make_soup(response)
    
    psuedo_username = soup.find('span', class_='avatar').find('img').get('alt')
    return psuedo_username


class ProfileStatistic():

    def __init__(self, username=SESSION.username):
        self.username = username
        self.soup = make_soup(SESSION.request('GET', f'{self.username}/'))
        
        profile_stats = [int(i.find_all('span')[0].text) for i in self.soup.find('div', class_='profile-stats').find_all('a')]
        self.watched, self.watched_this_year, self.lists, self.following, self.followers = profile_stats


class UserInfo():

    def __init__(self, username=SESSION.username):

        self.username = username
        self.profile_stats = ProfileStatistic(self.username)

    # --- Social Network ---

    """
        Return a list of (e.g followers) - e.g. ['dan_felix', 'kross1987', ...]
        r-type: list
    """

    @property
    def followers(self):
        pages_of_followers = [self.__get_page_of_followers(page_num) for page_num in range(1, ceil(self.profile_stats.followers / 25)+1)]
        return [i for sublist in pages_of_followers for i in sublist]

    @property
    def following(self):
        pages_of_following = [self.__get_page_of_following(page_num) for page_num in range(1, ceil(self.profile_stats.following / 25)+1)]
        return [i for sublist in pages_of_following for i in sublist]

    @property
    def blocked(self):
        if self.username != SESSION.username:
            raise Exception("Cannot get block list of users other than the SESSION's")
        page_of_blocked = [self.__get_page_of_blocked(page_num) for page_num in range(1, ceil(self.profile_stats.blocked / 25)+1)]
        return [i for sublist in page_of_blocked for i in sublist]

    @property
    def mutuals(self):
        following = set(self.following)
        followers = set(self.followers)
        return following.intersection(followers)

    # --- Ratings ---

    @property
    def ratings(self):
        """ Scrapes the user's Letterboxd profile to get the 
        number of times they have rated a film each score between 0.5 and 5.0
        Returns a dict of each score and the corresponding the user has rated that score.
        r-type: dict. """

        # Profile soup (i.e. /username/)
        soup = self.profile_stats.soup

        # Find ratings histogram section
        ratings_section = soup.find('div', class_=['rating-histogram clear rating-histogram-exploded']).find('ul')

        """ There are 10 li tags, 1 for each score 0.5 -> 5
        Within these li tags, there is a link provided that the user has rated >=1 film with that rating. """
        ratings_data = [i.find('a') for i in ratings_section.find_all('li', class_='rating-histogram-bar')]
        if len(ratings_data) != 10:
            raise ValueError("Number of possible rating scores should be 10, not", len(ratings_data))

        """ This link has an attribute 'title', at the start of which is the value for the number 
        of times the user has rated a movie that score. """
        score_count_pattern = r"\d+"
        get_quantity = lambda x: int(re.findall(score_count_pattern, x.get('title'))[0]) if x else 0
        score_quantities = [get_quantity(i) for i in ratings_data]

        # {0.5: 44, 1.0: 108... 5.0: 91}
        return {(score+1)/2: quantity for score, quantity in enumerate(score_quantities)}

    @property
    def total_ratings(self):
        """ Returns the total number of ratings. 
        NOTE: this should align with number on the user's profile. Though it is taken from reading
        the histogram data collected from self.ratings
        r-type: int """
        return sum(self.ratings.values())

    @property
    def avg_rating(self, round_to=2):
        """ Computes the average of the ratings collected in self.ratings.
        r-type: float """
        pre_rounded_score = sum([s*q for s,q in self.ratings.items()])/self.total_ratings
        return round(pre_rounded_score, round_to)
    
    # --- Social Network - Utility ---
    
    @staticmethod
    def __get_people(soup):
        """ Scrapes the profile links (original usernames) of all people on a given person's followers/following page. """
        return [person.find('a').get('href').replace('/', '') for person in soup.find_all("td", class_="table-person")]

    def __get_page_of_followers(self, page_num):
        request = SESSION.request("GET", f"{self.username}/followers/page/{page_num}")
        soup = make_soup(request)
        return self.__get_people(soup)

    def __get_page_of_following(self, page_num):
        request = SESSION.request("GET", f"{self.username}/following/page/{page_num}")
        soup = make_soup(request)
        return self.__get_people(soup)

    def __get_page_of_blocked(self, page_num):
        request = SESSION.request("GET", f"{self.username}/blocked/page/{page_num}")
        soup = make_soup(request)
        return self.__get_people(soup)


class UserRated():
    """ 
    This module mimics the behaviour of a user browsing through someone's rated films.
    You can get the film_ids a user has rated.
    You can also search by criteria (e.g. films released in 2007 that the user rated 4*)
    """
    
    def __init__(self, username=SESSION.username):
        """
        Creates an object associated with a particular Letterboxd username.
        Keyword Arguments:
        username(str):
            Constraints :-
            - must be valid Letterboxd username
                Be sure to use the name in the URL, rather than the one in the profile,
                as the latter can be modified without changing the former.
        """
        self.username = username
        self.psuedo_username = get_psuedo_username(username)
        self.requests_jar = requests.cookies.RequestsCookieJar()

    def __call__(
            self, 
            rated_only=False,
            year=None,
            genre=None,
            service=None,
            rating=None,
            sort_by='name',
            filters=[],
            limit=1000,
            extract=False
        ):
        """
        Returns a list of film_ids that correspond with the given search parameters.
        If no parameters are given, all film_ids in the rated_list will be returned
        
        Parameters:
            rated_only(bool)
            year(str or None):
                Options :-
                - 4 digits e.g. 1975
                - 4 digits + s e.g. 1970s # functions as decade
            genre(str or None):
                Contraints :-
                - must be in genre_list
            service(str or None):
                Constraints :-
                - must be in service_list
            rating(float or None):
                Constraints :-
                    - must be in inclusive range (0.5, 5)
                    - decimal must be 0.5 or 0, like Letterboxd ratings
            sort_by(str):
                How do you want the results sorted?
                Constraints :-
                - must be in sort_list
                Options :-
                - name
                - popular
                - date-earliest (release date)
                - date-latest
                - rating (average rating)
                - rating-lowest
                - your-rating (session user's rating)
                - your-rating-lowest
                - entry-rating (username's rating)
                - entry-rating-lowest
                - shortest (film length)
                - longest
            filters(list):
                Constraints :-
                - must be in SESSION's filters_dict
                Options :- (updated: 2020-11-20)
                - show-liked OR hide-liked
                - show-logged OR hide-logged
                - show-reviewed OR hide-reviewed
                - show-watchlisted OR hide-watchlisted
                - show-shorts OR hide-shorts
                - hide-docs
                - hide-unreleased
        Example suburl in full:
        - username/films/ratings/   year(or decade)/2015/genre/horror/on/amazon-gbr/by/rating
        """

        ## Set cookies according to filters
        filters = '' if not filters else SESSION.get_valid_filters(filters)
        self.requests_jar.set('filmFilter', filters)

        params = {
            'username': self.username,
            'rated_only': rated_only,
            'year': year,
            'genre': genre,
            'service': service,
            'rating': rating,
            'sort_by': sort_by
            }

        suburl = self.__build_suburl(**params)

        film_ids = self.__scrape_rated(suburl, limit)

        if not extract: return film_ids
        return (self.psuedo_username, suburl, film_ids)

    def __scrape_rated(self, suburl, limit):

        film_ids = []
        page_num = 1

        request = SESSION.request('GET', f'{suburl}page/{page_num}', cookies=self.requests_jar)
        soup = make_soup(request)
        num_pages = self.__get_num_pages(soup)

        end_page = min(ceil(limit/18), num_pages)

        while True:

            films_on_page = [int(i.find('div').get('data-film-id')) for i in soup.find_all('li', class_='poster-container')]
            film_ids += films_on_page
            
            if page_num == end_page: 
                break
                
            page_num += 1

            request = SESSION.request('GET', f'{suburl}page/{page_num}', cookies=self.requests_jar)
            soup = make_soup(request)
        
        return film_ids if len(film_ids) < limit else film_ids[:limit] 

    @staticmethod
    def __get_num_pages(soup):
        
        try:
            pagination = soup.find_all('li', class_='paginate-page')[-1]
        except IndexError:
            return 1
        else:
            return int(pagination.find('a').text)

    def __build_suburl(self, **kwargs):

        search_dict = {k:v if type(v) is not str else v.lower() for k,v in kwargs.items()}
        ns = SimpleNamespace(**search_dict)

        ## Get parts of suburl
        username_str = (lambda x: f"{x}/")(ns.username)
        rated_only_str = 'rating/' if ns.rated_only else ''
        year_str = self.get_year_str(ns.year)
        genre_str = self.get_genre_str(ns.genre)
        service_str = self.get_service_str(ns.service)
        rating_str = self.get_rating_str(ns.rating)
        sort_by_str = (lambda x: f"by/{x}/" if x else '')(ns.rated_only)

        ## Create full suburl
        suburl = f"{username_str}films/ratings/{rated_only_str}{rating_str}{year_str}{genre_str}{service_str}{sort_by_str}"
        return suburl

    """
    ** Methods for getting suburl parts for WatchedList search. **
    """
    @staticmethod
    def get_year_str(year):
        """ Converts a year to a section of the URL.
        r-type: str """
        if not year: 
            return ''

        # Ensure year has correct format
        elif not re.match(r"\d{4}s?", year): # 1975 or 1970s
            raise Exception("Invalid year/decade:", year)
        
        # Decade format
        elif 's' in year:
            if year[3] != "0":
                raise Exception(f"Mixed year/decade format: {year}! Please use one or other.")
            elif int(year[:-1]) not in range(SESSION.year_range):
                raise Exception(f"Invalid decade: {year}")
            return f"decade/{year}/"
        # Standard year format
        else:
            if int(year) not in range(SESSION.year_range):
                raise Exception(f"Invalid year: {year}")
            return f"year/{year}/"

    @staticmethod
    def get_genre_str(genre):
        """ Converts a genre to a section of the URL.
        r-type: str """
        if not genre:
            return ''
        elif genre not in SESSION.genre_list:
            raise Exception(f"Invalid genre: {genre}")
        return f"genre/{genre}/"

    @staticmethod
    def get_service_str(service):
        """ Converts a service to a section of the URL.
        r-type: str. """
        if not service:
            return ''
        elif service not in SESSION.service_list:
            raise Exception(f"Invalid service: {service}")
        return f"service/{service}/"

    @staticmethod
    def get_rating_str(rating):
        """ Converts a rating to a section of the URL.
        r-type: str. """
        if not rating:
            return ''

        # Edge cases where number after decimal is not 0 or .5
        elif not (after_decimal := divmod(rating, 1)[1] in (0.5, 0)):
            raise Exception(f"Must be 0 or 0.5 after the decimal to be a valid rating! Not {after_decimal}") 

        # Ensure that rating in inclusive 0.5 to 5 range
        elif not rating*2 in range(1,11):
            raise ValueError("Rating must be in inclusive range (0.5, 5)")

        rating = str(rating)
        if after_decimal == 0.5:
            # Taken from HTML encoding reference
            # This is the string placeholder for a 1/2 star 
            rating = rating[:-2] + "%C2%BD"
        return f"rated/{rating}/"


if __name__ == '__main__':
    #TODO you're only scraping page 1!
    #TODO get stats - i.e. count of followers, following, blocked, mutuals

    p = UserRated()
    print(p.username)

    results = p(rating=0.5, extract=True)
    print(results)

