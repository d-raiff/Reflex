import requests
import reflexsive
import reflexsive.core

class B(reflexsive.Reflexsive):
    @reflexsive.Reflexsive.alias('fetch')
    def fetch_pdf(self, url: str) -> requests.Response:
        return requests.get(url)

class B_meta(metaclass=reflexsive.core.ReflexsiveMeta):
    @B.alias('login', username='usr', password='pwd', secret='sec')
    @B.alias('login', username='u', password='p')
    def login_user(self, username: str, password: str) -> None:
        print(f'Logging in {username} with {password}.')