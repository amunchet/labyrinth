# Flask-Auth0 Quickstart Scaffolding Template
This is a simple project to quickstart a project using Flask (Python), Docker, and Auth0 authentication.

## Requirements
- Docker.  Docker-compose is recommended, but not required.
- Python3 (for the setup script)


## Setup Instructions
0.  Clone this repository `git clone https://github.com/amunchet/flask-auth0-quickstart.git`
1.  `cd flask-auth0-quickstart`
2.  `./setup.py` (or `python setup.py`)
3.  Follow the instructions.
4.  Enjoy!


## Tests
There are some basic tests to make sure the URLs are protected.  

**These must be run in the created docker**

1.  `cd /src/`
2.  `pytest`

When writing further test, take a look at `common/test.py` for the `unwrap` function.  That will allow you to test functions that are wrapped in the security decorator.  Syntax is `unwrap(wrapped_function)(function_arguments)`

## Typical Next Steps
This project is meant to be a starting point.  From here, a typical workflow could look at follows.

1.  `mv [PROJECT NAME] ..`
2.  `cat docker-compose.yml >> ../docker-compose.yml`
3.  `cd .. && rm -rf flask-auth0-quickstart`



## Trying out the authentication
To try out the authentication, you will need your Authorization Header from an already authenticated request.  Copy that (it should begin wtih "Bearer ...")

1.  `import requests`
2.  `a = requests.get("http://localhost:[PORT]/secure", headers={"Authorization" : "Bearer ..."})`

3.  If you did not set your user to have permissions `read`, the request will return `401`.  Otherwise, `a.text` contain "Secure route."

If you have a problem, check to make sure your Auth0 permissions are configured correctly for your user.

## Design Notes

The simple Flask application in `serve.py` is meant as a starting point.  

Permissions are defined at the top of the file.

From there, use the definied wrappers on flask routes.  Two examples are given, with and without a wrapper.
