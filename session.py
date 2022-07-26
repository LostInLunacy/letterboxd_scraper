"""
    For creating the requests.Session() that is used to make requests as the user.
"""

## Imports
import requests
from bs4 import BeautifulSoup as bs4
from types import SimpleNamespace
import pendulum
import re
import json

## Local Imports
import util
from exceptions import LoginException, LetterboxdException

## Global variables
FN_USER_DETAILS = "user_details" # Filename for getting user's credentials
USER_AGENT = util.load_json_data("user_agent")
make_soup = util.make_soup


class LetterboxdSession(requests.Session):
    """ Creates a session object that can be used to make requests as the user. """

    MAIN_URL = "https://letterboxd.com/"

    def __init__(self):
        super().__init__()

        ## Add User Agent
        self.headers.update(USER_AGENT)

        ## Set CSRF token
        token = self.__get_token()
        self.cookie_params = {'__csrf': token}

        ## Login details
        self.logged_in = False
        self.login_details = self.get_details_from_file()

        ## Search options and available filter
        self.__search_options = make_soup(self.request("GET", f"films/by/rating"))
        self.__search_options_user = make_soup(self.request("GET", f"{self.username}/films"))

        self.year_range = (1860, pendulum.now()._start_of_decade().year+10)
        self.genre_list = self.__get_genre_list()
        self.service_list = self.__get_service_list()
        self.sortby_list = self.__get_sortby_list()
        self.region_dict, self.language_dict = self.__get_country_language_dict()
        self.filters_dict = self.__get_filters_dict()

    def __str__(self):
        return f"Session (Logged in == {self.logged_in})"

    def __repr__(self):
        return f"<{type(self).__name__}>\nusername: {self.username}\nlogged_in: {self.logged_in}"

    ## *** Overloading ***
    @staticmethod
    def get_html_response_dict(response):
        """
        Util function that checks for erorrs in the HTML response.
        
        This function is called if response.ok == False
        """

        try:
            message_dict = json.loads(response.text)
        except:
            return

        if message_dict['result']:
            return 
        
        # The keys that exist within the message that we want to print out when raising the Exception
        error_msg_keys = [k for k in ('messages', 'errorCodes', 'errorFields') if k in message_dict.keys()]
        
        message = ''
        for key in error_msg_keys:
            message += f"\n{key}: "
            while (values := message_dict[key]):
                message += f"\n\t{values.pop(0)}"
        
        message = message.rstrip()

        # Raise the Exception because the message_dict['result'] evaluated to false
        raise LetterboxdException(message)

    def request(self, method, suburl='', **kwargs):
        """ 
        ** Overloading **
        Customise request to default to main Letterboxd url.
        And to include the __CSRF token if it's a POST request. 
        """
        if method == "POST":

            # No data passed. Create default data
            if not (data := kwargs.get("data")):
                kwargs['data'] = self.cookie_params

            else:
                # If data type is SimpleNamespace, convert to dict
                if isinstance(data, SimpleNamespace): 
                    kwargs['data'] = {i:j for i,j in data.__dict__.items()}
                
                # Add default data to passed data
                kwargs['data'] = dict(self.cookie_params, **kwargs['data'])

        response =  super().request(
            method,
            url=f"{self.MAIN_URL}{suburl}",
            **kwargs
        )
        
        if not response.ok:
            response.raise_for_status()
        
        self.get_html_response_dict(response)

        return response

    ## --- Token ---

    def __get_token(self):
        """ Get the __csrf token and pass its value to an instance variable.
        Called by __init__. """
        self.request("GET")
        token = self.cookies['com.xk72.webparts.csrf']
        return token

    ## --- User Details ---

    @staticmethod
    def get_details_from_file():
        """
        Gets the user's details form the user details json file.
        r-type: SimpleNamespace.
        """
        user_details = util.load_json_data(FN_USER_DETAILS)
        assert list(user_details.keys()) == ["username", "password"]

        return SimpleNamespace(**user_details)

    @property
    def username(self):
        return self.login_details.username

    @property
    def password(self):
        return self.login_details.password

    ## --- Logging In ---

    def __login(self):
        """ Attempt to login to Letterboxd
        If result unsuccessful -> attempts to return error displayed on webpage. """

        response = self.request('POST', '/user/login.do', data=self.login_details)
        soup = make_soup(response)
        text = soup.text

        result_pattern = r"\"result\": \"(\w+)\""
        result = re.findall(result_pattern, text)[0]

        if result == 'success': # Login successful
            print(f'Login successful! Welcome, {self.username}')
            return True

        # Else, assume error
        error_msg_pattern = r"\"messages\": \[([^\]]+)"
        
        try:
            # Try to find specific error in HTML
            error = re.findall(error_msg_pattern, text)[0]
        except IndexError:
            # Could not find specific error
            raise LoginException('Unknown exception')
        else:
            raise LoginException(error)

    def __call__(self):
        """ Login to Letterboxd if not already. """

        # Already logged in - __call__ func not needed
        if self.logged_in:
            print("Already logged in")
            return
            
        self.__login()

    ## --- Getting List of Search Options and Available Filters ---
    
    def __get_genre_list(self):
        """ Returns the list of genres you can search by on Letterboxd. """
        return [i.text.lower() for i in self.__search_options.find_all('a', attrs={'class': 'item', 'href': re.compile('/films/genre/')})]

    def __get_service_list(self):
        """ Returns a list of services you can search by on Letterboxd.
        NOTE: I think these may be specific to the user. 
        The code should still work since this is scraped using the user's session. """
        return [i.text.strip() for i in self.__search_options.find('ul', id='services-menu').find_all('a')]

    def __get_sortby_list(self):
        """ Returns a list of sort_by options on Letterboxd """
        pattern = r"films\/([a-z\/-]+)\/size\/small"
        return [re.findall(pattern, i.get('href'))[0] for i in self.__search_options.find_all('section', class_='smenu-wrapper')[1].find_all('a')]

    def __get_country_language_dict(self):
        response = self.request('GET', 'countries')
        soup = make_soup(response)

        ## Get list of regions
        list_items = soup.find_all('a', attrs={'href': re.compile('/country/')})
        region_dict = {i.get('href').split('/')[3]: int(i.find('span', class_='count').text.replace(',', '')) for i in list_items}
        # region_dict = {i.find('span', class_='name').text: int(i.find('span', class_='count').text.replace(',', '')) for i in list_items}

        ## Get list of languages
        list_items = soup.find_all('a', attrs={'href': re.compile('/language/')})
        language_dict = {i.get('href').split('/')[3]: int(i.find('span', class_='count').text.replace(',', '')) for i in list_items}

        return region_dict, language_dict

    def __get_filters_dict(self):
        """ Returns a list of the filters that can be applied to the session
        (e.g. hide-reviewed)
        """
        filter_li_tags = self.__search_options_user.find_all('li', class_='js-film-filter')
        data_categories = set([i.get('data-category') for i in filter_li_tags])
        filters = {i:[] for i in data_categories}
        [filters[i.get('data-category')].append(i.get('data-type')) for i in filter_li_tags]
        return filters

    def get_valid_filters(self, filters_tuple):
        """ 
        Given a tuple of filters (args),
        merges all into a valid filters string that can 
        subsequently be passed as a cookie to a search request
        Parameters:
        - Filters
            (e.g. show-watched)
        """
        # Check that format of each filter is correct
        pattern = r"^\w+-{1}\w+$" # >text-text<
        if not all([re.findall(pattern, i) for i in filters_tuple]):
            raise Exception("Invalid filters. Please use proper format.")
        
        # Checks each passed filter against those scraped from Letterboxd
        # to ensure that they are all valid
        filters = {}
        temp_args = list(filters_tuple)
        while temp_args:
            data_type, data_cat = temp_args.pop().split('-')
            if data_cat not in self.filters_dict.keys():
                raise Exception(f"Invalid data_category: {data_cat}")
            elif data_type not in self.filters_dict[data_cat]:
                raise Exception(f"Invalid data_type {data_type} for data_category: {data_cat}")

        filters = '%20'.join(filters_tuple)
        return filters


## Create Session
SESSION = LetterboxdSession()

## Login
SESSION()


if __name__ == '__main__':
    pass
