import requests


class SpringAPIService:
    def __init__(self, base_url, username, password, role):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.role = role
        self.token = None

    def _get_token(self):
        login_url = f"{self.base_url}/login"
        payload = {
            "username": self.username,
            "password": self.password,
            "role": self.role
        }
        response = requests.post(login_url, json=payload)
        if response.status_code == 200:
            token_data = response.json()
            self.token = token_data.get('token')
        else:
            print(f"Error logging in: {response.status_code}")
            self.token = None

    def get_data(self, endpoint):
        if not self.token:
            self._get_token()

        url = f"{self.base_url}/{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error accessing {url}: {response.status_code}")
            return None

    def post(self, endpoint, data, type):
        if not self.token:
            self._get_token()

        url = f"{self.base_url}/{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200 or response.status_code == 201:
            if type == "JSON":
                return response.json()
            else:
                return response.text
        elif response.status_code == 404 or response.status_code == 400:
            if type == "JSON":
                return response.json()
            else:
                return response.text
        else:
            return None

    def post_data_check(self, endpoint, data):
        if not self.token:
            self._get_token()

        url = f"{self.base_url}/{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return None

    def post_data(self, endpoint, data):
        return self.post(endpoint, data, "JSON")

    def post_data_text(self, endpoint, data):
        return self.post(endpoint, data, "TEXT")

    def delete_data(self, endpoint, data):
        if not self.token:
            self._get_token()

        url = f"{self.base_url}/{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        response = requests.delete(url, json=data, headers=headers)
        if response.status_code in [200, 400, 404]:
            return response.text
        else:
            return None

    def put_data(self, endpoint, data):
        if not self.token:
            self._get_token()

        url = f"{self.base_url}/{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        response = requests.put(url, json=data, headers=headers)
        if response.status_code in [200,201, 400, 404]:
            return response.text
        else:
            return None
