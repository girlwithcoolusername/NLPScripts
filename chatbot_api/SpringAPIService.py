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
            print(f"Error logging in: {response.status_code} - {response.text}")
            self.token = None

    def _make_request(self, method, endpoint, data=None, success_status=None, error_status=None):
        global response
        if not self.token:
            self._get_token()

        if success_status is None:
            success_status = {200}  # Default success status
        if error_status is None:
            error_status = set()  # Default empty error status set

        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        if method == "post":
            response = requests.post(url, headers=headers, json=data)
        elif method == "delete":
            response = requests.delete(url, headers=headers, json=data)
        elif method == "put":
            response = requests.put(url, headers=headers, json=data)
        elif method == "get":
            response = requests.get(url, headers=headers)
        if response.status_code in success_status:
            try:
                return response.json()
            except ValueError:
                return response.text
        elif response.status_code in error_status:
            return response.text
        else:
            print(f"Unexpected response {response.status_code}: {response.text}")
            response.raise_for_status()

    def get_data(self, endpoint):
        return self._make_request('get', endpoint)

    def post_data_check(self, endpoint, data):
        return self._make_request('post', endpoint, data)

    def post_data_text(self, endpoint, data):
        return self._make_request('post', endpoint, data, success_status={200, 201}, error_status={400, 404})

    def delete_data(self, endpoint, data):
        return self._make_request('delete', endpoint, data, success_status={200, 204}, error_status={404, 400})

    def put_data(self, endpoint, data):
        return self._make_request('put', endpoint, data, success_status={200, 201}, error_status={400, 404})
