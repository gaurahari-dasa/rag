## How to setup and run

- Create a python virtual environment:
`python -m venv .venv`

- Activate the virtual environment:
`.venv\Scripts\activate`

- Install the relevant python packages:
`pip install -r requirements.txt`
* Note: you may need to install PyYAML if you are using older python.

- Run uvicorn FastCGI server
`uvicorn api:app --reload --host 0.0.0.0 --port 8000`
