"""
    Get information about a film given its url.
"""

## Imports
import re
from scipy.stats import beta

## Local Imports
from session import SESSION
from util import make_soup, key_max
from numpy import mean

## Global vars
BAD_MOVIE = 1.55 # OR LESS
GOOD_MOVIE = 3.5 # OR MORE

class FilmInfo():
    """ For getting information about a given film on Letterboxd. """

    def __init__(self, film_path):
        """
        Parameters:
        - film_path (str): the path to the film on Letterboxd
            (e.g. black-swan)
        """

        # Remove '/film/' part of path if passed
        # As this will be added later via property suburl
        pattern = r"(https\:\/\/letterboxd\.com)?(\/film\/)?([-\w\s:]+)/?"

        try:
            self.path = re.findall(pattern, film_path.lower())[0][-1].replace(' ', '-').replace('--', '-')
        except:
            raise IndexError("Could not extract film path from string:", film_path)

        ## Get soup from film's main page
        self.soup = self.__get_soup()
        self.page_wrapper = self.__get_page_wrapper()
        self.filmData = self.__get_filmData_var()
        self.stats = self.__get_stats()

        ## Get soup from film's ratings page (separate page, so second request necessary)
        self.rating_soup = self.__get_rating_soup()
        self.ratings = self.__get_ratings()

        ## Get soup from film's friends ratings page (separate page, so second request necessary)
        self.friend_rated_soup = self.__get_friend_rated_soup()

        ## Load the film's properties into memory
        try:
            self.__get_film_info()
        except:
            print(f"Failed to get film info for {film_path}")
            self.id_ = False

    def __repr__(self):
        cls_name = self.__class__.__name__
        string = f"\tPath: {self.path}"
        string += f"\tName: {self.name}"
        return f"< {cls_name}{string} >"

    def __str__(self):
        s = ''
        s += f"Name: {self.name}"
        if self.director: s += f"\nDirector: {self.director}"
        if self.cast: s += f"\nCast: {self.cast}"
        if self.genres: s += f"\nGenre(s): {self.genres}"
        if self.release_year: s += f"\nYear: {self.release_year}"
        if self.language: s += f"\nLanguage: {self.language}"
        if self.country: s+= f"\nCountry: {self.country}"
        if self.ratings: s+= f"\nRating: {round(self.letterboxd_rating,3)} ({round(self.letterboxd_rating_fallback,3)})"
        return s

    @property
    def suburl(self):
        """ Returns the suburl for this film
        Used for making the request to the film's page on Letterboxd. """
        return f"film/{self.path}/"
    
    # --- Soup Getters - Main page ---

    def __get_soup(self):
        request = SESSION.request("GET", self.suburl)
        return make_soup(request)

    def __get_page_wrapper(self):
        """ Go the main film_page and grab the soup. 
        r-type: BeautifulSoup"""
        page_wrapper = self.soup.find('div', id='film-page-wrapper')
        return page_wrapper

    def __get_filmData_var(self):
        """ Letterboxd moved their name, releaseYear, and posterURL properties to a <script> under the variable filmData """
        
        pattern = re.compile(r"var filmData = \{(.*?)\};")
        try:
            script = self.soup.find("script", text=pattern)
            filmData = pattern.search(script.text).group(1).strip()
        except:
            print(f"\nFailed to get film data for {self.path}")
            raise

        return filmData

    def __get_stats(self):
        """ Watches; Lists; Favourites """
        suburl = f"esi/film/{self.path}/stats"
        request = SESSION.request("GET", suburl)
        return make_soup(request)

    # --- Info Extracters - Main page ---
    def __get_film_info(self):
        """ Grab the information available from the main page.
        - id
        - name
        - release year
        - poster_url
        - language
        - country
        - genre(s)
        - director
        - cast
        r-type: None
        All information is set to instance variables
        """

        ## --- filmData ---
        pattern = r"name: \"(.*?)\","
        self.name = re.findall(pattern, self.filmData)[0]

        pattern = r"releaseYear: \"(.*?)\","
        self.release_year = int(re.findall(pattern, self.filmData)[0])

        pattern = r"posterURL: \"(.*?)\","
        self.poster_url = re.findall(pattern, self.filmData)[0]
        
        ## --- Info ---
        info = self.page_wrapper.find('div', class_='film-poster')
        self.id_ = info.get('data-film-id')

        ## --- Details ---
        tab_details = self.page_wrapper.find('div', id="tab-details")

        # Language
        try:
            language_string = str(tab_details.find('a', attrs={'href': re.compile("/films/language/")}).get('href'))
        except:
            self.language = None
        else:
            self.language = language_string.split('language/')[1][:-1]

        # Country
        try:       
            country_string = str(tab_details.find('a', attrs={'href': re.compile("/films/country/")}).get('href'))
        except:
            self.country = None
        else:        
            self.country = country_string.split('country/')[1][:-1]

        ## Studio
        try:       
            studio_string = str(tab_details.find('a', attrs={'href': re.compile("studio/")}).get('href'))
        except:
            self.studio = None
        else:        
            self.studio = studio_string.split('studio/')[1][:-1]

        ## Genres
        try:
            tab_genres = self.page_wrapper.find('div', id="tab-genres")
            genre_links = tab_genres.find_all('a', class_='text-slug', attrs={'href': re.compile('/films/genre/')})
        except:
            self.genres = []
        else:
            self.genres = [i.get('href').split('genre/')[1][:-1] for i in genre_links]

        ## Cast
        try:
            tab_cast = self.page_wrapper.find('div', id="tab-cast")
            cast_list = tab_cast.find('div', class_='cast-list')
        except:
            self.cast = []
        else:
            self.cast = [i.text for i in cast_list.find_all('a')]
        
        ## Director
        try:
            film_header = self.page_wrapper.find('section', id='featured-film-header')
            self.director = film_header.find('a', href=re.compile('director')).text
        except:
            self.director = ''

        # --- Soup ---
        try:
            self.description = ' '.join([i.text for i in self.soup.find("div", class_="review").find_all("p")]).strip()
        except:
            self.description = ''

        ## --- Rating Soup ---

        ## Fans
        try:
            pattern = r"([\w\d\.]+) fans"
            fans = re.findall(pattern, self.rating_soup.text)[0]
        except:
            self.fans = 0
        else:
            self.fans = self.letterboxd_number_to_int(fans)

        ## --- Stats ---
        film_stats = self.stats.find("ul", class_="film-stats")
        self.views = self.letterboxd_number_to_int(film_stats.find_all('li')[0].text)
        self.lists = self.letterboxd_number_to_int(film_stats.find_all('li')[1].text)
        self.likes = self.letterboxd_number_to_int(film_stats.find_all('li')[2].text)

        ## --- My Rating ---
        #TODO Not able to find rating in any /csi/ links for films I've reviewed more than once

        ## --- Friends ---
        extract_rating = lambda x: x.count('★') + (0.5 * x.count('½'))
        friends_ratings = [extract_rating(i.text) for i in self.friend_rated_soup.find_all('span', class_='rating')]
        self.friends_ratings = {int(i): friends_ratings.count(i/2) for i in [i for i in range(1,11)]}

    @staticmethod
    def letterboxd_number_to_int(string):
        pre_final = float(string.replace('K', ' ').replace('M', ' '))
        if 'K' in string: pre_final *= 1000
        if 'M' in string: pre_final *= 1000000
        return int(pre_final)

    @property
    def length(self):
        """ Uses the page wrapper to grab the film_length. """
        footer = self.page_wrapper.find('p', class_=['text-link', 'text-footer'])
        text = footer.text
        try:
            film_length = re.findall(r"([\d,]+)", text)[0]
        except:
            return False
        else:
            return int(film_length.replace(',', ''))

    @property
    def is_short(self):
        """ #TODO change from hard code """
        if (fl:=self.film_length) is False:
            return False
        return fl < 40 

    @property
    def description_short(self):
        description = self.description
        
        cutoff = 128
        if len(description) < cutoff:
            return description
        
        while cutoff >= 1:
            cutoff -= 1
            if description[cutoff] == ' ':
                break

        try:
            description_short = '' if not cutoff else self.description[0:cutoff]
        except IndexError:
            description_short = self.description
        finally:
            return '' if not description else f"{description_short}..."

    # --- Soup Getters - Ratings page ---

    def __get_rating_soup(self):
        """ The film's rating info is loaded from a different page
        Hence we make the request to this separate page to get it
        r-type: BeautifulSoup """
        suburl = f"csi/film/{self.path}/rating-histogram/"
        request = SESSION.request("GET", suburl)
        return make_soup(request)

    def __get_friend_rated_soup(self):
        """ The film's friend rating info is loaded from a different page
        Hence we make the request to this separate page to get it
        r-type: BeautifulSoup """
        suburl = f"csi/film/{self.path}/friend-activity/?esiAllowUser=true"
        request = SESSION.request("GET", suburl)
        return make_soup(request)

    # --- Info Extracters - Ratings page ---
    
    def __get_ratings(self):
        """ Scrapes the user's Letterboxd profile to get the 
        number of times they have rated a film each score between 0.5 and 5.0
        Returns a dict of each score and the corresponding the user has rated that score.
        r-type: dict. """
        if not self.rating_soup.text:
            return None

        """ There are 10 li tags, 1 for each score 0.5 -> 5
        Within these li tags, there is a link provided that the user has rated >1 film with that rating. """
        ratings_data = [i.find('a') for i in self.rating_soup.find_all('li', class_='rating-histogram-bar')]
        
        if len(ratings_data) != 10:
            raise ValueError("Number of possible rating scores should be 10, not", len(ratings_data))
        
        """ This link has an attribute 'title', at the start of which is the value for the number 
        of times the user has rated a movie that score. """
        score_count_pattern = r"[\d,]+"
        get_quantity = lambda x: int(re.findall(score_count_pattern, x.get('title'))[0].replace(',', '')) if x else 0
        score_quantities = [get_quantity(i) for i in ratings_data]

        return {score+1: quantity for score, quantity in enumerate(score_quantities)} # {0.5: 44, 1.0: 108... 5.0: 91}
        
    @property
    def num_ratings(self):
        return self.get_total_ratings()

    @property
    def is_obscure(self):
        """ Checks the ratings soup to ensure that the film does not have enough ratings
        to be given a standard rating - otherwise creating an instance of this class
        is pointless because grabbing the standard rating would be easier. """
        return self.num_ratings < 30

    def get_total_ratings(self, rating=None):
        """
        Returns the count of a given rating for the film (e.g number of 4* ratings)
        
        If no argument passed, will return total ratings.
        However, you should use num_ratings property to get this info.

        Params:
        - rating (int), inclusive range 1 to 10.
        r-type: int """
        if not self.ratings:
            return 0
        elif not rating:
            return sum(self.ratings.values())
        return self.ratings[rating]

    @property
    def total_rating_score(self):
        """ Computes the combined score of all ratings """
        if not self.num_ratings: return 0
        return sum([s*q for s,q in self.ratings.items()])

    @property
    def letterboxd_rating(self):
        """ Returns the Letterboxd rating, if there is one.
        NOTE: Letterboxd uses a weighted average to calc. rating
        NOTE: Films with <30 num_ratings are not given a LB rating.
        """
        if self.num_ratings < 30:
            return None # NOTE this was FALSE before, may cause #BUG later

        pattern = r"Weighted average of ([\d\.]+) based on"
        title = self.rating_soup.find('a', attrs={'title': re.compile(pattern)}).get('title')
        return float(re.findall(pattern, title)[0])

    @staticmethod
    def __get_bayesian_average(d, a0=9, no_rating_fallback=2.75):
        if not d or not any(d.values()): return no_rating_fallback
        ratings = dict(d)

        up = [ratings[n] * ((n-1)/9) for n in range(1,11)]
        up[-1] /= 1.5
        up = sum(up)
        
        down = [ratings[n] * ((9-(n-1))/9) for n in range(1,11)]
        down[0] *= 1.5
        down = sum(down)
        
        return ( beta.ppf(0.05, up + a0, down + a0)  *4.5 ) + 0.5

    @property
    def bayesian_average(self):
        return self.__get_bayesian_average(self.ratings)

    @property
    def bayesian_average_friends(self):
        return self.__get_bayesian_average(self.friends_ratings, no_rating_fallback=None)

    @property
    def letterboxd_rating_fallback(self):
        """ Returns the Letterboxd rating, if there is one.
        ELSE returns its true average rating for films w/ <30 ratings.
        """
        if self.num_ratings < 30:
            return self.true_avg_rating

        pattern = r"Weighted average of ([\d\.]+) based on"
        title = self.rating_soup.find('a', attrs={'title': re.compile(pattern)}).get('title')
        return float(re.findall(pattern, title)[0])

    @property
    def true_avg_rating(self):
        """ Computes the mean of the ratings collected in self.ratings.
        r-type: float """
        if not self.num_ratings:
            return 0
        return (self.total_rating_score / self.num_ratings) * 0.5

    def get_true_avg_rating(self, no_rating_fallback=5, cutoff=3):
        if self.num_ratings < cutoff:
            return no_rating_fallback
        return self.true_avg_rating

    def get_slanted_avg_rating(self, no_rating_fallback=5, cutoff=3):
        if self.num_ratings < cutoff:
            return no_rating_fallback
        ratings = dict(self.ratings)
        ratings[1] *= 1.2
        ratings[2] *= 1.05
        ratings[10] *= 0.75

        num_ratings = sum(ratings.values())

        return sum([s*q for s,q in ratings.items()])  / num_ratings * 0.5 

    @property
    def ironic_ratings(self):
        if not self.ratings: return False
        ratings = dict(self.ratings)
        return self.num_ratings >= 10 and sorted([key_max(ratings), key_max(ratings, 2)]) == [1,10]

    def is_bad(self, no_rating_fallback=5, cutoff=5):
        # if self.is_hated(cutoff):
        #     return True
        if self.ironic_ratings:
            return True
        return self.bayesian_average < 1.6 and key_max(dict(self.ratings), only_max=True) == 1

    def is_good(self, no_rating_fallback=5, cutoff=5):
        return self.get_slanted_avg_rating(no_rating_fallback, cutoff) >= (GOOD_MOVIE)

    def is_hated(self, cutoff=5):
        """ Most frequent rating is 1/2 star """
        if self.num_ratings < cutoff:
            return False
        if key_max(self.ratings) != 1:
            return False
        return True    

    @property
    def url(self):
        return f"{SESSION.MAIN_URL}{self.suburl}"


