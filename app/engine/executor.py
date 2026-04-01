import requests


class Executor:

    def execute(self, request: dict, payload: dict, headers: dict = None) -> dict:
        from app.config.settings import settings

        url = request["endpoint"]
        method = request.get("method", "POST")
        timeout = settings.executor_timeout

        try:
            if method == "POST":
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            elif method == "GET":
                response = requests.get(url, params=payload, headers=headers, timeout=timeout)
            else:
                raise Exception(f"Unsupported HTTP method: {method}")

            try:
                body = response.json()
            except Exception:
                body = response.text

            return {"status_code": response.status_code, "body": body}

        except requests.exceptions.Timeout:
            return {"status_code": 408, "error": "timeout"}
        except requests.exceptions.ConnectionError:
            return {"status_code": 503, "error": "connection_error"}
        except Exception as e:
            return {"status_code": 500, "error": str(e)}
