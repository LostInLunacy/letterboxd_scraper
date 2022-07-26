
## Imports
import re
from tqdm import tqdm

## Local Imports
from session import SESSION, make_soup

class FilmSearch():
    """ Search for all the films (unless a page limit is specificed) for
    a given year, genre, or both. 
    """

    def __init__(self, sort_by='popular', genre=None, decade=None, year=None, country=None, language=None):
        """
        Sort by:
        - by/name
        - by/release
        - by/release-earliest
        - by/your-rating
        - by/your-rating-lowest
        - by/rating
        - by/rating-lowest
        - by/shortest
        - by/longest
        - popular
        - popular/this/year
        - popular/this/month
        - popular/this/week

        Genre (str)
        - Must be in SESSION.genre_list

        Year / Decade 
        - Must be valid decade on Letterboxd database (e.g. 1730 is invalid)

        Country (str)
        - Must be valid country listed on Letterboxd (i.e. with one film or more)

        Langauge (str)
        - As with country

        NOTE: Filters:
        - I can't recall why, but filters will not work with search. 
            If you require them, may have to:
                temp transport to list -> filter that list -> get desired entries
        """

        ## Ensure lower case otherwise requests don't work
        if genre: genre = genre.lower()
        if country: country = country.lower()
        if language: language = language.lower()
        

        ## Ensure valid data
        if year and decade:
            raise Exception("You cannot search by both decade and year!")  
        if year and year not in range(*SESSION.year_range):
            raise ValueError(f"Invalid year: {year}")
        if decade and decade not in range(*SESSION.year_range, 10):
            raise ValueError(f"Invalid decade: {decade}")
        if genre and genre not in SESSION.genre_list:
            raise ValueError(f"Inavlid genre: {genre}")
        if country and country not in list(i.lower() for i in SESSION.region_dict.keys()):
            raise ValueError(f"Invalid country: {country}")
        if language and language not in list(i.lower() for i in SESSION.language_dict.keys()):
            raise ValueError(f"Invalid language: {language}") 
        if sort_by not in SESSION.sortby_list:
            raise ValueError(f"Invalid sort_by option: {sort_by}")

        ## Convert decade to string for making requests
        if decade: decade = f"{decade}s"

        ## Replace spaces w/ hyphens
        if genre: genre = genre.replace(" ", "-")

        ## Set variables
        self.sort_by = sort_by
        self.genre = genre
        self.year = year
        self.decade = decade
        self.country = country
        self.language = language

    def __str__(self):
        return f'''\
        == FilmSearch ==\
        \nGenre:\
        \nYear:\
        \nDecade:\
        \nCountry:\
        \nLanguage\
        \nSort by:\
        '''

    def __repr__(self):
        cls_name = self.__class__.__name__
        return f'{cls_name} ({self})'

    def __call__(self, info=False, start_page=1, page_limit=None):
        """ Return film data as a list of dicts, each dict containing 'id' and 'link'
        r-type: list of dicts 
        """
        suburl = self.suburl
        film_data = []

        # Identify stopping point for while loop
        stop_page = start_page + (page_limit-1) if page_limit else self.num_pages

        def scrape_page(page_num):
            request = SESSION.request("GET", f"{suburl}page/{page_num}/")
            soup = make_soup(request)
            return self.get_page_of_film_ids(soup) if not info else self.get_page_of_film_info(soup)
        
        ## Commence scraping
        print(f'{self}\n\n**Searching now...**')
        [film_data.extend(scrape_page(i)) for i in tqdm(range(start_page, stop_page+1))]            

        return film_data

    @property
    def suburl(self):
        """ Construct a full suburl given the arguments passed to the init function.
        NOTE: Letterboxd does not make use of URL parameters, so the URL has to 
        be constructed in this ugly manner
        r-type: str
        """
        suburl = f"films/ajax/{self.sort_by}/"

        ## Add Years
        if self.year: 
            suburl += f"year/{self.year}/"
        elif self.decade:
            suburl += f"decade/{self.decade}/"

        ## Add Genres
        if self.genre: suburl += f"genre/{self.genre}/"

        ## Add Country
        if self.country: suburl += f"country/{self.country}/"

        ## Add language
        if self.language: suburl += f"language/{self.language}/"

        ## Add mandatory size/small section of suburl
        suburl += "size/small/"

        ## Final
        return suburl

    @property
    def num_pages(self):
        """ Return the number of pages in the selected search.
        r-type: int """
        request = SESSION.request("GET", self.suburl)
        soup = make_soup(request)

        h2_text = soup.find('h2', class_='ui-block-heading').text
        num_films = int(re.findall(r"([\d,]+)", h2_text)[0].replace(',', ''))
        num_pages = num_films//72+1
        return num_pages

    @staticmethod
    def get_page_of_film_ids(soup):
        """ Return a list of dictionaries containing film data for a single page.
        r-type: list of dicts """
        
        divs = [i.find('div') for i in soup.find_all('li', class_=['listitem', 'poster-container'])]
        films = [ {'filmId': int(i.get('data-film-id'))} for i in divs ] 
        return films

    @staticmethod
    def get_page_of_film_info(soup, popular=True, obscure=True):
        """ Return a list of dictionaries containing film data for a single page.
        r-type: list of dicts """
        
        if all([x is not True for x in (popular, obscure)]):
            raise ValueError("<popular> and <obscure> can't BOTH be false!")

        li_list = [i for i in soup.find_all('li', class_=['listitem', 'poster-container'])]

        # Lambda for scraping name of film
        link_name_getter = lambda x: re.findall(r"/film/([\w\d:-]+)/", x)[0] # NOTE digits are necessesary e.g. /film/boat-2009/
        
        # Lambda for identifying if a film is obscure (i.e. doesn't have a letterboxd rating, meaning <30 total ratings)
        obscure_identifier = lambda x: not x.has_attr('data-average-rating')

        # Lambda for getting surface rating of film
        rating_getter = lambda x: x.get('data-average-rating', False)
        
        films = [ {'filmId': int(i.find('div').get('data-film-id')), 'link': link_name_getter(i.find('div').get('data-film-slug')), 'obscure': obscure_identifier(i), 'rating': rating_getter(i)} for i in li_list ]
        return films



if __name__ == "__main__":
    ''' Testing '''

    pass
    
    # F = FilmSearch(genre="horror", year=2021, country="brazil")
    # films = F(start_page=1, page_limit=3)
    # print(films)