if __name__ == '__main__':
    ''' Testing '''


    for i in [
        # 'bassie-adriaan-in-het-theater-25-jaar-theater',
        # 'morbius',
        # 'Bedwetting Beautiful Ghost',
        # 'Semur-seytann-kabilesi',
        # '2025-the-world-enslaved-by-a-virus',
        # 'the-strip-tease-murder-case',
        # 'razorteeth',
        # 'nightmare museum',
        # 'badr',
        # 'Attraction',
        # 'what-i-did-for-love-1998',
        # 'xuxa-popstar',
        # 'another-9-1-2-weeks'
        'https://letterboxd.com/film/draculas-guest/',
        'https://letterboxd.com/film/naughty-40/'



    ]:
        print(f"\n{'='*30}\n")
        x = FilmInfo(i)
        print(x.name)
        # print(x.name)
        # print(x.bayesian_average)
        # print(x.bayesian_average_friends)
        # print(x.studio)
        # print(x.friend_rated_soup.find_all('span', class_='rating'))
        # print(x.ratings)
        # print(x.true_avg_rating)
        print(x.url)
        print(x.bayesian_average_friends)
        print(x.bayesian_average)
        # print(x.get_slanted_avg_rating())
        # print(x.get_bayesian_average())
        # print(x.is_bad())



    print("???")

    # # print(x.ratings)
    # # print(x.is_hated())
    # # print(x.is_good())
    # print(x.is_bad())
    # print(x.is_hated())
    # print(x.ironic_ratings())
    # # print(x.letterboxd_rating)
    # # print(x.letterboxd_rating_fallback)
    # # print(x.true_avg_rating)
    # print(x.get_slanted_avg_rating())
    # # print(x.ironic_ratings())

    # print("="*30)

    # x = FilmInfo('Daughter for Sale')
    # print(x.is_bad())
    # print(x.is_hated())
    # print(x.ironic_ratings())
    # print(x.get_slanted_avg_rating())

    # print("="*30)

    # x = FilmInfo('Earth Minus Zero')
    # print(x.is_bad())
    # print(x.is_hated())
    # print(x.ironic_ratings())
    # print(x.get_slanted_avg_rating())


    # print(x.letterboxd_rating)
    # print(x.letterboxd_rating_fallback)
    # print(x.true_avg_rating)
    # print(x.num_ratings)
    # print(x.total_rating_score)
    # print(x.num_ratings)
    # print(x.true_avg_rating)

    # for film in ['pocong mandi goyang pinggul', 'hip hop locos']:
    #     test = FilmInfo(film)
    #     print(test.path)
    #     print(f"{test.name}: {test.letterboxd_rating} vs {test.true_avg_rating}")
